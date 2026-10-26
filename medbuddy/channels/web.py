"""Persisted web-chat transport used by the temporary browser demo."""
from __future__ import annotations

from typing import Any

from medbuddy.db import SessionLocal
from medbuddy.db.repo import save_chat_message
from medbuddy.runtime import get_clock


class WebChannel:
    def send(self, phone: str, text: str, media: dict[str, Any] | None = None) -> None:
        with SessionLocal() as session:
            save_chat_message(
                session, phone=phone, direction="out", text=text,
                created_at=get_clock().now(),
                media_path=(media or {}).get("path"),
                media_type=(media or {}).get("type"),
                media_name=(media or {}).get("name"),
            )

    def send_text(self, to: str, text: str) -> None:
        self.send(to, text)
