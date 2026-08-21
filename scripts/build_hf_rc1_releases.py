"""Build locked, auditable Hugging Face payloads for XHotpotQA V2 RC1.

This is a publication builder, not a repair script.  It accepts only the
byte-exact artifacts listed in :data:`INPUT_LOCKS`, joins generated V2 rows to
the pinned HotpotQA sources, and preserves every observed defect as a status or
flag.  Missing rows are listed in a manifest and are never synthesized.

The same invocation derives two sanitized GLM-5.2 judge datasets.  Hidden
reasoning, source/candidate text, endpoint details, errors, and credentials are
not copied into the public payload.  The mixed V2 judge artifact is filtered to
paragraphs and questions; its known invalid partial answer run is discarded in
favor of the dedicated answer artifact.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import random
import re
import shutil
import sqlite3
import statistics
import tempfile
from collections import Counter, defaultdict
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import ijson
import pyarrow as pa  # type: ignore[import-not-found]
import pyarrow.parquet as pq  # type: ignore[import-not-found]

BUILD_VERSION = "xhotpotqa-hf-rc1-builder/1.0.0"
V2_CONFIG_NAME = "xhotpotqa_v2_audited_rc1"
JUDGE_V1_CONFIG_NAME = "xhotpotqa_glm52_judge_v1"
JUDGE_V2_CONFIG_NAME = "xhotpotqa_glm52_judge_v2"

EXPECTED_SOURCE_COUNTS = {"train": 15_661, "validation": 7_405}
EXPECTED_V2_COUNTS = {"train": 15_433, "validation": 7_403}
EXPECTED_JUDGE_UNIT_COUNTS = {"paragraph": 1_840, "question": 460, "answer": 460}
EXPECTED_DISCARDED_V2_MIXED_ANSWERS = 240
EXPECTED_TARGET_LANGUAGES = (
    "ar",
    "bn",
    "de",
    "el",
    "es",
    "fa",
    "fr",
    "hi",
    "id",
    "it",
    "ja",
    "ko",
    "nl",
    "pl",
    "pt",
    "ru",
    "sv",
    "sw",
    "th",
    "tr",
    "ur",
    "vi",
    "zh",
)
LANGUAGE_NAMES = {
    "ar": "Arabic",
    "bn": "Bengali",
    "de": "German",
    "el": "Greek",
    "en": "English",
    "es": "Spanish",
    "fa": "Persian",
    "fr": "French",
    "hi": "Hindi",
    "id": "Indonesian",
    "it": "Italian",
    "ja": "Japanese",
    "ko": "Korean",
    "nl": "Dutch",
    "pl": "Polish",
    "pt": "Portuguese",
    "ru": "Russian",
    "sv": "Swedish",
    "sw": "Swahili",
    "th": "Thai",
    "tr": "Turkish",
    "ur": "Urdu",
    "vi": "Vietnamese",
    "zh": "Mandarin Chinese",
}

JUDGE_GENERAL_PROMPT_SHA256 = "e939a00a58e2347b60e9dc04ad7278b88430d41e4a2aea8749023c08631db5af"
JUDGE_ANSWER_PROMPT_SHA256 = "7e560af3c545c22fee93f78f3b621326e04c92ddcd61844c79ee45994320a525"
JUDGE_PROMPT_VERSION = "xhotpotqa-glm52-translation-judge-v1.0"
JUDGE_REQUESTED_MODEL = "glm-5.2"
JUDGE_SAMPLE_SEED = 20260810
BOOTSTRAP_SEED = 20260821

_SCORE_PATTERN = re.compile(r"SCORE\s*[:\-]?\s*(\d{1,3})", re.IGNORECASE)
_INTEGER_PATTERN = re.compile(r"\b(\d{1,3})\b")
_FINAL_SCORE_LINE = re.compile(r"(?:^|\n)\s*SCORE\s*[:\-]?\s*\d{1,3}\s*$", re.IGNORECASE)


@dataclass(frozen=True, slots=True)
class InputLock:
    """Expected byte identity for a publication input."""

    filename: str
    size: int
    sha256: str


INPUT_LOCKS = {
    "hotpot_train": InputLock(
        "hotpot_train_v1.1.json",
        566_426_227,
        "26650cf50234ef5fb2e664ed70bbecdfd87815e6bffc257e068efeA5cf7cd316".lower(),
    ),
    "hotpot_validation": InputLock(
        "hotpot_dev_distractor_v1.json",
        61_065_698,
        "e3da074df24e8369009918aa5cdbdd254dadcde4c63f7569d36afd6f2268caa8",
    ),
    "v2_train": InputLock(
        "train.v2.jsonl",
        246_399_367,
        "dd1d5bb5950cfe3ca5d013685f9d6e71d1059bde0e5a316462e26a546d491270",
    ),
    "v2_validation": InputLock(
        "validation.v2.jsonl",
        118_715_033,
        "86542d9918dab1e0587683b51dfa7091a6e8b77171283c66caca35ed70ac931a",
    ),
    "v2_train_errors": InputLock(
        "train.v2.jsonl.errors.jsonl",
        93,
        "937e73a83277e469bd0caa6a730d9d2c9a69302737096e8d5a316beb3099e1bb",
    ),
    "v2_validation_errors": InputLock(
        "validation.v2.jsonl.errors.jsonl",
        192,
        "fff422e32057e64ce67cf87c2c42e3a902eca7e015007857062749d5a6236166",
    ),
    "judge_v1": InputLock(
        "judge_v1_full.records.jsonl",
        13_366_284,
        "23460f146ee8bb9c9e73cdf21167a97f2db77818e74c091db81d2ee38ced8c1e",
    ),
    "judge_v2_mixed": InputLock(
        "judge_all.records.jsonl",
        12_703_376,
        "bfda9f64707eff9c989f310f16da55350d8659f9f5b4f77e8336af1ce39999ac",
    ),
    "judge_v2_answers": InputLock(
        "judge_answers.records.jsonl",
        646_621,
        "62465580763a4a4eacee8b1efce82e583f771cc6587c9378b3998beceec7e0e0",
    ),
}

V2_SCHEMA = pa.schema(
    [
        pa.field("id", pa.string(), nullable=False),
        pa.field("source_id", pa.string(), nullable=False),
        pa.field("source_split", pa.string(), nullable=False),
        pa.field("source_position", pa.int32(), nullable=False),
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
                        pa.field("language_name", pa.string(), nullable=False),
                        pa.field("source_match", pa.bool_(), nullable=False),
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
                        pa.field("paragraph_id", pa.string(), nullable=False),
                        pa.field("sentence_id", pa.int32(), nullable=False),
                        pa.field("source_title", pa.string(), nullable=False),
                        pa.field("in_bounds", pa.bool_(), nullable=False),
                    ]
                )
            ),
            nullable=False,
        ),
        pa.field("status", pa.string(), nullable=False),
        pa.field("structural_flags", pa.list_(pa.string()), nullable=False),
        pa.field("quality_flags", pa.list_(pa.string()), nullable=False),
        pa.field("source_record_sha256", pa.string(), nullable=False),
        pa.field("input_record_checksum_sha256", pa.string(), nullable=False),
        pa.field("input_checksum_valid", pa.bool_(), nullable=False),
        pa.field("release_record_sha256", pa.string(), nullable=False),
        pa.field("translation_model", pa.string(), nullable=False),
        pa.field("translation_revision", pa.string(), nullable=False),
        pa.field("prompt_version", pa.string(), nullable=False),
        pa.field("prompt_sha256", pa.string(), nullable=False),
        pa.field("assignment_version", pa.string(), nullable=False),
        pa.field("assignment_manifest_sha256", pa.string(), nullable=False),
        pa.field("generation_seed", pa.int64(), nullable=False),
        pa.field("decoding_json", pa.string(), nullable=False),
        pa.field("created_at", pa.string(), nullable=False),
        pa.field("recorded_retry_count_unreliable", pa.int32(), nullable=False),
        pa.field("recorded_validation_status", pa.string(), nullable=False),
        pa.field("input_schema_version", pa.string(), nullable=False),
    ]
)

JUDGE_SCHEMA = pa.schema(
    [
        pa.field("judge_record_id", pa.string(), nullable=False),
        pa.field("dataset_version", pa.string(), nullable=False),
        pa.field("dataset_revision", pa.string(), nullable=False),
        pa.field("dataset_revision_status", pa.string(), nullable=False),
        pa.field("instance_id", pa.string(), nullable=False),
        pa.field("source_id", pa.string(), nullable=False),
        pa.field("source_split", pa.string(), nullable=False),
        pa.field("target_language", pa.string(), nullable=False),
        pa.field("target_language_name", pa.string(), nullable=False),
        pa.field("unit", pa.string(), nullable=False),
        pa.field("paragraph_id", pa.string()),
        pa.field("score", pa.int16(), nullable=False),
        pa.field("score_origin", pa.string(), nullable=False),
        pa.field("judge_explanation", pa.string(), nullable=False),
        pa.field("judge_explanation_available", pa.bool_(), nullable=False),
        pa.field("source_text_sha256", pa.string(), nullable=False),
        pa.field("candidate_text_sha256", pa.string(), nullable=False),
        pa.field("requested_judge_model", pa.string(), nullable=False),
        pa.field("resolved_judge_revision", pa.string()),
        pa.field("model_identity_status", pa.string(), nullable=False),
        pa.field("judge_prompt_version", pa.string(), nullable=False),
        pa.field("judge_prompt_sha256", pa.string(), nullable=False),
        pa.field("sampling_seed", pa.int64(), nullable=False),
        pa.field("run_group", pa.string(), nullable=False),
        pa.field("raw_artifact_sha256", pa.string(), nullable=False),
        pa.field("raw_line_number", pa.int32(), nullable=False),
    ]
)


def canonical_json(payload: Any) -> str:
    """Return the project-wide canonical JSON representation."""

    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def assert_locked_input(path: Path, lock: InputLock) -> dict[str, Any]:
    """Fail closed unless *path* is the exact locked artifact."""

    if not path.is_file():
        raise FileNotFoundError(f"Locked input does not exist: {path}")
    if path.name != lock.filename:
        raise ValueError(f"Expected input named {lock.filename!r}, got {path.name!r}")
    size = path.stat().st_size
    if size != lock.size:
        raise ValueError(f"Size mismatch for {path.name}: {size} != {lock.size}")
    digest = sha256_file(path)
    if digest.lower() != lock.sha256.lower():
        raise ValueError(f"SHA-256 mismatch for {path.name}: {digest}")
    return {"filename": lock.filename, "size": size, "sha256": digest}


def read_jsonl(path: Path) -> Iterator[tuple[int, dict[str, Any]]]:
    with path.open("r", encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, start=1):
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError as error:
                raise ValueError(f"Invalid JSON at {path.name}:{line_number}: {error}") from error
            if not isinstance(value, dict):
                raise ValueError(f"Expected object at {path.name}:{line_number}")
            yield line_number, value


def input_semantic_checksum(record: Mapping[str, Any]) -> str:
    """Reproduce the V2 generator's semantic checksum without importing ``src``."""

    stable = dict(record)
    stable["checksum"] = ""
    provenance = dict(stable.get("provenance") or {})
    provenance["created_at"] = ""
    provenance["retry_count"] = 0
    provenance["validation_status"] = ""
    if not provenance.get("assignment_manifest_sha256"):
        provenance.pop("assignment_manifest_sha256", None)
    stable["provenance"] = provenance
    return sha256_text(canonical_json(stable))


