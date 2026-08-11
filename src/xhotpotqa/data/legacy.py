"""Audited import of the historical pandas-column XHotpotQA shards.

The legacy files do not contain source IDs or supporting facts.  Import is
therefore only safe as an ordered join against a pinned HotpotQA JSON array.
Large inputs use the optional :mod:`ijson` backend; the stdlib fallback is
deliberately bounded so an absent optional dependency cannot silently exhaust
memory on a multi-hundred-megabyte shard.
"""

from __future__ import annotations

import hashlib
import importlib
import json
import os
import tempfile
from collections import Counter
from collections.abc import Iterator, Mapping, Sequence
from contextlib import ExitStack
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from itertools import zip_longest
from pathlib import Path
from typing import Any, Literal, cast

from xhotpotqa.data.checksum import with_checksum
from xhotpotqa.data.io import canonical_json, read_jsonl
from xhotpotqa.data.models import (
    CandidateParagraph,
    Provenance,
    SupportingFact,
    XHotpotInstance,
)
from xhotpotqa.languages import LANGUAGE_CODES, LANGUAGES

LegacyReaderBackend = Literal["auto", "ijson", "stdlib"]

LEGACY_COLUMNS = (
    "translate_context",
    "translate_question",
    "translate_answer",
    "target_language",
)
LEGACY_TRAIN_LANGUAGE_NAMES = (
    "English",
    "Mandarin Chinese",
    "Spanish",
    "Hindi",
    "Arabic",
    "French",
    "Russian",
    "Portuguese",
    "Bengali",
    "Urdu",
    "Indonesian",
    "Japanese",
    "German",
    "Swahili",
    "Turkish",
    "Vietnamese",
    "Korean",
    "Italian",
    "Persian",
    "Thai",
    "Dutch",
    "Polish",
    "Greek",
    "Swedish",
)
LEGACY_VIEWS_PER_SOURCE = {"train": len(LEGACY_TRAIN_LANGUAGE_NAMES), "validation": 1}
DEFAULT_EXPECTED_SOURCE_COUNTS = {"train": 15_661, "validation": 7_405}
MAX_STDLIB_BYTES = 128 * 1024 * 1024

CANONICAL_OUTPUT_NAME = "canonical.jsonl"
RAW_MANIFEST_NAME = "raw_manifest.json"
QUARANTINE_MANIFEST_NAME = "quarantine_manifest.jsonl"
CORRECTION_MANIFEST_NAME = "correction_manifest.jsonl"

_LANGUAGE_CODE_BY_NAME = {language.name: language.code for language in LANGUAGES}
_MISSING = object()


