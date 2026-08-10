"""Deterministic construction of the parallel XHotpotQA+ views."""

from __future__ import annotations

import json
import os
import tempfile
from collections.abc import Iterable, Iterator, Mapping
from dataclasses import dataclass, replace
from pathlib import Path
from typing import cast

from xhotpotqa.data.checksum import compute_checksum, with_checksum
from xhotpotqa.data.io import read_jsonl, write_instances
from xhotpotqa.data.models import XHotpotInstance
from xhotpotqa.languages import LANGUAGE_CODES, require_language

LANGUAGES_PER_INSTANCE = len(LANGUAGE_CODES)
EXPECTED_PLUS_SPLIT_COUNTS = {
    "train": 15_661 * LANGUAGES_PER_INSTANCE,
    "validation": 7_405 * LANGUAGES_PER_INSTANCE,
}


@dataclass(frozen=True, slots=True)
class QATranslation:
    """One question--answer translation for a canonical source record."""

    question: str
    answer: str

    def validate(self, *, source_id: str, language: str) -> None:
        require_language(language)
        if not self.question.strip() or not self.answer.strip():
            raise ValueError(
                f"Source {source_id!r}, language {language!r} has an empty question or answer"
            )


QATranslationSet = Mapping[str, QATranslation]
QATranslationMap = Mapping[str, QATranslationSet]


@dataclass(frozen=True, slots=True)
class ExpansionReport:
    """Cardinality summary returned after an atomic expansion write."""

    base_count: int
    variant_count: int
    languages_per_instance: int = LANGUAGES_PER_INSTANCE


def variant_id(base_id: str, language: str) -> str:
    """Return the stable ID for a question--answer language view."""

    if not base_id:
        raise ValueError("Base instance ID must be non-empty")
    require_language(language)
    return f"{base_id}--qa-{language}"


def load_qa_translations(path: Path) -> dict[str, dict[str, QATranslation]]:
    """Load the documented source-ID keyed JSON or JSONL translation mapping."""

    if path.suffix.lower() == ".jsonl":
        return _load_jsonl_translation_map(path)

    try:
        raw_payload: object = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ValueError(f"Invalid JSON in {path}: {error}") from error
    payload = _require_object(raw_payload, context=str(path))
    return _parse_source_mapping(payload)


def expand_instance(
    base: XHotpotInstance,
    translations: QATranslationSet,
) -> tuple[XHotpotInstance, ...]:
    """Create all 24 QA-language views while preserving the evidence payload."""

    base.validate()
    if not base.checksum or base.checksum != compute_checksum(base):
        raise ValueError(f"Base instance {base.id!r} has a missing or invalid checksum")
    _validate_translation_set(base.source_id, translations)

    variants: list[XHotpotInstance] = []
    for language in LANGUAGE_CODES:
        translation = translations[language]
        variant = replace(
            base,
            id=variant_id(base.id, language),
            question=translation.question,
            answer=translation.answer,
            question_language=language,
            answer_language=language,
            checksum="",
        )
        variant.validate()
        variants.append(with_checksum(variant))
    return tuple(variants)


def expand_instances(
    bases: Iterable[XHotpotInstance],
    translations_by_source: QATranslationMap,
    *,
    expected_base_count: int | None = None,
    expected_split: str | None = None,
) -> Iterator[XHotpotInstance]:
    """Expand base instances in input order and languages in canonical inventory order."""

    if expected_base_count is not None and expected_base_count < 0:
        raise ValueError("Expected base count cannot be negative")
    if expected_split is not None and expected_split not in EXPECTED_PLUS_SPLIT_COUNTS:
        raise ValueError(f"Unsupported split: {expected_split!r}")
    for source_id in sorted(translations_by_source):
        if not source_id:
            raise ValueError("Translation mapping contains an empty source ID")
        _validate_translation_set(source_id, translations_by_source[source_id])

    seen_base_ids: set[str] = set()
    seen_source_ids: set[str] = set()
    base_count = 0
    for base in bases:
        if base.id in seen_base_ids:
            raise ValueError(f"Duplicate base instance ID: {base.id!r}")
        if base.source_id in seen_source_ids:
            raise ValueError(f"Duplicate base source ID: {base.source_id!r}")
        if expected_split is not None and base.source_split != expected_split:
            raise ValueError(
                f"Base {base.id!r} belongs to {base.source_split!r}, expected {expected_split!r}"
            )
        try:
            translations = translations_by_source[base.source_id]
        except KeyError as error:
            raise ValueError(f"Missing translations for source ID {base.source_id!r}") from error

        seen_base_ids.add(base.id)
        seen_source_ids.add(base.source_id)
        base_count += 1
        yield from expand_instance(base, translations)

    unused_source_ids = sorted(set(translations_by_source) - seen_source_ids)
    if unused_source_ids:
        preview = ", ".join(repr(source_id) for source_id in unused_source_ids[:5])
        suffix = " ..." if len(unused_source_ids) > 5 else ""
        raise ValueError(f"Translations have no matching base source ID: {preview}{suffix}")
    if expected_base_count is not None and base_count != expected_base_count:
        raise ValueError(f"Expected {expected_base_count:,} base records, found {base_count:,}")


