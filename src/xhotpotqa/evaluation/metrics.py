"""Answer, supporting-fact, and Hotpot-style joint metrics."""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass

from xhotpotqa.evaluation.normalization import (
    DEFAULT_EVALUATION_PROTOCOL,
    EvaluationProtocol,
    answer_tokens,
    normalize_answer,
)

FactKey = tuple[str, int]


@dataclass(frozen=True, slots=True)
class ComponentScore:
    exact_match: float
    precision: float
    recall: float
    f1: float


@dataclass(frozen=True, slots=True)
class ExampleScore:
    answer: ComponentScore
    support: ComponentScore
    joint: ComponentScore


def answer_score(
    prediction: str,
    gold: str,
    language: str,
    *,
    protocol: EvaluationProtocol = DEFAULT_EVALUATION_PROTOCOL,
) -> ComponentScore:
    normalized_prediction = normalize_answer(prediction, language, protocol=protocol)
    normalized_gold = normalize_answer(gold, language, protocol=protocol)
    predicted_tokens = answer_tokens(prediction, language, protocol=protocol)
    gold_tokens = answer_tokens(gold, language, protocol=protocol)
    special_answers = {"yes", "no", "noanswer"}
    if (
        normalized_prediction in special_answers or normalized_gold in special_answers
    ) and normalized_prediction != normalized_gold:
        return ComponentScore(exact_match=0.0, precision=0.0, recall=0.0, f1=0.0)
    overlap = sum((Counter(predicted_tokens) & Counter(gold_tokens)).values())
    precision = _safe_ratio(overlap, len(predicted_tokens), empty_is_one=not gold_tokens)
    recall = _safe_ratio(overlap, len(gold_tokens), empty_is_one=not predicted_tokens)
    return ComponentScore(
        exact_match=float(normalized_prediction == normalized_gold),
        precision=precision,
        recall=recall,
        f1=_harmonic_mean(precision, recall),
    )


def support_score(prediction: Iterable[FactKey], gold: Iterable[FactKey]) -> ComponentScore:
    predicted_set, gold_set = set(prediction), set(gold)
    overlap = len(predicted_set & gold_set)
    precision = _safe_ratio(overlap, len(predicted_set), empty_is_one=not gold_set)
    recall = _safe_ratio(overlap, len(gold_set), empty_is_one=not predicted_set)
    return ComponentScore(
        exact_match=float(predicted_set == gold_set),
        precision=precision,
        recall=recall,
        f1=_harmonic_mean(precision, recall),
    )


def score_example(
    predicted_answer: str,
    gold_answer: str,
    language: str,
    predicted_support: Iterable[FactKey],
    gold_support: Iterable[FactKey],
    *,
    protocol: EvaluationProtocol = DEFAULT_EVALUATION_PROTOCOL,
) -> ExampleScore:
    answer = answer_score(predicted_answer, gold_answer, language, protocol=protocol)
    support = support_score(predicted_support, gold_support)
    joint_precision = answer.precision * support.precision
    joint_recall = answer.recall * support.recall
    joint = ComponentScore(
        exact_match=answer.exact_match * support.exact_match,
        precision=joint_precision,
        recall=joint_recall,
        f1=_harmonic_mean(joint_precision, joint_recall),
    )
    return ExampleScore(answer=answer, support=support, joint=joint)


def _safe_ratio(numerator: int, denominator: int, *, empty_is_one: bool) -> float:
    if denominator:
        return numerator / denominator
    return 1.0 if empty_is_one else 0.0


def _harmonic_mean(precision: float, recall: float) -> float:
    return 2 * precision * recall / (precision + recall) if precision + recall else 0.0
