"""Tests for medication-check request validation."""

import pytest

from rxcheck.models import (
    InputValidationError,
    MedicationEntry,
    parse_medication_input,
)


def test_valid_request_parses() -> None:
    raw = {
        "medications": [
            {"name": "warfarin", "dose": "5 mg daily"},
            {"name": "ibuprofen", "dose": "400 mg as needed"},
        ],
        "age_band": "65+",
    }

    parsed = parse_medication_input(raw)

    assert parsed.medications == (
        MedicationEntry(name="warfarin", dose="5 mg daily"),
        MedicationEntry(name="ibuprofen", dose="400 mg as needed"),
    )
    assert parsed.age_band == "65+"


def test_dose_is_optional() -> None:
    parsed = parse_medication_input({"medications": [{"name": "warfarin"}]})

    assert parsed.medications == (MedicationEntry(name="warfarin", dose=None),)


def test_age_band_is_optional() -> None:
    parsed = parse_medication_input({"medications": [{"name": "warfarin"}]})

    assert parsed.age_band is None


def test_missing_medications_key_raises() -> None:
    with pytest.raises(InputValidationError):
        parse_medication_input({})


def test_empty_medications_list_raises() -> None:
    with pytest.raises(InputValidationError):
        parse_medication_input({"medications": []})


def test_medication_without_name_raises() -> None:
    with pytest.raises(InputValidationError):
        parse_medication_input({"medications": [{"dose": "5 mg daily"}]})


def test_blank_medication_name_raises() -> None:
    with pytest.raises(InputValidationError):
        parse_medication_input({"medications": [{"name": "   "}]})


def test_non_dict_request_raises() -> None:
    with pytest.raises(InputValidationError):
        parse_medication_input(["not", "a", "dict"])


def test_medications_not_a_list_raises() -> None:
    with pytest.raises(InputValidationError):
        parse_medication_input({"medications": "warfarin"})


def test_medication_entry_not_a_dict_raises() -> None:
    with pytest.raises(InputValidationError):
        parse_medication_input({"medications": ["warfarin"]})


def test_non_string_dose_raises() -> None:
    with pytest.raises(InputValidationError):
        parse_medication_input({"medications": [{"name": "warfarin", "dose": 5}]})


def test_non_string_age_band_raises() -> None:
    with pytest.raises(InputValidationError):
        parse_medication_input(
            {"medications": [{"name": "warfarin"}], "age_band": 65}
        )
