import json
from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor
from threading import Lock

import pytest

from xhotpotqa.generation.protocols import GenerationResponseError
from xhotpotqa.generation.translation import (
    PROMPT_HASH,
    PROMPT_VERSION,
    StructuredTranslator,
    TranslationResponseError,
)


class SequenceGenerator:
    def __init__(self, responses: Sequence[str]) -> None:
        self.responses = list(responses)
        self.calls = 0
        self.messages: list[list[dict[str, str]]] = []

    def generate(self, messages: Sequence[dict[str, str]]) -> str:
        self.calls += 1
        self.messages.append([dict(message) for message in messages])
        return self.responses.pop(0)


def _user_payload(generator: SequenceGenerator) -> dict[str, object]:
    return json.loads(generator.messages[-1][1]["content"])


def test_prompt_identity_is_frozen_for_v2() -> None:
    assert PROMPT_VERSION == "xhotpotqa-translation-v2.0"
    assert PROMPT_HASH == "623496d198d7850c244ff4e2303b7ba9b61548499ce10256ae6691a6b58e71f3"


def test_single_translation_wire_contract_is_explicit() -> None:
    generator = SequenceGenerator(['{"translation":"answer"}'])
    translator = StructuredTranslator(generator, model_id="model", revision="revision")

    assert translator.translate_text("source", "fa", "answer") == "answer"
    payload = _user_payload(generator)
    assert payload["task"] == "translate"
    assert payload["response_schema"] == {
        "type": "object",
        "additionalProperties": False,
        "required": ["translation"],
        "properties": {"translation": {"type": "string", "minLength": 1}},
    }


def test_sentence_array_wire_contract_fixes_output_cardinality() -> None:
    generator = SequenceGenerator(['{"translations":["one","two"]}'])
    translator = StructuredTranslator(generator, model_id="model", revision="revision")

    assert translator.translate_sentences(("first", "second"), "fa") == ("one", "two")
    payload = _user_payload(generator)
    translations = payload["response_schema"]["properties"]["translations"]
    assert translations["minItems"] == 2
    assert translations["maxItems"] == 2
    assert payload["response_schema"]["required"] == ["translations"]


def test_schema_error_is_retried_not_just_invalid_json() -> None:
    generator = SequenceGenerator(['{"wrong_key":"value"}', '{"translation":" پاسخ "}'])
    translator = StructuredTranslator(
        generator, model_id="model", revision="revision", max_retries=2
    )

    assert translator.translate_text("answer", "fa", "answer") == "پاسخ"
    assert generator.calls == 2
    assert translator.retry_count == 1


def test_additional_response_keys_are_retried() -> None:
    generator = SequenceGenerator(
        ['{"translation":"answer","explanation":"extra"}', '{"translation":"answer"}']
    )
    translator = StructuredTranslator(
        generator, model_id="model", revision="revision", max_retries=2
    )

    assert translator.translate_text("source", "fa", "answer") == "answer"
    assert generator.calls == 2
    assert translator.retry_count == 1


@pytest.mark.parametrize(
    "invalid_response",
    [
        'Here is the translation: {"translation":"answer"}',
        '```json\n{"translation":"answer"}\n```',
        '{"translation":"answer"} trailing prose',
        '{"translation":"first"}{"translation":"second"}',
        '[{"translation":"answer"}]',
        '{"response":{"translation":"answer"}}',
        '{"translation":"first","translation":"second"}',
    ],
)
def test_response_must_be_exactly_one_unwrapped_json_object(invalid_response: str) -> None:
    generator = SequenceGenerator([invalid_response, '{"translation":"answer"}'])
    translator = StructuredTranslator(
        generator, model_id="model", revision="revision", max_retries=2
    )

    assert translator.translate_text("source", "fa", "answer") == "answer"
    assert generator.calls == 2
    assert translator.retry_count == 1


def test_surrounding_whitespace_is_the_only_permitted_wrapper() -> None:
    generator = SequenceGenerator([' \r\n\t{"translation":"answer"}\n '])
    translator = StructuredTranslator(generator, model_id="model", revision="revision")

    assert translator.translate_text("source", "fa", "answer") == "answer"
    assert generator.calls == 1