def _source_record(item: Mapping[str, Any]) -> dict[str, Any]:
    source_id = str(item.get("_id", item.get("id", "")))
    if not source_id:
        raise ValueError("HotpotQA source has no ID")
    context: list[dict[str, Any]] = []
    for index, candidate in enumerate(item.get("context") or []):
        if not isinstance(candidate, list) or len(candidate) < 2:
            raise ValueError(f"Source {source_id} has malformed context entry {index}")
        sentences = candidate[1]
        if not isinstance(sentences, list):
            raise ValueError(f"Source {source_id} context {index} has no sentence list")
        context.append(
            {
                "paragraph_id": f"p{index:02d}",
                "title": str(candidate[0]),
                "sentences": [str(sentence) for sentence in sentences],
            }
        )
    supporting: list[dict[str, Any]] = []
    for fact in item.get("supporting_facts") or []:
        if not isinstance(fact, list) or len(fact) < 2:
            raise ValueError(f"Source {source_id} has malformed supporting fact")
        supporting.append({"title": str(fact[0]), "sentence_id": int(fact[1])})
    return {
        "source_id": source_id,
        "question": str(item.get("question", "")),
        "answer": str(item.get("answer", "")),
        "question_type": str(item.get("type", "unknown")),
        "difficulty": str(item.get("level", "unknown")),
        "context": context,
        "supporting_facts": supporting,
    }


def index_hotpot_sources(
    connection: sqlite3.Connection,
    *,
    train_path: Path,
    validation_path: Path,
) -> dict[str, int]:
    """Stream pinned HotpotQA arrays into a deterministic temporary index."""

    connection.execute(
        "CREATE TABLE sources ("
        "source_id TEXT PRIMARY KEY, split TEXT NOT NULL, position INTEGER NOT NULL, "
        "payload TEXT NOT NULL, checksum TEXT NOT NULL, UNIQUE(split, position))"
    )
    counts: dict[str, int] = {}
    for split, path in (("train", train_path), ("validation", validation_path)):
        count = 0
        with path.open("rb") as stream:
            for item in ijson.items(stream, "item"):
                if not isinstance(item, Mapping):
                    raise ValueError(f"{path.name} contains a non-object source")
                if split == "train" and item.get("level") != "hard":
                    continue
                normalized = _source_record(item)
                payload = canonical_json(normalized)
                try:
                    connection.execute(
                        "INSERT INTO sources VALUES (?, ?, ?, ?, ?)",
                        (
                            normalized["source_id"],
                            split,
                            count,
                            payload,
                            sha256_text(payload),
                        ),
                    )
                except sqlite3.IntegrityError as error:
                    raise ValueError(
                        f"Duplicate HotpotQA source ID {normalized['source_id']!r}"
                    ) from error
                count += 1
        expected = EXPECTED_SOURCE_COUNTS[split]
        if count != expected:
            raise ValueError(f"{split} source count {count:,} != locked expectation {expected:,}")
        counts[split] = count
        connection.commit()
    return counts


