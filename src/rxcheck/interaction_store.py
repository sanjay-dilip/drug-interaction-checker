"""Curated interaction lookup, pair generation, and deterministic ranking.

The CSV dataset loaded here is the sole authority for interaction facts.
Nothing in this module infers an interaction that is not an explicit row
in the dataset.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

from rxcheck.models import DEFAULT_SEVERITY_SCORE, Severity

SOURCE_SEPARATOR = ";"


class DataIntegrityError(ValueError):
    """Raised when the interaction dataset itself is malformed."""


@dataclass(frozen=True)
class InteractionFact:
    """A single curated interaction row, keyed by canonical drug id pair."""

    drug_id_a: str
    drug_id_b: str
    severity: Severity
    mechanism_short: str
    clinical_text: str
    action: str
    sources: tuple[str, ...]
    severity_score: int = DEFAULT_SEVERITY_SCORE
    age_band: str | None = None
    age_note: str | None = None


InteractionTable = dict[tuple[str, str], InteractionFact]


def load_interaction_table(path: Path) -> InteractionTable:
    """Load the interaction dataset CSV into a canonical-pair lookup table.

    Args:
        path: Path to a CSV with columns drug_id_a, drug_id_b, severity,
            severity_score, mechanism_short, clinical_text, action,
            sources, age_band, age_note. drug_id_a must sort before
            drug_id_b (enforces one canonical row per unordered pair).

    Returns:
        A dict mapping (drug_id_a, drug_id_b) to InteractionFact.

    Raises:
        DataIntegrityError: If a row's ids are not in canonical order, its
            severity is not one of major/moderate/minor, or the same pair
            appears more than once.
    """
    table: InteractionTable = {}
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            drug_id_a = row["drug_id_a"]
            drug_id_b = row["drug_id_b"]
            if drug_id_a >= drug_id_b:
                raise DataIntegrityError(
                    f"Interaction row ({drug_id_a}, {drug_id_b}) is not in "
                    "canonical (sorted) order."
                )

            key = (drug_id_a, drug_id_b)
            if key in table:
                raise DataIntegrityError(f"Duplicate interaction row for {key}.")

            try:
                severity = Severity(row["severity"])
            except ValueError as exc:
                raise DataIntegrityError(
                    f"Unknown severity '{row['severity']}' for pair {key}."
                ) from exc

            table[key] = InteractionFact(
                drug_id_a=drug_id_a,
                drug_id_b=drug_id_b,
                severity=severity,
                mechanism_short=row["mechanism_short"],
                clinical_text=row["clinical_text"],
                action=row["action"],
                sources=_parse_sources(row.get("sources", "")),
                severity_score=_parse_severity_score(row.get("severity_score")),
                age_band=row.get("age_band") or None,
                age_note=row.get("age_note") or None,
            )
    return table


def _parse_sources(raw: str) -> tuple[str, ...]:
    """Split a ';'-separated sources column into a tuple, preserving text."""
    return tuple(
        source.strip() for source in raw.split(SOURCE_SEPARATOR) if source.strip()
    )


def _parse_severity_score(raw: str | None) -> int:
    """Parse the optional numeric severity_score column."""
    if not raw:
        return DEFAULT_SEVERITY_SCORE
    return int(raw)
