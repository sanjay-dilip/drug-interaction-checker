"""Tests for medication name resolution."""

from pathlib import Path

import pytest

from rxcheck.models import MedicationEntry
from rxcheck.resolver import load_drug_table, normalize_name, resolve_medications

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def drug_table():
    return load_drug_table(FIXTURES_DIR / "drugs_fixture.csv")


def test_normalize_name_trims_and_lowercases() -> None:
    assert normalize_name("  Alpha Drug  ") == "alpha drug"


def test_normalize_name_collapses_internal_whitespace() -> None:
    assert normalize_name("Alpha   Drug") == "alpha drug"


def test_case_insensitive_exact_match(drug_table) -> None:
    resolved, unknown = resolve_medications(
        (MedicationEntry(name="ALPHA DRUG"),), drug_table
    )

    assert unknown == []
    assert len(resolved) == 1
    assert resolved[0].drug_id == "alpha"
    assert resolved[0].canonical_name == "alpha drug"


def test_whitespace_normalization_match(drug_table) -> None:
    resolved, unknown = resolve_medications(
        (MedicationEntry(name="  beta   drug "),), drug_table
    )

    assert unknown == []
    assert resolved[0].drug_id == "beta"


def test_alias_resolution(drug_table) -> None:
    resolved, unknown = resolve_medications(
        (MedicationEntry(name="gam"),), drug_table
    )

    assert unknown == []
    assert resolved[0].drug_id == "gamma"
    assert resolved[0].canonical_name == "gamma drug"


def test_unknown_medication_is_reported(drug_table) -> None:
    resolved, unknown = resolve_medications(
        (MedicationEntry(name="not a real drug"),), drug_table
    )

    assert resolved == []
    assert unknown == ["not a real drug"]


def test_duplicate_canonical_medication_deduplicated(drug_table) -> None:
    resolved, unknown = resolve_medications(
        (
            MedicationEntry(name="alpha drug", dose="10 mg"),
            MedicationEntry(name="ALPHA-ALT", dose="20 mg"),
        ),
        drug_table,
    )

    assert unknown == []
    assert len(resolved) == 1
    assert resolved[0].drug_id == "alpha"
    assert resolved[0].dose == "10 mg"


def test_mixed_known_and_unknown_medications(drug_table) -> None:
    resolved, unknown = resolve_medications(
        (
            MedicationEntry(name="alpha drug"),
            MedicationEntry(name="mystery drug"),
        ),
        drug_table,
    )

    assert len(resolved) == 1
    assert unknown == ["mystery drug"]


def test_empty_input_resolves_to_nothing(drug_table) -> None:
    resolved, unknown = resolve_medications((), drug_table)

    assert resolved == []
    assert unknown == []
