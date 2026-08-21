"""Deterministic, resumable dataset-generation orchestration."""

from __future__ import annotations

import json
import os
import re
from collections import deque
from collections.abc import Iterable, Iterator
from concurrent.futures import Future, ThreadPoolExecutor
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

from xhotpotqa.data.checksum import compute_checksum
from xhotpotqa.data.io import canonical_json, read_jsonl
from xhotpotqa.data.models import XHotpotInstance
from xhotpotqa.generation.pipeline import XHotpotBuilder
from xhotpotqa.generation.translation import TranslationResponseError

_SECRET = re.compile(
    r"(?:hf_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|"
    r"gh[pousr]_[A-Za-z0-9]{20,}|sk-[A-Za-z0-9_-]{20,})"
)


@dataclass(frozen=True, slots=True)
class GenerationReport:
    """Machine-readable outcome of one generation or resume operation."""

    input_records: int
    already_completed: int
    attempted: int
    written: int
    failed: int
    output_records: int
    error_records: int

    @property
    def complete(self) -> bool:
        return self.already_completed + self.written == self.input_records and self.failed == 0


def load_hotpot_records(
    path: Path,
    split: str,
    *,
    difficulty: str | None = None,
) -> Iterable[dict[str, Any]]:
    """Load official HotpotQA records with an explicit optional difficulty filter."""
    if split not in {"train", "validation"}:
        raise ValueError("split must be 'train' or 'validation'")
    if difficulty not in {None, "easy", "medium", "hard"}:
        raise ValueError("difficulty must be easy, medium, hard, or omitted")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("Expected the official HotpotQA JSON array")
    for item in payload:
        if not isinstance(item, dict):
            raise ValueError("HotpotQA array contains a non-object record")
        if difficulty is not None and item.get("level") != difficulty:
            continue
        yield item


def completed_source_ids(
    path: Path,
    *,
    expected_split: str | None = None,
    expected_signature: dict[str, object] | None = None,
) -> set[str]:
    """Validate an existing output and return its immutable source IDs."""
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
) -> GenerationReport:
    """Generate records sequentially with the same failure contract as parallel mode."""
    return _generate_dataset(
        source_records,
        output_path,
        split,
        builder,
        max_workers=1,
        checkpoint_every=checkpoint_every,
        progress=False,
    )


def generate_dataset_parallel(
    source_records: Iterable[dict[str, Any]],
    output_path: Path,
    split: str,
    builder: XHotpotBuilder,
    *,
    max_workers: int = 8,
    checkpoint_every: int = 1,
    progress: bool = True,
) -> GenerationReport:
    """Generate concurrently while writing results in deterministic input order.

    At most ``2 * max_workers`` futures exist at once. An exclusive sidecar lock
    prevents two processes from mutating the same output. Failures are reconciled
    into one atomically replaced JSONL ledger rather than accumulated indefinitely.
    """
    return _generate_dataset(
        source_records,
        output_path,
        split,
        builder,
        max_workers=max_workers,
        checkpoint_every=checkpoint_every,
        progress=progress,
    )


def _generate_dataset(
    source_records: Iterable[dict[str, Any]],
    output_path: Path,
    split: str,
    builder: XHotpotBuilder,
    *,
    max_workers: int,
    checkpoint_every: int,
    progress: bool,
) -> GenerationReport:
    if checkpoint_every < 1:
        raise ValueError("checkpoint_every must be greater than zero")
    if max_workers < 1:
        raise ValueError("max_workers must be greater than zero")
    sources = _validated_sources(source_records)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    errors_path = output_path.with_suffix(output_path.suffix + ".errors.jsonl")

    with _exclusive_output_lock(output_path):
        completed = completed_source_ids(
            output_path,
            expected_split=split,
            expected_signature=builder.resume_signature,
        )
        input_ids = {_source_id(source) for source in sources}
        unexpected = completed - input_ids
        if unexpected:
            example = sorted(unexpected)[0]
            raise ValueError(
                f"Existing output contains source_id {example!r}, which is absent from the "
                "current input selection; use a different output path"
            )
        already_completed = len(completed & input_ids)
        pending = [source for source in sources if _source_id(source) not in completed]
        errors = _load_error_ledger(errors_path)
        for source_id in completed:
            errors.pop(source_id, None)

        progress_bar = _progress_bar(len(pending), progress)
        written = failed = 0
        try:
            with output_path.open("a", encoding="utf-8", newline="\n") as stream:
                for source_id, instance, error in _build_in_order(
                    pending,
                    split,
                    builder,
                    max_workers=max_workers,
                ):
                    if error is not None:
                        errors[source_id] = _error_record(source_id, error)
                        failed += 1
                    else:
                        assert instance is not None
                        stream.write(canonical_json(instance.to_dict()) + "\n")
                        errors.pop(source_id, None)
                        completed.add(source_id)
                        written += 1
                        if written % checkpoint_every == 0:
                            stream.flush()
                    if progress_bar is not None:
                        progress_bar.update(1)
                stream.flush()
                os.fsync(stream.fileno())
        finally:
            if progress_bar is not None:
                progress_bar.close()
            _write_error_ledger(errors_path, errors)

    return GenerationReport(
        input_records=len(sources),
        already_completed=already_completed,
        attempted=len(pending),
        written=written,
        failed=failed,
        output_records=len(completed),
        error_records=len(errors),
    )


