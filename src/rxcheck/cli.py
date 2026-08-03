"""Command-line entrypoint: `python -m rxcheck.cli <input.json>`."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from rxcheck.checker import check_medications, serialize_report
from rxcheck.explainer import (
    DeterministicExplanationProvider,
    ExplanationProvider,
)
from rxcheck.interaction_store import DataIntegrityError
from rxcheck.models import InputValidationError

EXIT_OK = 0
EXIT_INVALID_INPUT = 1

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
DEFAULT_DRUG_TABLE_PATH = DATA_DIR / "drugs.csv"
DEFAULT_INTERACTION_TABLE_PATH = DATA_DIR / "interactions.csv"

logger = logging.getLogger(__name__)


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI argument parser.

    Returns:
        A configured ArgumentParser for the rxcheck CLI.
    """
    parser = argparse.ArgumentParser(
        prog="python -m rxcheck.cli",
        description=(
            "Check a medication list for curated drug-drug interactions."
        ),
    )
    parser.add_argument(
        "input_file", help="Path to a JSON file matching the request contract."
    )
    parser.add_argument(
        "--output", help="Path to also write the JSON report to."
    )
    parser.add_argument(
        "--llm",
        action="store_true",
        help=(
            "Request LLM-rewritten explanations. Falls back to deterministic "
            "explanations if no LLM provider is configured."
        ),
    )
    return parser


def _build_explanation_provider(use_llm: bool) -> ExplanationProvider:
    """Select the explanation provider for this run.

    Args:
        use_llm: Whether the --llm flag was passed.

    Returns:
        DeterministicExplanationProvider in all cases in this build, since
        no LLM provider is wired up yet; a warning is logged if --llm was
        requested so the fallback is visible without failing the request.
    """
    if use_llm:
        logger.warning(
            "LLM explanations were requested via --llm, but no LLM provider "
            "is configured in this build; using deterministic explanations."
        )
    return DeterministicExplanationProvider()


def main(argv: list[str] | None = None) -> int:
    """Run the rxcheck CLI.

    Args:
        argv: Command-line arguments, excluding the program name. Defaults
            to sys.argv[1:] when None.

    Returns:
        The process exit code: 0 on success, 1 on invalid input or an
        unreadable/unwritable file.
    """
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        raw_text = Path(args.input_file).read_text(encoding="utf-8")
        raw_request = json.loads(raw_text)
        provider = _build_explanation_provider(args.llm)
        report = check_medications(
            raw_request,
            DEFAULT_DRUG_TABLE_PATH,
            DEFAULT_INTERACTION_TABLE_PATH,
            provider,
        )
        output_json = json.dumps(serialize_report(report), indent=2)
    except (
        OSError,
        json.JSONDecodeError,
        InputValidationError,
        DataIntegrityError,
    ) as exc:
        print(str(exc), file=sys.stderr)
        return EXIT_INVALID_INPUT
    except Exception:
        logger.exception("Unexpected error while checking medications.")
        print("An unexpected error occurred.", file=sys.stderr)
        return EXIT_INVALID_INPUT

    print(output_json)

    if args.output:
        try:
            Path(args.output).write_text(output_json + "\n", encoding="utf-8")
        except OSError as exc:
            print(str(exc), file=sys.stderr)
            return EXIT_INVALID_INPUT

    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