@dataclass(frozen=True, slots=True)
class LegacyRow:
    """One aligned row from the four legacy pandas columns."""

    shard: Path
    shard_row_index: int
    global_row_index: int
    context: object
    question: object
    answer: object
    target_language: object

    def payload(self) -> dict[str, object]:
        return {
            "translate_context": self.context,
            "translate_question": self.question,
            "translate_answer": self.answer,
            "target_language": self.target_language,
        }

    @property
    def sha256(self) -> str:
        return hashlib.sha256(canonical_json(self.payload()).encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class AuditIssue:
    code: str
    message: str


@dataclass(frozen=True, slots=True)
class Correction:
    legacy_id: str
    raw_sha256: str
    reason: str
    replacement: Mapping[str, Any]


@dataclass(frozen=True, slots=True)
class LegacyImportReport:
    output_dir: Path
    source_records: int
    raw_rows: int
    imported_records: int
    quarantined_records: int
    corrections_applied: int
    reader_backend: str


class LegacyContractError(ValueError):
    """Raised when order/cardinality no longer permits a defensible join."""


def import_legacy_shards(
    shards: Sequence[Path],
    source: Path,
    output_dir: Path,
    split: str,
    *,
    backend: LegacyReaderBackend = "auto",
    expected_source_count: int | None = None,
    expected_source_sha256: str | None = None,
    expected_source_order_sha256: str | None = None,
    corrections: Path | None = None,
) -> LegacyImportReport:
    """Audit, ordered-join, and import legacy shards into a traceable bundle.

    The bundle contains canonical accepted records plus content-addressed
    quarantine and correction manifests.  It never copies raw translated text
    into the manifests, so each issue remains traceable without duplicating the
    large historical inputs.
    """

    _validate_import_arguments(shards, source, output_dir, split, expected_source_count)
    input_paths = [source, *shards, *([corrections] if corrections is not None else [])]
    resolved_backend = _resolve_backend(input_paths, backend)
    source_sha256 = file_sha256(source)
    _require_expected_digest(source_sha256, expected_source_sha256, "source file")
    shard_metadata = [file_metadata(path) for path in shards]
    correction_metadata = file_metadata(corrections) if corrections is not None else None
    correction_map = load_corrections(corrections) if corrections is not None else {}

    parent = output_dir.parent
    parent.mkdir(parents=True, exist_ok=True)
    if output_dir.exists():
        raise FileExistsError(f"Refusing to replace existing import directory: {output_dir}")

    source_count = raw_count = imported_count = quarantined_count = applied_count = 0
    issue_counts: Counter[str] = Counter()
    seen_source_ids: set[str] = set()
    used_corrections: set[str] = set()
    source_order_digest = hashlib.sha256()

    with tempfile.TemporaryDirectory(prefix=".xhotpotqa-legacy-", dir=parent) as temporary_name:
        temporary_dir = Path(temporary_name)
        canonical_path = temporary_dir / CANONICAL_OUTPUT_NAME
        quarantine_path = temporary_dir / QUARANTINE_MANIFEST_NAME
        correction_path = temporary_dir / CORRECTION_MANIFEST_NAME

        rows = iter_legacy_rows(shards, backend=resolved_backend)
        sources = iter_hotpot_sources(source, split=split, backend=resolved_backend)
        with (
            canonical_path.open("w", encoding="utf-8", newline="\n") as canonical_stream,
            quarantine_path.open("w", encoding="utf-8", newline="\n") as quarantine_stream,
            correction_path.open("w", encoding="utf-8", newline="\n") as correction_stream,
        ):
            for source_position, source_record in enumerate(sources):
                source_id = _source_id(source_record, source_position)
                if source_id in seen_source_ids:
                    raise LegacyContractError(f"Duplicate selected source ID: {source_id!r}")
                seen_source_ids.add(source_id)
                source_count += 1
                source_order_digest.update(
                    canonical_json({"position": source_position, "source_id": source_id}).encode(
                        "utf-8"
                    )
                    + b"\n"
                )

                group = _take_source_group(rows, split=split, source_id=source_id)
                raw_count += len(group)
                ordered_group = _validate_and_order_group(group, split=split, source_id=source_id)
                for row in ordered_group:
                    legacy_id, instance, issues = _build_instance(
                        source_record,
                        row,
                        split=split,
                        source_position=source_position,
                    )
                    correction = correction_map.get(legacy_id)
                    if correction is not None:
                        used_corrections.add(legacy_id)
                        replacement, correction_issues = _apply_correction(
                            correction,
                            source_record,
                            row,
                            split=split,
                            source_position=source_position,
                            expected_id=legacy_id,
                        )
                        issues.extend(correction_issues)
                        if replacement is not None:
                            instance = replacement
                            issues = []
                            applied_count += 1
                            _write_jsonl(
                                correction_stream,
                                {
                                    "legacy_id": legacy_id,
                                    "raw_sha256": row.sha256,
                                    "status": "applied",
                                    "reason": correction.reason,
                                    "replacement_checksum": replacement.checksum,
                                },
                            )

                    if instance is not None and not issues:
                        _write_jsonl(canonical_stream, instance.to_dict())
                        imported_count += 1
                        continue

                    quarantined_count += 1
                    issue_counts.update(issue.code for issue in issues)
                    locator = _raw_locator(row)
                    issue_payload = [asdict(issue) for issue in issues]
                    _write_jsonl(
                        quarantine_stream,
                        {
                            "legacy_id": legacy_id,
                            "source_id": source_id,
                            "source_position": source_position,
                            "raw_sha256": row.sha256,
                            "raw_locator": locator,
                            "issues": issue_payload,
                        },
                    )
                    _write_jsonl(
                        correction_stream,
                        {
                            "legacy_id": legacy_id,
                            "raw_sha256": row.sha256,
                            "status": "pending",
                            "raw_locator": locator,
                            "required_for": [issue.code for issue in issues],
                            "replacement_checksum": None,
                        },
                    )

            extra_row = next(rows, None)
            if extra_row is not None:
                raise LegacyContractError(
                    "Legacy shards contain rows after the selected source sequence ended: "
                    f"{extra_row.shard.name}:{extra_row.shard_row_index}"
                )

        actual_source_order_sha256 = source_order_digest.hexdigest()
        _require_expected_digest(
            actual_source_order_sha256,
            expected_source_order_sha256,
            "selected source order",
        )
        if expected_source_count is not None and source_count != expected_source_count:
            raise LegacyContractError(
                f"Expected {expected_source_count:,} selected source records, "
                f"found {source_count:,}"
            )
        unused_corrections = sorted(set(correction_map) - used_corrections)
        if unused_corrections:
            preview = ", ".join(repr(item) for item in unused_corrections[:5])
            raise LegacyContractError(
                f"Correction entries did not match imported records: {preview}"
            )

        expected_rows = source_count * LEGACY_VIEWS_PER_SOURCE[split]
        if raw_count != expected_rows:
            raise LegacyContractError(
                f"Expected {expected_rows:,} legacy rows for {source_count:,} sources, "
                f"found {raw_count:,}"
            )

        manifest = {
            "manifest_version": "xhotpotqa-legacy-import-v1",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "status": "complete" if quarantined_count == 0 else "complete-with-quarantine",
            "split": split,
            "reader_backend": resolved_backend,
            "join_contract": {
                "mode": "ordered-source-join",
                "source_selection": "level=hard" if split == "train" else "all",
                "views_per_source": LEGACY_VIEWS_PER_SOURCE[split],
                "train_target_order": (
                    list(LEGACY_TRAIN_LANGUAGE_NAMES) if split == "train" else None
                ),
                "source_order_sha256": actual_source_order_sha256,
                "source_order_predeclared": expected_source_order_sha256 is not None,
            },
            "inputs": {
                "source": file_metadata(source),
                "shards": shard_metadata,
                "corrections": correction_metadata,
            },
            "counts": {
                "source_records": source_count,
                "raw_rows": raw_count,
                "imported_records": imported_count,
                "quarantined_records": quarantined_count,
                "corrections_applied": applied_count,
            },
            "issue_counts": dict(sorted(issue_counts.items())),
            "outputs": {
                CANONICAL_OUTPUT_NAME: file_metadata(canonical_path),
                QUARANTINE_MANIFEST_NAME: file_metadata(quarantine_path),
                CORRECTION_MANIFEST_NAME: file_metadata(correction_path),
            },
            "provenance_limitations": [
                "legacy random-assignment seed was not recorded",
                "provider-resolved translation-model revision was not recorded",
                "raw shards contain no source IDs; alignment depends on this ordered join",
                *(
                    ["historical one-view train-base selection indices were not recorded"]
                    if split == "train"
                    else ["validation contains one QA-language view per source"]
                ),
            ],
        }
        (temporary_dir / RAW_MANIFEST_NAME).write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        os.replace(temporary_dir, output_dir)

    return LegacyImportReport(
        output_dir=output_dir,
        source_records=source_count,
        raw_rows=raw_count,
        imported_records=imported_count,
        quarantined_records=quarantined_count,
        corrections_applied=applied_count,
        reader_backend=resolved_backend,
    )


def iter_legacy_rows(
    shards: Sequence[Path], *, backend: LegacyReaderBackend = "auto"
) -> Iterator[LegacyRow]:
    """Yield column-aligned legacy rows across explicitly ordered shards."""

    resolved_backend = _resolve_backend(shards, backend)
    global_index = 0
    for shard in shards:
        raw_rows = (
            _iter_legacy_rows_ijson(shard)
            if resolved_backend == "ijson"
            else _iter_legacy_rows_stdlib(shard)
        )
        for shard_index, payload in raw_rows:
            yield LegacyRow(
                shard=shard,
                shard_row_index=shard_index,
                global_row_index=global_index,
                context=payload["translate_context"],
                question=payload["translate_question"],
                answer=payload["translate_answer"],
                target_language=payload["target_language"],
            )
            global_index += 1


def iter_hotpot_sources(
    path: Path, *, split: str, backend: LegacyReaderBackend = "auto"
) -> Iterator[Mapping[str, object]]:
    """Yield the source sequence selected by the historical split contract."""

    if split not in LEGACY_VIEWS_PER_SOURCE:
        raise ValueError(f"Unsupported split: {split!r}")
    resolved_backend = _resolve_backend([path], backend)
    if resolved_backend == "ijson":
        ijson = _require_ijson()
        with path.open("rb") as stream:
            records = ijson.items(stream, "item")
            for position, raw_record in enumerate(records):
                record = _require_mapping(raw_record, f"{path}:source[{position}]")
                if split == "train" and record.get("level") != "hard":
                    continue
                yield record
        return

    try:
        payload: object = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise LegacyContractError(f"Invalid source JSON in {path}: {error}") from error
    if not isinstance(payload, list):
        raise LegacyContractError(f"Ordered source input must be a JSON array: {path}")
    for position, raw_record in enumerate(payload):
        record = _require_mapping(raw_record, f"{path}:source[{position}]")
        if split == "train" and record.get("level") != "hard":
            continue
        yield record


def load_corrections(path: Path) -> dict[str, Correction]:
    """Load full-record corrections guarded by the raw record digest."""

    corrections: dict[str, Correction] = {}
    for line_number, row in enumerate(read_jsonl(path), start=1):
        expected_fields = {"legacy_id", "raw_sha256", "reason", "replacement"}
        extra = set(row) - expected_fields
        if extra:
            raise LegacyContractError(
                f"Unexpected correction fields at {path}:{line_number}: {sorted(extra)}"
            )
        legacy_id, raw_sha256, reason = (
            row.get("legacy_id"),
            row.get("raw_sha256"),
            row.get("reason"),
        )
        replacement = row.get("replacement")
        if not isinstance(legacy_id, str) or not legacy_id:
            raise LegacyContractError(f"Invalid legacy_id at {path}:{line_number}")
        if legacy_id in corrections:
            raise LegacyContractError(f"Duplicate correction for {legacy_id!r}")
        if not _is_sha256(raw_sha256):
            raise LegacyContractError(f"Invalid raw_sha256 at {path}:{line_number}")
        if not isinstance(reason, str) or not reason.strip():
            raise LegacyContractError(f"Correction reason is required at {path}:{line_number}")
        replacement_mapping = _require_mapping(replacement, f"{path}:{line_number}.replacement")
        corrections[legacy_id] = Correction(
            legacy_id=legacy_id,
            raw_sha256=cast(str, raw_sha256),
            reason=reason,
            replacement=cast(Mapping[str, Any], replacement_mapping),
        )
    return corrections


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def file_metadata(path: Path) -> dict[str, object]:
    return {"name": path.name, "bytes": path.stat().st_size, "sha256": file_sha256(path)}


def _iter_legacy_rows_stdlib(path: Path) -> Iterator[tuple[int, Mapping[str, object]]]:
    try:
        payload: object = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise LegacyContractError(f"Invalid legacy JSON in {path}: {error}") from error
    columns = _require_mapping(payload, str(path))
    missing = set(LEGACY_COLUMNS) - set(columns)
    extra = set(columns) - set(LEGACY_COLUMNS)
    if missing or extra:
        raise LegacyContractError(
            f"Legacy columns differ at {path}: missing={sorted(missing)}, extra={sorted(extra)}"
        )
    column_maps = [
        _require_mapping(columns[column], f"{path}:{column}") for column in LEGACY_COLUMNS
    ]
    yield from _zip_legacy_columns(path, [iter(column.items()) for column in column_maps])


def _iter_legacy_rows_ijson(path: Path) -> Iterator[tuple[int, Mapping[str, object]]]:
    ijson = _require_ijson()
    with ExitStack() as stack:
        streams = [stack.enter_context(path.open("rb")) for _ in LEGACY_COLUMNS]
        iterators = [
            ijson.kvitems(stream, column)
            for stream, column in zip(streams, LEGACY_COLUMNS, strict=True)
        ]
        yield from _zip_legacy_columns(path, iterators)


def _zip_legacy_columns(
    path: Path, iterators: Sequence[Iterator[tuple[str, object]]]
) -> Iterator[tuple[int, Mapping[str, object]]]:
    for expected_index, values in enumerate(zip_longest(*iterators, fillvalue=_MISSING)):
        if any(value is _MISSING for value in values):
            raise LegacyContractError(f"Legacy columns have unequal lengths in {path}")
        pairs = cast(tuple[tuple[str, object], ...], values)
        indices = [pair[0] for pair in pairs]
        expected_key = str(expected_index)
        if len(set(indices)) != 1 or indices[0] != expected_key:
            raise LegacyContractError(
                f"Legacy row keys are not aligned at {path}; expected {expected_key!r}, "
                f"found {indices!r}"
            )
        yield (
            expected_index,
            {column: pair[1] for column, pair in zip(LEGACY_COLUMNS, pairs, strict=True)},
        )


def _take_source_group(
    rows: Iterator[LegacyRow], *, split: str, source_id: str
) -> tuple[LegacyRow, ...]:
    group: list[LegacyRow] = []
    for _ in range(LEGACY_VIEWS_PER_SOURCE[split]):
        try:
            group.append(next(rows))
        except StopIteration as error:
            raise LegacyContractError(
                f"Legacy rows ended inside the group for source {source_id!r}"
            ) from error
    return tuple(group)


def _validate_and_order_group(
    group: tuple[LegacyRow, ...], *, split: str, source_id: str
) -> tuple[LegacyRow, ...]:
    if split == "validation":
        return group
    first_context = group[0].context
    if any(row.context != first_context for row in group[1:]):
        raise LegacyContractError(
            f"Train source {source_id!r} does not keep evidence fixed across its 24 QA views"
        )
    target_names = tuple(row.target_language for row in group)
    if target_names != LEGACY_TRAIN_LANGUAGE_NAMES:
        raise LegacyContractError(
            f"Train source {source_id!r} violates the historical 24-language target order"
        )
    by_code = {_LANGUAGE_CODE_BY_NAME[cast(str, row.target_language)]: row for row in group}
    return tuple(by_code[code] for code in LANGUAGE_CODES)


def _build_instance(
    source: Mapping[str, object],
    row: LegacyRow,
    *,
    split: str,
    source_position: int,
) -> tuple[str, XHotpotInstance | None, list[AuditIssue]]:
    source_id = _source_id(source, source_position)
    issues: list[AuditIssue] = []
    target_code = _language_code(row.target_language, issues, field="target_language")
    base_id = f"xhp-{split}-{source_id}"
    legacy_id = (
        f"{base_id}--qa-{target_code}" if split == "train" and target_code is not None else base_id
    )

    source_context = _source_context(source, source_id)
    if not isinstance(row.context, list):
        issues.append(AuditIssue("invalid_context_type", "translate_context must be a list"))
        return legacy_id, None, issues
    if len(row.context) != len(source_context):
        issues.append(
            AuditIssue(
                "candidate_count_mismatch",
                f"translated={len(row.context)}, source={len(source_context)}",
            )
        )
        return legacy_id, None, issues

    candidates: list[CandidateParagraph] = []
    buildable = target_code is not None
    for index, (raw_candidate, source_candidate) in enumerate(
        zip(row.context, source_context, strict=True)
    ):
        candidate, candidate_issues = _build_candidate(raw_candidate, source_candidate, index=index)
        issues.extend(candidate_issues)
        if candidate is None:
            buildable = False
        else:
            candidates.append(candidate)

    question = row.question if isinstance(row.question, str) else None
    answer = row.answer if isinstance(row.answer, str) else None
    if question is None:
        issues.append(AuditIssue("invalid_question_type", "translate_question must be a string"))
        buildable = False
    elif not question.strip():
        issues.append(AuditIssue("empty_question", "translated question is empty"))
    if answer is None:
        issues.append(AuditIssue("invalid_answer_type", "translate_answer must be a string"))
        buildable = False
    elif not answer.strip():
        issues.append(AuditIssue("empty_answer", "translated answer is empty"))

    facts = _source_supporting_facts(source, source_context, source_id)
    if len(candidates) == len(source_context):
        candidate_by_id = {candidate.id: candidate for candidate in candidates}
        for fact in facts:
            candidate = candidate_by_id[fact.paragraph_id]
            if fact.sentence_id >= len(candidate.sentences):
                issues.append(
                    AuditIssue(
                        "supporting_fact_out_of_bounds",
                        f"{fact.paragraph_id}:{fact.sentence_id} exceeds translated sentences",
                    )
                )

    if not buildable or question is None or answer is None or target_code is None:
        return legacy_id, None, issues
    instance = XHotpotInstance(
        id=legacy_id,
        source_id=source_id,
        source_split=split,
        question=question,
        answer=answer,
        question_language=target_code,
        answer_language=target_code,
        candidates=tuple(candidates),
        supporting_facts=facts,
        question_type=_source_text(source, "type", default="unknown"),
        difficulty=_source_text(source, "level", default="unknown"),
        provenance=Provenance(
            assignment_version="legacy-random-v1-unseeded",
            seed=None,
            translation_model="gpt-4o-mini",
            translation_revision="provider-resolved-revision-unavailable",
            prompt_version="legacy-script-unversioned",
            validation_status="legacy-import-audited",
            decoding={"provenance_status": "incomplete"},
        ),
    )
    try:
        instance.validate()
    except ValueError as error:
        issues.append(AuditIssue("canonical_validation_error", str(error)))
    return legacy_id, with_checksum(instance), issues


def _build_candidate(
    raw: object, source: tuple[str, tuple[str, ...]], *, index: int
) -> tuple[CandidateParagraph | None, list[AuditIssue]]:
    issues: list[AuditIssue] = []
    if not isinstance(raw, list) or len(raw) != 3:
        return None, [
            AuditIssue(
                "invalid_candidate_shape",
                f"candidate {index} must be [title, sentences, language]",
            )
        ]
    title, sentences_raw, language_raw = raw
    buildable = True
    if not isinstance(title, str):
        issues.append(AuditIssue("invalid_title_type", f"candidate {index} title is not a string"))
        buildable = False
    elif not title.strip():
        issues.append(AuditIssue("empty_translated_title", f"candidate {index} title is empty"))
    if not isinstance(sentences_raw, list) or any(
        not isinstance(sentence, str) for sentence in sentences_raw
    ):
        issues.append(
            AuditIssue(
                "invalid_sentences_type",
                f"candidate {index} sentences must be a list of strings",
            )
        )
        buildable = False
        sentences: tuple[str, ...] = ()
    else:
        sentences = tuple(cast(list[str], sentences_raw))
        if not sentences:
            issues.append(AuditIssue("empty_paragraph", f"candidate {index} has no sentences"))
        if any(not sentence.strip() for sentence in sentences):
            issues.append(
                AuditIssue("empty_sentence", f"candidate {index} contains an empty sentence")
            )
        if len(sentences) != len(source[1]):
            issues.append(
                AuditIssue(
                    "sentence_cardinality_mismatch",
                    f"candidate {index}: translated={len(sentences)}, source={len(source[1])}",
                )
            )
    language = _language_code(language_raw, issues, field=f"candidate[{index}].language")
    if language is None or not buildable or not isinstance(title, str):
        return None, issues
    return (
        CandidateParagraph(
            id=f"p{index:02d}",
            title=title,
            sentences=sentences,
            language=language,
            source_title=source[0],
            source_sentences=source[1],
        ),
        issues,
    )


def _apply_correction(
    correction: Correction,
    source: Mapping[str, object],
    row: LegacyRow,
    *,
    split: str,
    source_position: int,
    expected_id: str,
) -> tuple[XHotpotInstance | None, list[AuditIssue]]:
    if correction.raw_sha256 != row.sha256:
        return None, [
            AuditIssue(
                "correction_raw_hash_mismatch",
                "correction was authored for different raw content",
            )
        ]
    try:
        replacement = with_checksum(XHotpotInstance.from_dict(correction.replacement))
        replacement.validate()
        _require_replacement_contract(
            replacement,
            source,
            split=split,
            source_position=source_position,
            expected_id=expected_id,
        )
    except (KeyError, TypeError, ValueError) as error:
        return None, [AuditIssue("invalid_correction", str(error))]
    return replacement, []


def _require_replacement_contract(
    replacement: XHotpotInstance,
    source: Mapping[str, object],
    *,
    split: str,
    source_position: int,
    expected_id: str,
) -> None:
    source_id = _source_id(source, source_position)
    if replacement.id != expected_id:
        raise LegacyContractError(
            f"Correction ID {replacement.id!r} differs from expected {expected_id!r}"
        )
    if replacement.source_id != source_id or replacement.source_split != split:
        raise LegacyContractError("Correction changed source identity or split")
    source_context = _source_context(source, source_id)
    if len(replacement.candidates) != len(source_context):
        raise LegacyContractError("Correction changed source candidate count")
    for index, (candidate, source_candidate) in enumerate(
        zip(replacement.candidates, source_context, strict=True)
    ):
        if candidate.id != f"p{index:02d}":
            raise LegacyContractError("Correction changed ordered candidate IDs")
        if (
            candidate.source_title != source_candidate[0]
            or candidate.source_sentences != source_candidate[1]
        ):
            raise LegacyContractError("Correction changed pinned source evidence")
    expected_facts = _source_supporting_facts(source, source_context, source_id)
    if replacement.supporting_facts != expected_facts:
        raise LegacyContractError("Correction changed source supporting-fact supervision")


def _source_context(
    source: Mapping[str, object], source_id: str
) -> tuple[tuple[str, tuple[str, ...]], ...]:
    raw_context = source.get("context")
    if not isinstance(raw_context, list):
        raise LegacyContractError(f"Source {source_id!r} context must be a list")
    context: list[tuple[str, tuple[str, ...]]] = []
    for index, raw_candidate in enumerate(raw_context):
        if (
            not isinstance(raw_candidate, list)
            or len(raw_candidate) != 2
            or not isinstance(raw_candidate[0], str)
            or not isinstance(raw_candidate[1], list)
            or any(not isinstance(sentence, str) for sentence in raw_candidate[1])
        ):
            raise LegacyContractError(f"Source {source_id!r} has invalid context candidate {index}")
        context.append((raw_candidate[0], tuple(cast(list[str], raw_candidate[1]))))
    if not context:
        raise LegacyContractError(f"Source {source_id!r} has no candidates")
    return tuple(context)


def _source_supporting_facts(
    source: Mapping[str, object],
    context: tuple[tuple[str, tuple[str, ...]], ...],
    source_id: str,
) -> tuple[SupportingFact, ...]:
    raw_facts = source.get("supporting_facts")
    if not isinstance(raw_facts, list) or not raw_facts:
        raise LegacyContractError(f"Source {source_id!r} has invalid supporting facts")
    title_indices: dict[str, list[int]] = {}
    for index, (title, _) in enumerate(context):
        title_indices.setdefault(title, []).append(index)
    facts: list[SupportingFact] = []
    for raw_fact in raw_facts:
        if (
            not isinstance(raw_fact, list)
            or len(raw_fact) != 2
            or not isinstance(raw_fact[0], str)
            or isinstance(raw_fact[1], bool)
            or not isinstance(raw_fact[1], int)
            or raw_fact[1] < 0
        ):
            raise LegacyContractError(f"Source {source_id!r} has malformed supporting fact")
        matching_indices = title_indices.get(raw_fact[0], [])
        if len(matching_indices) != 1:
            raise LegacyContractError(
                f"Source {source_id!r} support title {raw_fact[0]!r} is missing or ambiguous"
            )
        paragraph_index = matching_indices[0]
        if raw_fact[1] >= len(context[paragraph_index][1]):
            raise LegacyContractError(
                f"Source {source_id!r} has an out-of-bounds source supporting fact"
            )
        facts.append(SupportingFact(f"p{paragraph_index:02d}", raw_fact[1], "support"))
    if len(set(facts)) != len(facts):
        raise LegacyContractError(f"Source {source_id!r} has duplicate supporting facts")
    return tuple(facts)


def _source_id(source: Mapping[str, object], position: int) -> str:
    raw_id = source.get("_id", source.get("id"))
    if not isinstance(raw_id, (str, int)) or isinstance(raw_id, bool) or not str(raw_id):
        raise LegacyContractError(f"Source record at selected position {position} lacks an ID")
    return str(raw_id)


def _source_text(source: Mapping[str, object], field: str, *, default: str) -> str:
    value = source.get(field, default)
    return value if isinstance(value, str) and value else default


def _language_code(value: object, issues: list[AuditIssue], *, field: str) -> str | None:
    if not isinstance(value, str):
        issues.append(AuditIssue("invalid_language_type", f"{field} must be a string"))
        return None
    code = _LANGUAGE_CODE_BY_NAME.get(value)
    if code is None:
        issues.append(AuditIssue("unsupported_language", f"{field}={value!r}"))
    return code


def _raw_locator(row: LegacyRow) -> dict[str, object]:
    return {
        "shard": row.shard.name,
        "shard_row_index": row.shard_row_index,
        "global_row_index": row.global_row_index,
    }


def _write_jsonl(stream: Any, payload: Mapping[str, object]) -> None:
    stream.write(canonical_json(payload) + "\n")


def _validate_import_arguments(
    shards: Sequence[Path],
    source: Path,
    output_dir: Path,
    split: str,
    expected_source_count: int | None,
) -> None:
    if split not in LEGACY_VIEWS_PER_SOURCE:
        raise ValueError(f"Unsupported split: {split!r}")
    if not shards:
        raise ValueError("At least one legacy shard is required")
    if len(set(shards)) != len(shards):
        raise ValueError("Legacy shard paths must be unique and explicitly ordered")
    for path in [source, *shards]:
        if not path.is_file():
            raise FileNotFoundError(path)
    if expected_source_count is not None and expected_source_count < 0:
        raise ValueError("Expected source count cannot be negative")
    resolved_output = output_dir.resolve()
    if any(path.resolve() == resolved_output for path in [source, *shards]):
        raise ValueError("Output directory cannot replace an input file")


def _resolve_backend(
    paths: Sequence[Path], backend: LegacyReaderBackend
) -> Literal["ijson", "stdlib"]:
    if backend not in {"auto", "ijson", "stdlib"}:
        raise ValueError(f"Unsupported reader backend: {backend!r}")
    has_ijson = _load_ijson() is not None
    if backend == "ijson":
        if not has_ijson:
            raise RuntimeError('The ijson backend requires pip install -e ".[legacy]"')
        return "ijson"
    if backend == "auto" and has_ijson:
        return "ijson"
    oversized = [
        path for path in paths if path is not None and path.stat().st_size > MAX_STDLIB_BYTES
    ]
    if oversized:
        names = ", ".join(path.name for path in oversized)
        raise RuntimeError(
            f"Stdlib JSON fallback is limited to {MAX_STDLIB_BYTES // (1024 * 1024)} MiB; "
            f"install the legacy extra for streaming: {names}"
        )
    return "stdlib"


def _load_ijson() -> Any | None:
    try:
        return importlib.import_module("ijson")
    except ImportError:
        return None


def _require_ijson() -> Any:
    module = _load_ijson()
    if module is None:
        raise RuntimeError('Install the streaming reader with pip install -e ".[legacy]"')
    return module


def _require_mapping(value: object, context: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping) or any(not isinstance(key, str) for key in value):
        raise LegacyContractError(f"Expected an object at {context}")
    return cast(Mapping[str, object], value)


def _require_expected_digest(actual: str, expected: str | None, label: str) -> None:
    if expected is None:
        return
    if not _is_sha256(expected):
        raise ValueError(f"Expected {label} digest must be a lowercase SHA-256 value")
    if actual != expected:
        raise LegacyContractError(
            f"Pinned {label} SHA-256 mismatch: expected {expected}, found {actual}"
        )


def _is_sha256(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )
