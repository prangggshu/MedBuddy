"""extract_medications — OCR-text or image -> structured medications (LLM).

Uses OCR text if the agent passes it; otherwise reads the pending image directly with the
vision model. Output is validated against the ExtractionResult Pydantic schema.

TODO(week2): switch to native structured outputs (response_format json_schema) per provider
instead of prompt-and-parse, once the target models are pinned.
"""
from __future__ import annotations

import json
from typing import Any

from medbuddy.schemas import ExtractionResult
from medbuddy.tools.base import Tool, ToolContext

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
        "Extract structured medications (name, dosage, frequency, duration) from the prescription. "
        "Pass raw_text if you already ran OCR; otherwise omit it and the tool reads the image "
        "directly (vision). Returns validated JSON. Normalize each name afterward."
    )
    parameters = {
        "type": "object",
        "properties": {
            "raw_text": {
                "type": "string",
                "description": "OCR text from run_ocr, if available (optional)",
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
                )
                resp = ctx.llm.complete(
                    [{"role": "system", "content": _SYSTEM}, msg], role="vision"
                )
                content = resp.choices[0].message.content or "{}"
            else:
                return {"ok": False, "error": "no raw_text and no image to extract from"}

            result = ExtractionResult.model_validate(_loads_json(content))
            return {"ok": True, **result.model_dump()}
        except Exception as err:  # noqa: BLE001 - surface extraction failure to the agent
            return {"ok": False, "error": f"extraction failed: {err}"}
