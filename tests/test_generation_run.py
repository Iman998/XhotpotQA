import json
import time
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
from test_models import make_instance

from xhotpotqa.data.checksum import with_checksum
from xhotpotqa.data.io import canonical_json
from xhotpotqa.data.models import Provenance, XHotpotInstance
from xhotpotqa.generation.run import (
    completed_source_ids,
    generate_dataset_parallel,
    load_hotpot_records,
)


def _write(path: Path, instance: XHotpotInstance) -> None:
    path.write_text(canonical_json(instance.to_dict()) + "\n", encoding="utf-8")


def test_resume_rejects_incompatible_provenance(tmp_path: Path) -> None:
    instance = with_checksum(
        replace(
            make_instance(),
            provenance=Provenance(
                assignment_version="sha256-hash-v1",
                assignment_manifest_sha256="a" * 64,
                seed=42,
                translation_model="model-a",
                translation_revision="rev-a",
                prompt_version="prompt-a",
                prompt_hash="hash-a",
                decoding={"temperature": 0.0},
            ),
        )
    )
    output = tmp_path / "validation.jsonl"
    _write(output, instance)

    with pytest.raises(ValueError, match="incompatible provenance"):
        completed_source_ids(
            output,
            expected_split="validation",
            expected_signature={"assignment_manifest_sha256": "b" * 64},
        )


def test_resume_accepts_matching_provenance(tmp_path: Path) -> None:
    instance = with_checksum(make_instance())
    output = tmp_path / "validation.jsonl"
    _write(output, instance)

    assert completed_source_ids(output, expected_split="validation") == {"1"}


class FakeBuilder:
    resume_signature: dict[str, object] = {}

    def __init__(self, *, failed: set[str] | None = None) -> None:
        self.failed = failed or set()

    def build(self, source: dict[str, Any], split: str) -> XHotpotInstance:
        source_id = str(source["_id"])
        time.sleep(float(source.get("delay", 0.0)))
        if source_id in self.failed:
            raise RuntimeError(f"endpoint failed for {source_id}")
        return with_checksum(
            replace(
                make_instance(),
                id=f"xhp-{split}-{source_id}",
                source_id=source_id,
                source_split=split,
            )
        )


def _source(source_id: str, *, delay: float = 0.0) -> dict[str, Any]:
    return {"_id": source_id, "delay": delay}


def test_parallel_generation_is_bounded_and_writes_input_order(tmp_path: Path) -> None:
    output = tmp_path / "validation.jsonl"
    sources = [_source("slow", delay=0.03), _source("fast"), _source("last")]

    report = generate_dataset_parallel(
        sources,
        output,
        "validation",
        FakeBuilder(),
        max_workers=2,
        progress=False,
    )

    rows = [json.loads(line) for line in output.read_text(encoding="utf-8").splitlines()]
    assert [row["source_id"] for row in rows] == ["slow", "fast", "last"]
    assert report.complete
    assert report.written == 3
    assert report.failed == 0
    assert not output.with_name(output.name + ".lock").exists()


def test_resume_reconciles_failures_instead_of_accumulating_stale_errors(
    tmp_path: Path,
) -> None:
    output = tmp_path / "validation.jsonl"
    sources = [_source("a"), _source("b"), _source("c")]

    failed = generate_dataset_parallel(
        sources,
        output,
        "validation",
        FakeBuilder(failed={"b"}),
        max_workers=2,
        progress=False,
    )
    error_path = output.with_suffix(output.suffix + ".errors.jsonl")
    errors = [json.loads(line) for line in error_path.read_text(encoding="utf-8").splitlines()]

    assert not failed.complete
    assert failed.failed == 1
    assert errors == [
        {
            "code": "generation_exception",
            "error_type": "RuntimeError",
            "message": "endpoint failed for b",
            "origin": "execution",
            "source_id": "b",
        }
    ]

    recovered = generate_dataset_parallel(
        sources,
        output,
        "validation",
        FakeBuilder(),
        max_workers=2,
        progress=False,
    )

    assert recovered.complete
    assert recovered.already_completed == 2
    assert recovered.written == 1
    assert error_path.read_text(encoding="utf-8") == ""
    assert completed_source_ids(output, expected_split="validation") == {"a", "b", "c"}


def test_generation_refuses_a_second_writer_for_the_same_output(tmp_path: Path) -> None:
    output = tmp_path / "validation.jsonl"
    lock = output.with_name(output.name + ".lock")
    lock.write_text("pid=123\n", encoding="utf-8")

    with pytest.raises(RuntimeError, match="already locked"):
        generate_dataset_parallel(
            [_source("a")],
            output,
            "validation",
            FakeBuilder(),
            progress=False,
        )


def test_train_difficulty_filter_is_never_implicit(tmp_path: Path) -> None:
    path = tmp_path / "hotpot.json"
    path.write_text(
        json.dumps(
            [
                {"_id": "easy", "level": "easy"},
                {"_id": "hard", "level": "hard"},
            ]
        ),
        encoding="utf-8",
    )

    assert [row["_id"] for row in load_hotpot_records(path, "train")] == ["easy", "hard"]
    assert [row["_id"] for row in load_hotpot_records(path, "train", difficulty="hard")] == ["hard"]
