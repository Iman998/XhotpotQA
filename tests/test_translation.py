from collections.abc import Sequence

from xhotpotqa.generation.translation import StructuredTranslator


class SequenceGenerator:
    def __init__(self, responses: Sequence[str]) -> None:
        self.responses = list(responses)
        self.calls = 0

    def generate(self, messages: Sequence[dict[str, str]]) -> str:
        self.calls += 1
        return self.responses.pop(0)


def test_schema_error_is_retried_not_just_invalid_json() -> None:
    generator = SequenceGenerator(['{"wrong_key":"value"}', '{"translation":" پاسخ "}'])
    translator = StructuredTranslator(
        generator, model_id="model", revision="revision", max_retries=2
    )

    assert translator.translate_text("answer", "fa", "answer") == "پاسخ"
    assert generator.calls == 2
    assert translator.retry_count == 1


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
