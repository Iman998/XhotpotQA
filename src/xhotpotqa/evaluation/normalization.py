"""Unicode- and script-aware answer normalization."""

from __future__ import annotations

import re
import unicodedata

from xhotpotqa.languages import require_language

_ENGLISH_ARTICLES = re.compile(r"\b(a|an|the)\b", flags=re.IGNORECASE)
_SPACE = re.compile(r"\s+")
_CHARACTER_TOKEN_SCRIPTS = {"Han", "Japanese", "Thai"}


def normalize_answer(text: str, language: str) -> str:
    require_language(language)
    value = unicodedata.normalize("NFKC", text).casefold()
    value = "".join(
        " " if unicodedata.category(character).startswith(("P", "S")) else character
        for character in value
    )
    if language == "en":
        value = _ENGLISH_ARTICLES.sub(" ", value)
    return _SPACE.sub(" ", value).strip()


def answer_tokens(text: str, language: str) -> tuple[str, ...]:
    normalized = normalize_answer(text, language)
    if not normalized:
        return ()
    if require_language(language).script in _CHARACTER_TOKEN_SCRIPTS:
        return tuple(character for character in normalized if not character.isspace())
    return tuple(normalized.split())
