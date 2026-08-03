"""Patient-friendly explanation generation for interaction records.

The deterministic provider is the default and only ever restates fields
already present in the retrieved InteractionRecord.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from rxcheck.models import InteractionRecord


@dataclass(frozen=True)
class ExplanationContext:
    """Request-level context available to explanation providers."""

    age_band: str | None = None


class ExplanationProvider(Protocol):
    """Produces a patient-friendly explanation for an interaction record."""

    def explain(
        self, record: InteractionRecord, context: ExplanationContext
    ) -> str: ...


class DeterministicExplanationProvider:
    """Formats an explanation using only fields already in the record."""

    def explain(self, record: InteractionRecord, context: ExplanationContext) -> str:
        """Build a plain-language explanation from the retrieved record.

        Args:
            record: The curated interaction fact to explain.
            context: The request's explanation context (e.g. age_band).

        Returns:
            An explanation string grounded only in `record`'s fields.
        """
        sentence = (
            f"{record.drug_a_name} and {record.drug_b_name} have a "
            f"{record.severity.value} interaction: {record.clinical_text} "
            f"Recommended action: {record.action}."
        )
        if (
            context.age_band is not None
            and context.age_band == record.age_band
            and record.age_note
        ):
            sentence += f" Note for patients age {context.age_band}: {record.age_note}"
        return sentence
