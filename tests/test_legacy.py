import json
from pathlib import Path

import pytest

from xhotpotqa.data.io import read_jsonl
from xhotpotqa.data.legacy import (
    CANONICAL_OUTPUT_NAME,
    LEGACY_TRAIN_LANGUAGE_NAMES,
    QUARANTINE_MANIFEST_NAME,
    RAW_MANIFEST_NAME,
    LegacyContractError,
    import_legacy_shards,
)


def _write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def _source() -> list[dict[str, object]]:
    return [
        {
            "_id": "source-1",
            "question": "source question",
            "answer": "source answer",
            "type": "bridge",
            "level": "hard",
            "supporting_facts": [["Title A", 0], ["Title B", 0]],
            "context": [["Title A", ["Sentence A."]], ["Title B", ["Sentence B."]]],
        }
    ]


def _legacy_payload(rows: list[dict[str, object]]) -> dict[str, dict[str, object]]:
    return {
        column: {str(index): row[column] for index, row in enumerate(rows)}
        for column in (
            "translate_context",
            "translate_question",
            "translate_answer",
            "target_language",
        )
    }


def _valid_row(target_language: str = "Persian") -> dict[str, object]:
    return {
        "translate_context": [
            ["عنوان الف", ["جمله الف."], "Persian"],
            ["タイトルB", ["文B。"], "Japanese"],
        ],
        "translate_question": "پرسش",
        "translate_answer": "پاسخ",
        "target_language": target_language,
    }


def test_validation_import_materializes_ids_and_manifest(tmp_path: Path) -> None:
    source = tmp_path / "source.json"
    shard = tmp_path / "validation.json"
    output = tmp_path / "imported"
    _write_json(source, _source())
    _write_json(shard, _legacy_payload([_valid_row()]))

    report = import_legacy_shards(
        [shard],
        source,
        output,
        "validation",
        backend="stdlib",
        expected_source_count=1,
    )

    assert report.imported_records == 1
    assert report.quarantined_records == 0
    [record] = list(read_jsonl(output / CANONICAL_OUTPUT_NAME))
    assert record["id"] == "xhp-validation-source-1"
    assert record["source_id"] == "source-1"
    assert record["question_language"] == "fa"
    assert [candidate["language"] for candidate in record["candidates"]] == ["fa", "ja"]
    manifest = json.loads((output / RAW_MANIFEST_NAME).read_text(encoding="utf-8"))
    assert manifest["status"] == "complete"
    assert manifest["join_contract"]["mode"] == "ordered-source-join"


def test_invalid_sentence_alignment_is_quarantined(tmp_path: Path) -> None:
    source = tmp_path / "source.json"
    shard = tmp_path / "validation.json"
    output = tmp_path / "imported"
    row = _valid_row()
    row["translate_context"] = [
        ["عنوان الف", [], "Persian"],
        ["タイトルB", ["文B。"], "Japanese"],
    ]
    _write_json(source, _source())
    _write_json(shard, _legacy_payload([row]))

    report = import_legacy_shards(
        [shard], source, output, "validation", backend="stdlib", expected_source_count=1
    )

    assert report.imported_records == 0
    assert report.quarantined_records == 1
    [quarantine] = list(read_jsonl(output / QUARANTINE_MANIFEST_NAME))
    issue_codes = {issue["code"] for issue in quarantine["issues"]}
    assert "sentence_cardinality_mismatch" in issue_codes
    assert "supporting_fact_out_of_bounds" in issue_codes


def test_train_import_requires_and_accepts_exact_parallel_language_order(tmp_path: Path) -> None:
    source = tmp_path / "source.json"
    shard = tmp_path / "train.json"
    output = tmp_path / "imported"
    _write_json(source, _source())
    rows = [_valid_row(language) for language in LEGACY_TRAIN_LANGUAGE_NAMES]
    _write_json(shard, _legacy_payload(rows))

    report = import_legacy_shards(
        [shard], source, output, "train", backend="stdlib", expected_source_count=1
    )

    assert report.source_records == 1
    assert report.raw_rows == 24
    assert report.imported_records == 24
    records = list(read_jsonl(output / CANONICAL_OUTPUT_NAME))
    assert len({record["question_language"] for record in records}) == 24
    assert len({json.dumps(record["candidates"], sort_keys=True) for record in records}) == 1


def test_train_import_rejects_changed_parallel_language_order(tmp_path: Path) -> None:
    source = tmp_path / "source.json"
    shard = tmp_path / "train.json"
    _write_json(source, _source())
    rows = [_valid_row(language) for language in reversed(LEGACY_TRAIN_LANGUAGE_NAMES)]
    _write_json(shard, _legacy_payload(rows))

    with pytest.raises(LegacyContractError, match="target order"):
        import_legacy_shards(
            [shard],
            source,
            tmp_path / "imported",
            "train",
            backend="stdlib",
            expected_source_count=1,
        )
