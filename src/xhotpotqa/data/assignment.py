"""Shard-independent deterministic language assignment."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from xhotpotqa.languages import LANGUAGE_CODES


@dataclass(frozen=True, slots=True)
class LanguageAssigner:
    seed: int
    languages: tuple[str, ...] = LANGUAGE_CODES

    def assign(self, source_id: str, unit_id: str) -> str:
        """Map an immutable unit ID to a language without mutable RNG state."""
        key = f"{self.seed}\x1f{source_id}\x1f{unit_id}".encode()
        digest = hashlib.sha256(key).digest()
        index = int.from_bytes(digest[:8], "big") % len(self.languages)
        return self.languages[index]