def _source_by_id(
    connection: sqlite3.Connection, source_id: str, split: str
) -> tuple[int, dict[str, Any], str]:
    row = connection.execute(
        "SELECT position, payload, checksum FROM sources WHERE source_id=? AND split=?",
        (source_id, split),
    ).fetchone()
    if row is None:
        raise ValueError(f"Generated record {source_id!r} is not in pinned {split} source")
    return int(row[0]), json.loads(row[1]), str(row[2])


def _paragraph_index(paragraph_id: str) -> int | None:
    match = re.fullmatch(r"p(\d{2})", paragraph_id)
    return int(match.group(1)) if match else None


def _release_checksum(record: Mapping[str, Any]) -> str:
    payload = dict(record)
    payload["release_record_sha256"] = ""
    return sha256_text(canonical_json(payload))


def normalize_v2_record(
    raw: Mapping[str, Any],
    *,
    split: str,
    source_position: int,
    source: Mapping[str, Any],
    source_checksum: str,
) -> dict[str, Any]:
    """Join one generated record to source truth and derive transparent flags."""

    structural: set[str] = set()
    quality: set[str] = set()
    source_id = str(raw.get("source_id", ""))
    if str(raw.get("source_split", "")) != split:
        structural.add("xhotpot:source_split_mismatch")
    if str(raw.get("source_id", "")) != str(source["source_id"]):
        structural.add("xhotpot:source_id_mismatch")

    stored_checksum = str(raw.get("checksum", ""))
    checksum_valid = bool(stored_checksum) and input_semantic_checksum(raw) == stored_checksum
    if not checksum_valid:
        structural.add("xhotpot:input_checksum_mismatch")

    question = str(raw.get("question", ""))
    answer = str(raw.get("answer", ""))
    question_language = str(raw.get("question_language", ""))
    answer_language = str(raw.get("answer_language", ""))
    if not question.strip():
        structural.add("xhotpot:blank_question")
    if not answer.strip():
        structural.add("xhotpot:blank_answer")
    if question_language not in LANGUAGE_NAMES:
        structural.add("xhotpot:unknown_question_language")
    if answer_language not in LANGUAGE_NAMES:
        structural.add("xhotpot:unknown_answer_language")
    if question_language != answer_language:
        structural.add("xhotpot:question_answer_language_mismatch")
    if question_language != "en" and question == source["question"]:
        quality.add("xhotpot:question_source_copy")
    if answer_language != "en" and answer == source["answer"]:
        quality.add("xhotpot:answer_source_copy")

    expected_context = list(source.get("context") or [])
    raw_candidates = raw.get("candidates")
    if not isinstance(raw_candidates, list):
        raw_candidates = []
        structural.add("xhotpot:candidates_not_list")
    if len(raw_candidates) != len(expected_context):
        structural.add("xhotpot:candidate_count_mismatch")
    candidates: list[dict[str, Any]] = []
    for candidate_index, raw_candidate in enumerate(raw_candidates):
        if not isinstance(raw_candidate, Mapping):
            structural.add("xhotpot:malformed_candidate")
            continue
        paragraph_id = str(raw_candidate.get("id", ""))
        resolved_index = _paragraph_index(paragraph_id)
        if resolved_index is None or resolved_index >= len(expected_context):
            structural.add("xhotpot:invalid_paragraph_id")
            expected = {
                "paragraph_id": paragraph_id or f"invalid-{candidate_index}",
                "title": "",
                "sentences": [],
            }
        else:
            expected = expected_context[resolved_index]
        if resolved_index != candidate_index:
            structural.add("xhotpot:candidate_order_mismatch")
        recorded_source_title = str(raw_candidate.get("source_title", ""))
        recorded_source_sentences = raw_candidate.get("source_sentences")
        if not isinstance(recorded_source_sentences, list):
            recorded_source_sentences = []
        normalized_recorded_source = [str(value) for value in recorded_source_sentences]
        source_match = (
            recorded_source_title == expected["title"]
            and normalized_recorded_source == expected["sentences"]
        )
        if recorded_source_title != expected["title"]:
            structural.add("xhotpot:source_title_mismatch")
        if normalized_recorded_source != expected["sentences"]:
            structural.add("xhotpot:source_sentences_mismatch")
        if any(not sentence.strip() for sentence in expected["sentences"]):
            structural.add("source:blank_source_sentence")

        sentences = raw_candidate.get("sentences")
        if not isinstance(sentences, list):
            sentences = []
            structural.add("xhotpot:translation_sentences_not_list")
        translated_sentences = [str(value) for value in sentences]
        if len(translated_sentences) != len(expected["sentences"]):
            structural.add("xhotpot:sentence_count_mismatch")
        if any(not value.strip() for value in translated_sentences):
            structural.add("xhotpot:blank_translation_sentence")
        language = str(raw_candidate.get("language", ""))
        if language not in LANGUAGE_NAMES:
            structural.add("xhotpot:unknown_candidate_language")
        if language != "en" and any(
            translated == original
            for translated, original in zip(
                translated_sentences, expected["sentences"], strict=False
            )
            if original.strip()
        ):
            quality.add("xhotpot:paragraph_sentence_source_copy")
        title = str(raw_candidate.get("title", ""))
        if not title.strip():
            structural.add("xhotpot:blank_translated_title")
        candidates.append(
            {
                "paragraph_id": paragraph_id or str(expected["paragraph_id"]),
                "candidate_index": candidate_index,
                "source_title": str(expected["title"]),
                "source_sentences": list(expected["sentences"]),
                "title": title,
                "sentences": translated_sentences,
                "language": language,
                "language_name": LANGUAGE_NAMES.get(language, "Unknown"),
                "source_match": source_match,
            }
        )

    title_to_ids: dict[str, list[str]] = defaultdict(list)
    for candidate in expected_context:
        title_to_ids[str(candidate["title"])].append(str(candidate["paragraph_id"]))
    expected_support: list[tuple[str, int]] = []
    for fact in source.get("supporting_facts") or []:
        ids = title_to_ids.get(str(fact["title"]), [])
        if len(ids) != 1:
            structural.add("source:supporting_title_not_unique")
            continue
        expected_support.append((ids[0], int(fact["sentence_id"])))

    raw_facts = raw.get("supporting_facts")
    if not isinstance(raw_facts, list):
        raw_facts = []
        structural.add("xhotpot:supporting_facts_not_list")
    supporting_facts: list[dict[str, Any]] = []
    observed_support: list[tuple[str, int]] = []
    for raw_fact in raw_facts:
        if not isinstance(raw_fact, Mapping):
            structural.add("xhotpot:malformed_supporting_fact")
            continue
        paragraph_id = str(raw_fact.get("paragraph_id", ""))
        try:
            sentence_id = int(raw_fact.get("sentence_id"))
        except (TypeError, ValueError):
            sentence_id = -1
            structural.add("xhotpot:invalid_support_sentence_id")
        index = _paragraph_index(paragraph_id)
        if index is None or index >= len(expected_context):
            source_title = ""
            in_bounds = False
            structural.add("xhotpot:invalid_support_paragraph_id")
        else:
            source_title = str(expected_context[index]["title"])
            in_bounds = 0 <= sentence_id < len(expected_context[index]["sentences"])
            if not in_bounds:
                structural.add("source:support_index_out_of_range")
        observed_support.append((paragraph_id, sentence_id))
        supporting_facts.append(
            {
                "paragraph_id": paragraph_id,
                "sentence_id": sentence_id,
                "source_title": source_title,
                "in_bounds": in_bounds,
            }
        )
    if observed_support != expected_support:
        structural.add("xhotpot:support_annotation_mismatch")

    if str(raw.get("question_type", "unknown")) != str(source["question_type"]):
        structural.add("xhotpot:question_type_mismatch")
    if str(raw.get("difficulty", "unknown")) != str(source["difficulty"]):
        structural.add("xhotpot:difficulty_mismatch")

    provenance = raw.get("provenance")
    if not isinstance(provenance, Mapping):
        provenance = {}
        structural.add("xhotpot:missing_provenance")
    if not str(provenance.get("assignment_manifest_sha256", "")):
        quality.add("provenance:assignment_manifest_hash_missing")

    status = "quarantined" if structural else "review_required" if quality else "accepted"
    record: dict[str, Any] = {
        "id": str(raw.get("id", "")),
        "source_id": source_id,
        "source_split": split,
        "source_position": source_position,
        "question": question,
        "answer": answer,
        "question_language": question_language,
        "question_language_name": LANGUAGE_NAMES.get(question_language, "Unknown"),
        "answer_language": answer_language,
        "answer_language_name": LANGUAGE_NAMES.get(answer_language, "Unknown"),
        "source_question": str(source["question"]),
        "source_answer": str(source["answer"]),
        "question_type": str(source["question_type"]),
        "difficulty": str(source["difficulty"]),
        "candidates": candidates,
        "supporting_facts": supporting_facts,
        "status": status,
        "structural_flags": sorted(structural),
        "quality_flags": sorted(quality),
        "source_record_sha256": source_checksum,
        "input_record_checksum_sha256": stored_checksum,
        "input_checksum_valid": checksum_valid,
        "release_record_sha256": "",
        "translation_model": str(provenance.get("translation_model", "")),
        "translation_revision": str(provenance.get("translation_revision", "")),
        "prompt_version": str(provenance.get("prompt_version", "")),
        "prompt_sha256": str(provenance.get("prompt_hash", "")),
        "assignment_version": str(provenance.get("assignment_version", "")),
        "assignment_manifest_sha256": str(provenance.get("assignment_manifest_sha256", "")),
        "generation_seed": int(provenance.get("seed", 0)),
        "decoding_json": canonical_json(provenance.get("decoding") or {}),
        "created_at": str(provenance.get("created_at", "")),
        "recorded_retry_count_unreliable": int(provenance.get("retry_count", 0)),
        "recorded_validation_status": str(provenance.get("validation_status", "")),
        "input_schema_version": str(provenance.get("schema_version", "")),
    }
    record["release_record_sha256"] = _release_checksum(record)
    return record