def write_plus_instances(
    output_path: Path,
    bases: Iterable[XHotpotInstance],
    translations_by_source: QATranslationMap,
    *,
    expected_base_count: int | None = None,
    expected_split: str | None = None,
) -> ExpansionReport:
    """Validate and atomically write an XHotpotQA+ JSONL file."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{output_path.name}.", suffix=".tmp", dir=output_path.parent
    )
    os.close(descriptor)
    temporary_path = Path(temporary_name)
    try:
        variants = expand_instances(
            bases,
            translations_by_source,
            expected_base_count=expected_base_count,
            expected_split=expected_split,
        )
        variant_count = write_instances(temporary_path, variants)
        if variant_count % LANGUAGES_PER_INSTANCE:
            raise AssertionError("Expansion produced an incomplete language group")
        base_count = variant_count // LANGUAGES_PER_INSTANCE
        expected_variant_count = (
            expected_base_count * LANGUAGES_PER_INSTANCE
            if expected_base_count is not None
            else base_count * LANGUAGES_PER_INSTANCE
        )
        if variant_count != expected_variant_count:
            raise ValueError(
                f"Expected {expected_variant_count:,} variants, found {variant_count:,}"
            )
        os.replace(temporary_path, output_path)
    except BaseException:
        temporary_path.unlink(missing_ok=True)
        raise
    return ExpansionReport(base_count=base_count, variant_count=variant_count)


def _load_jsonl_translation_map(path: Path) -> dict[str, dict[str, QATranslation]]:
    translations_by_source: dict[str, dict[str, QATranslation]] = {}
    for row_number, row in enumerate(read_jsonl(path), start=1):
        extra_fields = set(row) - {"source_id", "translations"}
        if extra_fields:
            raise ValueError(f"Unexpected field(s) at {path}:{row_number}: {sorted(extra_fields)}")
        source_id = row.get("source_id")
        if not isinstance(source_id, str) or not source_id:
            raise ValueError(f"Expected a non-empty source_id at {path}:{row_number}")
        if source_id in translations_by_source:
            raise ValueError(
                f"Duplicate translation source ID at {path}:{row_number}: {source_id!r}"
            )
        translation_payload = _require_object(
            row.get("translations"), context=f"{path}:{row_number}.translations"
        )
        translations_by_source[source_id] = _parse_translation_set(source_id, translation_payload)
    return translations_by_source


def _parse_source_mapping(
    payload: Mapping[str, object],
) -> dict[str, dict[str, QATranslation]]:
    translations_by_source: dict[str, dict[str, QATranslation]] = {}
    for source_id, raw_translations in payload.items():
        if not source_id:
            raise ValueError("Translation mapping contains an empty source ID")
        translation_payload = _require_object(raw_translations, context=f"source {source_id!r}")
        translations_by_source[source_id] = _parse_translation_set(source_id, translation_payload)
    return translations_by_source


def _parse_translation_set(
    source_id: str,
    payload: Mapping[str, object],
) -> dict[str, QATranslation]:
    translations: dict[str, QATranslation] = {}
    for language, raw_translation in payload.items():
        translation_payload = _require_object(
            raw_translation, context=f"source {source_id!r}, language {language!r}"
        )
        extra_fields = set(translation_payload) - {"question", "answer"}
        if extra_fields:
            raise ValueError(
                f"Unexpected translation field(s) for source {source_id!r}, "
                f"language {language!r}: {sorted(extra_fields)}"
            )
        question = translation_payload.get("question")
        answer = translation_payload.get("answer")
        if not isinstance(question, str) or not isinstance(answer, str):
            raise ValueError(
                f"Source {source_id!r}, language {language!r} requires string "
                "question and answer fields"
            )
        translations[language] = QATranslation(question=question, answer=answer)
    _validate_translation_set(source_id, translations)
    return translations


def _validate_translation_set(source_id: str, translations: QATranslationSet) -> None:
    expected_languages = set(LANGUAGE_CODES)
    actual_languages = set(translations)
    missing = sorted(expected_languages - actual_languages)
    extra = sorted(actual_languages - expected_languages)
    if missing or extra:
        raise ValueError(
            f"Source {source_id!r} must contain exactly {LANGUAGES_PER_INSTANCE} languages; "
            f"missing={missing}, extra={extra}"
        )
    for language in LANGUAGE_CODES:
        translation = translations[language]
        if not isinstance(translation, QATranslation):
            raise TypeError(f"Source {source_id!r}, language {language!r} is not a QATranslation")
        translation.validate(source_id=source_id, language=language)


def _require_object(value: object, *, context: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping) or any(not isinstance(key, str) for key in value):
        raise ValueError(f"Expected a JSON object at {context}")
    return cast(Mapping[str, object], value)
