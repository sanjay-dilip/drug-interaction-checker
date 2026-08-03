"""Core data models for rxcheck.

These types are the shared vocabulary between the resolver, interaction
store, explainer, and checker modules.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

MIN_MEDICATIONS = 1
DEFAULT_SEVERITY_SCORE = 0


class InputValidationError(ValueError):
    """Raised when the supplied medication-check request is malformed."""


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


def parse_medication_input(raw: Any) -> ParsedRequest:
    """Validate and parse a raw medication-check request.

    Args:
        raw: The decoded JSON request body.

    Returns:
        A validated ParsedRequest.

    Raises:
        InputValidationError: If the request does not match the required
            shape (missing/empty medication list, missing or blank names,
            or wrong field types).
    """
    if not isinstance(raw, dict):
        raise InputValidationError("Request body must be a JSON object.")

    medications_raw = raw.get("medications")
    if medications_raw is None:
        raise InputValidationError("'medications' is required.")
    if not isinstance(medications_raw, list):
        raise InputValidationError("'medications' must be a list.")
    if len(medications_raw) < MIN_MEDICATIONS:
        raise InputValidationError("'medications' must not be empty.")

    medications = tuple(
        _parse_medication_entry(entry, index)
        for index, entry in enumerate(medications_raw)
    )

    age_band = raw.get("age_band")
    if age_band is not None and not isinstance(age_band, str):
        raise InputValidationError("'age_band' must be a string if provided.")

    return ParsedRequest(medications=medications, age_band=age_band)


def _parse_medication_entry(entry: Any, index: int) -> MedicationEntry:
    """Validate and parse a single medication entry.

    Args:
        entry: The raw medication entry from the request.
        index: The entry's position, used for error messages.

    Returns:
        A validated MedicationEntry.

    Raises:
        InputValidationError: If the entry is not an object, is missing a
            non-empty 'name', or has a non-string 'dose'.
    """
    if not isinstance(entry, dict):
        raise InputValidationError(f"medications[{index}] must be an object.")

    name = entry.get("name")
    if not isinstance(name, str) or not name.strip():
        raise InputValidationError(
            f"medications[{index}] must have a non-empty 'name'."
        )

    dose = entry.get("dose")
    if dose is not None and not isinstance(dose, str):
        raise InputValidationError(
            f"medications[{index}].dose must be a string if provided."
        )

    return MedicationEntry(name=name, dose=dose)
