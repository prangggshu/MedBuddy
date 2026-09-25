"""Pydantic domain models shared across tools, the agent, and the DB layer."""
from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class Severity(str, Enum):
    minor = "minor"
    moderate = "moderate"
    major = "major"


class Medication(BaseModel):
    """A single medicine as it appears on a prescription."""

    name: str = Field(description="Drug name exactly as written (brand or generic)")
    dosage: str | None = Field(default=None, description="e.g. '500 mg'")
    frequency: str | None = Field(default=None, description="e.g. 'twice daily', 'every 8 hrs'")
    duration: str | None = Field(default=None, description="e.g. '5 days'")


class ExtractionResult(BaseModel):
    """Output of the structured-extraction tool (LLM, schema-validated)."""

    medications: list[Medication] = Field(default_factory=list)
    raw_text: str | None = None


class NormalizedDrug(BaseModel):
    """Result of brand -> generic normalization.

    `matched` is the grounding gate: if False, the drug is unknown to our curated
    dataset and MUST be routed to the disclaimer path — never described from model knowledge.
    """

    input_name: str
    generic: str | None = None
    matched: bool = False
    score: float | None = None


class InteractionFinding(BaseModel):
    """A flagged drug-drug interaction, drawn from the curated dataset."""

    drug_a: str
    drug_b: str
    severity: Severity
    description: str
    source: str | None = None