def _validated_sources(
    source_records: Iterable[dict[str, Any]],
) -> list[dict[str, Any]]:
    sources: list[dict[str, Any]] = []
    seen: set[str] = set()
    for source in source_records:
        source_id = _source_id(source)
        if source_id in seen:
            raise ValueError(f"Duplicate source ID in input: {source_id!r}")
        seen.add(source_id)
        sources.append(source)
    return sources


def _source_id(source: dict[str, Any]) -> str:
    source_id = str(source.get("_id", source.get("id", "")))
    if not source_id:
        raise ValueError("HotpotQA source record is missing _id/id")
    return source_id


def _build_in_order(
    sources: list[dict[str, Any]],
    split: str,
    builder: XHotpotBuilder,
    *,
    max_workers: int,
) -> Iterator[tuple[str, XHotpotInstance | None, Exception | None]]:
    if max_workers == 1:
        for source in sources:
            source_id = _source_id(source)
            try:
                yield source_id, builder.build(source, split), None
            except Exception as error:  # noqa: BLE001 - one bad source must not abort the split
                yield source_id, None, error
        return

    source_iterator = iter(sources)
    in_flight: deque[tuple[str, Future[XHotpotInstance]]] = deque()
    capacity = max_workers * 2
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        _fill_futures(in_flight, source_iterator, executor, builder, split, capacity)
        while in_flight:
            source_id, future = in_flight.popleft()
            try:
                yield source_id, future.result(), None
            except Exception as error:  # noqa: BLE001 - persisted as a typed failure
                yield source_id, None, error
            _fill_futures(in_flight, source_iterator, executor, builder, split, capacity)


def _fill_futures(
    in_flight: deque[tuple[str, Future[XHotpotInstance]]],
    sources: Iterator[dict[str, Any]],
    executor: ThreadPoolExecutor,
    builder: XHotpotBuilder,
    split: str,
    capacity: int,
) -> None:
    while len(in_flight) < capacity:
        try:
            source = next(sources)
        except StopIteration:
            return
        source_id = _source_id(source)
        in_flight.append((source_id, executor.submit(builder.build, source, split)))


def _load_error_ledger(path: Path) -> dict[str, dict[str, object]]:
    errors: dict[str, dict[str, object]] = {}
    if not path.exists():
        return errors
    for item in read_jsonl(path):
        source_id = item.get("source_id")
        if not isinstance(source_id, str) or not source_id:
            raise ValueError(f"Invalid source_id in error ledger {path}")
        if source_id in errors:
            raise ValueError(f"Duplicate source_id {source_id!r} in error ledger {path}")
        errors[source_id] = dict(item)
    return errors


def _error_record(source_id: str, error: Exception) -> dict[str, object]:
    if isinstance(error, TranslationResponseError):
        origin = "transformation"
        code = "structured_response_exhausted"
    elif isinstance(error, ValueError) and _looks_like_source_error(str(error)):
        origin = "source"
        code = "invalid_source_annotation"
    else:
        origin = "execution"
        code = "generation_exception"
    message = _SECRET.sub("<redacted>", str(error)).replace("\r", " ").replace("\n", " ")
    return {
        "source_id": source_id,
        "origin": origin,
        "code": code,
        "error_type": type(error).__name__,
        "message": message[:500],
    }


def _looks_like_source_error(message: str) -> bool:
    prefixes = (
        "Candidate ",
        "Supporting sentence ",
        "Supporting title ",
        "HotpotQA source record ",
        "Unknown supporting paragraph",
    )
    return message.startswith(prefixes)


def _write_error_ledger(path: Path, errors: dict[str, dict[str, object]]) -> None:
    temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    try:
        with temporary.open("w", encoding="utf-8", newline="\n") as stream:
            for source_id in sorted(errors):
                stream.write(canonical_json(errors[source_id]) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


@contextmanager
def _exclusive_output_lock(path: Path) -> Iterator[None]:
    lock_path = path.with_name(path.name + ".lock")
    try:
        descriptor = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError as error:
        raise RuntimeError(
            f"Output is already locked: {path}. Remove {lock_path} only after confirming "
            "that no generation process is active."
        ) from error
    try:
        os.write(descriptor, f"pid={os.getpid()}\n".encode())
        os.close(descriptor)
        descriptor = -1
        yield
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        lock_path.unlink(missing_ok=True)


def _progress_bar(total: int, enabled: bool) -> Any | None:
    if not enabled:
        return None
    try:
        from tqdm.auto import tqdm  # type: ignore[import-untyped]
    except ImportError:
        return None
    return tqdm(total=total, desc="generate-v2", unit="rec", dynamic_ncols=True)
