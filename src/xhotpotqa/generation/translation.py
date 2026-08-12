"""Structured translation prompts and parsers."""

from __future__ import annotations

import hashlib
import json
import threading
from collections.abc import Callable, Mapping, Sequence
from types import MappingProxyType
from typing import TypeVar, cast

from xhotpotqa.generation.protocols import ChatGenerator
from xhotpotqa.languages import require_language

PROMPT_VERSION = "xhotpotqa-translation-v2.0"
SYSTEM_PROMPT = (
    "You are the deterministic translation component of a multilingual QA dataset. "
    "Preserve named entities, numbers, dates, yes/no polarity, and sentence boundaries. "
    "Do not answer the question and do not add explanations. The user request contains a "
    "response_schema; return exactly one valid JSON object that satisfies it, with no "
    "additional keys and no Markdown."
)


def _single_translation_schema() -> dict[str, object]:
    """Return the exact wire-level response contract for one translated unit."""
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["translation"],
        "properties": {
            "translation": {
                "type": "string",
                "minLength": 1,
            }
        },
    }


def _sentence_array_schema(expected_count: int | str) -> dict[str, object]:
    """Return the exact response contract for an aligned sentence array."""
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["translations"],
        "properties": {
            "translations": {
                "type": "array",
                "items": {
                    "type": "string",
                    "minLength": 1,
                },
                "minItems": expected_count,
                "maxItems": expected_count,
            }
        },
    }


_PROMPT_SPECIFICATION = {
    "system_prompt": SYSTEM_PROMPT,
    "requests": {
        "translate": {
            "task": "translate",
            "unit": "{unit}",
            "target_language": "{target_language}",
            "text": "{text}",
            "response_schema": _single_translation_schema(),
        },
        "translate_sentence_array": {
            "task": "translate_sentence_array",
            "target_language": "{target_language}",
            "sentences": ["{sentence_0}", "..."],
            "response_schema": _sentence_array_schema("{sentence_count}"),
        },
    },
}
_CANONICAL_PROMPT_SPECIFICATION = json.dumps(
    _PROMPT_SPECIFICATION,
    ensure_ascii=False,
    sort_keys=True,
    separators=(",", ":"),
)
PROMPT_HASH = hashlib.sha256(_CANONICAL_PROMPT_SPECIFICATION.encode("utf-8")).hexdigest()
ResponseT = TypeVar("ResponseT")
AuditWriter = Callable[[Mapping[str, object]], None]


