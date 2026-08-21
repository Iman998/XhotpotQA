"""Narrow interfaces used for dependency inversion and testability."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from contextlib import AbstractContextManager
from dataclasses import dataclass
from typing import Protocol


class GenerationResponseError(ValueError):
    """An endpoint response cannot satisfy the requested generation contract."""


class ChatGenerator(Protocol):
    def generate(self, messages: Sequence[dict[str, str]]) -> str:
        """Generate one assistant response."""


@dataclass(slots=True)
class TranslationStats:
    """Mutable counters scoped to one source record."""

    retry_count: int = 0


class TranslationService(Protocol):
    @property
    def model_id(self) -> str: ...

    @property
    def revision(self) -> str: ...

    @property
    def decoding(self) -> Mapping[str, object]: ...

    def record_scope(self) -> AbstractContextManager[TranslationStats]: ...

    def translate_text(self, text: str, target_language: str, unit: str) -> str: ...

    def translate_sentences(
        self, sentences: Sequence[str], target_language: str
    ) -> tuple[str, ...]: ...
