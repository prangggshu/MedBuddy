"""Photo path (hybrid design): a fixed pipeline, exactly one LLM call, grounded reply."""
from __future__ import annotations

import json
from types import SimpleNamespace

from sqlalchemy import func, select

from medbuddy.agent import Agent
from medbuddy.agent.prescription import render_reply
from medbuddy.channels import IncomingMessage
from medbuddy.db.models import Medication

JPEG = bytes((0xFF, 0xD8, 0xFF, 0xE0))


def _response(content):
    message = SimpleNamespace(content=content, tool_calls=None)
    return SimpleNamespace(choices=[SimpleNamespace(message=message)])


class VisionOnlyLLM:
    """Answers vision calls with a fixed extraction; any other call is a test failure."""

    def __init__(self, medications: list[dict] | None, raw: str | None = None) -> None:
        self.raw = raw if raw is not None else json.dumps({"medications": medications})
        self.calls: list[str] = []

    def complete(self, messages, *, role="agent", tools=None, **kwargs):
        self.calls.append(role)
        assert role == "vision", f"photo path must not call the {role} model"
        return _response(self.raw)

    @staticmethod
    def image_message(prompt, **kwargs):
        return {"role": "user", "content": prompt}


def _send_photo(llm, session, datasets, channel, clock) -> str:
    agent = Agent(llm)  # type: ignore[arg-type]
    incoming = IncomingMessage(sender="test:+1", text=None, media_bytes=JPEG)
    return agent.handle(incoming, session=session, datasets=datasets, channel=channel, clock=clock)


def test_photo_uses_exactly_one_llm_call(session, datasets, clock, channel):
    llm = VisionOnlyLLM([{"name": "Ecosprin"}, {"name": "Brufen", "dosage": "400 mg"}])
    reply = _send_photo(llm, session, datasets, channel, clock)

    assert llm.calls == ["vision"]
    assert channel.last().text == reply
    assert "Ecosprin" in reply and "Brufen" in reply
    assert "Moderate" in reply  # aspirin + ibuprofen from the curated dataset
    assert "not for clinical use" in reply.lower()


def test_photo_saves_medications(session, datasets, clock, channel):
    llm = VisionOnlyLLM([{"name": "Crocin"}, {"name": "Brufen"}])
    _send_photo(llm, session, datasets, channel, clock)
    assert session.scalar(select(func.count()).select_from(Medication)) == 2


def test_unknown_drug_gets_disclaimer_not_facts(session, datasets, clock, channel):
    llm = VisionOnlyLLM([{"name": "Zzxqwertium"}])
    reply = _send_photo(llm, session, datasets, channel, clock)
    assert "Not in MedBuddy's dataset" in reply
    assert "generic name" not in reply


def test_no_interaction_is_not_called_safe(session, datasets, clock, channel):
    llm = VisionOnlyLLM([{"name": "Crocin"}])
    reply = _send_photo(llm, session, datasets, channel, clock)
    assert "does not prove the combination is safe" in reply


def test_unreadable_photo_asks_for_a_better_one(session, datasets, clock, channel):
    llm = VisionOnlyLLM(None, raw="sorry, I can't read this")
    reply = _send_photo(llm, session, datasets, channel, clock)
    assert "clearer" in reply


def test_major_warnings_listed_before_moderate():
    reply = render_reply(
        {
            "ok": True,
            "medications": [{"name": "X", "matched": True, "generic": "X"}],
            "interactions": [
                {"drug_a": "A", "drug_b": "B", "severity": "moderate", "description": "m"},
                {"drug_a": "C", "drug_b": "D", "severity": "major", "description": "M"},
            ],
        }
    )
    assert reply.index("MAJOR") < reply.index("Moderate")


class DownLLM(VisionOnlyLLM):
    def complete(self, messages, *, role="agent", tools=None, **kwargs):
        raise RuntimeError("503 model is currently experiencing high demand")


def test_service_outage_is_not_blamed_on_the_photo(session, datasets, clock, channel):
    reply = _send_photo(DownLLM([]), session, datasets, channel, clock)
    assert "send the same photo again" in reply
    assert "clearer" not in reply
