"""FastAPI app: health check + WhatsApp webhook.

The webhook is transport-agnostic here — it builds an IncomingMessage and hands it to the
agent. Twilio-specific parsing (form fields, media download) is wired in Week 3 via
TwilioChannel.parse_incoming; for now it reads the common Twilio form keys directly.
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request

from medbuddy.channels import IncomingMessage
from medbuddy.datasets.loaders import load_datasets
from medbuddy.db import SessionLocal, init_db
from medbuddy.runtime import get_agent, get_channel, get_clock


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="MedBuddy", version="0.1.0", lifespan=lifespan)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "medbuddy", "note": "proof-of-concept, not for clinical use"}


@app.post("/webhook/whatsapp")
async def whatsapp_webhook(request: Request) -> dict:
    form = dict(await request.form())
    # TODO(week3): TwilioChannel.parse_incoming(form) + download MediaUrl0 into media_bytes.
    incoming = IncomingMessage(
        sender=str(form.get("From", "")),
        text=form.get("Body"),
        media_url=form.get("MediaUrl0"),
    )

    agent = get_agent()
    channel = get_channel()
    with SessionLocal() as session:
        reply = agent.handle(
            incoming,
            session=session,
            datasets=load_datasets(),
            channel=channel,
            clock=get_clock(),
        )
    return {"reply": reply}
