"""Tests for deterministic and LLM-backed explanation providers."""

from rxcheck.explainer import (
    DeterministicExplanationProvider,
    ExplanationContext,
    LLMExplanationProvider,
)
from rxcheck.models import InteractionRecord, Severity

NO_AGE_CONTEXT = ExplanationContext()


def _record(**overrides) -> InteractionRecord:
    defaults = dict(
        drug_id_a="alpha",
        drug_id_b="beta",
        drug_a_name="Alpha Drug",
        drug_b_name="Beta Drug",
        severity=Severity.MAJOR,
        mechanism_short="Increased risk",
        clinical_text="Alpha Drug and Beta Drug together increase bleeding risk.",
        action="talk_to_doctor",
        sources=("Fixture Source",),
        severity_score=90,
    )
    defaults.update(overrides)
    return InteractionRecord(**defaults)


class StubClient:
    """A mockable LLM client that returns a fixed response or raises."""

    def __init__(self, response=None, exc=None):
        self.response = response
        self.exc = exc
        self.last_prompt = None

    def generate(self, prompt: str) -> str:
        self.last_prompt = prompt
        if self.exc is not None:
            raise self.exc
        return self.response


def test_deterministic_explanation_uses_retrieved_content() -> None:
    record = _record()
    provider = DeterministicExplanationProvider()

    explanation = provider.explain(record, NO_AGE_CONTEXT)

    assert record.drug_a_name in explanation
    assert record.drug_b_name in explanation
    assert record.severity.value in explanation
    assert record.clinical_text in explanation
    assert record.action in explanation


def test_deterministic_explanation_omits_age_note_when_band_not_supplied() -> None:
    record = _record(age_band="65+", age_note="Extra caution for older adults.")
    provider = DeterministicExplanationProvider()

    explanation = provider.explain(record, NO_AGE_CONTEXT)

    assert "Extra caution" not in explanation


def test_deterministic_explanation_uses_age_note_when_band_matches() -> None:
    record = _record(age_band="65+", age_note="Extra caution for older adults.")
    provider = DeterministicExplanationProvider()

    explanation = provider.explain(record, ExplanationContext(age_band="65+"))

    assert "Extra caution for older adults." in explanation


def test_deterministic_explanation_ignores_non_matching_age_band() -> None:
    record = _record(age_band="65+", age_note="Extra caution for older adults.")
    provider = DeterministicExplanationProvider()

    explanation = provider.explain(record, ExplanationContext(age_band="18-40"))

    assert "Extra caution" not in explanation


def test_llm_provider_returns_valid_rewrite() -> None:
    record = _record()
    base = DeterministicExplanationProvider()
    client = StubClient(
        response="Alpha Drug and Beta Drug can raise your bleeding risk. "
        "Please talk_to_doctor about this combination."
    )
    provider = LLMExplanationProvider(base_provider=base, client=client)

    explanation = provider.explain(record, NO_AGE_CONTEXT)

    assert explanation == client.response


def test_llm_prompt_never_contains_full_dataset_only_record_fields() -> None:
    record = _record()
    base = DeterministicExplanationProvider()
    client = StubClient(response="valid Alpha Drug Beta Drug rewrite")
    provider = LLMExplanationProvider(base_provider=base, client=client)

    provider.explain(record, NO_AGE_CONTEXT)

    assert record.clinical_text in client.last_prompt
    assert record.action in client.last_prompt
    assert "interactions.csv" not in client.last_prompt


def test_llm_failure_triggers_deterministic_fallback() -> None:
    record = _record()
    base = DeterministicExplanationProvider()
    client = StubClient(exc=TimeoutError("provider timed out"))
    provider = LLMExplanationProvider(base_provider=base, client=client)

    explanation = provider.explain(record, NO_AGE_CONTEXT)

    assert explanation == base.explain(record, NO_AGE_CONTEXT)


def test_empty_llm_output_triggers_fallback() -> None:
    record = _record()
    base = DeterministicExplanationProvider()
    client = StubClient(response="   ")
    provider = LLMExplanationProvider(base_provider=base, client=client)

    explanation = provider.explain(record, NO_AGE_CONTEXT)

    assert explanation == base.explain(record, NO_AGE_CONTEXT)


def test_llm_output_missing_a_drug_name_triggers_fallback() -> None:
    record = _record()
    base = DeterministicExplanationProvider()
    client = StubClient(response="This combination increases bleeding risk.")
    provider = LLMExplanationProvider(base_provider=base, client=client)

    explanation = provider.explain(record, NO_AGE_CONTEXT)

    assert explanation == base.explain(record, NO_AGE_CONTEXT)


def test_llm_output_with_invented_number_triggers_fallback() -> None:
    record = _record()
    base = DeterministicExplanationProvider()
    client = StubClient(
        response="Alpha Drug and Beta Drug raise bleeding risk by 42 percent."
    )
    provider = LLMExplanationProvider(base_provider=base, client=client)

    explanation = provider.explain(record, NO_AGE_CONTEXT)

    assert explanation == base.explain(record, NO_AGE_CONTEXT)


def test_llm_output_exceeding_max_length_triggers_fallback() -> None:
    record = _record()
    base = DeterministicExplanationProvider()
    long_text = "Alpha Drug Beta Drug " + ("x" * 900)
    client = StubClient(response=long_text)
    provider = LLMExplanationProvider(base_provider=base, client=client)

    explanation = provider.explain(record, NO_AGE_CONTEXT)

    assert explanation == base.explain(record, NO_AGE_CONTEXT)


def test_explanation_generation_cannot_modify_record_fields() -> None:
    record = _record()
    base = DeterministicExplanationProvider()
    client = StubClient(response="Alpha Drug and Beta Drug: a rewritten notice.")
    provider = LLMExplanationProvider(base_provider=base, client=client)

    provider.explain(record, NO_AGE_CONTEXT)

    assert record.severity == Severity.MAJOR
    assert record.action == "talk_to_doctor"
    assert record.sources == ("Fixture Source",)
    assert record.drug_a_name == "Alpha Drug"
    assert record.drug_b_name == "Beta Drug"
