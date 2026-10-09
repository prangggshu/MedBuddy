"""lookup_drug_info — the grounding gate for explanations.

MedBuddy's curated data is a brand-generic map + an interaction table. That is the ONLY
thing we may state as fact. This tool makes that boundary explicit: known drugs get their
grounded facts; unknown drugs get a forced disclaimer and nothing else.
"""
from __future__ import annotations

from typing import Any

from medbuddy.tools.base import Tool, ToolContext

DISCLAIMER = "Proof-of-concept, not for clinical use — always confirm with a pharmacist or doctor."


class LookupDrugInfoTool(Tool):
    name = "lookup_drug_info"
    description = (
        "Return the ONLY facts MedBuddy is permitted to state about a drug. If known=false you "
        "MUST NOT describe the drug at all — tell the patient it isn't in MedBuddy's dataset and "
        "to ask a pharmacist. Never state any drug fact that did not come from this tool."
    )
    parameters = {
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "One drug name (brand or generic)"},
            "names": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Several drug names at once — prefer this to one call per drug",
            },
        },
    }

    def run(self, args: dict[str, Any], ctx: ToolContext) -> dict[str, Any]:
        if args.get("names"):
            return {"results": [self._lookup(str(n), ctx) for n in args["names"]]}
        return self._lookup(str(args.get("name", "")), ctx)

    @staticmethod
    def _lookup(name: str, ctx: ToolContext) -> dict[str, Any]:
        raw = name.strip()
        key = raw.lower()
        ds = ctx.datasets

        generic: str | None = None
        if key in ds.brand_to_generic:
            generic = ds.brand_to_generic[key]
        elif key in ds.generics:
            generic = key.title()

        if generic is None:
            return {
                "name": raw,
                "known": False,
                "disclaimer": f"'{raw}' is not in MedBuddy's curated dataset. {DISCLAIMER}",
            }

        return {
            "name": raw,
            "known": True,
            "generic": generic,
            # Deliberately narrow: our dataset carries no dosage/effect facts, so neither may you.
            "grounded_facts": f"'{raw}' is the brand/name for the generic drug {generic}.",
            "note": "Do not add dosage, effect, or side-effect claims beyond what tools return.",
            "disclaimer": DISCLAIMER,
        }
