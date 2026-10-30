"""HTTP API for the MedBuddy browser chat."""
from __future__ import annotations

import logging
import re
import threading
import time
import uuid
from collections import defaultdict
from datetime import timezone
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import select

from medbuddy.channels import IncomingMessage
from medbuddy.config import get_settings
from medbuddy.db import SessionLocal
from medbuddy.db.models import Patient, Reminder
from medbuddy.db.repo import chat_messages_after, get_chat_message, get_or_create_patient, save_chat_message
from medbuddy.datasets.loaders import load_datasets
from medbuddy.media import pdf_first_pages, read_upload, safe_display_name
from medbuddy.runtime import get_agent, get_channel, get_clock
from medbuddy.health_search import search_medlineplus

router = APIRouter(prefix="/api")
logger = logging.getLogger(__name__)
_phone_locks: dict[str, threading.Lock] = defaultdict(threading.Lock)
_dispatch_locks: dict[str, threading.Lock] = defaultdict(threading.Lock)
_typing: set[str] = set()
_UPLOAD_ROOT = Path(__file__).resolve().parent.parent / "data" / "uploads"


def normalize_phone(value: str) -> str:
    digits = re.sub(r"\D", "", value or "")
    if not 10 <= len(digits) <= 15:
        raise HTTPException(422, detail="Enter a phone number with 10 to 15 digits.")
    return "+" + digits


def _message_json(row) -> dict:
    created_at = row.created_at
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    return {
        "id": row.id, "phone": row.phone, "direction": row.direction, "text": row.text,
        "media_url": f"/api/media/{row.id}" if row.media_path else None,
        "media_type": row.media_type, "media_name": row.media_name, "media_size": row.media_size,
        "created_at": created_at.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
        "status": row.status,
    }


def _patient_ref(phone: str) -> str:
    digits = re.sub(r"\D", "", phone)
    return f"…{digits[-4:]}"


@router.post("/login")
def login(body: dict):
    phone = normalize_phone(str(body.get("phone", "")))
    with SessionLocal() as session:
        is_new = session.scalar(select(Patient.id).where(Patient.wa_number == phone)) is None
        patient = get_or_create_patient(session, phone)
        session.commit()
        logger.info(
            "step=patient_login patient=%s created=%s profile_complete=%s",
            _patient_ref(phone), is_new, bool(patient.name and patient.age is not None),
        )
    return {"phone": phone, "is_new": is_new}


def _run_agent(phone: str, text: str | None, images: list[bytes], pdf_skipped: int) -> None:
    channel = get_channel()
    started = time.perf_counter()
    logger.info(
        "step=agent_started patient=%s mode=%s pages=%d",
        _patient_ref(phone), "prescription" if images else "chat", len(images),
    )
    with _phone_locks[phone]:
        _typing.add(phone)
        try:
            turns: list[bytes | None] = images if images else [None]
            for index, image in enumerate(turns):
                image_text = text or ("(the patient sent a prescription image)" if image else None)
                if len(images) > 1:
                    image_text += f" (PDF page {index + 1} of {len(images)})"
                incoming = IncomingMessage(sender=phone, text=image_text, media_bytes=image)
                with SessionLocal() as session:
                    get_agent().handle(
                        incoming, session=session, datasets=load_datasets(), channel=channel,
                        clock=get_clock(),
                    )
            if pdf_skipped:
                channel.send_text(phone, f"I read the first 3 pages; {pdf_skipped} additional page(s) were skipped.")
            logger.info(
                "step=agent_finished patient=%s duration_seconds=%.2f",
                _patient_ref(phone), time.perf_counter() - started,
            )
        except Exception:
            logger.exception("step=agent_background_failed patient=%s", _patient_ref(phone))
            raise
        finally:
            _typing.discard(phone)


