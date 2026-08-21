"""Build the audited public V1 Parquet release from legacy translation shards.

The historical shards are pandas ``orient=columns`` JSON objects and omit
HotpotQA IDs and support labels.  This tool performs an ordered join against
the pinned HotpotQA sources, retains every source (including flagged records),
and emits one reproducible public view per source.  It never repairs or hides
legacy defects: each record carries a status and machine-readable flags.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import shutil
import subprocess
import tempfile
import unicodedata
from collections import Counter
from collections.abc import Iterator, Mapping, Sequence
from contextlib import ExitStack
from dataclasses import dataclass
from itertools import zip_longest
from pathlib import Path

import ijson
import pyarrow as pa  # type: ignore[import-not-found]
import pyarrow.parquet as pq  # type: ignore[import-not-found]

LANGUAGE_NAMES = (
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

LANGUAGE_CODES = {
    "English": "en",
    "Mandarin Chinese": "zh",
    "Spanish": "es",
    "Hindi": "hi",
    "Arabic": "ar",
    "French": "fr",
    "Russian": "ru",
    "Portuguese": "pt",
    "Bengali": "bn",
    "Urdu": "ur",
    "Indonesian": "id",
    "Japanese": "ja",
    "German": "de",
    "Swahili": "sw",
    "Turkish": "tr",
    "Vietnamese": "vi",
    "Korean": "ko",
    "Italian": "it",
    "Persian": "fa",
    "Thai": "th",
    "Dutch": "nl",
    "Polish": "pl",
    "Greek": "el",
    "Swedish": "sv",
}

BUILD_VERSION = "xhotpotqa-public-v1-builder/1.2.0"
CONFIG_NAME = "xhotpotqa_v1_1_audited"
EXPECTED_SOURCE_NAMES = {
    "train": "hotpot_train_v1.1.json",
    "validation": "hotpot_dev_distractor_v1.json",
}
EXPECTED_SHARD_NAMES = {
    "train": tuple(
        [f"hotpot_train_translate_{index}-{index + 1}.json" for index in range(8)]
        + ["hotpot_train_translate_8-end.json"]
    ),
    "validation": tuple(
        [f"hotpot_validation_translate_{index}-{index + 1}.json" for index in range(6)]
        + ["hotpot_validation_translate_6-end.json"]
    ),
}
EXPECTED_INPUTS = {
    "hotpot_train_v1.1.json": (
        566_426_227,
        "26650cf50234ef5fb2e664ed70bbecdfd87815e6bffc257e068efea5cf7cd316",
    ),
    "hotpot_dev_distractor_v1.json": (
        61_065_698,
        "e3da074df24e8369009918aa5cdbdd254dadcde4c63f7569d36afd6f2268caa8",
    ),
    "hotpot_train_translate_0-1.json": (
        629_493_158,
        "b15613ae12b9c0da21a0b3fd7ce1ccfdab4c12bc310760dfa664ded52356edf5",
    ),
    "hotpot_train_translate_1-2.json": (
        614_848_166,
        "4002d7e5bb23712672eff0a662190117d8effec21478367c8317285211be7f82",
    ),
    "hotpot_train_translate_2-3.json": (
        628_845_384,
        "d5c6898397d111bf702b6cd482101d478c41067275f368a134bc7a4c570c6f78",
    ),
    "hotpot_train_translate_3-4.json": (
        613_825_214,
        "3e08e0ae3eaffca999f72195f259ab4a7d1138040fef443d159f51b36ca3f96d",
    ),
    "hotpot_train_translate_4-5.json": (
        631_766_893,
        "b8ee2ae8cb056769e4203499a46efadb1ba68595cf18c99adf14f9469e0bfae7",
    ),
    "hotpot_train_translate_5-6.json": (
        604_500_669,
        "b7d133af0a39a11fd2092e759ff8dd7a082fefd4af1e9a6c87182157679634f9",
    ),
    "hotpot_train_translate_6-7.json": (
        596_310_485,
        "f706a08715245990d6cfd2654c7c0a4763f074899220d41591c46d2e36b73f8a",
    ),
    "hotpot_train_translate_7-8.json": (
        634_196_437,
        "9c6cf05e3f225bf6fb4346e114062ad16ced0a95b14f5f1a974a38adee48c0ff",
    ),
    "hotpot_train_translate_8-end.json": (
        647_609_488,
        "b276ea065461c21f88746f61c19a885ec74947696cd10806638d297642bb900d",
    ),
    "hotpot_validation_translate_0-1.json": (
        15_092_309,
        "78d7980340a9fc7943b099ebe96a0610daf9c1db1c82da960c46d6e486024492",
    ),
    "hotpot_validation_translate_1-2.json": (
        14_982_022,
        "efce9dc18b0ed49a39bf7ff54e8abfc2faea2247858056b879b0e4cbc22012ac",
    ),
    "hotpot_validation_translate_2-3.json": (
        14_967_037,
        "b116435bf77af9ea87b62ad9756577db16ae4800719a04ed522dee141d5e7ec5",
    ),
    "hotpot_validation_translate_3-4.json": (
        14_859_050,
        "ed2f0586b233483ddcbbfb055982d78d39f9cd20e7cd05a756ec43c7dffca295",
    ),
    "hotpot_validation_translate_4-5.json": (
        15_122_788,
        "39ea640764f8a15ab23acbbee700863eb32479ac942a0a23bbd04a0580124798",
    ),
    "hotpot_validation_translate_5-6.json": (
        14_836_305,
        "9c3bf0158af727d6d3cc7f369391296c90d69616a790e9c3bda6c3de6c037ca8",
    ),
    "hotpot_validation_translate_6-end.json": (
        21_444_136,
        "4a6e68b440361d6cee90e02b0fcde0e9ffcfb3792e00422d15e0dd18a9afbfbb",
    ),
}

LEGACY_COLUMNS = (
    "translate_context",
    "translate_question",
    "translate_answer",
    "target_language",
)

BLOCKING_FLAGS = {
    "blank_answer",
    "blank_question",
    "candidate_count_mismatch",
    "english_identity_mismatch",
    "invalid_candidate",
    "invalid_context",
    "invalid_source_candidate",
    "invalid_source_context",
    "malformed_supporting_fact",
    "paragraph_sentence_shortfall",
    "paragraph_sentence_surplus",
    "blank_sentence",
    "supporting_title_missing",
    "supporting_title_ambiguous",
    "support_index_out_of_range",
    "unknown_candidate_language",
    "unknown_question_language",
}

SCHEMA = pa.schema(
    [
        pa.field("id", pa.string(), nullable=False),
        pa.field("source_id", pa.string(), nullable=False),
        pa.field("source_split", pa.string(), nullable=False),
        pa.field("source_position", pa.int32(), nullable=False),
        pa.field("release_position", pa.int32(), nullable=False),
        pa.field("legacy_view_index", pa.int16(), nullable=False),
        pa.field("question", pa.string(), nullable=False),
        pa.field("answer", pa.string(), nullable=False),
        pa.field("question_language", pa.string(), nullable=False),
        pa.field("question_language_name", pa.string(), nullable=False),
        pa.field("answer_language", pa.string(), nullable=False),
        pa.field("answer_language_name", pa.string(), nullable=False),
        pa.field("source_question", pa.string(), nullable=False),
        pa.field("source_answer", pa.string(), nullable=False),
        pa.field("question_type", pa.string(), nullable=False),
        pa.field("difficulty", pa.string(), nullable=False),
        pa.field(
            "candidates",
            pa.list_(
                pa.struct(
                    [
                        pa.field("paragraph_id", pa.string(), nullable=False),
                        pa.field("candidate_index", pa.int16(), nullable=False),
                        pa.field("source_title", pa.string(), nullable=False),
                        pa.field("source_sentences", pa.list_(pa.string()), nullable=False),
                        pa.field("title", pa.string(), nullable=False),
                        pa.field("sentences", pa.list_(pa.string()), nullable=False),
                        pa.field("language", pa.string(), nullable=False),
                        pa.field("language_code", pa.string(), nullable=False),
                    ]
                )
            ),
            nullable=False,
        ),
        pa.field(
            "supporting_facts",
            pa.list_(
                pa.struct(
                    [
                        pa.field("source_title", pa.string(), nullable=False),
                        pa.field("paragraph_id", pa.string()),
                        pa.field("candidate_index", pa.int16()),
                        pa.field("sentence_index", pa.int32(), nullable=False),
                        pa.field("in_bounds", pa.bool_(), nullable=False),
                    ]
                )
            ),
            nullable=False,
        ),
        pa.field("status", pa.string(), nullable=False),
        pa.field("structural_flags", pa.list_(pa.string()), nullable=False),
        pa.field(
            "provenance",
            pa.struct(
                [
                    pa.field("source_dataset", pa.string(), nullable=False),
                    pa.field("source_file", pa.string(), nullable=False),
                    pa.field("source_record_sha256", pa.string(), nullable=False),
                    pa.field("legacy_shard", pa.string(), nullable=False),
                    pa.field("legacy_shard_row", pa.int32(), nullable=False),
                    pa.field("legacy_raw_sha256", pa.string(), nullable=False),
                    pa.field("translation_model", pa.string(), nullable=False),
                    pa.field("prompt_version", pa.string(), nullable=False),
                    pa.field("assignment_version", pa.string(), nullable=False),
                    pa.field("release_selection", pa.string(), nullable=False),
                    pa.field("build_version", pa.string(), nullable=False),
                ]
            ),
            nullable=False,
        ),
        pa.field("record_sha256", pa.string(), nullable=False),
    ]
)


@dataclass(frozen=True, slots=True)
class LegacyRow:
    context: object
    question: object
    answer: object
    language: object
    shard_name: str
    shard_row: int


class ShardedParquetWriter:
    """Write bounded Parquet shards while preserving one explicit schema."""

    def __init__(self, output_dir: Path, split: str, rows_per_shard: int) -> None:
        self.output_dir = output_dir
        self.split = split
        self.rows_per_shard = rows_per_shard
        self.buffer: list[dict[str, object]] = []
        self.paths: list[Path] = []

    def append(self, record: dict[str, object]) -> None:
        self.buffer.append(record)
        if len(self.buffer) >= self.rows_per_shard:
            self._flush()

    def close(self) -> tuple[Path, ...]:
        self._flush()
        return tuple(self.paths)

    def _flush(self) -> None:
        if not self.buffer:
            return
        self.output_dir.mkdir(parents=True, exist_ok=True)
        path = self.output_dir / f"{self.split}-{len(self.paths):05d}.parquet"
        table = pa.Table.from_pylist(self.buffer, schema=SCHEMA)
        pq.write_table(
            table,
            path,
            compression="zstd",
            compression_level=9,
            use_dictionary=True,
            write_statistics=True,
        )
        self.paths.append(path)
        self.buffer.clear()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--train-source", type=Path, required=True)
    parser.add_argument("--validation-source", type=Path, required=True)
    parser.add_argument("--train-shard", type=Path, action="append", required=True)
    parser.add_argument("--validation-shard", type=Path, action="append", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--rows-per-shard", type=int, default=5_000)
    return parser.parse_args()


def validate_inputs(
    train_source: Path,
    validation_source: Path,
    train_shards: Sequence[Path],
    validation_shards: Sequence[Path],
) -> tuple[dict[str, object], dict[Path, tuple[int, int]]]:
    """Reject reordered, renamed, missing, duplicated, or non-file inputs."""

    sources = {"train": train_source, "validation": validation_source}
    shard_sets = {"train": train_shards, "validation": validation_shards}
    all_paths: list[tuple[str, int, Path]] = []
    for split, path in sources.items():
        if path.name != EXPECTED_SOURCE_NAMES[split]:
            raise ValueError(
                f"Unexpected {split} source basename {path.name!r}; "
                f"expected {EXPECTED_SOURCE_NAMES[split]!r}"
            )
        all_paths.append((f"{split}_source", 0, path))
    for split, paths in shard_sets.items():
        names = tuple(path.name for path in paths)
        if names != EXPECTED_SHARD_NAMES[split]:
            raise ValueError(
                f"Unexpected {split} shard order {names!r}; "
                f"expected {EXPECTED_SHARD_NAMES[split]!r}"
            )
        all_paths.extend((f"{split}_legacy_shard", index, path) for index, path in enumerate(paths))
    for _, _, path in all_paths:
        if not path.is_file():
            raise FileNotFoundError(f"Required input is not a file: {path}")
    resolved = [path.resolve() for _, _, path in all_paths]
    if len(set(resolved)) != len(resolved):
        raise ValueError("Input paths must be unique")

    entries: list[dict[str, object]] = []
    snapshots: dict[Path, tuple[int, int]] = {}
    for role, ordinal, path in all_paths:
        resolved_path = path.resolve()
        stat = resolved_path.stat()
        expected_bytes, expected_sha256 = EXPECTED_INPUTS[path.name]
        if stat.st_size != expected_bytes:
            raise ValueError(
                f"Size mismatch for {path.name}: expected {expected_bytes}, found {stat.st_size}"
            )
        observed_sha256 = file_sha256(resolved_path)
        if observed_sha256 != expected_sha256:
            raise ValueError(
                f"SHA-256 mismatch for {path.name}: expected {expected_sha256}, "
                f"found {observed_sha256}"
            )
        snapshots[resolved_path] = (stat.st_size, stat.st_mtime_ns)
        entries.append(
            {
                "role": role,
                "ordinal": ordinal,
                "name": path.name,
                "bytes": stat.st_size,
                "sha256": observed_sha256,
            }
        )
    return {"ordered_inputs": entries}, snapshots


def verify_inputs_unchanged(snapshots: Mapping[Path, tuple[int, int]]) -> None:
    """Detect in-place changes that happen after the pre-build hash pass."""

    for path, before in snapshots.items():
        stat = path.stat()
        after = (stat.st_size, stat.st_mtime_ns)
        if after != before:
            raise RuntimeError(f"Input changed during build: {path.name}")


def iter_sources(path: Path, *, hard_only: bool) -> Iterator[tuple[int, Mapping[str, object]]]:
    with path.open("rb") as stream:
        for position, source in enumerate(ijson.items(stream, "item")):
            if not isinstance(source, Mapping):
                raise ValueError(f"Non-object source record in {path}")
            if hard_only and source.get("level") != "hard":
                continue
            yield position, source


def iter_legacy_rows(paths: Sequence[Path]) -> Iterator[LegacyRow]:
    for path in paths:
        yield from iter_legacy_shard(path)


def iter_legacy_shard(path: Path) -> Iterator[LegacyRow]:
    with ExitStack() as stack:
        streams = [stack.enter_context(path.open("rb")) for _ in LEGACY_COLUMNS]
        columns = [
            ijson.kvitems(stream, name)
            for stream, name in zip(streams, LEGACY_COLUMNS, strict=True)
        ]
        sentinel = object()
        for row_number, aligned in enumerate(zip_longest(*columns, fillvalue=sentinel)):
            if any(item is sentinel for item in aligned):
                raise ValueError(f"Legacy columns have unequal lengths in {path}")
            keys = [pair[0] for pair in aligned]
            if len(set(keys)) != 1 or keys[0] != str(row_number):
                raise ValueError(f"Legacy key misalignment in {path} at row {row_number}: {keys}")
            values = [pair[1] for pair in aligned]
            yield LegacyRow(
                values[0],
                values[1],
                values[2],
                values[3],
                path.name,
                row_number,
            )


def select_train_view(source_id: str) -> int:
    digest = hashlib.sha256(f"xhotpotqa-public-v1|{source_id}".encode()).digest()
    return int.from_bytes(digest[:8], "big") % len(LANGUAGE_NAMES)


def take_rows(rows: Iterator[LegacyRow], count: int, source_id: str) -> list[LegacyRow]:
    selected: list[LegacyRow] = []
    for _ in range(count):
        try:
            selected.append(next(rows))
        except StopIteration as error:
            raise ValueError(f"Legacy rows ended while joining source {source_id}") from error
    return selected


def normalize_title(value: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", value).split()).casefold()


def source_id(source: Mapping[str, object], position: int) -> str:
    value = source.get("_id", source.get("id"))
    if not isinstance(value, (str, int)) or isinstance(value, bool):
        raise ValueError(f"Source at selected position {position} has no stable ID")
    return str(value)


def canonical_hash(row: LegacyRow) -> str:
    payload = {
        "translate_context": row.context,
        "translate_question": row.question,
        "translate_answer": row.answer,
        "target_language": row.language,
    }
    return canonical_object_hash(payload)


def canonical_object_hash(value: object) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode()).hexdigest()


def record_hash(record: Mapping[str, object]) -> str:
    payload = {key: value for key, value in record.items() if key != "record_sha256"}
    return canonical_object_hash(payload)


def build_record(
    source: Mapping[str, object],
    row: LegacyRow,
    *,
    split: str,
    source_position: int,
    release_position: int,
    view_index: int,
) -> dict[str, object]:
    identifier = source_id(source, source_position)
    question = row.question if isinstance(row.question, str) else ""
    answer = row.answer if isinstance(row.answer, str) else ""
    language = row.language if isinstance(row.language, str) else "Unknown"
    flags: set[str] = set()
    if not question.strip():
        flags.add("blank_question")
    if not answer.strip():
        flags.add("blank_answer")
    if language not in LANGUAGE_CODES:
        flags.add("unknown_question_language")
    if language == "English" and (
        question != source.get("question") or answer != source.get("answer")
    ):
        flags.add("english_identity_mismatch")

    raw_source_context = source.get("context")
    source_context = raw_source_context if isinstance(raw_source_context, list) else []
    if not isinstance(raw_source_context, list):
        flags.add("invalid_source_context")
    raw_context = row.context
    translated_context = raw_context if isinstance(raw_context, list) else []
    if not isinstance(raw_context, list):
        flags.add("invalid_context")
    if len(source_context) != len(translated_context):
        flags.add("candidate_count_mismatch")

    candidates: list[dict[str, object]] = []
    candidate_lengths: dict[int, int] = {}
    translated_titles: list[str] = []
    for index, raw_candidate in enumerate(translated_context):
        if (
            not isinstance(raw_candidate, list)
            or len(raw_candidate) != 3
            or not isinstance(raw_candidate[0], str)
            or not isinstance(raw_candidate[1], list)
            or not isinstance(raw_candidate[2], str)
            or any(not isinstance(sentence, str) for sentence in raw_candidate[1])
        ):
            flags.add("invalid_candidate")
            continue
        title = raw_candidate[0]
        sentences = list(raw_candidate[1])
        paragraph_language = raw_candidate[2]
        if paragraph_language not in LANGUAGE_CODES:
            flags.add("unknown_candidate_language")
        translated_titles.append(title)
        candidate_lengths[index] = len(sentences)
        if any(not sentence.strip() for sentence in sentences):
            flags.add("blank_sentence")
        source_title = ""
        source_sentences: list[str] = []
        if index < len(source_context):
            raw_source_candidate = source_context[index]
            if (
                isinstance(raw_source_candidate, list)
                and len(raw_source_candidate) == 2
                and isinstance(raw_source_candidate[0], str)
                and isinstance(raw_source_candidate[1], list)
                and all(isinstance(sentence, str) for sentence in raw_source_candidate[1])
            ):
                source_title = raw_source_candidate[0]
                source_sentences = list(raw_source_candidate[1])
                difference = len(sentences) - len(source_sentences)
                if difference < 0:
                    flags.add("paragraph_sentence_shortfall")
                elif difference > 0:
                    flags.add("paragraph_sentence_surplus")
                if paragraph_language == "English" and (
                    title != raw_source_candidate[0] or sentences != raw_source_candidate[1]
                ):
                    flags.add("english_identity_mismatch")
            else:
                flags.add("invalid_source_candidate")
        candidates.append(
            {
                "paragraph_id": f"p{index:02d}",
                "candidate_index": index,
                "source_title": source_title,
                "source_sentences": source_sentences,
                "title": title,
                "sentences": sentences,
                "language": paragraph_language,
                "language_code": LANGUAGE_CODES.get(paragraph_language, "und"),
            }
        )

    normalized_titles = [normalize_title(title) for title in translated_titles]
    if len(set(normalized_titles)) != len(normalized_titles):
        flags.add("duplicate_normalized_translated_title")

    source_title_indices: dict[str, list[int]] = {}
    for index, raw_candidate in enumerate(source_context):
        if (
            isinstance(raw_candidate, list)
            and len(raw_candidate) == 2
            and isinstance(raw_candidate[0], str)
        ):
            source_title_indices.setdefault(raw_candidate[0], []).append(index)

    supporting_facts: list[dict[str, object]] = []
    raw_facts = source.get("supporting_facts")
    for fact in raw_facts if isinstance(raw_facts, list) else []:
        if (
            not isinstance(fact, list)
            or len(fact) != 2
            or not isinstance(fact[0], str)
            or isinstance(fact[1], bool)
            or not isinstance(fact[1], int)
            or fact[1] < 0
        ):
            flags.add("malformed_supporting_fact")
            continue
        matches = source_title_indices.get(fact[0], [])
        if not matches:
            flags.add("supporting_title_missing")
            paragraph_index: int | None = None
        elif len(matches) > 1:
            flags.add("supporting_title_ambiguous")
            paragraph_index = None
        else:
            paragraph_index = matches[0]
        in_bounds = (
            paragraph_index is not None
            and paragraph_index in candidate_lengths
            and fact[1] < candidate_lengths[paragraph_index]
        )
        if not in_bounds:
            flags.add("support_index_out_of_range")
        supporting_facts.append(
            {
                "source_title": fact[0],
                "paragraph_id": (
                    f"p{paragraph_index:02d}" if paragraph_index is not None else None
                ),
                "candidate_index": paragraph_index,
                "sentence_index": fact[1],
                "in_bounds": in_bounds,
            }
        )

    status = "quarantined" if flags & BLOCKING_FLAGS else "accepted"
    if status == "accepted" and "duplicate_normalized_translated_title" in flags:
        status = "review_required"
    selection = "sha256-public-v1" if split == "train" else "legacy-validation-view"
    language_code = LANGUAGE_CODES.get(language, "und")
    record: dict[str, object] = {
        "id": identifier,
        "source_id": identifier,
        "source_split": split,
        "source_position": source_position,
        "release_position": release_position,
        "legacy_view_index": view_index,
        "question": question,
        "answer": answer,
        "question_language": language_code,
        "question_language_name": language,
        "answer_language": language_code,
        "answer_language_name": language,
        "source_question": str(source.get("question", "")),
        "source_answer": str(source.get("answer", "")),
        "question_type": str(source.get("type", "unknown")),
        "difficulty": str(source.get("level", "unknown")),
        "candidates": candidates,
        "supporting_facts": supporting_facts,
        "status": status,
        "structural_flags": sorted(flags),
        "provenance": {
            "source_dataset": "hotpot_qa",
            "source_file": EXPECTED_SOURCE_NAMES[split],
            "source_record_sha256": canonical_object_hash(source),
            "legacy_shard": row.shard_name,
            "legacy_shard_row": row.shard_row,
            "legacy_raw_sha256": canonical_hash(row),
            "translation_model": "gpt-4o-mini (historical mutable alias)",
            "prompt_version": "legacy-v1-recovered",
            "assignment_version": "legacy-random-v1-unseeded",
            "release_selection": selection,
            "build_version": BUILD_VERSION,
        },
    }
    record["record_sha256"] = record_hash(record)
    return record


def build_split(
    *,
    source_path: Path,
    shard_paths: Sequence[Path],
    output_dir: Path,
    split: str,
    rows_per_source: int,
    expected_sources: int,
    rows_per_shard: int,
) -> dict[str, object]:
    rows = iter_legacy_rows(shard_paths)
    writer = ShardedParquetWriter(output_dir, split, rows_per_shard)
    status_counts: Counter[str] = Counter()
    flag_counts: Counter[str] = Counter()
    language_counts: Counter[str] = Counter()
    legacy_shard_row_counts: Counter[str] = Counter()
    identifiers: set[str] = set()
    source_count = 0
    for release_position, (source_position, source) in enumerate(
        iter_sources(source_path, hard_only=split == "train")
    ):
        identifier = source_id(source, source_position)
        if identifier in identifiers:
            raise ValueError(f"Duplicate source ID in {split}: {identifier}")
        identifiers.add(identifier)
        group = take_rows(rows, rows_per_source, identifier)
        legacy_shard_row_counts.update(row.shard_name for row in group)
        if split == "train":
            languages = tuple(row.language for row in group)
            if languages != LANGUAGE_NAMES:
                raise ValueError(f"Unexpected language order for train source {identifier}")
            if group[0].question != source.get("question") or group[0].answer != source.get(
                "answer"
            ):
                raise ValueError(
                    f"English identity join check failed for train source {identifier}"
                )
            if len({canonical_object_hash(row.context) for row in group}) != 1:
                raise ValueError(f"Train context views diverge for source {identifier}")
            view_index = select_train_view(identifier)
        else:
            view_index = 0
        record = build_record(
            source,
            group[view_index],
            split=split,
            source_position=source_position,
            release_position=release_position,
            view_index=view_index,
        )
        writer.append(record)
        status_counts[str(record["status"])] += 1
        language_counts[str(record["question_language_name"])] += 1
        raw_flags = record["structural_flags"]
        if not isinstance(raw_flags, list) or any(not isinstance(flag, str) for flag in raw_flags):
            raise TypeError("Internal error: structural_flags must be a list of strings")
        flag_counts.update(raw_flags)
        source_count += 1
        if source_count % 1_000 == 0:
            print(f"{split}: {source_count:,} sources", flush=True)
    try:
        extra = next(rows)
    except StopIteration:
        extra = None
    if extra is not None:
        raise ValueError(f"Unused legacy rows remain after the {split} ordered join")
    if source_count != expected_sources:
        raise ValueError(f"Expected {expected_sources:,} {split} sources, found {source_count:,}")
    expected_names = EXPECTED_SHARD_NAMES[split]
    observed_names = tuple(legacy_shard_row_counts)
    if observed_names != expected_names:
        raise ValueError(
            f"Observed {split} shard coverage order {observed_names!r}; expected {expected_names!r}"
        )
    expected_legacy_rows = expected_sources * rows_per_source
    if legacy_shard_row_counts.total() != expected_legacy_rows:
        raise ValueError(
            f"Expected {expected_legacy_rows:,} legacy {split} rows, "
            f"found {legacy_shard_row_counts.total():,}"
        )
    paths = writer.close()
    return {
        "sources": source_count,
        "parquet_files": [path.name for path in paths],
        "status_counts": dict(sorted(status_counts.items())),
        "flag_counts": dict(sorted(flag_counts.items())),
        "question_language_counts": dict(sorted(language_counts.items())),
        "legacy_shard_row_counts": {name: legacy_shard_row_counts[name] for name in expected_names},
    }


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def detect_git_revision(start: Path) -> str:
    """Return the nearest Git revision, including an explicit dirty marker."""

    repository = next(
        (parent for parent in start.resolve().parents if (parent / ".git").exists()),
        None,
    )
    if repository is None:
        return "not-a-git-worktree"
    try:
        revision = subprocess.run(
            ["git", "-C", str(repository), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        dirty = bool(
            subprocess.run(
                ["git", "-C", str(repository), "status", "--porcelain"],
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
        )
    except (OSError, subprocess.CalledProcessError):
        return "git-unavailable"
    return f"{revision}+dirty" if dirty else revision


def expected_status(flags: Sequence[str]) -> str:
    flag_set = set(flags)
    if flag_set & BLOCKING_FLAGS:
        return "quarantined"
    if "duplicate_normalized_translated_title" in flag_set:
        return "review_required"
    return "accepted"


def validate_release(output_dir: Path, report: Mapping[str, object]) -> None:
    """Read back every Parquet row and verify schema, ordering, and checksums."""

    data_dir = output_dir / "data" / CONFIG_NAME
    all_identifiers: set[str] = set()
    expected_total = 0
    for split, expected_rows in (("train", 15_661), ("validation", 7_405)):
        split_report = report.get(split)
        if not isinstance(split_report, Mapping):
            raise TypeError(f"Missing report for split {split}")
        raw_names = split_report.get("parquet_files")
        if not isinstance(raw_names, list) or any(not isinstance(name, str) for name in raw_names):
            raise TypeError(f"Invalid Parquet file list for split {split}")
        paths = [data_dir / name for name in raw_names]
        if not paths or any(not path.is_file() for path in paths):
            raise FileNotFoundError(f"Missing Parquet output for split {split}")
        observed_positions: list[int] = []
        split_identifiers: set[str] = set()
        split_rows = 0
        for path in paths:
            if not path.name.startswith(f"{split}-"):
                raise ValueError(f"Unexpected file in {split} output: {path.name}")
            parquet = pq.ParquetFile(path)
            if not parquet.schema_arrow.equals(SCHEMA):
                raise ValueError(f"Schema mismatch in {path}")
            for batch in parquet.iter_batches(batch_size=128):
                for record in batch.to_pylist():
                    split_rows += 1
                    identifier = record["id"]
                    if identifier != record["source_id"] or identifier in split_identifiers:
                        raise ValueError(f"Invalid or duplicate ID in {path}: {identifier}")
                    split_identifiers.add(identifier)
                    observed_positions.append(record["release_position"])
                    language_code = record["question_language"]
                    language_name = record["question_language_name"]
                    if LANGUAGE_CODES.get(language_name, "und") != language_code:
                        raise ValueError(f"Language code/name mismatch for {identifier}")
                    flags = record["structural_flags"]
                    if record["status"] != expected_status(flags):
                        raise ValueError(f"Status/flags mismatch for {identifier}")
                    if record_hash(record) != record["record_sha256"]:
                        raise ValueError(f"Record checksum mismatch for {identifier}")
        if split_rows != expected_rows:
            raise ValueError(f"Expected {expected_rows:,} {split} rows, read {split_rows:,}")
        if observed_positions != list(range(expected_rows)):
            raise ValueError(f"Non-contiguous release_position sequence in {split}")
        if all_identifiers & split_identifiers:
            raise ValueError("Source IDs overlap across train and validation")
        all_identifiers.update(split_identifiers)
        expected_total += expected_rows
    if len(all_identifiers) != expected_total:
        raise ValueError("Release-wide ID cardinality mismatch")


def enrich_output_metadata(output_dir: Path, report: dict[str, object]) -> None:
    files: dict[str, dict[str, object]] = {}
    total_rows = 0
    total_bytes = 0
    for path in sorted(output_dir.rglob("*.parquet")):
        relative = path.relative_to(output_dir).as_posix()
        metadata = pq.read_metadata(path)
        rows = metadata.num_rows
        size = path.stat().st_size
        files[relative] = {
            "rows": rows,
            "bytes": size,
            "sha256": file_sha256(path),
        }
        total_rows += rows
        total_bytes += size
    report["files"] = files
    report["total_rows"] = total_rows
    report["total_bytes"] = total_bytes


def build_release(
    args: argparse.Namespace,
    staging_dir: Path,
    input_metadata: Mapping[str, object],
    input_snapshots: Mapping[Path, tuple[int, int]],
) -> dict[str, object]:
    report: dict[str, object] = {
        "release_version": "xhotpotqa-public-v1.1-audited",
        "config_name": CONFIG_NAME,
        "train_selection": "sha256-public-v1",
        "builder": {
            "version": BUILD_VERSION,
            "script_sha256": file_sha256(Path(__file__).resolve()),
            "git_revision": detect_git_revision(Path(__file__)),
        },
        "environment": {
            "python": platform.python_version(),
            "python_implementation": platform.python_implementation(),
            "platform": platform.platform(),
            "pyarrow": pa.__version__,
            "ijson": getattr(ijson, "__version__", "unknown"),
        },
        "inputs": input_metadata,
        "notes": [
            "All 7,405 validation sources are retained; status marks structural quarantine.",
            "Training selects one deterministic QA-language view from each 24-view source group.",
            "Every candidate retains its ordered original English source_sentences array.",
            "No translated text is silently repaired or deleted.",
        ],
    }
    report["train"] = build_split(
        source_path=args.train_source,
        shard_paths=args.train_shard,
        output_dir=staging_dir / "data" / CONFIG_NAME,
        split="train",
        rows_per_source=len(LANGUAGE_NAMES),
        expected_sources=15_661,
        rows_per_shard=args.rows_per_shard,
    )
    report["validation"] = build_split(
        source_path=args.validation_source,
        shard_paths=args.validation_shard,
        output_dir=staging_dir / "data" / CONFIG_NAME,
        split="validation",
        rows_per_source=1,
        expected_sources=7_405,
        rows_per_shard=args.rows_per_shard,
    )
    verify_inputs_unchanged(input_snapshots)
    validate_release(staging_dir, report)
    enrich_output_metadata(staging_dir, report)
    manifest_path = staging_dir / "RELEASE_MANIFEST.json"
    manifest_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return report


def main() -> int:
    args = parse_args()
    if isinstance(args.rows_per_shard, bool) or args.rows_per_shard <= 0:
        raise ValueError("--rows-per-shard must be positive")
    if args.output_dir.exists():
        raise FileExistsError(f"Refusing to replace existing output: {args.output_dir}")
    input_metadata, input_snapshots = validate_inputs(
        args.train_source,
        args.validation_source,
        args.train_shard,
        args.validation_shard,
    )
    args.output_dir.parent.mkdir(parents=True, exist_ok=True)
    staging_dir = Path(
        tempfile.mkdtemp(
            prefix=f".{args.output_dir.name}.building-",
            dir=args.output_dir.parent,
        )
    )
    try:
        report = build_release(args, staging_dir, input_metadata, input_snapshots)
        os.replace(staging_dir, args.output_dir)
    except BaseException:
        shutil.rmtree(staging_dir, ignore_errors=True)
        raise
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
