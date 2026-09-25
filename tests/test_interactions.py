"""check_interactions: known pairs surface with correct severity; unknown pairs return none."""
from __future__ import annotations

from medbuddy.tools.interactions import CheckInteractionsTool

tool = CheckInteractionsTool()


def test_moderate_interaction_found(ctx):
    out = tool.run({"drugs": ["Aspirin", "Ibuprofen"]}, ctx)
    assert out["count"] == 1
    assert out["findings"][0]["severity"] == "moderate"


def test_major_interaction_found(ctx):
    out = tool.run({"drugs": ["Warfarin", "Aspirin"]}, ctx)
    assert out["count"] == 1
    assert out["findings"][0]["severity"] == "major"


def test_no_interaction_in_dataset(ctx):
    # A pair we deliberately did not curate -> "not in our dataset", not "safe".
    out = tool.run({"drugs": ["Metformin", "Paracetamol"]}, ctx)
    assert out["count"] == 0


def test_order_independent_and_deduped(ctx):
    out = tool.run({"drugs": ["ibuprofen", "aspirin", "aspirin"]}, ctx)
    assert out["count"] == 1  # (aspirin, ibuprofen) found once regardless of order/dupes
