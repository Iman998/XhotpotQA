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
    assert report["by_script_relation"]["same-script"]["n"] == 1
    assert report["by_gold_mismatch"]["zero"]["n"] == 1
    assert report["by_distractor_mismatch"]["full"]["n"] == 1
    assert report["by_gold_entropy"]["zero"]["n"] == 1
    assert report["by_distinct_candidate_languages"]["two-to-four"]["n"] == 1
    assert report["descriptor_summaries"]["gold_mismatch"] == {
        "symbol": "rho_G",
        "n": 1,
        "mean": 0.0,
        "median": 0.0,
        "min": 0.0,
        "max": 0.0,
    }


def test_missing_prediction_scores_zero() -> None:
    report = evaluate([make_instance()], {})

    assert report["missing_predictions"] == 1
    assert report["overall"]["answer"]["f1"] == 0.0
    assert report["overall"]["support"]["f1"] == 0.0


def test_evaluator_summarizes_formal_language_descriptors() -> None:
    cross_script = XHotpotInstance(
        id="xhp-validation-2",
        source_id="2",
        source_split="validation",
        question="Who?",
        answer="Ada",
        question_language="en",
        answer_language="en",
        candidates=(
            CandidateParagraph("p0", "A", ("A",), "fa"),
            CandidateParagraph("p1", "B", ("B",), "ja"),
            CandidateParagraph("p2", "C", ("C",), "en"),
        ),
        supporting_facts=(SupportingFact("p0", 0), SupportingFact("p1", 0)),
    )
    predictions = {
        "xhp-validation-1": {
            "answer": "Ada",
            "supporting_facts": [{"paragraph_id": "p0", "sentence_id": 0}],
        },
        "xhp-validation-2": {
            "answer": "Ada",
            "supporting_facts": [
                {"paragraph_id": "p0", "sentence_id": 0},
                {"paragraph_id": "p1", "sentence_id": 0},
            ],
        },
    }

    report = evaluate([make_instance(), cross_script], predictions)

    assert report["by_script_relation"]["same-script"]["n"] == 1
    assert report["by_script_relation"]["different-script"]["n"] == 1
    assert report["by_gold_mismatch"]["zero"]["n"] == 1
    assert report["by_gold_mismatch"]["full"]["n"] == 1
    assert report["by_distractor_mismatch"]["zero"]["n"] == 1
    assert report["by_distractor_mismatch"]["full"]["n"] == 1
    assert report["by_gold_entropy"]["zero"]["n"] == 1
    assert report["by_gold_entropy"]["maximal"]["n"] == 1
    assert report["descriptor_summaries"]["gold_mismatch"]["mean"] == 0.5
    assert report["descriptor_summaries"]["distractor_mismatch"]["mean"] == 0.5
    assert report["descriptor_summaries"]["gold_entropy"]["mean"] == 0.5
    assert report["descriptor_summaries"]["distinct_candidate_languages"]["mean"] == 2.5


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
