"""Structured translation prompts and parsers."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Mapping, Sequence
from types import MappingProxyType
from typing import TypeVar, cast

from xhotpotqa.generation.protocols import ChatGenerator
from xhotpotqa.languages import require_language

PROMPT_VERSION = "xhotpotqa-translation-v2.0"
SYSTEM_PROMPT = (
    "You are the deterministic translation component of a multilingual QA dataset. "
    "Preserve named entities, numbers, dates, yes/no polarity, and sentence boundaries. "
    "Do not answer the question and do not add explanations. Return exactly one valid "
    "JSON object with the requested keys and no Markdown."
)
PROMPT_HASH = hashlib.sha256(SYSTEM_PROMPT.encode("utf-8")).hexdigest()
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
        request = {
            "task": "translate",
            "unit": unit,
            "target_language": language.name,
            "text": text,
        }
        return self._request(request, _parse_translation)

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
        }
        return self._request(
            request,
            lambda response: _parse_translations(response, expected_count=len(sentences)),
        )

    def _request(
        self,
        payload: Mapping[str, object],
        parse_response: Callable[[Mapping[str, object]], ResponseT],
    ) -> ResponseT:
        last_error: Exception | None = None
        for attempt in range(self._max_retries):
            if attempt:
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


def _extract_json(text: str) -> str:
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end < start:
        raise ValueError("Response contains no JSON object")
    return text[start : end + 1]


def _parse_json_object(text: str) -> dict[str, object]:
    parsed: object = json.loads(_extract_json(text))
    if not isinstance(parsed, dict) or not all(isinstance(key, str) for key in parsed):
        raise ValueError("Expected a JSON object with string keys")
    return cast(dict[str, object], parsed)


def _parse_translation(response: Mapping[str, object]) -> str:
    translation = response.get("translation")
    if not isinstance(translation, str) or not translation.strip():
        raise ValueError("Translation response lacks a non-empty 'translation' string")
    return translation.strip()


def _parse_translations(response: Mapping[str, object], *, expected_count: int) -> tuple[str, ...]:
    translated = response.get("translations")
    if not isinstance(translated, list) or not all(isinstance(item, str) for item in translated):
        raise ValueError("Translation response lacks a string 'translations' array")
    if len(translated) != expected_count:
        raise ValueError(f"Sentence alignment changed from {expected_count} to {len(translated)}")
    translations = cast(list[str], translated)
    if any(not item.strip() for item in translations):
        raise ValueError("Translation response contains an empty sentence")
    return tuple(item.strip() for item in translations)
