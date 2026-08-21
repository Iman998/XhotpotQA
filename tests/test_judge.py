import json
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest
from test_models import make_instance

from xhotpotqa.data.models import CandidateParagraph
from xhotpotqa.evaluation.judge import (
    JUDGE_PROMPT_HASH,
    JUDGE_PROMPT_VERSION,
    LEGACY_JUDGE_PROMPT_HASH,
    JudgeConfig,
    JudgeRecord,
    JudgeResult,
    SourceRecord,
    TranslationJudge,
    _parse_judge_response,
    load_source_records,
    run_judge,
    sample_units,
)


def _instance(index: int, language: str = "fa"):
    base = make_instance()
    return replace(
        base,
        id=f"xhp-validation-{index}",
        source_id=str(index),
        question=f"question-{index}",
        answer=f"answer-{index}",
        question_language=language,
        answer_language=language,
        candidates=(
            CandidateParagraph(
                id="p00",
                title=f"title-{index}",
                sentences=(f"translated paragraph {index}",),
                language=language,
                source_title=f"source-title-{index}",
                source_sentences=(f"English paragraph {index}",),
            ),
        ),
    )


def _sources(count: int) -> dict[str, SourceRecord]:
    return {
        str(index): SourceRecord(
            source_id=str(index),
            split="validation",
            question=f"English question {index}",
            answer=f"English answer {index}",
            context=(),
        )
        for index in range(count)
    }


def test_judge_config_rejects_embedded_credentials(tmp_path: Path) -> None:
    path = tmp_path / "judge.yaml"
    path.write_text("model_id: model\napi_key: secret-value\n", encoding="utf-8")

    with pytest.raises(ValueError, match="Invalid judge configuration"):
        JudgeConfig.from_yaml(path)


def test_source_loader_returns_typed_records_and_rejects_duplicate_ids(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.json"
    source.write_text(
        json.dumps(
            [
                {
                    "_id": "one",
                    "question": "Who?",
                    "answer": "Ada",
                    "context": [["Ada", ["Ada wrote it."]]],
                }
            ]
        ),
        encoding="utf-8",
    )

    records = load_source_records({"validation": source})

    assert records["one"].question == "Who?"
    assert records["one"].context[0].sentences == ("Ada wrote it.",)
    with pytest.raises(ValueError, match="Duplicate source_id"):
        load_source_records({"train": source, "validation": source})


def test_language_balanced_sample_is_order_invariant_and_pairs_questions_answers() -> None:
    instances = [_instance(index) for index in range(8)]
    sources = _sources(8)

    forward = sample_units(
        instances,
        sources,
        paragraph_per_language=3,
        question_per_language=2,
        answer_per_language=2,
        seed=42,
    )
    reverse = sample_units(
        reversed(instances),
        sources,
        paragraph_per_language=3,
        question_per_language=2,
        answer_per_language=2,
        seed=42,
    )

    assert [record.record_id for record in forward] == [record.record_id for record in reverse]
    assert [record.unit for record in forward].count("paragraph") == 3
    questions = {record.source_id for record in forward if record.unit == "question"}
    answers = {record.source_id for record in forward if record.unit == "answer"}
    assert questions == answers


class SequenceClient:
    def __init__(self, responses: list[str]) -> None:
        self.responses = responses
        self.requests: list[dict[str, object]] = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))

    def create(self, **request):
        self.requests.append(request)
        content = self.responses.pop(0)
        message = SimpleNamespace(content=content, reasoning="must-not-be-read")
        return SimpleNamespace(choices=[SimpleNamespace(message=message)])


def test_judge_requires_strict_json_and_never_captures_hidden_reasoning() -> None:
    client = SequenceClient(
        [
            "SCORE: 99",
            '{"score":91,"rationale":"Faithful.","error_tags":[]}',
        ]
    )
    config = JudgeConfig(model_id="served-model", response_max_attempts=2)
    judge = TranslationJudge(config, client=client)
    record = JudgeRecord(
        instance_id="instance",
        source_id="source",
        source_split="validation",
        language="fa",
        unit="question",
        source_text="Who?",
        candidate_text="translated",
    )

    result = judge.judge(record)

    assert result.score == 91
    assert result.rationale == "Faithful."
    assert result.attempts == 2
    assert client.requests[-1]["response_format"] == {"type": "json_object"}
    assert "must-not-be-read" not in result.raw_response


class FixedJudge:
    def __init__(self) -> None:
        self.calls = 0

    def judge(self, record: JudgeRecord) -> JudgeResult:
        self.calls += 1
        return JudgeResult(record=record, score=95, rationale="Faithful.")


def test_run_judge_replays_manifest_and_resumes_without_duplicate_calls(
    tmp_path: Path,
) -> None:
    config = JudgeConfig(
        model_id="served-model",
        paragraph_sample_per_language=1,
        question_sample_per_language=1,
        answer_sample_per_language=1,
    )
    output = tmp_path / "judge"
    fixed = FixedJudge()

    first = run_judge(
        [_instance(0)],
        config,
        source_records=_sources(1),
        output_path=output,
        progress=False,
        judge=fixed,  # type: ignore[arg-type]
    )
    second = run_judge(
        [_instance(0)],
        config,
        source_records=_sources(1),
        output_path=output,
        progress=False,
        judge=fixed,  # type: ignore[arg-type]
    )

    rows = [
        json.loads(line)
        for line in (tmp_path / "judge.records.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert first.total_units == second.total_units == 3
    assert fixed.calls == 3
    assert len(rows) == 3
    assert all(row["prompt_hash"] == JUDGE_PROMPT_HASH for row in rows)
    assert all("reasoning" not in row for row in rows)
    assert (tmp_path / "judge.sample.jsonl").exists()


def test_prompt_identities_are_explicit_and_hash_shaped() -> None:
    assert JUDGE_PROMPT_VERSION == "xhotpotqa-translation-judge-v2.0"
    assert JUDGE_PROMPT_HASH == "8441dfa2f45abd4d07c1e4113f52c6513ba9bc4b0ae0942c5cf1918a0ee03a00"
    assert (
        LEGACY_JUDGE_PROMPT_HASH
        == "ccd5adc8d265e396f584c4a55d93a2546641439cd370ba1678056f654f8769a0"
    )


def test_duplicate_json_keys_are_rejected() -> None:
    with pytest.raises(ValueError, match="Duplicate JSON key"):
        _parse_judge_response('{"score":1,"score":2,"rationale":"ok","error_tags":[]}')
