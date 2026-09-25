"""The state-change guardrail: nothing is saved until confirm=true."""
from __future__ import annotations

from sqlalchemy import func, select

from medbuddy.db.models import AdherenceLog, Reminder
from medbuddy.tools.adherence import LogAdherenceTool
from medbuddy.tools.reminders import ScheduleReminderTool


def _count(session, model) -> int:
    return session.scalar(select(func.count()).select_from(model))


def test_schedule_reminder_proposes_without_saving(ctx):
    out = ScheduleReminderTool().run(
        {"medication": "Paracetamol", "times": ["09:00", "21:00"]}, ctx
    )
    assert out["status"] == "proposed"
    assert _count(ctx.session, Reminder) == 0  # nothing committed


def test_schedule_reminder_commits_on_confirm(ctx):
    out = ScheduleReminderTool().run(
        {"medication": "Paracetamol", "times": ["09:00", "21:00"], "confirm": True}, ctx
    )
    assert out["status"] == "scheduled"
    assert _count(ctx.session, Reminder) == 2


def test_log_adherence_requires_confirm(ctx):
    out = LogAdherenceTool().run({"response": "taken"}, ctx)
    assert out["status"] == "proposed"
    assert _count(ctx.session, AdherenceLog) == 0


def test_log_adherence_rejects_bad_response(ctx):
    out = LogAdherenceTool().run({"response": "maybe", "confirm": True}, ctx)
    assert out["status"] == "error"
    assert _count(ctx.session, AdherenceLog) == 0
