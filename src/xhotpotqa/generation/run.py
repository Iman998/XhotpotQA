"""Resumable dataset-generation orchestration."""

from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from xhotpotqa.data.checksum import compute_checksum
from xhotpotqa.data.io import canonical_json, read_jsonl
from xhotpotqa.data.models import XHotpotInstance
from xhotpotqa.generation.pipeline import XHotpotBuilder


def load_hotpot_records(path: Path, split: str) -> Iterable[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("Expected the official HotpotQA JSON array")
    for item in payload:
        if not isinstance(item, dict):
            raise ValueError("HotpotQA array contains a non-object record")
        if split == "train" and item.get("level") != "hard":
            continue
        yield item


def completed_source_ids(
    path: Path,
    *,
    expected_split: str | None = None,
    expected_signature: dict[str, object] | None = None,
) -> set[str]:
    if not path.exists():
        return set()
    completed: set[str] = set()
    for item in read_jsonl(path):
        instance = XHotpotInstance.from_dict(item)
        instance.validate()
        source_id = instance.source_id
        if not instance.checksum or compute_checksum(instance) != instance.checksum:
            raise ValueError(f"Existing output {path} contains an invalid checksum")
        if expected_split is not None and instance.source_split != expected_split:
            raise ValueError(
                f"Existing output {path} mixes split {instance.source_split!r} "
                f"with requested split {expected_split!r}"
            )
        if expected_signature is not None:
            provenance = instance.provenance
            for key, expected in expected_signature.items():
                actual = getattr(provenance, key)
                if key == "decoding":
                    actual = dict(actual)
                if actual != expected:
                    raise ValueError(
                        f"Existing output {path} has incompatible provenance for {key}: "
                        f"{actual!r} != {expected!r}"
                    )
        if source_id in completed:
            raise ValueError(f"Existing output {path} contains duplicate source_id {source_id!r}")
        completed.add(source_id)
    return completed


def generate_dataset(
    source_records: Iterable[dict[str, Any]],
    output_path: Path,
    split: str,
    builder: XHotpotBuilder,
    *,
    checkpoint_every: int = 1,
) -> int:
    if checkpoint_every < 1:
        raise ValueError("checkpoint_every must be greater than zero")
    completed = completed_source_ids(
        output_path,
        expected_split=split,
        expected_signature=builder.resume_signature,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    written = 0
    seen_input: set[str] = set()
    with output_path.open("a", encoding="utf-8", newline="\n") as stream:
        for source in source_records:
            source_id = str(source.get("_id", source.get("id", "")))
            if not source_id:
                raise ValueError("HotpotQA source record is missing _id/id")
            if source_id in seen_input:
                raise ValueError(f"Duplicate source ID in input: {source_id!r}")
            seen_input.add(source_id)
            if source_id in completed:
                continue
            instance = builder.build(source, split)
            stream.write(canonical_json(instance.to_dict()) + "\n")
            completed.add(source_id)
            written += 1
            if written % checkpoint_every == 0:
                stream.flush()
    return written
