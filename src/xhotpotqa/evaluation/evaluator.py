"""Streaming evaluator and aggregate report."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping
from statistics import fmean, median
from typing import Any

from xhotpotqa.data.models import XHotpotInstance
from xhotpotqa.evaluation.metrics import ExampleScore, FactKey, score_example
from xhotpotqa.evaluation.stratification import (
    CANDIDATE_LANGUAGE_COUNT_BINS,
    ENTROPY_BINS,
    MISMATCH_BINS,
    candidate_language_count_bin,
    describe_language_stratum,
    entropy_bin,
    mismatch_bin,
)


def evaluate(
    gold: Iterable[XHotpotInstance], predictions: Mapping[str, Mapping[str, Any]]
) -> dict[str, Any]:
    scores: list[ExampleScore] = []
    by_language: dict[str, list[ExampleScore]] = defaultdict(list)
    by_condition: dict[str, list[ExampleScore]] = defaultdict(list)
    by_script_relation: dict[str, list[ExampleScore]] = defaultdict(list)
    by_gold_mismatch: dict[str, list[ExampleScore]] = defaultdict(list)
    by_distractor_mismatch: dict[str, list[ExampleScore]] = defaultdict(list)
    by_gold_entropy: dict[str, list[ExampleScore]] = defaultdict(list)
    by_distinct_candidate_languages: dict[str, list[ExampleScore]] = defaultdict(list)
    gold_mismatch_values: list[float] = []
    distractor_mismatch_values: list[float] = []
    gold_entropy_values: list[float] = []
    distinct_candidate_language_values: list[float] = []
    missing: list[str] = []
    gold_ids: set[str] = set()
    for instance in gold:
        gold_ids.add(instance.id)
        prediction = predictions.get(instance.id)
        if prediction is None:
            missing.append(instance.id)
            predicted_answer = ""
            predicted_support: list[FactKey] = []
        else:
            predicted_answer = str(prediction.get("answer", ""))
            predicted_support = _parse_supporting_facts(prediction.get("supporting_facts", []))
        gold_support = [(fact.paragraph_id, fact.sentence_id) for fact in instance.supporting_facts]
        score = score_example(
            predicted_answer,
            instance.answer,
            instance.answer_language,
            predicted_support,
            gold_support,
        )
        scores.append(score)
        by_language[instance.question_language].append(score)
        stratum = describe_language_stratum(instance)
        by_condition[stratum.condition].append(score)
        by_script_relation[stratum.script_relation].append(score)
        by_gold_mismatch[mismatch_bin(stratum.gold_mismatch)].append(score)
        by_distractor_mismatch[mismatch_bin(stratum.distractor_mismatch)].append(score)
        by_gold_entropy[entropy_bin(stratum.gold_entropy)].append(score)
        by_distinct_candidate_languages[
            candidate_language_count_bin(stratum.distinct_candidate_language_count)
        ].append(score)
        gold_mismatch_values.append(stratum.gold_mismatch)
        distractor_mismatch_values.append(stratum.distractor_mismatch)
        gold_entropy_values.append(stratum.gold_entropy)
        distinct_candidate_language_values.append(float(stratum.distinct_candidate_language_count))
    report = {
        "count": len(scores),
        "missing_predictions": len(missing),
        "unexpected_predictions": len(set(predictions) - gold_ids),
        "overall": _aggregate(scores),
        "macro_by_question_language": _macro(by_language),
        "by_question_language": {
            key: _aggregate(value) for key, value in sorted(by_language.items())
        },
        "by_language_condition": {
            key: _aggregate(value) for key, value in sorted(by_condition.items())
        },
        "by_script_relation": {
            key: _aggregate(value) for key, value in sorted(by_script_relation.items())
        },
        "descriptor_summaries": {
            "gold_mismatch": _numeric_summary(gold_mismatch_values, "rho_G"),
            "distractor_mismatch": _numeric_summary(distractor_mismatch_values, "rho_D"),
            "gold_entropy": _numeric_summary(gold_entropy_values, "H_G"),
            "distinct_candidate_languages": _numeric_summary(
                distinct_candidate_language_values, "K_C"
            ),
        },
        "by_gold_mismatch": _aggregate_ordered_bins(by_gold_mismatch, MISMATCH_BINS),
        "by_distractor_mismatch": _aggregate_ordered_bins(by_distractor_mismatch, MISMATCH_BINS),
        "by_gold_entropy": _aggregate_ordered_bins(by_gold_entropy, ENTROPY_BINS),
        "by_distinct_candidate_languages": _aggregate_ordered_bins(
            by_distinct_candidate_languages, CANDIDATE_LANGUAGE_COUNT_BINS
        ),
    }
    return report


def _parse_supporting_facts(value: object) -> list[FactKey]:
    if not isinstance(value, list):
        raise ValueError("Prediction supporting_facts must be a list")
    facts: list[FactKey] = []
    for item in value:
        if not isinstance(item, Mapping):
            raise ValueError("Each predicted supporting fact must be an object")
        paragraph_id = item.get("paragraph_id")
        sentence_id = item.get("sentence_id")
        if not isinstance(paragraph_id, str) or not paragraph_id:
            raise ValueError("Predicted paragraph_id must be a non-empty string")
        if isinstance(sentence_id, bool) or not isinstance(sentence_id, int) or sentence_id < 0:
            raise ValueError("Predicted sentence_id must be a non-negative integer")
        facts.append((paragraph_id, sentence_id))
    if len(set(facts)) != len(facts):
        raise ValueError("Prediction contains duplicate supporting facts")
    return facts


def _aggregate(scores: list[ExampleScore]) -> dict[str, Any]:
    if not scores:
        return {"n": 0}
    return {
        "n": len(scores),
        **{
            component: {
                metric: fmean(getattr(getattr(score, component), metric) for score in scores)
                for metric in ("exact_match", "precision", "recall", "f1")
            }
            for component in ("answer", "support", "joint")
        },
    }


def _macro(groups: Mapping[str, list[ExampleScore]]) -> dict[str, float]:
    if not groups:
        return {}
    group_reports = [_aggregate(scores) for scores in groups.values()]
    return {
        f"{component}_{metric}": fmean(report[component][metric] for report in group_reports)
        for component in ("answer", "support", "joint")
        for metric in ("exact_match", "f1")
    }


def _numeric_summary(values: list[float], symbol: str) -> dict[str, Any]:
    if not values:
        return {"symbol": symbol, "n": 0}
    return {
        "symbol": symbol,
        "n": len(values),
        "mean": fmean(values),
        "median": median(values),
        "min": min(values),
        "max": max(values),
    }


def _aggregate_ordered_bins(
    groups: Mapping[str, list[ExampleScore]], order: tuple[str, ...]
) -> dict[str, dict[str, Any]]:
    """Aggregate populated descriptor bins in a stable, meaningful order."""
    return {label: _aggregate(groups[label]) for label in order if groups.get(label)}