def test_sentence_cardinality_error_is_retried() -> None:
    generator = SequenceGenerator(
        [
            '{"translations":["یک"]}',
            '{"translations":["یک","دو"]}',
        ]
    )
    translator = StructuredTranslator(
        generator, model_id="model", revision="revision", max_retries=2
    )

    assert translator.translate_sentences(("one", "two"), "fa") == ("یک", "دو")
    assert generator.calls == 2
    assert translator.retry_count == 1


def test_english_passthrough_does_not_call_model() -> None:
    generator = SequenceGenerator([])
    translator = StructuredTranslator(generator, model_id="model", revision="revision")

    assert translator.translate_text("answer", "en", "answer") == "answer"
    assert translator.translate_sentences(("one", "two"), "en") == ("one", "two")
    assert generator.calls == 0


def test_audit_writer_records_rejected_and_accepted_raw_responses() -> None:
    records: list[dict[str, object]] = []
    generator = SequenceGenerator(['{"wrong":true}', '{"translation":"answer"}'])
    translator = StructuredTranslator(
        generator,
        model_id="model",
        revision="revision",
        max_retries=2,
        audit_writer=lambda record: records.append(dict(record)),
    )

    assert translator.translate_text("source", "fa", "answer") == "answer"
    assert [record["status"] for record in records] == ["rejected", "accepted"]
    assert records[0]["raw_response"] == '{"wrong":true}'


def test_exhausted_contract_never_silently_copies_source_text() -> None:
    generator = SequenceGenerator(['{"wrong":true}', '{"still_wrong":true}'])
    translator = StructuredTranslator(
        generator,
        model_id="model",
        revision="revision",
        max_retries=2,
    )

    with pytest.raises(TranslationResponseError, match="exhausted"):
        translator.translate_text("English source", "fa", "answer")

    assert generator.calls == 2


def test_one_character_source_is_sent_to_the_model_without_placeholder_repair() -> None:
    generator = SequenceGenerator(['{"translation":"one"}'])
    translator = StructuredTranslator(generator, model_id="model", revision="revision")

    assert translator.translate_text("1", "fa", "answer") == "one"
    assert _user_payload(generator)["text"] == "1"


class PerSourceGenerator:
    def __init__(self) -> None:
        self._counts: dict[str, int] = {}
        self._lock = Lock()

    def generate(self, messages: Sequence[dict[str, str]]) -> str:
        source = str(json.loads(messages[1]["content"])["text"])
        with self._lock:
            count = self._counts.get(source, 0)
            self._counts[source] = count + 1
        if source == "retry" and count == 0:
            return '{"wrong":true}'
        return json.dumps({"translation": f"translated-{source}"})


def test_record_retry_provenance_is_isolated_across_worker_threads() -> None:
    translator = StructuredTranslator(
        PerSourceGenerator(),
        model_id="model",
        revision="revision",
        max_retries=2,
    )

    def translate(source: str) -> tuple[str, int]:
        with translator.record_scope() as stats:
            value = translator.translate_text(source, "fa", "answer")
            return value, stats.retry_count

    with ThreadPoolExecutor(max_workers=2) as executor:
        retried = executor.submit(translate, "retry")
        clean = executor.submit(translate, "clean")

    assert retried.result() == ("translated-retry", 1)
    assert clean.result() == ("translated-clean", 0)
    assert translator.retry_count == 1


class TruncatedThenValidGenerator:
    def __init__(self) -> None:
        self.calls = 0

    def generate(self, messages: Sequence[dict[str, str]]) -> str:
        self.calls += 1
        if self.calls == 1:
            raise GenerationResponseError("truncated")
        return '{"translation":"answer"}'


def test_invalid_endpoint_response_is_retried_under_the_same_contract() -> None:
    generator = TruncatedThenValidGenerator()
    translator = StructuredTranslator(
        generator,
        model_id="model",
        revision="revision",
        max_retries=2,
    )

    with translator.record_scope() as stats:
        assert translator.translate_text("source", "fa", "answer") == "answer"

    assert generator.calls == 2
    assert stats.retry_count == 1
