"""End-to-end orchestration: request -> resolved pairs -> ranked report."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from rxcheck.explainer import ExplanationContext, ExplanationProvider
from rxcheck.interaction_store import (
    generate_pairs,
    load_interaction_table,
    lookup_interactions,
    rank_interactions,
)
from rxcheck.models import CheckReport, InteractionResult, parse_medication_input
from rxcheck.resolver import load_drug_table, resolve_medications


def check_medications(
    raw_request: Any,
    drug_table_path: Path,
    interaction_table_path: Path,
    explanation_provider: ExplanationProvider,
) -> CheckReport:
    """Validate a request and return its ranked, explained interaction report.

    Args:
        raw_request: The decoded JSON request body (see parse_medication_input).
        drug_table_path: Path to the drug dictionary CSV.
        interaction_table_path: Path to the curated interactions CSV.
        explanation_provider: Provider used to generate patient-facing text.

    Returns:
        A CheckReport with ranked interactions, the checked pair count, and
        any unrecognized medication names.

    Raises:
        InputValidationError: If raw_request does not match the required shape.
        DataIntegrityError: If either dataset file is malformed.
    """
    parsed = parse_medication_input(raw_request)
    drug_table = load_drug_table(drug_table_path)
    resolved, unknown = resolve_medications(parsed.medications, drug_table)

    pairs = generate_pairs(resolved)
    interaction_table = load_interaction_table(interaction_table_path)
    records = lookup_interactions(pairs, interaction_table)
    ranked = rank_interactions(records)

    context = ExplanationContext(age_band=parsed.age_band)
    results = tuple(
        InteractionResult(
            record=record, explanation=explanation_provider.explain(record, context)
        )
        for record in ranked
    )

    return CheckReport(
        interactions=results,
        checked_pairs=len(pairs),
        unknown_drugs=tuple(unknown),
    )
