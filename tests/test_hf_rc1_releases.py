"""Publication-contract tests for the locked V2/judge RC1 builder."""

from __future__ import annotations

import importlib.util
import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
BUILDER_PATH = ROOT / "scripts" / "build_hf_rc1_releases.py"
SPEC = importlib.util.spec_from_file_location("xhotpotqa_hf_rc1_builder", BUILDER_PATH)
assert SPEC is not None and SPEC.loader is not None
builder = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = builder
SPEC.loader.exec_module(builder)


def _judge_row(
    *,
    instance_id: str = "instance-1",
    language: str = "fa",
    unit: str = "paragraph",
    score: int = 97,
    visible: str = "Faithful and fluent.\nSCORE: 97",
    reasoning: str = "private trace",
) -> dict[str, object]:
    return {
        "instance_id": instance_id,
        "source_id": f"source-{instance_id}",
        "source_split": "validation",
        "language": language,
        "unit": unit,
        "paragraph_id": "p00" if unit == "paragraph" else None,
        "source_text": "English source",
        "candidate_text": "Translated candidate",
        "score": score,
        "judge_text": visible,
        "reasoning": reasoning,
        "error": None,
    }


def test_locked_input_contract_and_expected_counts() -> None:
    assert builder.EXPECTED_SOURCE_COUNTS == {"train": 15_661, "validation": 7_405}
    assert builder.EXPECTED_V2_COUNTS == {"train": 15_433, "validation": 7_403}
    assert builder.EXPECTED_DISCARDED_V2_MIXED_ANSWERS == 240
    assert sum(builder.EXPECTED_SOURCE_COUNTS.values()) == 23_066
    assert sum(builder.EXPECTED_V2_COUNTS.values()) == 22_836
    assert builder.INPUT_LOCKS["v2_train"].sha256 == (
        "dd1d5bb5950cfe3ca5d013685f9d6e71d1059bde0e5a316462e26a546d491270"
    )
    assert builder.INPUT_LOCKS["judge_v1"].size == 13_366_284
    assert len(builder.INPUT_LOCKS) == 9


def test_input_lock_fails_closed(tmp_path: Path) -> None:
    candidate = tmp_path / "sample.jsonl"
    candidate.write_text("{}\n", encoding="utf-8")
    lock = builder.InputLock(candidate.name, candidate.stat().st_size, "0" * 64)
    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        builder.assert_locked_input(candidate, lock)


def test_sanitized_judge_row_omits_private_and_raw_fields() -> None:
    clean = builder.sanitize_judge_row(
        _judge_row(),
        dataset_version="v2_audited_rc1",
        dataset_revision="revision",
        dataset_revision_status="locked",
        run_group="test",
        raw_artifact_sha256="a" * 64,
        raw_line_number=1,
    )
    assert clean["score_origin"] == "visible_explicit"
    assert clean["judge_explanation"] == "Faithful and fluent."
    assert clean["resolved_judge_revision"] is None
    for forbidden in (
        "reasoning",
        "reasoning_content",
        "source_text",
        "candidate_text",
        "judge_text",
        "error",
        "base_url",
        "api_key",
    ):
        assert forbidden not in clean


def test_reasoning_fallback_is_labeled_without_releasing_trace() -> None:
    row = _judge_row(score=88, visible="", reasoning="Internal analysis ending in 88")
    clean = builder.sanitize_judge_row(
        row,
        dataset_version="v1_audited",
        dataset_revision="revision",
        dataset_revision_status="retrospective",
        run_group="test",
        raw_artifact_sha256="b" * 64,
        raw_line_number=2,
    )
    assert clean["score_origin"] == "reasoning_integer_fallback"
    assert clean["judge_explanation"] == ""
    assert clean["judge_explanation_available"] is False
    assert "reasoning" not in clean


