"""Web-chat transport, persistence, and upload safety checks."""
from __future__ import annotations

from types import SimpleNamespace
from datetime import datetime, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from medbuddy import api_web
from medbuddy.agent import Agent
from medbuddy.channels import web as web_channel_module
from medbuddy.channels.web import WebChannel
from medbuddy.db.models import Base, Reminder
from medbuddy.db.repo import get_or_create_patient, save_chat_message
from medbuddy.scheduler.clock import FakeClock
from tests.test_agent_orchestration import ScriptedLLM, _response

PNG = b"\x89PNG\r\n\x1a\n" + b"demo-image"
JPEG = b"\xff\xd8\xff\xe0" + b"demo-image"


@pytest.fixture
def web_client(monkeypatch, tmp_path):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    monkeypatch.setattr(api_web, "SessionLocal", factory)
    monkeypatch.setattr(web_channel_module, "SessionLocal", factory)
    fake_clock = FakeClock(datetime(2026, 1, 1, tzinfo=timezone.utc))
    monkeypatch.setattr(api_web, "get_clock", lambda: fake_clock)
    monkeypatch.setattr(web_channel_module, "get_clock", lambda: fake_clock)
    monkeypatch.setattr(api_web, "_UPLOAD_ROOT", tmp_path / "uploads")
    app = FastAPI()
    app.include_router(api_web.router)
    with TestClient(app) as client:
        yield client, factory
    engine.dispose()


def test_login_normalizes_phone_and_reuses_patient(web_client):
    client, _ = web_client
    first = client.post("/api/login", json={"phone": "+91 98765-43210"})
    second = client.post("/api/login", json={"phone": "919876543210"})
    assert first.status_code == 200 and first.json() == {"phone": "+919876543210", "is_new": True}
    assert second.json() == {"phone": "+919876543210", "is_new": False}


def test_message_round_trip_and_after_id_polling(web_client, monkeypatch):
    client, _ = web_client
    llm = ScriptedLLM([_response(content="Hello from a fake LLM.")])
    agent = Agent(llm)  # same offline scripted fake used by the orchestration tests
    channel = WebChannel()
    monkeypatch.setattr(api_web, "get_agent", lambda: agent)
    monkeypatch.setattr(api_web, "get_channel", lambda: channel)
    posted = client.post("/api/messages", data={"phone": "+91 98765 43210", "text": "Hi"})
    assert posted.status_code == 200
    inbound = posted.json()
    assert inbound["direction"] == "in" and inbound["text"] == "Hi"
    assert inbound["created_at"] == "2026-01-01T00:00:00Z"
    all_rows = client.get("/api/messages", params={"phone": inbound["phone"], "after_id": 0}).json()
    after_inbound = client.get("/api/messages", params={"phone": inbound["phone"], "after_id": inbound["id"]})
    assert len(after_inbound.json()) == 1, all_rows
    assert after_inbound.json()[0]["text"] == "Hello from a fake LLM."
    assert after_inbound.json()[0]["created_at"] == "2026-01-01T00:00:00Z"
    assert client.get("/api/messages", params={"phone": inbound["phone"], "after_id": after_inbound.json()[0]["id"]}).json() == []


def test_legacy_naive_message_timestamp_is_serialized_as_utc(web_client):
    client, factory = web_client
    with factory() as session:
        save_chat_message(
            session,
            phone="+919876543210",
            direction="out",
            text="Existing message",
            created_at=datetime(2026, 1, 1, 0, 0),
        )

    rows = client.get("/api/messages", params={"phone": "+919876543210"}).json()
    assert rows[0]["created_at"] == "2026-01-01T00:00:00Z"


