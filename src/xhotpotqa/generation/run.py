"""Resumable dataset-generation orchestration."""

from __future__ import annotations

import json
import threading
from collections.abc import Iterable
from concurrent.futures import ThreadPoolExecutor, as_completed
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


def generate_dataset_parallel(
    source_records: Iterable[dict[str, Any]],
    output_path: Path,
    split: str,
    builder: XHotpotBuilder,
    *,
    max_workers: int = 128,
    checkpoint_every: int = 1,
    progress: bool = True,
) -> int:
    """Concurrent variant of :func:`generate_dataset`.

    Source records are built in parallel by a thread pool; each worker performs
    its own translation API calls. Completed instances are appended to the output
    JSONL under a write lock, so the on-disk ordering reflects completion order
    rather than input order. Resume semantics (by immutable source ID), provenance
    signature checks, and checksum validation are identical to the sequential path.
    """
    if checkpoint_every < 1:
        raise ValueError("checkpoint_every must be greater than zero")
    if max_workers < 1:
        raise ValueError("max_workers must be greater than zero")
    completed = completed_source_ids(
        output_path,
        expected_split=split,
        expected_signature=builder.resume_signature,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)

    write_lock = threading.Lock()
    seen_input: set[str] = set()
    pending: list[dict[str, Any]] = []
    for source in source_records:
        source_id = str(source.get("_id", source.get("id", "")))
        if not source_id:
            raise ValueError("HotpotQA source record is missing _id/id")
        if source_id in seen_input:
            raise ValueError(f"Duplicate source ID in input: {source_id!r}")
        seen_input.add(source_id)
        if source_id in completed:
            continue
        pending.append(source)

    written = 0
    failed = 0
    progress_bar = None
    if progress:
        try:
            from tqdm.auto import tqdm

            progress_bar = tqdm(
                total=len(pending), desc="generate-v2", unit="rec", dynamic_ncols=True
            )
        except ImportError:
            progress_bar = None

    def _work(source: dict[str, Any]) -> str:
        instance = builder.build(source, split)
        return canonical_json(instance.to_dict())

    errors_path = output_path.with_suffix(output_path.suffix + ".errors.jsonl")
    with output_path.open("a", encoding="utf-8", newline="\n") as stream, \
         errors_path.open("a", encoding="utf-8", newline="\n") as err_stream:
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_source = {
                executor.submit(_work, source): str(source.get("_id", source.get("id", "")))
                for source in pending
            }
            for future in as_completed(future_to_source):
                source_id = future_to_source[future]
                try:
                    line = future.result()
                except Exception as error:
                    with write_lock:
                        err_stream.write(
                            json.dumps(
                                {"source_id": source_id, "error": str(error)},
                                ensure_ascii=False,
                            )
                            + "\n"
                        )
                        err_stream.flush()
                        failed += 1
                    if progress_bar is not None:
                        progress_bar.update(1)
                    continue
                with write_lock:
                    stream.write(line + "\n")
                    completed.add(source_id)
                    written += 1
                    if written % checkpoint_every == 0:
                        stream.flush()
                if progress_bar is not None:
                    progress_bar.update(1)

    if progress_bar is not None:
        progress_bar.close()
    if failed:
        import sys
        print(f"WARNING: {failed} record(s) failed and were skipped; see {errors_path}", file=sys.stderr)
    return written
