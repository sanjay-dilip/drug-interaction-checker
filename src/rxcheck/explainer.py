"""Patient-friendly explanation generation for interaction records.

The deterministic provider is the default and only ever restates fields
already present in the retrieved InteractionRecord. The optional LLM
provider may rewrite that same text for tone, but every output is
validated and falls back to the deterministic text on any failure —
the LLM can never introduce a fact, change severity, or invent a source.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Protocol

from rxcheck.models import InteractionRecord

MAX_LLM_EXPLANATION_CHARS = 800

logger = logging.getLogger(__name__)


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


class LLMClientProtocol(Protocol):
    """A minimal, mockable interface for an LLM text-generation backend."""

    def generate(self, prompt: str) -> str: ...


@dataclass
class LLMExplanationProvider:
    """Rewrites the deterministic explanation via an LLM, with fail-closed validation.

    The LLM is given only the retrieved record's own fields and is
    instructed to simplify wording without changing facts. Its output is
    used only if it passes `_is_valid_llm_output`; otherwise the
    deterministic explanation is returned unchanged.
    """

    base_provider: ExplanationProvider
    client: LLMClientProtocol

    def explain(self, record: InteractionRecord, context: ExplanationContext) -> str:
        """Return an LLM-rewritten explanation, or the deterministic fallback.

        Args:
            record: The curated interaction fact to explain.
            context: The request's explanation context (e.g. age_band).

        Returns:
            The validated LLM rewrite, or the deterministic explanation if
            the LLM is unavailable, errors, or produces invalid output.
        """
        deterministic_text = self.base_provider.explain(record, context)
        prompt = _build_prompt(record, context, deterministic_text)

        try:
            llm_text = self.client.generate(prompt)
        except Exception:
            logger.warning("LLM explanation generation failed; using fallback.")
            return deterministic_text

        if not _is_valid_llm_output(record, llm_text):
            logger.warning("LLM explanation failed validation; using fallback.")
            return deterministic_text

        return llm_text.strip()


def _build_prompt(
    record: InteractionRecord, context: ExplanationContext, deterministic_text: str
) -> str:
    """Build a prompt that supplies only retrieved facts, never dataset access.

    Args:
        record: The curated interaction fact to rewrite.
        context: The request's explanation context (e.g. age_band).
        deterministic_text: The deterministic explanation being rewritten.

    Returns:
        The prompt string for the LLM client.
    """
    age_note_line = ""
    if (
        context.age_band is not None
        and context.age_band == record.age_band
        and record.age_note
    ):
        age_note_line = f"Age-related note: {record.age_note}\n"

    return (
        "Rewrite the following drug interaction explanation in clear, "
        "plain language for a patient. Preserve its meaning exactly. "
        "Do not introduce any new fact, medication, symptom, risk factor, "
        "probability, timeline, or treatment alternative. Do not change "
        "the severity or the recommended action. Do not give diagnosis or "
        "treatment advice beyond what is stated. Return only the rewritten "
        "explanation text.\n\n"
        f"Drug A: {record.drug_a_name}\n"
        f"Drug B: {record.drug_b_name}\n"
        f"Severity: {record.severity.value}\n"
        f"Mechanism: {record.mechanism_short}\n"
        f"Clinical text: {record.clinical_text}\n"
        f"Recommended action: {record.action}\n"
        f"{age_note_line}"
        f"\nOriginal explanation: {deterministic_text}"
    )


def _is_valid_llm_output(record: InteractionRecord, llm_text: str) -> bool:
    """Check that an LLM rewrite is safe to use in place of the deterministic text.

    Args:
        record: The curated interaction fact the rewrite must stay grounded in.
        llm_text: The raw text returned by the LLM client.

    Returns:
        True if the output is non-empty, within the length limit, still
        mentions both drug names, and introduces no numbers absent from
        the retrieved record's own fields.
    """
    text = llm_text.strip()
    if not text or len(text) > MAX_LLM_EXPLANATION_CHARS:
        return False

    lowered = text.lower()
    if record.drug_a_name.lower() not in lowered:
        return False
    if record.drug_b_name.lower() not in lowered:
        return False

    source_text = " ".join(
        part
        for part in (
            record.mechanism_short,
            record.clinical_text,
            record.action,
            record.age_note,
        )
        if part
    )
    if _numbers_in(text) - _numbers_in(source_text):
        return False

    return True


def _numbers_in(text: str) -> set[str]:
    """Extract the set of numeric substrings appearing in text."""
    return set(re.findall(r"\d+", text))
