"""Cross-lingual instance descriptors used in paper analyses."""

from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass

from xhotpotqa.data.models import XHotpotInstance
from xhotpotqa.languages import require_language

MISMATCH_BINS = ("zero", "partial", "full")
DISTRACTOR_MISMATCH_BINS = ("not-applicable", *MISMATCH_BINS)
ENTROPY_BINS = ("zero", "intermediate", "maximal")
CANDIDATE_LANGUAGE_COUNT_BINS = ("one", "two-to-four", "five-to-eight", "nine-or-more")


@dataclass(frozen=True, slots=True)
class LanguageStratum:
    """Per-instance language descriptors defined in the benchmark paper.

    ``gold_mismatch`` and ``distractor_mismatch`` correspond to :math:`rho_G`
    and :math:`rho_D`; ``gold_entropy`` corresponds to :math:`H_G`.  The
    distinct-candidate count is kept alongside them because it measures the
    multilingual search space seen by a selector.
    """

    gold_mismatch: float
    distractor_mismatch: float | None
    gold_language_count: int
    gold_entropy: float
    condition: str
    script_relation: str
    distinct_candidate_language_count: int = 0
    distractor_count: int = 0


def describe_language_stratum(instance: XHotpotInstance) -> LanguageStratum:
    paragraph_by_id = {candidate.id: candidate for candidate in instance.candidates}
    gold_ids = tuple(dict.fromkeys(fact.paragraph_id for fact in instance.supporting_facts))
    gold_languages = tuple(paragraph_by_id[item].language for item in gold_ids)
    distractor_languages = tuple(
        candidate.language for candidate in instance.candidates if candidate.id not in set(gold_ids)
    )
    gold_mismatch = _mismatch(instance.question_language, gold_languages)
    if gold_mismatch is None:
        raise ValueError("At least one gold paragraph is required for language stratification")
    distractor_mismatch = _mismatch(instance.question_language, distractor_languages)
    distinct_gold = len(set(gold_languages))
    return LanguageStratum(
        gold_mismatch=gold_mismatch,
        distractor_mismatch=distractor_mismatch,
        gold_language_count=distinct_gold,
        gold_entropy=_normalized_entropy(gold_languages),
        condition=_condition(gold_mismatch, distractor_mismatch, distinct_gold),
        script_relation=_script_relation(instance.question_language, gold_languages),
        distinct_candidate_language_count=len(
            {candidate.language for candidate in instance.candidates}
        ),
        distractor_count=len(distractor_languages),
    )


def mismatch_bin(value: float | None) -> str:
    """Bin a mismatch rate; ``None`` means that its denominator is empty."""
    if value is None:
        return "not-applicable"
    _require_unit_interval(value, "mismatch")
    if math.isclose(value, 0.0, abs_tol=1e-12):
        return "zero"
    if math.isclose(value, 1.0, abs_tol=1e-12):
        return "full"
    return "partial"


def entropy_bin(value: float) -> str:
    """Return the manuscript-aligned bin for normalized gold entropy."""
    _require_unit_interval(value, "entropy")
    if math.isclose(value, 0.0, abs_tol=1e-12):
        return "zero"
    if math.isclose(value, 1.0, abs_tol=1e-12):
        return "maximal"
    return "intermediate"


def candidate_language_count_bin(value: int) -> str:
    """Bin the number of distinct candidate languages for selector analysis."""
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError("Distinct candidate-language count must be a positive integer")
    if value == 1:
        return "one"
    if value <= 4:
        return "two-to-four"
    if value <= 8:
        return "five-to-eight"
    return "nine-or-more"


def _mismatch(question_language: str, languages: tuple[str, ...]) -> float | None:
    if not languages:
        return None
    return sum(language != question_language for language in languages) / len(languages)


def _normalized_entropy(languages: tuple[str, ...]) -> float:
    if len(languages) <= 1:
        return 0.0
    counts = Counter(languages)
    entropy = -sum(
        (count / len(languages)) * math.log(count / len(languages)) for count in counts.values()
    )
    return entropy / math.log(len(languages))


def _require_unit_interval(value: float, name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{name.capitalize()} must be a finite number in [0, 1]")
    if not 0.0 <= value <= 1.0:
        raise ValueError(f"{name.capitalize()} must be in [0, 1]")


def _condition(gold_mismatch: float, distractor_mismatch: float | None, distinct_gold: int) -> str:
    if gold_mismatch == 0 and distractor_mismatch is None:
        return "gold-aligned-no-distractors"
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
