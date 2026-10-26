"""Deterministic prescription pipeline — the photo path of the hybrid design.

When a patient sends a photo, the graph routes here instead of to the agent:

    vision extract (1 LLM call) -> normalize -> check_interactions -> lookup_drug_info -> reply

Everything after extraction is pure Python over the curated datasets, and the reply is
rendered from a template using only tool results — so grounding is guaranteed by code, not
by prompt. With PHOTO_REPLY_MODE=rephrase, one extra explanation-model call rewrites the
template more warmly; if that fails or drops a warning, the template is sent unchanged.
"""
from __future__ import annotations

from typing import Any

from medbuddy.config import get_settings
from medbuddy.tools.base import ToolContext
from medbuddy.tools.drug_info import DISCLAIMER, LookupDrugInfoTool
from medbuddy.tools.extract import ExtractMedicationsTool
from medbuddy.tools.interactions import CheckInteractionsTool

_SEVERITY_ORDER = {"major": 0, "moderate": 1, "minor": 2}
_SEVERITY_ICON = {"major": "🔴 MAJOR", "moderate": "🟠 Moderate", "minor": "🟡 Minor"}

_REPHRASE_SYSTEM = (
    "You rewrite a medication assistant message to sound warm and simple for "
    "a worried patient. Rules: keep EVERY medicine, generic name, interaction warning, "
    "severity and the disclaimer. Do NOT add any drug fact, effect, dose or advice that is "
    "not in the original. Keep it short. Return only the rewritten message."
)


def _generics_for_check(medications: list[dict]) -> list[str]:
    """Matched generics, with combination products ("Ibuprofen + Paracetamol") split."""
    names: list[str] = []
    for med in medications:
        if med.get("matched") and med.get("generic"):
            names.extend(part.strip() for part in med["generic"].split("+") if part.strip())
    return list(dict.fromkeys(n.lower() for n in names))


def process_prescription(ctx: ToolContext) -> dict[str, Any]:
    """Run the fixed pipeline. Exactly one LLM call (vision extraction)."""
    extraction = ExtractMedicationsTool().run({}, ctx)
    if not extraction.get("ok"):
        return {
            "ok": False,
            "reason": extraction.get("reason", "unreadable"),
            "error": extraction.get("error", "extraction failed"),
        }

    medications = extraction["medications"]
    generics = _generics_for_check(medications)
    interactions = CheckInteractionsTool().run({"drugs": generics}, ctx)
    lookups = LookupDrugInfoTool().run({"names": [m["name"] for m in medications]}, ctx)
    return {
        "ok": True,
        "medications": medications,
        "interactions": interactions["findings"],
        "drug_info": lookups["results"],
    }


def _describe_med(med: dict) -> str:
    detail = ", ".join(
        part
        for part in (med.get("dosage"), med.get("frequency"), med.get("duration"))
        if part
    )
    line = f"*{med['name']}*" + (f" ({detail})" if detail else "")
    if med.get("matched") and med.get("generic"):
        return f"{line}\n   → generic name: {med['generic']}"
    return f"{line}\n   ⚠️ Not in MedBuddy's dataset — please ask your pharmacist about this one."


def render_reply(result: dict[str, Any]) -> str:
    """Build the patient reply purely from pipeline output."""
    if result.get("reason") == "service":
        return (
            "Sorry, I'm having trouble reading prescriptions right now — the service is busy. "
            "⏳ Please send the same photo again in a minute.\n\n"
            f"_{DISCLAIMER}_"
        )
    if not result.get("ok") or not result.get("medications"):
        return (
            "I couldn't read any medicines from that photo. 📷 Please send a clearer, "
            "well-lit photo with the whole prescription in frame.\n\n"
            f"_{DISCLAIMER}_"
        )

    meds = result["medications"]
    parts = ["📋 *I found these medicines on your prescription:*"]
    parts += [f"{i}. {_describe_med(m)}" for i, m in enumerate(meds, 1)]

    findings = sorted(
        result["interactions"], key=lambda f: _SEVERITY_ORDER.get(f["severity"], 9)
    )
    if findings:
        parts.append("\n⚠️ *Interaction warnings:*")
        for f in findings:
            icon = _SEVERITY_ICON.get(f["severity"], f["severity"])
            parts.append(f"{icon}: {f['drug_a']} + {f['drug_b']} — {f['description']}")
        parts.append("Please talk to your doctor or pharmacist before changing anything.")
    else:
        parts.append(
            "\n✅ No interactions found between these medicines *in MedBuddy's dataset*. "
            "That does not prove the combination is safe."
        )

    if any(not m.get("matched") for m in meds):
        parts.append("I could only check the medicines I recognised.")

    parts.append('\nWould you like daily reminders for these? Just say e.g. "remind me".')
    parts.append(f"\n_{DISCLAIMER}_")
    return "\n".join(parts)


def _rephrase(ctx: ToolContext, template: str, result: dict[str, Any]) -> str:
    """Optional 2nd call. Falls back to the template if anything looks lost."""
    try:
        text = ctx.llm.text(template, role="explanation", system=_REPHRASE_SYSTEM).strip()
    except Exception:  # noqa: BLE001 - the template is always a valid answer
        return template
    must_keep = [m["name"] for m in result.get("medications", [])]
    must_keep += [f["severity"] for f in result.get("interactions", [])]
    if not text or any(word.lower() not in text.lower() for word in must_keep):
        return template
    return text


def prescription_reply(ctx: ToolContext) -> str:
    result = process_prescription(ctx)
    template = render_reply(result)
    if result.get("ok") and get_settings().photo_reply_mode == "rephrase":
        return _rephrase(ctx, template, result)
    return template
