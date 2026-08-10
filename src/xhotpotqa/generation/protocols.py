"""Narrow interfaces used for dependency inversion and testability."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Protocol


class ChatGenerator(Protocol):
    def generate(self, messages: Sequence[dict[str, str]]) -> str:
        """Generate one assistant response."""


class TranslationService(Protocol):
    @property
    def model_id(self) -> str: ...

    @property
    def revision(self) -> str: ...

    @property
    def decoding(self) -> Mapping[str, object]: ...

    def translate_text(self, text: str, target_language: str, unit: str) -> str: ...

    def translate_sentences(
        self, sentences: Sequence[str], target_language: str
    ) -> tuple[str, ...]: ...
