"""normalize_drug — brand/generic resolution via fuzzy matching (fully implemented)."""
from __future__ import annotations

from typing import Any

from rapidfuzz import fuzz, process

from medbuddy.schemas import NormalizedDrug
from medbuddy.tools.base import Tool, ToolContext

# Below this WRatio score we treat the name as unknown rather than risk a wrong match.
MATCH_THRESHOLD = 85.0


def _resolve(datasets, matched_key: str) -> str:
    """Map a matched (normalized) name to a display generic."""
    if matched_key in datasets.brand_to_generic:
        return datasets.brand_to_generic[matched_key]
    return matched_key.title()


def normalize_name(ds, raw: str) -> NormalizedDrug:
    """Resolve one name against the curated dataset (exact brand, exact generic, then fuzzy)."""
    raw = str(raw or "").strip()
    if not raw:
        return NormalizedDrug(input_name=raw, matched=False)

    key = raw.lower()
    if key in ds.brand_to_generic:
        return NormalizedDrug(
            input_name=raw, generic=ds.brand_to_generic[key], matched=True, score=100.0
        )
    if key in ds.generics:
        return NormalizedDrug(input_name=raw, generic=_resolve(ds, key), matched=True, score=100.0)

    candidates = ds.known_names()
    if candidates:
        best = process.extractOne(key, candidates, scorer=fuzz.WRatio)
        if best and best[1] >= MATCH_THRESHOLD:
            return NormalizedDrug(
                input_name=raw, generic=_resolve(ds, best[0]), matched=True, score=float(best[1])
            )

    return NormalizedDrug(input_name=raw, matched=False)


class NormalizeDrugTool(Tool):
    name = "normalize_drug"
    description = (
        "Resolve a drug name as written on a prescription (brand or generic) to its generic "
        "name using MedBuddy's curated brand-generic dataset. Returns matched=false when the "
        "drug is NOT in the dataset. If matched=false you must not state any facts about the "
        "drug — treat it as unknown and tell the patient to consult a pharmacist."
    )
    parameters = {
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "One drug name as written"},
            "names": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Several drug names at once — prefer this to one call per drug",
            },
        },
    }

    def run(self, args: dict[str, Any], ctx: ToolContext) -> dict[str, Any]:
        if args.get("names"):
            return {
                "results": [normalize_name(ctx.datasets, n).model_dump() for n in args["names"]]
            }
        return normalize_name(ctx.datasets, args.get("name", "")).model_dump()
