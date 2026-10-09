"""log_adherence — STATE-CHANGING. Records taken / missed.

Same propose->confirm->commit guardrail as schedule_reminder. The patient's own message
("took it", "missed it") is what justifies confirm=true — the agent should not fabricate an
adherence event the patient didn't report.
"""
from __future__ import annotations

from typing import Any

from medbuddy.db.models import AdherenceLog
from medbuddy.db.repo import get_or_create_patient
from medbuddy.tools.base import Tool, ToolContext

_VALID = {"taken", "missed"}


class LogAdherenceTool(Tool):
    name = "log_adherence"
    description = (
        "Record whether the patient took a dose. STATE-CHANGING: response must be one of "
        "'taken' or 'missed'. The system asks the patient to confirm before saving — call it "
        "once. Only log what the patient actually told you."
    )
    parameters = {
        "type": "object",
        "properties": {
            "response": {"type": "string", "enum": sorted(_VALID)},
            "confirm": {
                "type": "boolean",
                "description": "Must be true to save. Base it on what the patient actually said.",
            },
        },
        "required": ["response"],
    }

    def run(self, args: dict[str, Any], ctx: ToolContext) -> dict[str, Any]:
        response = str(args.get("response", "")).strip().lower()
        confirm = bool(args.get("confirm", False))

        if response not in _VALID:
            return {"status": "error", "error": f"response must be one of {sorted(_VALID)}"}

        if not confirm:
            return {
                "status": "proposed",
                "response": response,
                "message": f"Understood '{response}'. Confirm to log it.",
            }

        patient = get_or_create_patient(ctx.session, ctx.sender)
        ctx.session.add(AdherenceLog(patient_id=patient.id, response=response))
        ctx.session.commit()
        return {"status": "logged", "response": response}
