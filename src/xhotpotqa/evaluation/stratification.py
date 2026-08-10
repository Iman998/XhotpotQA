"""Cross-lingual instance descriptors used in paper analyses."""

from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass

from xhotpotqa.data.models import XHotpotInstance
from xhotpotqa.languages import require_language


@dataclass(frozen=True, slots=True)
class LanguageStratum:
    gold_mismatch: float
    distractor_mismatch: float
    gold_language_count: int
    gold_entropy: float
    condition: str
    script_relation: str


def describe_language_stratum(instance: XHotpotInstance) -> LanguageStratum:
    paragraph_by_id = {candidate.id: candidate for candidate in instance.candidates}
    gold_ids = tuple(dict.fromkeys(fact.paragraph_id for fact in instance.supporting_facts))
    gold_languages = tuple(paragraph_by_id[item].language for item in gold_ids)
    distractor_languages = tuple(
        candidate.language for candidate in instance.candidates if candidate.id not in set(gold_ids)
    )
    gold_mismatch = _mismatch(instance.question_language, gold_languages)
    distractor_mismatch = _mismatch(instance.question_language, distractor_languages)
    distinct_gold = len(set(gold_languages))
    return LanguageStratum(
        gold_mismatch=gold_mismatch,
        distractor_mismatch=distractor_mismatch,
        gold_language_count=distinct_gold,
        gold_entropy=_normalized_entropy(gold_languages),
        condition=_condition(gold_mismatch, distractor_mismatch, distinct_gold),
        script_relation=_script_relation(instance.question_language, gold_languages),
    )


def _mismatch(question_language: str, languages: tuple[str, ...]) -> float:
    if not languages:
        return 0.0
    return sum(language != question_language for language in languages) / len(languages)


def _normalized_entropy(languages: tuple[str, ...]) -> float:
    if len(languages) <= 1:
        return 0.0
    counts = Counter(languages)
    entropy = -sum(
        (count / len(languages)) * math.log(count / len(languages)) for count in counts.values()
    )
    return entropy / math.log(len(languages))


def _condition(gold_mismatch: float, distractor_mismatch: float, distinct_gold: int) -> str:
    if gold_mismatch == 0 and distractor_mismatch == 0:
        return "fully-monolingual"
    if gold_mismatch == 0:
        return "multilingual-distractors-only"
    if 0 < gold_mismatch < 1:
        return "partial-gold-mismatch"
    if distinct_gold == 1:
        return "full-mismatch-single-evidence-language"
    return "full-mismatch-multilingual-evidence"


def _script_relation(question_language: str, gold_languages: tuple[str, ...]) -> str:
    question_script = require_language(question_language).script
    scripts = {require_language(language).script for language in gold_languages}
    if scripts == {question_script}:
        return "same-script"
    if question_script in scripts:
        return "mixed-script"
    return "different-script"