def _read_error_ledger(path: Path) -> dict[str, str]:
    ledger: dict[str, str] = {}
    for _, row in read_jsonl(path):
        source_id = str(row.get("source_id", ""))
        if not source_id or source_id in ledger:
            raise ValueError(f"Malformed or duplicate source ID in {path.name}")
        ledger[source_id] = str(row.get("error", ""))
    return ledger


def _missing_reason(message: str | None) -> str:
    if message is None:
        return "absent_without_final_error_record"
    lowered = message.lower()
    if "empty sentence" in lowered:
        return "inherited_source_empty_sentence"
    if "outside" in lowered and "supporting sentence" in lowered:
        return "inherited_source_support_index_out_of_range"
    return "logged_generation_error"


def ingest_v2_split(
    connection: sqlite3.Connection,
    *,
    split: str,
    path: Path,
) -> dict[str, Any]:
    expected = EXPECTED_V2_COUNTS[split]
    status_counts: Counter[str] = Counter()
    structural_flags: Counter[str] = Counter()
    quality_flags: Counter[str] = Counter()
    count = 0
    connection.execute(
        "CREATE TABLE IF NOT EXISTS records ("
        "source_id TEXT PRIMARY KEY, split TEXT NOT NULL, position INTEGER NOT NULL, "
        "payload TEXT NOT NULL, UNIQUE(split, position))"
    )
    for _, raw in read_jsonl(path):
        source_id = str(raw.get("source_id", ""))
        if not source_id:
            raise ValueError(f"{path.name} contains a row without source_id")
        position, source, source_checksum = _source_by_id(connection, source_id, split)
        normalized = normalize_v2_record(
            raw,
            split=split,
            source_position=position,
            source=source,
            source_checksum=source_checksum,
        )
        try:
            connection.execute(
                "INSERT INTO records VALUES (?, ?, ?, ?)",
                (source_id, split, position, canonical_json(normalized)),
            )
        except sqlite3.IntegrityError as error:
            raise ValueError(f"Duplicate generated source ID {source_id!r}") from error
        status_counts[normalized["status"]] += 1
        structural_flags.update(normalized["structural_flags"])
        quality_flags.update(normalized["quality_flags"])
        count += 1
    connection.commit()
    if count != expected:
        raise ValueError(f"Locked {split} V2 count {count:,} != {expected:,}")
    return {
        "rows": count,
        "status_counts": dict(sorted(status_counts.items())),
        "structural_flag_counts": dict(sorted(structural_flags.items())),
        "quality_flag_counts": dict(sorted(quality_flags.items())),
    }


def _schema_with_metadata(schema: pa.Schema, config_name: str) -> pa.Schema:
    return schema.with_metadata(
        {
            b"xhotpotqa_config": config_name.encode("utf-8"),
            b"xhotpotqa_builder": BUILD_VERSION.encode("utf-8"),
        }
    )


