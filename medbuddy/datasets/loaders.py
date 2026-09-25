"""Load the curated CSV datasets into in-memory lookup structures.

These are intentionally STATIC files (not live API calls) — see CLAUDE.md scope.
"""
from __future__ import annotations

import csv
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

# repo_root/data  (this file is repo_root/medbuddy/datasets/loaders.py)
DATA_DIR = Path(__file__).resolve().parents[2] / "data"


def _norm(s: str) -> str:
    return s.strip().lower()


@dataclass
class Datasets:
    brand_to_generic: dict[str, str] = field(default_factory=dict)  # lowercased brand -> generic
    generics: set[str] = field(default_factory=set)  # all lowercased generic names we know
    interactions: dict[frozenset[str], dict] = field(default_factory=dict)  # {gen_a, gen_b} -> row

    def known_names(self) -> list[str]:
        """Every name we can match against: brands + generics (original casing lost -> lower)."""
        return sorted(set(self.brand_to_generic) | self.generics)


@lru_cache
def load_datasets(data_dir: str | None = None) -> Datasets:
    d = Path(data_dir) if data_dir else DATA_DIR
    ds = Datasets()

    bg = d / "brand_generic.csv"
    if bg.exists():
        with bg.open(newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                generic = row["generic"].strip()
                ds.brand_to_generic[_norm(row["brand"])] = generic
                ds.generics.add(_norm(generic))

    inter = d / "interactions.csv"
    if inter.exists():
        with inter.open(newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                a, b = _norm(row["drug_a"]), _norm(row["drug_b"])
                ds.interactions[frozenset({a, b})] = row
                # interaction drugs are themselves known generics we can match against
                ds.generics.update({a, b})

    return ds
