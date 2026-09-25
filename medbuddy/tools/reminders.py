"""schedule_reminder — STATE-CHANGING. Propose -> confirm -> commit.

Calling with confirm=false (the default) returns a *proposal* and writes nothing. Only
confirm=true commits reminders to the DB. The system prompt forbids the agent from setting
confirm=true unless the patient explicitly agreed — that's the structural guardrail against
the agent silently changing state.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from medbuddy.db.models import Reminder
from medbuddy.db.repo import get_or_create_patient
from medbuddy.tools.base import Tool, ToolContext


def _next_occurrence(now: datetime, hhmm: str) -> datetime:
    hh, mm = (int(x) for x in hhmm.split(":"))
    cand = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
    if cand <= now:
        cand += timedelta(days=1)
    return cand


class ScheduleReminderTool(Tool):
    name = "schedule_reminder"
    description = (
        "Schedule daily dose reminders for a medication. STATE-CHANGING: call FIRST with "
        "confirm=false to propose the times (nothing is saved), show them to the patient, and "
        "only call again with confirm=true AFTER they explicitly agree. Never set confirm=true "
        "on your own initiative."
    )
    parameters = {
        "type": "object",
        "properties": {
            "medication": {"type": "string", "description": "Medication name"},
            "times": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Daily times as HH:MM (24h), e.g. ['09:00','21:00']",
            },
            "confirm": {
                "type": "boolean",
                "description": "Must be true to actually save. Only after explicit patient consent.",
            },
        },
        "required": ["medication", "times"],
    }

    def run(self, args: dict[str, Any], ctx: ToolContext) -> dict[str, Any]:
        med = str(args.get("medication", "")).strip()
        times = [str(t).strip() for t in args.get("times", []) if str(t).strip()]
        confirm = bool(args.get("confirm", False))

        if not med or not times:
            return {"status": "error", "error": "medication and at least one time are required"}

        if not confirm:
            return {
                "status": "proposed",
                "medication": med,
                "times": times,
                "message": "Nothing saved yet. Ask the patient to confirm these reminder times.",
            }

        patient = get_or_create_patient(ctx.session, ctx.sender)
        now = ctx.clock.now()
        scheduled: list[str] = []
        for t in times:
            when = _next_occurrence(now, t)
            ctx.session.add(
                Reminder(patient_id=patient.id, scheduled_for=when, status="scheduled")
            )
            scheduled.append(when.isoformat())
        ctx.session.commit()
        return {"status": "scheduled", "medication": med, "times": times, "scheduled_for": scheduled}
