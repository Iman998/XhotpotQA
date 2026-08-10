"""Structured translation prompts and parsers."""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping, Sequence
from types import MappingProxyType
from typing import TypeVar, cast

from xhotpotqa.generation.protocols import ChatGenerator
from xhotpotqa.languages import require_language

PROMPT_VERSION = "xhotpotqa-translation-v2.0"
ResponseT = TypeVar("ResponseT")


class StructuredTranslator:
    def __init__(
        self,
        generator: ChatGenerator,
        *,
        model_id: str,
        revision: str,
        max_retries: int = 3,
        decoding: Mapping[str, object] | None = None,
    ) -> None:
        if max_retries < 1:
            raise ValueError("max_retries must be greater than zero")
        self._generator = generator
        self._model_id = model_id
        self._revision = revision
        self._max_retries = max_retries
        self._decoding: Mapping[str, object] = MappingProxyType(dict(decoding or {}))

    @property
    def model_id(self) -> str:
        return self._model_id

    @property
    def revision(self) -> str:
        return self._revision

    @property
    def decoding(self) -> Mapping[str, object]:
        return self._decoding

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
        system = (
            "You are the deterministic translation component of a multilingual QA dataset. "
            "Preserve named entities, numbers, dates, yes/no polarity, and sentence boundaries. "
            "Do not answer the question and do not add explanations. Return exactly one valid "
            "JSON object with the requested keys and no Markdown."
        )
        last_error: Exception | None = None
        for _ in range(self._max_retries):
            raw = self._generator.generate(
                [
                    {"role": "system", "content": system},
                    {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
                ]
            )
            try:
                parsed = _parse_json_object(raw)
                return parse_response(parsed)
            except (json.JSONDecodeError, TypeError, ValueError) as error:
                last_error = error
        raise ValueError(f"Could not parse a structured translation response: {last_error}")


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
