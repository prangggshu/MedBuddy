"""extract_medications — prescription image (or OCR text) -> structured medications (LLM).

Reads the pending image directly with the vision model in ONE call (no separate OCR step),
validates against the ExtractionResult schema, normalizes each name against the curated
dataset, and saves the prescription so get_my_meds and reminders can use it.

TODO(week2): switch to native structured outputs (response_format json_schema) per provider
instead of prompt-and-parse, once the target models are pinned.
"""
from __future__ import annotations

import json
from typing import Any

from medbuddy.db.repo import get_or_create_patient, save_prescription
from medbuddy.schemas import ExtractionResult
from medbuddy.tools.base import Tool, ToolContext, guess_image_mime
from medbuddy.tools.normalize import normalize_name

_SYSTEM = (
    "You extract medications from a prescription. Return ONLY minified JSON of the form "
    '{"medications":[{"name":str,"dosage":str|null,"frequency":str|null,"duration":str|null}],'
    '"raw_text":str|null}. Use null for fields you cannot read. Never invent a medication '
    "that is not present in the source."
)


def _loads_json(content: str) -> dict:
    """Parse model output that may be wrapped in ```json fences or surrounding prose."""
    content = content.strip()
    if content.startswith("```"):
        content = content.split("```", 2)[1]
        if content.startswith("json"):
            content = content[4:]
    start, end = content.find("{"), content.rfind("}")
    if start != -1 and end != -1:
        content = content[start : end + 1]
    return json.loads(content)


class ExtractMedicationsTool(Tool):
    name = "extract_medications"
    description = (
        "Read the patient's prescription image and return its medications (name, dosage, "
        "frequency, duration), each already normalized to a generic name with a matched flag, "
        "and save them as the patient's current prescription. Call with no arguments when an "
        "image was sent; pass raw_text only to extract from typed text."
    )
    parameters = {
        "type": "object",
        "properties": {
            "raw_text": {
                "type": "string",
                "description": "Prescription text typed by the patient (optional)",
            }
        },
    }

    def run(self, args: dict[str, Any], ctx: ToolContext) -> dict[str, Any]:
        raw_text = args.get("raw_text")
        try:
            if raw_text:
                content = ctx.llm.text(
                    f"Prescription text:\n{raw_text}\n\nExtract the medications as JSON.",
                    role="agent",
                    system=_SYSTEM,
                )
            elif ctx.pending_image:
                msg = ctx.llm.image_message(
                    "Extract the medications from this prescription image as JSON.",
                    image_bytes=ctx.pending_image,
                    mime=guess_image_mime(ctx.pending_image),
                )
                resp = ctx.llm.complete(
                    [{"role": "system", "content": _SYSTEM}, msg], role="vision"
                )
                content = resp.choices[0].message.content or "{}"
            else:
                return {"ok": False, "error": "no raw_text and no image to extract from"}
        except Exception as err:  # noqa: BLE001 - API down/overloaded, not the photo's fault
            return {"ok": False, "reason": "service", "error": f"model call failed: {err}"}

        try:
            result = ExtractionResult.model_validate(_loads_json(content))
        except Exception as err:  # noqa: BLE001 - model answered but nothing usable
            return {"ok": False, "reason": "unreadable", "error": f"extraction failed: {err}"}

        medications = []
        for med in result.medications:
            norm = normalize_name(ctx.datasets, med.name)
            medications.append({**med.model_dump(), "generic": norm.generic, "matched": norm.matched})

        patient = get_or_create_patient(ctx.session, ctx.sender)
        save_prescription(
            ctx.session, patient.id, raw_text=result.raw_text or raw_text, medications=medications
        )
        ctx.session.commit()

        return {
            "ok": True,
            "medications": medications,
            "note": "matched=false drugs are NOT in MedBuddy's dataset — do not describe them.",
        }
