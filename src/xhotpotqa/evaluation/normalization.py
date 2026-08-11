"""Versioned legacy-Hotpot and Unicode/script-aware answer normalization."""

from __future__ import annotations

import re
import string
import unicodedata
from typing import Literal

from xhotpotqa.languages import require_language

_ENGLISH_ARTICLES = re.compile(r"\b(a|an|the)\b", flags=re.IGNORECASE)
_SPACE = re.compile(r"\s+")
_CHARACTER_TOKEN_SCRIPTS = {"Han", "Japanese", "Thai"}
EvaluationProtocol = Literal["legacy_hotpot", "unicode_script_aware"]
EVALUATION_PROTOCOLS: tuple[EvaluationProtocol, ...] = (
    "legacy_hotpot",
    "unicode_script_aware",
)
DEFAULT_EVALUATION_PROTOCOL: EvaluationProtocol = "unicode_script_aware"
EVALUATION_PROTOCOL_VERSIONS: dict[EvaluationProtocol, str] = {
    "legacy_hotpot": "1.0",
    "unicode_script_aware": "1.0",
}


def normalize_answer(
    text: str,
    language: str,
    *,
    protocol: EvaluationProtocol = DEFAULT_EVALUATION_PROTOCOL,
) -> str:
    require_language(language)
    require_evaluation_protocol(protocol)
    if protocol == "legacy_hotpot":
        # Mirrors the official HotpotQA/SQuAD-style normalizer.  In
        # particular, it only removes ASCII punctuation and tokenizes on
        # whitespace; this behavior is retained for historical comparability.
        value = text.lower()
        value = "".join(character for character in value if character not in string.punctuation)
        value = _ENGLISH_ARTICLES.sub(" ", value)
        return " ".join(value.split())

    value = unicodedata.normalize("NFKC", text).casefold()
    value = "".join(
        " " if unicodedata.category(character).startswith(("P", "S")) else character
        for character in value
    )
    if language == "en":
        value = _ENGLISH_ARTICLES.sub(" ", value)
    return _SPACE.sub(" ", value).strip()


def answer_tokens(
    text: str,
    language: str,
    *,
    protocol: EvaluationProtocol = DEFAULT_EVALUATION_PROTOCOL,
) -> tuple[str, ...]:
    normalized = normalize_answer(text, language, protocol=protocol)
    if not normalized:
        return ()
    if (
        protocol == "unicode_script_aware"
        and require_language(language).script in _CHARACTER_TOKEN_SCRIPTS
    ):
        return tuple(character for character in normalized if not character.isspace())
    return tuple(normalized.split())


def require_evaluation_protocol(protocol: str) -> EvaluationProtocol:
    """Validate and narrow a public evaluation-protocol name."""

    if protocol not in EVALUATION_PROTOCOLS:
        raise ValueError(
            f"Unsupported evaluation protocol {protocol!r}; expected one of {EVALUATION_PROTOCOLS}"
        )
    return protocol
