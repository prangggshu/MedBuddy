"""check_interactions — pairwise lookup against the curated dataset (fully implemented)."""
from __future__ import annotations

from typing import Any

from medbuddy.schemas import InteractionFinding, Severity
from medbuddy.tools.base import Tool, ToolContext


class CheckInteractionsTool(Tool):
    name = "check_interactions"
    description = (
        "Check every pair among the given drugs against MedBuddy's curated interaction dataset. "
        "Pass GENERIC names (call normalize_drug first). Returns only the pairs that exist in the "
        "dataset — absence of a finding means 'not in our dataset', NOT 'proven safe'. Say so."
    )
    parameters = {
        "type": "object",
        "properties": {
            "drugs": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Generic drug names to cross-check",
            }
        },
        "required": ["drugs"],
    }

    def run(self, args: dict[str, Any], ctx: ToolContext) -> dict[str, Any]:
        drugs = [str(d).strip().lower() for d in args.get("drugs", []) if str(d).strip()]
        ds = ctx.datasets

        findings: list[dict] = []
        seen: set[frozenset[str]] = set()
        for i in range(len(drugs)):
            for j in range(i + 1, len(drugs)):
                pair = frozenset({drugs[i], drugs[j]})
                if pair in seen or pair not in ds.interactions:
                    continue
                seen.add(pair)
                row = ds.interactions[pair]
                findings.append(
                    InteractionFinding(
                        drug_a=row["drug_a"],
                        drug_b=row["drug_b"],
                        severity=Severity(row["severity"].strip().lower()),
                        description=row["description"],
                        source=row.get("source"),
                    ).model_dump()
                )

        return {"findings": findings, "count": len(findings), "checked": drugs}
