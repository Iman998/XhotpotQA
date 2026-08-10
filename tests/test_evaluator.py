import pytest

from xhotpotqa.data.models import CandidateParagraph, SupportingFact, XHotpotInstance
from xhotpotqa.evaluation.evaluator import evaluate


def make_instance() -> XHotpotInstance:
    return XHotpotInstance(
        id="xhp-validation-1",
        source_id="1",
        source_split="validation",
        question="Who?",
        answer="Ada",
        question_language="en",
        answer_language="en",
        candidates=(
            CandidateParagraph("p0", "Ada", ("Ada wrote it.",), "en"),
            CandidateParagraph("p1", "Other", ("Distractor.",), "fa"),
        ),
        supporting_facts=(SupportingFact("p0", 0),),
    )


def test_evaluator_reports_aggregate_macro_and_unexpected_predictions() -> None:
    prediction = {
        "answer": "Ada",
        "supporting_facts": [{"paragraph_id": "p0", "sentence_id": 0}],
    }

    report = evaluate([make_instance()], {"xhp-validation-1": prediction, "extra": prediction})

    assert report["count"] == 1
    assert report["missing_predictions"] == 0
    assert report["unexpected_predictions"] == 1
    assert report["overall"]["joint"]["f1"] == 1.0
    assert report["macro_by_question_language"]["answer_exact_match"] == 1.0
    assert report["by_question_language"]["en"]["n"] == 1


def test_missing_prediction_scores_zero() -> None:
    report = evaluate([make_instance()], {})

    assert report["missing_predictions"] == 1
    assert report["overall"]["answer"]["f1"] == 0.0
    assert report["overall"]["support"]["f1"] == 0.0


@pytest.mark.parametrize(
    "supporting_facts",
    [
        "not-a-list",
        ["not-an-object"],
        [{"paragraph_id": "", "sentence_id": 0}],
        [{"paragraph_id": "p0", "sentence_id": True}],
        [
            {"paragraph_id": "p0", "sentence_id": 0},
            {"paragraph_id": "p0", "sentence_id": 0},
        ],
    ],
)
def test_malformed_support_predictions_are_rejected(supporting_facts: object) -> None:
    with pytest.raises(ValueError):
        evaluate(
            [make_instance()],
            {"xhp-validation-1": {"answer": "Ada", "supporting_facts": supporting_facts}},
        )
