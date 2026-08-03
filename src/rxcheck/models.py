"""Core data models for rxcheck.

These types are the shared vocabulary between the resolver, interaction
store, explainer, and checker modules.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

DEFAULT_SEVERITY_SCORE = 0


class Severity(str, Enum):
    """Closed set of interaction severities recognized by the dataset."""

    MAJOR = "major"
    MODERATE = "moderate"
    MINOR = "minor"


SEVERITY_RANK: dict[Severity, int] = {
    Severity.MAJOR: 3,
    Severity.MODERATE: 2,
    Severity.MINOR: 1,
}


@dataclass(frozen=True)
class MedicationEntry:
    """A single medication as supplied in the request input."""

    name: str
    dose: str | None = None


@dataclass(frozen=True)
class ParsedRequest:
    """A validated medication-check request."""

    medications: tuple[MedicationEntry, ...]
    age_band: str | None = None


@dataclass(frozen=True)
class ResolvedDrug:
    """A medication resolved to a canonical dataset identity."""

    drug_id: str
    canonical_name: str
    input_text: str
    dose: str | None = None


@dataclass(frozen=True)
class InteractionRecord:
    """A curated interaction fact retrieved from the local dataset."""

    drug_id_a: str
    drug_id_b: str
    drug_a_name: str
    drug_b_name: str
    severity: Severity
    mechanism_short: str
    clinical_text: str
    action: str
    sources: tuple[str, ...]
    severity_score: int = DEFAULT_SEVERITY_SCORE
    age_band: str | None = None
    age_note: str | None = None


@dataclass(frozen=True)
class InteractionResult:
    """An interaction record paired with its generated explanation text."""

    record: InteractionRecord
    explanation: str


@dataclass(frozen=True)
class CheckReport:
    """The full result of checking a medication list for interactions."""

    interactions: tuple[InteractionResult, ...]
    checked_pairs: int
    unknown_drugs: tuple[str, ...]
