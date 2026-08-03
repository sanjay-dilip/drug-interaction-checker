"""Tests for interaction lookup, pair generation, and ranking."""

from pathlib import Path

import pytest

from rxcheck.interaction_store import (
    DataIntegrityError,
    generate_pairs,
    load_interaction_table,
    lookup_interactions,
    rank_interactions,
)
from rxcheck.models import InteractionRecord, ResolvedDrug, Severity

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def interaction_table():
    return load_interaction_table(FIXTURES_DIR / "interactions_fixture.csv")


def _drug(drug_id: str, canonical_name: str) -> ResolvedDrug:
    return ResolvedDrug(
        drug_id=drug_id, canonical_name=canonical_name, input_text=canonical_name
    )


ALPHA = _drug("alpha", "Alpha Drug")
BETA = _drug("beta", "Beta Drug")
GAMMA = _drug("gamma", "Gamma Drug")


def test_generate_pairs_zero_medications() -> None:
    assert generate_pairs([]) == []


def test_generate_pairs_one_medication() -> None:
    assert generate_pairs([ALPHA]) == []


def test_generate_pairs_two_medications() -> None:
    pairs = generate_pairs([BETA, ALPHA])

    assert pairs == [(ALPHA, BETA)]


def test_generate_pairs_three_medications_produce_three_pairs() -> None:
    pairs = generate_pairs([GAMMA, ALPHA, BETA])

    assert len(pairs) == 3
    assert set(pairs) == {(ALPHA, BETA), (ALPHA, GAMMA), (BETA, GAMMA)}


def test_matching_interaction_is_returned(interaction_table) -> None:
    records = lookup_interactions(generate_pairs([ALPHA, GAMMA]), interaction_table)

    assert len(records) == 1
    record = records[0]
    assert record.severity == Severity.MAJOR
    assert record.mechanism_short == "Synthetic major mechanism"
    assert record.action == "fixture_action_major"
    assert record.sources == ("Fixture Source A",)


def test_pair_order_does_not_affect_lookup(interaction_table) -> None:
    forward = lookup_interactions(generate_pairs([ALPHA, GAMMA]), interaction_table)
    reverse = lookup_interactions(generate_pairs([GAMMA, ALPHA]), interaction_table)

    assert forward == reverse


def test_non_matching_pair_is_omitted(interaction_table) -> None:
    unrelated = _drug("delta", "Delta Drug")

    records = lookup_interactions(generate_pairs([ALPHA, unrelated]), interaction_table)

    assert records == []


def test_load_interaction_table_rejects_unordered_pair(tmp_path) -> None:
    bad_csv = tmp_path / "bad.csv"
    bad_csv.write_text(
        "drug_id_a,drug_id_b,severity,severity_score,mechanism_short,"
        "clinical_text,action,sources,age_band,age_note\n"
        "gamma,alpha,major,90,m,c,a,s,,\n",
        encoding="utf-8",
    )

    with pytest.raises(DataIntegrityError):
        load_interaction_table(bad_csv)


def test_load_interaction_table_rejects_unknown_severity(tmp_path) -> None:
    bad_csv = tmp_path / "bad.csv"
    bad_csv.write_text(
        "drug_id_a,drug_id_b,severity,severity_score,mechanism_short,"
        "clinical_text,action,sources,age_band,age_note\n"
        "alpha,gamma,catastrophic,90,m,c,a,s,,\n",
        encoding="utf-8",
    )

    with pytest.raises(DataIntegrityError):
        load_interaction_table(bad_csv)


def test_load_interaction_table_rejects_duplicate_pair(tmp_path) -> None:
    bad_csv = tmp_path / "bad.csv"
    bad_csv.write_text(
        "drug_id_a,drug_id_b,severity,severity_score,mechanism_short,"
        "clinical_text,action,sources,age_band,age_note\n"
        "alpha,gamma,major,90,m,c,a,s,,\n"
        "alpha,gamma,minor,10,m,c,a,s,,\n",
        encoding="utf-8",
    )

    with pytest.raises(DataIntegrityError):
        load_interaction_table(bad_csv)


def _record(
    severity: Severity, severity_score: int, drug_a_name: str, drug_b_name: str
) -> InteractionRecord:
    return InteractionRecord(
        drug_id_a=drug_a_name.lower(),
        drug_id_b=drug_b_name.lower(),
        drug_a_name=drug_a_name,
        drug_b_name=drug_b_name,
        severity=severity,
        mechanism_short="mechanism",
        clinical_text="clinical text",
        action="action",
        sources=("Source",),
        severity_score=severity_score,
    )


def test_major_ranks_before_moderate() -> None:
    moderate = _record(Severity.MODERATE, 50, "Alpha", "Beta")
    major = _record(Severity.MAJOR, 50, "Alpha", "Beta")

    ranked = rank_interactions([moderate, major])

    assert ranked == [major, moderate]


def test_moderate_ranks_before_minor() -> None:
    minor = _record(Severity.MINOR, 50, "Alpha", "Beta")
    moderate = _record(Severity.MODERATE, 50, "Alpha", "Beta")

    ranked = rank_interactions([minor, moderate])

    assert ranked == [moderate, minor]


def test_secondary_sort_by_severity_score() -> None:
    lower_score = _record(Severity.MAJOR, 40, "Alpha", "Beta")
    higher_score = _record(Severity.MAJOR, 90, "Charlie", "Delta")

    ranked = rank_interactions([lower_score, higher_score])

    assert ranked == [higher_score, lower_score]


def test_tie_ordering_is_deterministic_by_drug_names() -> None:
    zeta_pair = _record(Severity.MAJOR, 50, "Zeta", "Zulu")
    alpha_pair = _record(Severity.MAJOR, 50, "Alpha", "Beta")

    ranked = rank_interactions([zeta_pair, alpha_pair])

    assert ranked == [alpha_pair, zeta_pair]


def test_ranking_preserves_sources_and_action_unchanged() -> None:
    record = _record(Severity.MAJOR, 50, "Alpha", "Beta")

    (ranked,) = rank_interactions([record])

    assert ranked.sources == ("Source",)
    assert ranked.action == "action"
