"""Patient profile + med-list tools (register_patient, get_my_meds)."""
from __future__ import annotations

from typing import Any

from medbuddy.db.repo import get_or_create_patient, latest_medications, set_profile
from medbuddy.tools.base import Tool, ToolContext


class RegisterPatientTool(Tool):
    name = "register_patient"
    description = (
        "Save or update the patient's name and age during onboarding, after they provide it. "
        "One WhatsApp number is one patient."
    )
    parameters = {
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "age": {"type": "integer"},
        },
    }

    def run(self, args: dict[str, Any], ctx: ToolContext) -> dict[str, Any]:
        name = args.get("name")
        age = args.get("age")
        patient = get_or_create_patient(ctx.session, ctx.sender)
        set_profile(ctx.session, patient, name=name, age=age)
        ctx.session.commit()
        return {"ok": True, "name": patient.name, "age": patient.age}


class GetMyMedsTool(Tool):
    name = "get_my_meds"
    description = "List the medications from the patient's most recent prescription."
    parameters = {"type": "object", "properties": {}}

    def run(self, args: dict[str, Any], ctx: ToolContext) -> dict[str, Any]:
        patient = get_or_create_patient(ctx.session, ctx.sender)
        meds = latest_medications(ctx.session, patient.id)
        return {
            "medications": [
                {
                    "name": m.name,
                    "generic": m.generic,
                    "dosage": m.dosage,
                    "frequency": m.frequency,
                    "duration": m.duration,
                }
                for m in meds
            ]
        }
