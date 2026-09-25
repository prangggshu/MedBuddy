"""normalize_drug: exact brand, exact generic, fuzzy typo, and unknown -> matched=False."""
from __future__ import annotations

from medbuddy.tools.normalize import NormalizeDrugTool

tool = NormalizeDrugTool()


def test_brand_maps_to_generic(ctx):
    out = tool.run({"name": "Crocin"}, ctx)
    assert out["matched"] is True
    assert out["generic"].lower() == "paracetamol"


def test_generic_is_recognized(ctx):
    out = tool.run({"name": "Paracetamol"}, ctx)
    assert out["matched"] is True
    assert out["generic"].lower() == "paracetamol"


def test_fuzzy_typo_still_matches(ctx):
    out = tool.run({"name": "Parcetamol"}, ctx)  # dropped an 'a'
    assert out["matched"] is True
    assert out["generic"].lower() == "paracetamol"
    assert out["score"] is not None and out["score"] >= 85


def test_unknown_drug_is_not_matched(ctx):
    out = tool.run({"name": "Zzxqwertium"}, ctx)
    assert out["matched"] is False
    assert out["generic"] is None


def test_empty_name_is_not_matched(ctx):
    out = tool.run({"name": ""}, ctx)
    assert out["matched"] is False
