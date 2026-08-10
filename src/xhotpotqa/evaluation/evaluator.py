"""Streaming evaluator and aggregate report."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping
from statistics import fmean
from typing import Any

from xhotpotqa.data.models import XHotpotInstance
from xhotpotqa.evaluation.metrics import ExampleScore, FactKey, score_example
from xhotpotqa.evaluation.stratification import describe_language_stratum


def evaluate(
    gold: Iterable[XHotpotInstance], predictions: Mapping[str, Mapping[str, Any]]
) -> dict[str, Any]:
    scores: list[ExampleScore] = []
    by_language: dict[str, list[ExampleScore]] = defaultdict(list)
    by_condition: dict[str, list[ExampleScore]] = defaultdict(list)
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
        condition = describe_language_stratum(instance).condition
        by_condition[condition].append(score)
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