@router.post("/messages")
async def post_message(
    background: BackgroundTasks,
    phone: str = Form(...),
    text: str | None = Form(default=None),
    file: UploadFile | None = File(default=None),
):
    normalized = normalize_phone(phone)
    content = (text or "").strip() or None
    media_bytes: list[bytes] = []
    media_path = media_type = media_name = None
    media_size = None
    skipped = 0
    if file is not None:
        settings = get_settings()
        folder = _UPLOAD_ROOT / normalized.lstrip("+")
        raw, media_type, extension, temporary = await read_upload(
            file, settings.max_upload_mb * 1024 * 1024, folder
        )
        media_name = safe_display_name(file.filename)
        media_size = len(raw)
        destination = folder / f"{uuid.uuid4().hex}{extension}"
        temporary.replace(destination)
        media_path = str(destination.resolve())
        if media_type == "application/pdf":
            pages, total, _ = pdf_first_pages(raw)
            media_bytes = pages
            skipped = max(0, total - len(pages))
        else:
            media_bytes = [raw]
    if content is None and not media_bytes:
        raise HTTPException(422, detail="Write a message or attach a file.")

    with SessionLocal() as session:
        get_or_create_patient(session, normalized)
        row = save_chat_message(
            session, phone=normalized, direction="in", text=content,
            media_path=media_path, media_type=media_type, media_name=media_name,
            media_size=media_size, created_at=get_clock().now(), status="sent",
        )
        saved = _message_json(row)
    logger.info(
        "step=incoming_message_saved patient=%s has_text=%s has_attachment=%s",
        _patient_ref(normalized), bool(content), bool(media_bytes),
    )
    background.add_task(_run_agent, normalized, content, media_bytes, skipped)
    logger.info("step=agent_queued patient=%s", _patient_ref(normalized))
    return saved


@router.get("/messages")
def get_messages(phone: str = Query(...), after_id: int = Query(default=0, ge=0)):
    normalized = normalize_phone(phone)
    # Polling is the web chat's lightweight reminder dispatcher.
    with _dispatch_locks[normalized], SessionLocal() as session:
        patient = session.scalar(select(Patient).where(Patient.wa_number == normalized))
        now = get_clock().now()
        due = []
        if patient:
            due = list(session.scalars(
                select(Reminder).where(
                    Reminder.patient_id == patient.id,
                    Reminder.status == "scheduled",
                    Reminder.scheduled_for <= now,
                ).order_by(Reminder.scheduled_for)
            ))
        if due:
            for reminder in due:
                reminder.status = "sent"
            session.commit()
            channel = get_channel()
            for _ in due:
                channel.send_text(normalized, "⏰ Your scheduled medication reminder is due.")
    with SessionLocal() as session:
        return [_message_json(row) for row in chat_messages_after(session, normalized, after_id)]


@router.get("/typing")
def get_typing(phone: str = Query(...)):
    return {"typing": normalize_phone(phone) in _typing}


@router.get("/health-search")
def health_search(q: str = Query(min_length=2, max_length=160)):
    query = re.sub(r"\s+", " ", q).strip()
    if len(query) < 2:
        raise HTTPException(422, detail="Enter at least two characters to search.")
    try:
        results = search_medlineplus(query)
    except RuntimeError as exc:
        logger.warning("step=health_search_unavailable")
        raise HTTPException(503, detail=str(exc)) from exc
    logger.info("step=health_search_completed result_count=%d", len(results))
    return {"query": query, "source": "MedlinePlus", "results": results}


@router.get("/media/{message_id}")
def get_media(message_id: int):
    with SessionLocal() as session:
        row = get_chat_message(session, message_id)
        if row is None or row.direction != "in" or not row.media_path:
            raise HTTPException(404, detail="Media not found.")
        path = Path(row.media_path).resolve()
        if not path.is_relative_to(_UPLOAD_ROOT.resolve()) or not path.is_file():
            raise HTTPException(404, detail="Media not found.")
        return FileResponse(
            path, media_type=row.media_type or "application/octet-stream",
            filename=row.media_name or "prescription", content_disposition_type="inline",
        )