def test_due_reminder_is_dispatched_and_pollable(web_client, monkeypatch):
    client, factory = web_client
    monkeypatch.setattr(api_web, "get_channel", lambda: WebChannel())
    with factory() as session:
        patient = get_or_create_patient(session, "+919876543210")
        session.add(Reminder(patient_id=patient.id, scheduled_for=datetime(2025, 12, 31, 23, 59, tzinfo=timezone.utc)))
        session.commit()
    rows = client.get("/api/messages", params={"phone": "+919876543210", "after_id": 0}).json()
    assert len(rows) == 1 and rows[0]["direction"] == "out"
    assert rows[0]["text"] == "⏰ Your scheduled medication reminder is due."


def test_oversized_upload_is_rejected(web_client, monkeypatch):
    client, _ = web_client
    monkeypatch.setattr(api_web, "get_settings", lambda: SimpleNamespace(max_upload_mb=1))
    response = client.post("/api/messages", data={"phone": "+919876543210"}, files={"file": ("large.png", PNG + b"x" * (1024 * 1024 + 1), "image/png")})
    assert response.status_code == 413


@pytest.mark.parametrize("filename,payload,mime", [
    ("note.txt", b"plain text", "text/plain"),
    ("disguised.png", b"MZ executable bytes", "image/png"),
])
def test_wrong_or_misnamed_upload_is_rejected(web_client, filename, payload, mime):
    client, _ = web_client
    response = client.post("/api/messages", data={"phone": "+919876543210"}, files={"file": (filename, payload, mime)})
    assert response.status_code == 415


def test_pdf_page_is_converted_and_passed_to_agent(web_client, monkeypatch):
    client, _ = web_client
    seen = []

    class FakeAgent:
        def handle(self, incoming, **kwargs):
            seen.append(incoming.media_bytes)
            kwargs["channel"].send_text(incoming.sender, "Prescription read.")

    monkeypatch.setattr(api_web, "get_agent", lambda: FakeAgent())
    monkeypatch.setattr(api_web, "get_channel", lambda: WebChannel())
    monkeypatch.setattr(api_web, "pdf_first_pages", lambda raw: ([PNG], 1, "image/png"))
    response = client.post("/api/messages", data={"phone": "+919876543210"}, files={"file": ("rx.pdf", b"%PDF-demo", "application/pdf")})
    assert response.status_code == 200 and seen == [PNG]


def test_real_one_page_pdf_renders_to_png_for_agent(web_client, monkeypatch):
    fitz = pytest.importorskip("fitz")
    document = fitz.open()
    page = document.new_page()
    page.insert_text((72, 72), "Prescription demo")
    pdf = document.tobytes()
    seen = []

    class FakeAgent:
        def handle(self, incoming, **kwargs):
            seen.append(incoming.media_bytes)
            kwargs["channel"].send_text(incoming.sender, "Prescription read.")

    monkeypatch.setattr(api_web, "get_agent", lambda: FakeAgent())
    monkeypatch.setattr(api_web, "get_channel", lambda: WebChannel())
    response = web_client[0].post("/api/messages", data={"phone": "+919876543210"}, files={"file": ("rx.pdf", pdf, "application/pdf")})
    assert response.status_code == 200
    assert len(seen) == 1 and seen[0].startswith(b"\x89PNG\r\n\x1a\n")


@pytest.mark.parametrize("filename,payload,mime", [
    ("rx.jpg", JPEG, "image/jpeg"),
    ("rx.png", PNG, "image/png"),
])
def test_allowed_image_upload_reaches_agent(web_client, monkeypatch, filename, payload, mime):
    client, _ = web_client
    seen = []

    class FakeAgent:
        def handle(self, incoming, **kwargs):
            seen.append(incoming.media_bytes)
            kwargs["channel"].send_text(incoming.sender, "Extraction reply.")

    monkeypatch.setattr(api_web, "get_agent", lambda: FakeAgent())
    monkeypatch.setattr(api_web, "get_channel", lambda: WebChannel())
    response = client.post("/api/messages", data={"phone": "+919876543210"}, files={"file": (filename, payload, mime)})
    assert response.status_code == 200 and seen == [payload]
