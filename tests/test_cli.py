"""Tests for the rxcheck CLI entrypoint."""

import json

import pytest

from rxcheck.cli import EXIT_INVALID_INPUT, EXIT_OK, main


@pytest.fixture
def sample_input(tmp_path):
    path = tmp_path / "input.json"
    path.write_text(
        json.dumps(
            {
                "medications": [
                    {"name": "warfarin", "dose": "5 mg daily"},
                    {"name": "ibuprofen", "dose": "400 mg as needed"},
                ]
            }
        ),
        encoding="utf-8",
    )
    return path


def test_valid_input_exits_zero_and_prints_json(sample_input, capsys) -> None:
    exit_code = main([str(sample_input)])

    assert exit_code == EXIT_OK
    payload = json.loads(capsys.readouterr().out)
    assert payload["checked_pairs"] == 1
    assert payload["interactions"][0]["severity"] == "major"


def test_output_flag_writes_file(sample_input, tmp_path) -> None:
    output_path = tmp_path / "out.json"

    exit_code = main([str(sample_input), "--output", str(output_path)])

    assert exit_code == EXIT_OK
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["checked_pairs"] == 1


def test_missing_file_exits_nonzero_with_stderr_message(tmp_path, capsys) -> None:
    missing_path = tmp_path / "does_not_exist.json"

    exit_code = main([str(missing_path)])

    captured = capsys.readouterr()
    assert exit_code == EXIT_INVALID_INPUT
    assert captured.err.strip()
    assert "Traceback" not in captured.err


def test_malformed_json_exits_nonzero_with_stderr_message(tmp_path, capsys) -> None:
    bad_json_path = tmp_path / "bad.json"
    bad_json_path.write_text("{not valid json", encoding="utf-8")

    exit_code = main([str(bad_json_path)])

    captured = capsys.readouterr()
    assert exit_code == EXIT_INVALID_INPUT
    assert captured.err.strip()
    assert "Traceback" not in captured.err


def test_invalid_request_shape_exits_nonzero_with_stderr_message(
    tmp_path, capsys
) -> None:
    bad_shape_path = tmp_path / "bad_shape.json"
    bad_shape_path.write_text(json.dumps({"medications": []}), encoding="utf-8")

    exit_code = main([str(bad_shape_path)])

    captured = capsys.readouterr()
    assert exit_code == EXIT_INVALID_INPUT
    assert captured.err.strip()
    assert "Traceback" not in captured.err


def test_llm_flag_still_succeeds_via_deterministic_fallback(
    sample_input, capsys
) -> None:
    exit_code = main([str(sample_input), "--llm"])

    assert exit_code == EXIT_OK
    payload = json.loads(capsys.readouterr().out)
    assert payload["checked_pairs"] == 1