def test_v2_normalization_adds_source_fields_and_exact_flags() -> None:
    source = {
        "source_id": "source-1",
        "question": "Who wrote it?",
        "answer": "Ada",
        "question_type": "bridge",
        "difficulty": "hard",
        "context": [{"paragraph_id": "p00", "title": "Ada", "sentences": ["Ada wrote it."]}],
        "supporting_facts": [{"title": "Ada", "sentence_id": 0}],
    }
    raw: dict[str, object] = {
        "id": "x-1",
        "source_id": "source-1",
        "source_split": "validation",
        "question": "Who wrote it?",
        "answer": "Ada",
        "question_language": "fa",
        "answer_language": "fa",
        "question_type": "bridge",
        "difficulty": "hard",
        "candidates": [
            {
                "id": "p00",
                "source_title": "Ada",
                "source_sentences": ["Ada wrote it."],
                "title": "آدا",
                "sentences": ["Ada wrote it."],
                "language": "fa",
            }
        ],
        "supporting_facts": [{"paragraph_id": "p00", "sentence_id": 0}],
        "provenance": {
            "translation_model": "gemma-4-31B-it",
            "translation_revision": "gemma-4-31B-it-vllm-v0.19.1",
            "prompt_version": "xhotpotqa-translation-v2.0",
            "prompt_hash": "c" * 64,
            "assignment_version": "sha256-hash-v1",
            "assignment_manifest_sha256": "",
            "seed": 20260810,
            "decoding": {"temperature": 0.0},
            "created_at": "2026-08-12T00:00:00+00:00",
            "retry_count": 5,
            "validation_status": "structural-passed",
            "schema_version": "xhotpotqa-record-v2",
        },
        "checksum": "",
    }
    raw["checksum"] = builder.input_semantic_checksum(raw)
    normalized = builder.normalize_v2_record(
        raw,
        split="validation",
        source_position=0,
        source=source,
        source_checksum=builder.sha256_text(builder.canonical_json(source)),
    )
    assert normalized["input_checksum_valid"] is True
    assert normalized["source_question"] == "Who wrote it?"
    assert normalized["source_answer"] == "Ada"
    assert normalized["candidates"][0]["source_sentences"] == ["Ada wrote it."]
    assert normalized["status"] == "review_required"
    assert normalized["structural_flags"] == []
    assert normalized["quality_flags"] == [
        "provenance:assignment_manifest_hash_missing",
        "xhotpot:answer_source_copy",
        "xhotpot:paragraph_sentence_source_copy",
        "xhotpot:question_source_copy",
    ]
    assert re.fullmatch(r"[0-9a-f]{64}", normalized["release_record_sha256"])


def test_judge_schema_and_balance_contract() -> None:
    names = set(builder.JUDGE_SCHEMA.names)
    assert {"score_origin", "source_text_sha256", "candidate_text_sha256"} <= names
    assert not {"reasoning", "source_text", "candidate_text", "api_key"} & names
    records: list[dict[str, object]] = []
    for language in builder.EXPECTED_TARGET_LANGUAGES:
        for unit, count in (("paragraph", 80), ("question", 20), ("answer", 20)):
            for index in range(count):
                records.append(
                    {
                        "judge_record_id": f"{language}-{unit}-{index}",
                        "target_language": language,
                        "unit": unit,
                    }
                )
    builder.validate_judge_records(records)


@pytest.mark.parametrize(
    "relative_path,required_text",
    [
        ("dataset_cards/v2/README.md", "22,836"),
        ("dataset_cards/judge_v1/README.md", "90.913"),
        ("dataset_cards/judge_v2/README.md", "94.468"),
    ],
)
def test_cards_are_hf_ready_without_broken_math_or_secrets(
    relative_path: str, required_text: str
) -> None:
    text = (ROOT / relative_path).read_text(encoding="utf-8")
    assert text.startswith("---\n")
    assert "configs:" in text
    assert required_text in text
    assert "$$" not in text
    assert "\\[" not in text
    assert "\\]" not in text
    assert not re.search(r"(?:github_pat_|hf_)[A-Za-z0-9_\-]{12,}", text)
    assert not re.search(r"sk-[A-Za-z0-9_\-]{16,}", text)
    assert "boof-ai" not in text.lower()


def test_public_release_sources_contain_no_embedded_credentials() -> None:
    paths = [BUILDER_PATH, *sorted((ROOT / "dataset_cards").glob("*/README.md"))]
    patterns = (
        re.compile(r"github_pat_[A-Za-z0-9_\-]+"),
        re.compile(r"hf_[A-Za-z0-9_\-]{16,}"),
        re.compile(r"sk-[A-Za-z0-9_\-]{16,}"),
    )
    for path in paths:
        text = path.read_text(encoding="utf-8")
        assert all(pattern.search(text) is None for pattern in patterns), path


def test_missing_manifest_reason_taxonomy() -> None:
    assert builder._missing_reason(None) == "absent_without_final_error_record"
    assert builder._missing_reason("Candidate has empty sentence content") == (
        "inherited_source_empty_sentence"
    )
    assert builder._missing_reason("Supporting sentence 2 is outside p04") == (
        "inherited_source_support_index_out_of_range"
    )


def test_manifest_fingerprint_ignores_only_its_own_field() -> None:
    manifest = {"rows": 2_760, "release_fingerprint_sha256": "old"}
    expected = builder.sha256_text(builder.canonical_json({"rows": 2_760}))
    assert builder._manifest_fingerprint(manifest) == expected


def test_json_fixture_is_canonical() -> None:
    assert builder.canonical_json(json.loads('{"b": 2, "a": 1}')) == '{"a":1,"b":2}'
