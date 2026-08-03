"""End-to-end tests for the checker orchestration."""

from pathlib import Path

from rxcheck.checker import check_medications, serialize_report
from rxcheck.explainer import DeterministicExplanationProvider

FIXTURES_DIR = Path(__file__).parent / "fixtures"
DRUG_TABLE_PATH = FIXTURES_DIR / "drugs_fixture.csv"
INTERACTION_TABLE_PATH = FIXTURES_DIR / "interactions_fixture.csv"


def _check(raw_request):
    return check_medications(
        raw_request,
        DRUG_TABLE_PATH,
        INTERACTION_TABLE_PATH,
        DeterministicExplanationProvider(),
    )


def test_three_known_medications_produce_three_checked_pairs() -> None:
    report = _check(
        {
            "medications": [
                {"name": "alpha drug"},
                {"name": "beta drug"},
                {"name": "gamma drug"},
            ]
        }
    )

    assert report.checked_pairs == 3
    assert report.unknown_drugs == ()


def test_matching_interactions_are_ranked_major_first() -> None:
    report = _check(
        {
            "medications": [
                {"name": "alpha drug"},
                {"name": "beta drug"},
                {"name": "gamma drug"},
            ]
        }
    )

    severities = [result.record.severity.value for result in report.interactions]
    assert severities == ["major", "moderate", "minor"]


def test_unknown_medication_is_reported_without_failing_request() -> None:
    report = _check(
        {
            "medications": [
                {"name": "alpha drug"},
                {"name": "not a real drug"},
            ]
        }
    )

    assert report.unknown_drugs == ("not a real drug",)
    assert report.checked_pairs == 0


def test_explanations_are_generated_for_each_interaction() -> None:
    report = _check(
        {"medications": [{"name": "alpha drug"}, {"name": "gamma drug"}]}
    )

    (result,) = report.interactions
    assert result.explanation
    assert result.record.drug_a_name in result.explanation


def test_serialize_report_matches_output_contract_shape() -> None:
    report = _check(
        {"medications": [{"name": "alpha drug"}, {"name": "gamma drug"}]}
    )

    serialized = serialize_report(report)

    assert set(serialized.keys()) == {"interactions", "checked_pairs", "unknown_drugs"}
    (interaction,) = serialized["interactions"]
    assert set(interaction.keys()) == {
        "drugs",
        "severity",
        "mechanism_short",
        "explanation",
        "action",
        "sources",
    }
    assert interaction["drugs"] == ["alpha drug", "gamma drug"]
    assert interaction["severity"] == "major"
    assert serialized["checked_pairs"] == 1
    assert serialized["unknown_drugs"] == []


def test_age_alone_cannot_create_an_interaction() -> None:
    without_age = _check({"medications": [{"name": "not a real drug"}]})
    with_age = _check(
        {"medications": [{"name": "not a real drug"}], "age_band": "65+"}
    )

    assert without_age.checked_pairs == with_age.checked_pairs == 0
    assert without_age.interactions == with_age.interactions == ()