def _write_parquet(
    path: Path,
    rows: Sequence[Mapping[str, Any]],
    schema: pa.Schema,
    *,
    config_name: str,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    table = pa.Table.from_pylist(list(rows), schema=_schema_with_metadata(schema, config_name))
    pq.write_table(
        table,
        path,
        compression="zstd",
        use_dictionary=True,
        write_statistics=True,
        version="2.6",
    )


def write_v2_parquet_shards(
    connection: sqlite3.Connection,
    *,
    output_dir: Path,
    rows_per_shard: int,
) -> list[dict[str, Any]]:
    files: list[dict[str, Any]] = []
    for split in ("train", "validation"):
        row_count = int(
            connection.execute("SELECT COUNT(*) FROM records WHERE split=?", (split,)).fetchone()[0]
        )
        shard_count = math.ceil(row_count / rows_per_shard)
        cursor = connection.execute(
            "SELECT payload FROM records WHERE split=? ORDER BY position", (split,)
        )
        for shard_index in range(shard_count):
            rows: list[dict[str, Any]] = []
            for _ in range(rows_per_shard):
                row = cursor.fetchone()
                if row is None:
                    break
                rows.append(json.loads(row[0]))
            filename = f"{split}-{shard_index:05d}-of-{shard_count:05d}.parquet"
            path = output_dir / "data" / filename
            _write_parquet(path, rows, V2_SCHEMA, config_name=V2_CONFIG_NAME)
            files.append(
                {
                    "path": f"data/{filename}",
                    "split": split,
                    "rows": len(rows),
                    "size": path.stat().st_size,
                    "sha256": sha256_file(path),
                }
            )
    return files


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _manifest_fingerprint(manifest: Mapping[str, Any]) -> str:
    payload = dict(manifest)
    payload.pop("release_fingerprint_sha256", None)
    return sha256_text(canonical_json(payload))


def build_v2_release(
    *,
    output_dir: Path,
    paths: Mapping[str, Path],
    locked_inputs: Mapping[str, Mapping[str, Any]],
    rows_per_shard: int,
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=False)
    database = output_dir / ".build-index.sqlite3"
    connection = sqlite3.connect(database)
    try:
        source_counts = index_hotpot_sources(
            connection,
            train_path=paths["hotpot_train"],
            validation_path=paths["hotpot_validation"],
        )
        split_reports = {
            split: ingest_v2_split(connection, split=split, path=paths[f"v2_{split}"])
            for split in ("train", "validation")
        }
        ledgers = {
            split: _read_error_ledger(paths[f"v2_{split}_errors"])
            for split in ("train", "validation")
        }
        missing: list[dict[str, Any]] = []
        for source_id, split, position, checksum in connection.execute(
            "SELECT s.source_id, s.split, s.position, s.checksum "
            "FROM sources s LEFT JOIN records r ON s.source_id=r.source_id "
            "WHERE r.source_id IS NULL ORDER BY s.split, s.position"
        ):
            message = ledgers[str(split)].get(str(source_id))
            missing.append(
                {
                    "source_id": source_id,
                    "source_split": split,
                    "source_position": position,
                    "source_record_sha256": checksum,
                    "logged_error": message is not None,
                    "reason": _missing_reason(message),
                    "logged_error_message": message,
                }
            )
        missing_counts = Counter(row["source_split"] for row in missing)
        if missing_counts != Counter({"train": 228, "validation": 2}):
            raise ValueError(f"Unexpected missing-source counts: {dict(missing_counts)}")
        if sum(bool(row["logged_error"]) for row in missing) != 3:
            raise ValueError("Expected exactly three final logged source errors")

        missing_path = output_dir / "MISSING_SOURCE_MANIFEST.json"
        _write_json(
            missing_path,
            {
                "schema_version": "xhotpotqa-missing-sources/1.0",
                "release_policy": "never fabricate or silently drop a source",
                "total": len(missing),
                "logged_final_errors": sum(bool(row["logged_error"]) for row in missing),
                "absent_without_final_error_record": sum(
                    row["reason"] == "absent_without_final_error_record" for row in missing
                ),
                "records": missing,
            },
        )
        parquet_files = write_v2_parquet_shards(
            connection, output_dir=output_dir, rows_per_shard=rows_per_shard
        )
    finally:
        connection.close()
        database.unlink(missing_ok=True)

    released_counts = {split: report["rows"] for split, report in split_reports.items()}
    expected_total = sum(source_counts.values())
    released_total = sum(released_counts.values())
    manifest: dict[str, Any] = {
        "schema_version": "xhotpotqa-hf-release-manifest/1.0",
        "build_version": BUILD_VERSION,
        "config_name": V2_CONFIG_NAME,
        "release_status": "release_candidate_incomplete",
        "publication_gate": "not_canonical_until_missing_sources_are_regenerated_and_reaudited",
        "input_locks": dict(sorted(locked_inputs.items())),
        "source_counts": source_counts,
        "released_counts": released_counts,
        "missing_counts": dict(sorted(missing_counts.items())),
        "coverage": {
            "released": released_total,
            "expected": expected_total,
            "fraction": released_total / expected_total,
            "percent": 100.0 * released_total / expected_total,
        },
        "split_reports": split_reports,
        "missing_source_manifest": {
            "path": missing_path.name,
            "size": missing_path.stat().st_size,
            "sha256": sha256_file(missing_path),
        },
        "parquet_files": parquet_files,
        "schema": str(V2_SCHEMA),
        "reproducibility_caveats": [
            "assignment_manifest_sha256 is empty in every supplied V2 record",
            "recorded retry_count is unreliable under the historical concurrent run",
            "structural-passed never implied semantic or target-language validity",
        ],
        "tool_versions": {"pyarrow": pa.__version__, "ijson": ijson.__version__},
    }
    manifest["release_fingerprint_sha256"] = _manifest_fingerprint(manifest)
    _write_json(output_dir / "RELEASE_MANIFEST.json", manifest)
    return manifest


def _score_from_text(text: str) -> tuple[int | None, bool]:
    explicit = _SCORE_PATTERN.search(text)
    if explicit:
        return max(0, min(100, int(explicit.group(1)))), True
    integers = _INTEGER_PATTERN.findall(text)
    if integers:
        return max(0, min(100, int(integers[-1]))), False
    return None, False


def score_origin(row: Mapping[str, Any]) -> str:
    """Identify exactly where the historical parser obtained the stored score."""

    score = row.get("score")
    if not isinstance(score, int) or isinstance(score, bool) or not 0 <= score <= 100:
        raise ValueError("Judge row has no valid integer score")
    visible = str(row.get("judge_text") or "")
    reasoning = str(row.get("reasoning") or "")
    visible_score, visible_explicit = _score_from_text(visible)
    if visible_score is not None:
        if visible_score != score:
            raise ValueError("Visible judge output does not match stored score")
        return "visible_explicit" if visible_explicit else "visible_integer_fallback"
    reasoning_score, reasoning_explicit = _score_from_text(reasoning)
    if reasoning_score is None or reasoning_score != score:
        raise ValueError("Reasoning fallback does not match stored score")
    return "reasoning_explicit" if reasoning_explicit else "reasoning_integer_fallback"


def _judge_explanation(text: str) -> str:
    return _FINAL_SCORE_LINE.sub("", text.strip()).strip()


def sanitize_judge_row(
    row: Mapping[str, Any],
    *,
    dataset_version: str,
    dataset_revision: str,
    dataset_revision_status: str,
    run_group: str,
    raw_artifact_sha256: str,
    raw_line_number: int,
) -> dict[str, Any]:
    if row.get("error") not in (None, ""):
        raise ValueError("Final judge release cannot contain failed rows")
    unit = str(row.get("unit", ""))
    if unit not in EXPECTED_JUDGE_UNIT_COUNTS:
        raise ValueError(f"Unknown judge unit {unit!r}")
    language = str(row.get("language", ""))
    if language not in EXPECTED_TARGET_LANGUAGES:
        raise ValueError(f"Unknown target language {language!r}")
    source_text = str(row.get("source_text", ""))
    candidate_text = str(row.get("candidate_text", ""))
    if not source_text or not candidate_text:
        raise ValueError("Final judge row has empty source or candidate text")
    paragraph_id = row.get("paragraph_id")
    if unit == "paragraph" and not paragraph_id:
        raise ValueError("Paragraph judge row has no paragraph_id")
    if unit != "paragraph":
        paragraph_id = None
    identity = {
        "dataset_version": dataset_version,
        "instance_id": str(row.get("instance_id", "")),
        "unit": unit,
        "paragraph_id": paragraph_id,
    }
    visible = str(row.get("judge_text") or "")
    explanation = _judge_explanation(visible)
    prompt_hash = JUDGE_ANSWER_PROMPT_SHA256 if unit == "answer" else JUDGE_GENERAL_PROMPT_SHA256
    return {
        "judge_record_id": sha256_text(canonical_json(identity)),
        "dataset_version": dataset_version,
        "dataset_revision": dataset_revision,
        "dataset_revision_status": dataset_revision_status,
        "instance_id": identity["instance_id"],
        "source_id": str(row.get("source_id", "")),
        "source_split": str(row.get("source_split", "")),
        "target_language": language,
        "target_language_name": LANGUAGE_NAMES[language],
        "unit": unit,
        "paragraph_id": paragraph_id,
        "score": int(row["score"]),
        "score_origin": score_origin(row),
        "judge_explanation": explanation,
        "judge_explanation_available": bool(explanation),
        "source_text_sha256": sha256_text(source_text),
        "candidate_text_sha256": sha256_text(candidate_text),
        "requested_judge_model": JUDGE_REQUESTED_MODEL,
        "resolved_judge_revision": None,
        "model_identity_status": "requested_alias_only_provider_revision_not_recorded",
        "judge_prompt_version": JUDGE_PROMPT_VERSION,
        "judge_prompt_sha256": prompt_hash,
        "sampling_seed": JUDGE_SAMPLE_SEED,
        "run_group": run_group,
        "raw_artifact_sha256": raw_artifact_sha256,
        "raw_line_number": raw_line_number,
    }


def load_sanitized_judge_v1(path: Path) -> list[dict[str, Any]]:
    lock = INPUT_LOCKS["judge_v1"]
    records = [
        sanitize_judge_row(
            row,
            dataset_version="v1_audited",
            dataset_revision="52b8bee41ff2bb0d41cd400ff5646c0e800b5127",
            dataset_revision_status="retrospective_candidate_not_recorded_by_judge_run",
            run_group="v1_full",
            raw_artifact_sha256=lock.sha256,
            raw_line_number=line_number,
        )
        for line_number, row in read_jsonl(path)
    ]
    validate_judge_records(records)
    return records


def load_sanitized_judge_v2(
    mixed_path: Path, answer_path: Path
) -> tuple[list[dict[str, Any]], int]:
    mixed_lock = INPUT_LOCKS["judge_v2_mixed"]
    answer_lock = INPUT_LOCKS["judge_v2_answers"]
    records: list[dict[str, Any]] = []
    discarded_answers = 0
    v2_revision = sha256_text(
        canonical_json(
            {
                "train": INPUT_LOCKS["v2_train"].sha256,
                "validation": INPUT_LOCKS["v2_validation"].sha256,
            }
        )
    )
    for line_number, row in read_jsonl(mixed_path):
        if row.get("unit") == "answer":
            discarded_answers += 1
            continue
        records.append(
            sanitize_judge_row(
                row,
                dataset_version="v2_audited_rc1",
                dataset_revision=v2_revision,
                dataset_revision_status="locked_raw_jsonl_pair_fingerprint",
                run_group="v2_paragraph_question_retry_complete",
                raw_artifact_sha256=mixed_lock.sha256,
                raw_line_number=line_number,
            )
        )
    for line_number, row in read_jsonl(answer_path):
        if row.get("unit") != "answer":
            raise ValueError("Dedicated V2 answer artifact contains a non-answer unit")
        records.append(
            sanitize_judge_row(
                row,
                dataset_version="v2_audited_rc1",
                dataset_revision=v2_revision,
                dataset_revision_status="locked_raw_jsonl_pair_fingerprint",
                run_group="v2_answer_dedicated_prompt",
                raw_artifact_sha256=answer_lock.sha256,
                raw_line_number=line_number,
            )
        )
    if discarded_answers != EXPECTED_DISCARDED_V2_MIXED_ANSWERS:
        raise ValueError(
            "Expected to discard "
            f"{EXPECTED_DISCARDED_V2_MIXED_ANSWERS} invalid V2 answer rows, "
            f"got {discarded_answers}"
        )
    validate_judge_records(records)
    return records, discarded_answers


def validate_judge_records(records: Sequence[Mapping[str, Any]]) -> None:
    if len(records) != 2_760:
        raise ValueError(f"Judge release count {len(records):,} != 2,760")
    ids = [str(row["judge_record_id"]) for row in records]
    if len(ids) != len(set(ids)):
        raise ValueError("Judge release contains duplicate IDs")
    unit_counts = Counter(str(row["unit"]) for row in records)
    if unit_counts != Counter(EXPECTED_JUDGE_UNIT_COUNTS):
        raise ValueError(f"Unexpected judge unit counts: {dict(unit_counts)}")
    language_counts = Counter(str(row["target_language"]) for row in records)
    expected_languages = Counter({language: 120 for language in EXPECTED_TARGET_LANGUAGES})
    if language_counts != expected_languages:
        raise ValueError("Judge release is not 120 units per target language")
    for language in EXPECTED_TARGET_LANGUAGES:
        per_unit = Counter(
            str(row["unit"]) for row in records if row["target_language"] == language
        )
        if per_unit != Counter({"paragraph": 80, "question": 20, "answer": 20}):
            raise ValueError(f"Unexpected unit balance for {language}: {dict(per_unit)}")


def _score_summary(scores: Sequence[int]) -> dict[str, Any]:
    return {
        "count": len(scores),
        "mean": statistics.fmean(scores),
        "median": statistics.median(scores),
        "standard_deviation": statistics.stdev(scores),
        "minimum": min(scores),
        "maximum": max(scores),
        "below_60": sum(score < 60 for score in scores),
        "below_80": sum(score < 80 for score in scores),
        "at_least_90": sum(score >= 90 for score in scores),
    }


def summarize_judge_records(records: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    by_unit = {
        unit: _score_summary([int(row["score"]) for row in records if row["unit"] == unit])
        for unit in EXPECTED_JUDGE_UNIT_COUNTS
    }
    by_language: dict[str, Any] = {}
    for language in EXPECTED_TARGET_LANGUAGES:
        language_rows = [row for row in records if row["target_language"] == language]
        by_language[language] = {
            "language_name": LANGUAGE_NAMES[language],
            "overall": _score_summary([int(row["score"]) for row in language_rows]),
            "by_unit": {
                unit: _score_summary(
                    [int(row["score"]) for row in language_rows if row["unit"] == unit]
                )
                for unit in EXPECTED_JUDGE_UNIT_COUNTS
            },
        }
    return {
        "overall": _score_summary([int(row["score"]) for row in records]),
        "by_unit": by_unit,
        "by_language": by_language,
        "by_source_split": dict(sorted(Counter(row["source_split"] for row in records).items())),
        "score_origin_counts": dict(
            sorted(Counter(row["score_origin"] for row in records).items())
        ),
    }


def _percentile(sorted_values: Sequence[float], probability: float) -> float:
    if not sorted_values:
        raise ValueError("Cannot calculate percentile of empty values")
    position = (len(sorted_values) - 1) * probability
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return float(sorted_values[lower])
    fraction = position - lower
    return float(sorted_values[lower] * (1.0 - fraction) + sorted_values[upper] * fraction)


def stratified_bootstrap(
    records: Sequence[Mapping[str, Any]],
    *,
    replicates: int,
    seed: int,
) -> dict[str, Any]:
    """Bootstrap within language/unit strata and return means plus distributions."""

    if replicates < 100:
        raise ValueError("At least 100 bootstrap replicates are required")
    strata: dict[tuple[str, str], list[int]] = defaultdict(list)
    for row in records:
        strata[(str(row["target_language"]), str(row["unit"]))].append(int(row["score"]))
    rng = random.Random(seed)
    totals = [0.0] * replicates
    unit_totals = {unit: [0.0] * replicates for unit in EXPECTED_JUDGE_UNIT_COUNTS}
    unit_counts = Counter()
    total_count = 0
    for (_, unit), scores in sorted(strata.items()):
        unit_counts[unit] += len(scores)
        total_count += len(scores)
        for index in range(replicates):
            sample_sum = float(sum(rng.choices(scores, k=len(scores))))
            totals[index] += sample_sum
            unit_totals[unit][index] += sample_sum
    distributions = {
        "overall": [value / total_count for value in totals],
        **{
            unit: [value / unit_counts[unit] for value in unit_totals[unit]]
            for unit in EXPECTED_JUDGE_UNIT_COUNTS
        },
    }
    intervals: dict[str, Any] = {}
    observed_summary = summarize_judge_records(records)
    for label, values in distributions.items():
        ordered = sorted(values)
        observed = (
            observed_summary["overall"]["mean"]
            if label == "overall"
            else observed_summary["by_unit"][label]["mean"]
        )
        intervals[label] = {
            "observed_mean": observed,
            "lower_95": _percentile(ordered, 0.025),
            "upper_95": _percentile(ordered, 0.975),
        }
    return {
        "method": "within-language-by-unit nonparametric bootstrap",
        "replicates": replicates,
        "seed": seed,
        "percentile_interpolation": "linear",
        "intervals": intervals,
        "_distributions": distributions,
    }


def independent_bootstrap_difference(
    v1_bootstrap: Mapping[str, Any], v2_bootstrap: Mapping[str, Any]
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "design": "independent_stratified_samples_not_paired",
        "warning": "These intervals do not account for judge-model uncertainty.",
        "intervals": {},
    }
    v1_distributions = v1_bootstrap["_distributions"]
    v2_distributions = v2_bootstrap["_distributions"]
    for label in ("overall", *EXPECTED_JUDGE_UNIT_COUNTS):
        differences = sorted(
            right - left
            for left, right in zip(v1_distributions[label], v2_distributions[label], strict=True)
        )
        result["intervals"][label] = {
            "observed_difference": (
                v2_bootstrap["intervals"][label]["observed_mean"]
                - v1_bootstrap["intervals"][label]["observed_mean"]
            ),
            "lower_95": _percentile(differences, 0.025),
            "upper_95": _percentile(differences, 0.975),
        }
    return result


def _public_bootstrap(bootstrap: Mapping[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in bootstrap.items() if not key.startswith("_")}


def _write_language_csv(path: Path, summary: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(
            [
                "language",
                "language_name",
                "paragraph_count",
                "paragraph_mean",
                "question_count",
                "question_mean",
                "answer_count",
                "answer_mean",
                "overall_count",
                "overall_mean",
            ]
        )
        for language in EXPECTED_TARGET_LANGUAGES:
            item = summary["by_language"][language]
            writer.writerow(
                [
                    language,
                    item["language_name"],
                    item["by_unit"]["paragraph"]["count"],
                    f"{item['by_unit']['paragraph']['mean']:.8f}",
                    item["by_unit"]["question"]["count"],
                    f"{item['by_unit']['question']['mean']:.8f}",
                    item["by_unit"]["answer"]["count"],
                    f"{item['by_unit']['answer']['mean']:.8f}",
                    item["overall"]["count"],
                    f"{item['overall']['mean']:.8f}",
                ]
            )


def build_judge_release(
    *,
    output_dir: Path,
    config_name: str,
    records: Sequence[Mapping[str, Any]],
    summary: Mapping[str, Any],
    bootstrap: Mapping[str, Any],
    input_locks: Mapping[str, Mapping[str, Any]],
    discarded_invalid_answer_rows: int,
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=False)
    data_path = output_dir / "data" / "audit-00000-of-00001.parquet"
    _write_parquet(data_path, records, JUDGE_SCHEMA, config_name=config_name)
    summary_path = output_dir / "tables" / "SUMMARY.json"
    bootstrap_path = output_dir / "tables" / "BOOTSTRAP.json"
    language_path = output_dir / "tables" / "BY_LANGUAGE.csv"
    _write_json(summary_path, summary)
    _write_json(bootstrap_path, _public_bootstrap(bootstrap))
    _write_language_csv(language_path, summary)
    artifacts = []
    for path in (data_path, summary_path, bootstrap_path, language_path):
        artifacts.append(
            {
                "path": path.relative_to(output_dir).as_posix(),
                "size": path.stat().st_size,
                "sha256": sha256_file(path),
                **({"rows": len(records)} if path == data_path else {}),
            }
        )
    manifest: dict[str, Any] = {
        "schema_version": "xhotpotqa-judge-release-manifest/1.0",
        "build_version": BUILD_VERSION,
        "config_name": config_name,
        "rows": len(records),
        "target_languages": len(EXPECTED_TARGET_LANGUAGES),
        "sample_design": {
            "paragraph_per_language": 80,
            "question_per_language": 20,
            "answer_per_language": 20,
        },
        "sampling_seed": JUDGE_SAMPLE_SEED,
        "requested_judge_model": JUDGE_REQUESTED_MODEL,
        "resolved_judge_revision": None,
        "model_identity_status": "requested_alias_only_provider_revision_not_recorded",
        "prompt_version": JUDGE_PROMPT_VERSION,
        "prompt_hashes": {
            "paragraph_question": JUDGE_GENERAL_PROMPT_SHA256,
            "answer": JUDGE_ANSWER_PROMPT_SHA256,
        },
        "hidden_reasoning_released": False,
        "source_candidate_text_released": False,
        "discarded_invalid_partial_answer_rows": discarded_invalid_answer_rows,
        "input_locks": dict(sorted(input_locks.items())),
        "summary": summary,
        "bootstrap": _public_bootstrap(bootstrap),
        "artifacts": artifacts,
        "schema": str(JUDGE_SCHEMA),
        "limitations": [
            "single LLM judge with no human calibration",
            "provider-resolved judge revision was not recorded",
            "temperature zero and a seed do not guarantee endpoint determinism",
            "scores derived from reasoning fallback are explicitly labeled",
        ],
    }
    manifest["release_fingerprint_sha256"] = _manifest_fingerprint(manifest)
    _write_json(output_dir / "RELEASE_MANIFEST.json", manifest)
    return manifest


def _copy_comparison(
    path: Path,
    *,
    v1_summary: Mapping[str, Any],
    v2_summary: Mapping[str, Any],
    difference: Mapping[str, Any],
) -> None:
    _write_json(
        path,
        {
            "schema_version": "xhotpotqa-judge-descriptive-comparison/1.0",
            "design": "independent_language_balanced_samples",
            "paired": False,
            "warning": (
                "Do not interpret these descriptive differences as paired or causal "
                "translator effects."
            ),
            "v1": {
                "overall_mean": v1_summary["overall"]["mean"],
                "by_unit": {
                    unit: v1_summary["by_unit"][unit]["mean"] for unit in EXPECTED_JUDGE_UNIT_COUNTS
                },
            },
            "v2": {
                "overall_mean": v2_summary["overall"]["mean"],
                "by_unit": {
                    unit: v2_summary["by_unit"][unit]["mean"] for unit in EXPECTED_JUDGE_UNIT_COUNTS
                },
            },
            "independent_bootstrap_difference": difference,
        },
    )


def build_all(args: argparse.Namespace) -> Path:
    paths = {
        "hotpot_train": args.hotpot_train,
        "hotpot_validation": args.hotpot_validation,
        "v2_train": args.v2_train,
        "v2_validation": args.v2_validation,
        "v2_train_errors": args.v2_train_errors,
        "v2_validation_errors": args.v2_validation_errors,
        "judge_v1": args.judge_v1,
        "judge_v2_mixed": args.judge_v2_mixed,
        "judge_v2_answers": args.judge_v2_answers,
    }
    locked_inputs = {
        role: assert_locked_input(path, INPUT_LOCKS[role]) for role, path in paths.items()
    }
    output_dir = args.output_dir.resolve()
    if output_dir.exists():
        raise FileExistsError(f"Refusing to overwrite existing output: {output_dir}")
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{output_dir.name}.", dir=str(output_dir.parent)))
    try:
        build_v2_release(
            output_dir=staging / V2_CONFIG_NAME,
            paths=paths,
            locked_inputs={
                role: locked_inputs[role]
                for role in (
                    "hotpot_train",
                    "hotpot_validation",
                    "v2_train",
                    "v2_validation",
                    "v2_train_errors",
                    "v2_validation_errors",
                )
            },
            rows_per_shard=args.rows_per_shard,
        )
        judge_v1 = load_sanitized_judge_v1(paths["judge_v1"])
        judge_v2, discarded_answers = load_sanitized_judge_v2(
            paths["judge_v2_mixed"], paths["judge_v2_answers"]
        )
        v1_summary = summarize_judge_records(judge_v1)
        v2_summary = summarize_judge_records(judge_v2)
        v1_bootstrap = stratified_bootstrap(
            judge_v1, replicates=args.bootstrap_replicates, seed=BOOTSTRAP_SEED
        )
        v2_bootstrap = stratified_bootstrap(
            judge_v2, replicates=args.bootstrap_replicates, seed=BOOTSTRAP_SEED + 1
        )
        difference = independent_bootstrap_difference(v1_bootstrap, v2_bootstrap)
        build_judge_release(
            output_dir=staging / JUDGE_V1_CONFIG_NAME,
            config_name=JUDGE_V1_CONFIG_NAME,
            records=judge_v1,
            summary=v1_summary,
            bootstrap=v1_bootstrap,
            input_locks={"judge_v1": locked_inputs["judge_v1"]},
            discarded_invalid_answer_rows=0,
        )
        build_judge_release(
            output_dir=staging / JUDGE_V2_CONFIG_NAME,
            config_name=JUDGE_V2_CONFIG_NAME,
            records=judge_v2,
            summary=v2_summary,
            bootstrap=v2_bootstrap,
            input_locks={
                role: locked_inputs[role]
                for role in (
                    "v2_train",
                    "v2_validation",
                    "judge_v2_mixed",
                    "judge_v2_answers",
                )
            },
            discarded_invalid_answer_rows=discarded_answers,
        )
        comparison_path = staging / "V1_V2_DESCRIPTIVE_COMPARISON.json"
        _copy_comparison(
            comparison_path,
            v1_summary=v1_summary,
            v2_summary=v2_summary,
            difference=difference,
        )
        for config in (JUDGE_V1_CONFIG_NAME, JUDGE_V2_CONFIG_NAME):
            destination = staging / config / "tables" / comparison_path.name
            shutil.copyfile(comparison_path, destination)
        root_manifest: dict[str, Any] = {
            "schema_version": "xhotpotqa-rc1-release-set/1.0",
            "build_version": BUILD_VERSION,
            "configs": [V2_CONFIG_NAME, JUDGE_V1_CONFIG_NAME, JUDGE_V2_CONFIG_NAME],
            "comparison": {
                "path": comparison_path.name,
                "size": comparison_path.stat().st_size,
                "sha256": sha256_file(comparison_path),
            },
            "publication_performed": False,
        }
        root_manifest["release_fingerprint_sha256"] = _manifest_fingerprint(root_manifest)
        _write_json(staging / "RELEASE_SET_MANIFEST.json", root_manifest)
        os.replace(staging, output_dir)
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    return output_dir


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hotpot-train", type=Path, required=True)
    parser.add_argument("--hotpot-validation", type=Path, required=True)
    parser.add_argument("--v2-train", type=Path, required=True)
    parser.add_argument("--v2-validation", type=Path, required=True)
    parser.add_argument("--v2-train-errors", type=Path, required=True)
    parser.add_argument("--v2-validation-errors", type=Path, required=True)
    parser.add_argument("--judge-v1", type=Path, required=True)
    parser.add_argument("--judge-v2-mixed", type=Path, required=True)
    parser.add_argument("--judge-v2-answers", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--rows-per-shard", type=int, default=5_000)
    parser.add_argument("--bootstrap-replicates", type=int, default=10_000)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.rows_per_shard < 1:
        raise ValueError("--rows-per-shard must be positive")
    output = build_all(args)
    print(f"Built locked RC1 release set at {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
