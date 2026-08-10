"""Canonical language inventory and metadata."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Language:
    code: str
    name: str
    script: str
    family: str


LANGUAGES: tuple[Language, ...] = (
    Language("en", "English", "Latin", "Germanic"),
    Language("zh", "Mandarin Chinese", "Han", "Sinitic"),
    Language("hi", "Hindi", "Devanagari", "Indo-Aryan"),
    Language("es", "Spanish", "Latin", "Romance"),
    Language("ar", "Arabic", "Arabic", "Semitic"),
    Language("fr", "French", "Latin", "Romance"),
    Language("bn", "Bengali", "Bengali", "Indo-Aryan"),
    Language("pt", "Portuguese", "Latin", "Romance"),
    Language("ru", "Russian", "Cyrillic", "Slavic"),
    Language("ur", "Urdu", "Arabic", "Indo-Aryan"),
    Language("id", "Indonesian", "Latin", "Austronesian"),
    Language("de", "German", "Latin", "Germanic"),
    Language("ja", "Japanese", "Japanese", "Japonic"),
    Language("tr", "Turkish", "Latin", "Turkic"),
    Language("vi", "Vietnamese", "Latin", "Austroasiatic"),
    Language("sw", "Swahili", "Latin", "Bantu"),
    Language("ko", "Korean", "Hangul", "Koreanic"),
    Language("fa", "Persian", "Arabic", "Iranian"),
    Language("it", "Italian", "Latin", "Romance"),
    Language("th", "Thai", "Thai", "Kra-Dai"),
    Language("nl", "Dutch", "Latin", "Germanic"),
    Language("pl", "Polish", "Latin", "Slavic"),
    Language("el", "Greek", "Greek", "Hellenic"),
    Language("sv", "Swedish", "Latin", "Germanic"),
)

LANGUAGE_BY_CODE = {language.code: language for language in LANGUAGES}
LANGUAGE_CODES = tuple(language.code for language in LANGUAGES)


def require_language(code: str) -> Language:
    """Return metadata for a supported ISO 639-1 code."""
    try:
        return LANGUAGE_BY_CODE[code]
    except KeyError as error:
        raise ValueError(f"Unsupported language code: {code!r}") from error
