"""Medication name normalization, alias resolution, and deduplication.

Resolution is intentionally conservative: exact, case/whitespace-normalized
matching against canonical names and aliases only. No fuzzy matching is
performed.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

from rxcheck.models import MedicationEntry, ResolvedDrug

ALIAS_SEPARATOR = ";"


@dataclass(frozen=True)
class DrugTableEntry:
    """A single canonical drug identity in the drug table."""

    drug_id: str
    canonical_name: str


DrugTable = dict[str, DrugTableEntry]


def normalize_name(raw: str) -> str:
    """Normalize a medication name for lookup.

    Trims surrounding whitespace, collapses repeated internal whitespace,
    and lowercases the result.

    Args:
        raw: The raw medication name.

    Returns:
        The normalized name.
    """
    return " ".join(raw.strip().lower().split())


def load_drug_table(path: Path) -> DrugTable:
    """Load the drug dictionary CSV into a normalized-name lookup table.

    Args:
        path: Path to a CSV with columns drug_id, canonical_name, aliases
            (aliases is a ';'-separated string of alternate names).

    Returns:
        A dict mapping every normalized canonical name and alias to its
        DrugTableEntry.
    """
    table: DrugTable = {}
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            entry = DrugTableEntry(
                drug_id=row["drug_id"], canonical_name=row["canonical_name"]
            )
            table[normalize_name(entry.canonical_name)] = entry
            for alias in row.get("aliases", "").split(ALIAS_SEPARATOR):
                alias = alias.strip()
                if alias:
                    table[normalize_name(alias)] = entry
    return table


def resolve_medications(
    entries: tuple[MedicationEntry, ...], table: DrugTable
) -> tuple[list[ResolvedDrug], list[str]]:
    """Resolve medication entries against the drug table, then deduplicate.

    Args:
        entries: Validated medication entries from the request.
        table: The loaded drug table, as returned by load_drug_table().

    Returns:
        A tuple of (resolved_drugs, unknown_names). resolved_drugs is
        deduplicated by canonical drug_id, keeping the first-seen dose for
        each duplicate. unknown_names preserves the original input strings
        for entries that did not match any canonical name or alias.
    """
    resolved_by_id: dict[str, ResolvedDrug] = {}
    unknown_names: list[str] = []

    for entry in entries:
        table_entry = table.get(normalize_name(entry.name))
        if table_entry is None:
            unknown_names.append(entry.name)
            continue
        if table_entry.drug_id not in resolved_by_id:
            resolved_by_id[table_entry.drug_id] = ResolvedDrug(
                drug_id=table_entry.drug_id,
                canonical_name=table_entry.canonical_name,
                input_text=entry.name,
                dose=entry.dose,
            )

    return list(resolved_by_id.values()), unknown_names