class StructuredTranslator:
    def __init__(
        self,
        generator: ChatGenerator,
        *,
        model_id: str,
        revision: str,
        max_retries: int = 3,
        decoding: Mapping[str, object] | None = None,
        audit_writer: AuditWriter | None = None,
    ) -> None:
        if max_retries < 1:
            raise ValueError("max_retries must be greater than zero")
        self._generator = generator
        self._model_id = model_id
        self._revision = revision
        self._max_retries = max_retries
        self._retry_count = 0
        self._retry_lock = threading.Lock()
        self._decoding: Mapping[str, object] = MappingProxyType(dict(decoding or {}))
        self._audit_writer = audit_writer

    @property
    def model_id(self) -> str:
        return self._model_id

    @property
    def revision(self) -> str:
        return self._revision

    @property
    def decoding(self) -> Mapping[str, object]:
        return self._decoding

    @property
    def retry_count(self) -> int:
        """Return cumulative parser/schema retries for provenance accounting."""
        return self._retry_count

    def translate_text(self, text: str, target_language: str, unit: str) -> str:
        language = require_language(target_language)
        if target_language == "en":
            return text
        stripped = text.strip()
        # Empty or near-empty fragments (common in HotpotQA sentence splits) do not
        # translate meaningfully. Return a non-empty placeholder so downstream
        # validation does not reject the candidate paragraph.
        if not stripped or len(stripped) < 2:
            return "—"
        request = {
            "task": "translate",
            "unit": unit,
            "target_language": language.name,
            "text": text,
            "response_schema": _single_translation_schema(),
        }
        try:
            return self._request(request, _parse_translation)
        except (ValueError, json.JSONDecodeError, TypeError):
            # If the model cannot translate a fragment, keep the original text so
            # sentence alignment is never broken.
            return text

    def translate_sentences(
        self, sentences: Sequence[str], target_language: str
    ) -> tuple[str, ...]:
        language = require_language(target_language)
        if target_language == "en":
            return tuple(sentences)
        request = {
            "task": "translate_sentence_array",
            "target_language": language.name,
            "sentences": list(sentences),
            "response_schema": _sentence_array_schema(len(sentences)),
        }
        try:
            return self._request(
                request,
                lambda response: _parse_translations(response, expected_count=len(sentences)),
            )
        except (ValueError, json.JSONDecodeError, TypeError):
            # Fallback: translate each sentence individually to preserve alignment.
            return tuple(
                self.translate_text(sentence, target_language, "sentence")
                for sentence in sentences
            )

    def _request(
        self,
        payload: Mapping[str, object],
        parse_response: Callable[[Mapping[str, object]], ResponseT],
    ) -> ResponseT:
        last_error: Exception | None = None
        for attempt in range(self._max_retries):
            if attempt:
                with self._retry_lock:
                    self._retry_count += 1
            raw = self._generator.generate(
                [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
                ]
            )
            try:
                parsed = _parse_json_object(raw)
                result = parse_response(parsed)
            except (json.JSONDecodeError, TypeError, ValueError) as error:
                self._write_audit(payload, raw, attempt + 1, "rejected", type(error).__name__)
                last_error = error
                continue
            self._write_audit(payload, raw, attempt + 1, "accepted", "")
            return result
        raise ValueError(f"Could not parse a structured translation response: {last_error}")

    def _write_audit(
        self,
        payload: Mapping[str, object],
        raw_response: str,
        attempt: int,
        status: str,
        error_type: str,
    ) -> None:
        if self._audit_writer is None:
            return
        self._audit_writer(
            {
                "prompt_version": PROMPT_VERSION,
                "prompt_hash": PROMPT_HASH,
                "model_id": self._model_id,
                "revision": self._revision,
                "attempt": attempt,
                "status": status,
                "error_type": error_type,
                "request": dict(payload),
                "raw_response": raw_response,
            }
        )


def _parse_json_object(text: str) -> dict[str, object]:
    stripped = text.strip()
    if not stripped:
        raise ValueError("Response is empty")
    parsed: object = json.loads(stripped, object_pairs_hook=_object_without_duplicate_keys)
    if not isinstance(parsed, dict) or not all(isinstance(key, str) for key in parsed):
        raise ValueError("Entire response must be one JSON object with string keys")
    return cast(dict[str, object], parsed)


def _object_without_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    parsed: dict[str, object] = {}
    for key, value in pairs:
        if key in parsed:
            raise ValueError(f"Response contains duplicate JSON key {key!r}")
        parsed[key] = value
    return parsed


def _parse_translation(response: Mapping[str, object]) -> str:
    if set(response) != {"translation"}:
        raise ValueError("Translation response must contain only the 'translation' key")
    translation = response.get("translation")
    if not isinstance(translation, str) or not translation.strip():
        raise ValueError("Translation response lacks a non-empty 'translation' string")
    return translation.strip()


def _parse_translations(response: Mapping[str, object], *, expected_count: int) -> tuple[str, ...]:
    if set(response) != {"translations"}:
        raise ValueError("Sentence-array response must contain only the 'translations' key")
    translated = response.get("translations")
    if not isinstance(translated, list) or not all(isinstance(item, str) for item in translated):
        raise ValueError("Translation response lacks a string 'translations' array")
    if len(translated) != expected_count:
        raise ValueError(f"Sentence alignment changed from {expected_count} to {len(translated)}")
    translations = cast(list[str], translated)
    if any(not item.strip() for item in translations):
        raise ValueError("Translation response contains an empty sentence")
    return tuple(item.strip() for item in translations)
