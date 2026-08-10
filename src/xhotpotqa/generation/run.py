"""Resumable dataset-generation orchestration."""

from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from xhotpotqa.data.io import canonical_json, read_jsonl
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


def completed_source_ids(path: Path) -> set[str]:
    if not path.exists():
        return set()
    completed: set[str] = set()
    for item in read_jsonl(path):
        source_id = item.get("source_id")
        if not isinstance(source_id, str) or not source_id:
            raise ValueError(f"Existing output {path} contains an invalid source_id")
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
    completed = completed_source_ids(output_path)
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
