import pytest

from xhotpotqa.data.models import CandidateParagraph, SupportingFact, XHotpotInstance
from xhotpotqa.evaluation.stratification import (
    candidate_language_count_bin,
    describe_language_stratum,
    entropy_bin,
    mismatch_bin,
)


def test_full_mismatch_multilingual_evidence() -> None:
    instance = XHotpotInstance(
        id="x",
        source_id="s",
        source_split="validation",
        question="Question",
        answer="Answer",
        question_language="en",
        answer_language="en",
        candidates=(
            CandidateParagraph("p0", "A", ("a",), "fa"),
            CandidateParagraph("p1", "B", ("b",), "ja"),
            CandidateParagraph("p2", "C", ("c",), "en"),
        ),
        supporting_facts=(SupportingFact("p0", 0), SupportingFact("p1", 0)),
    )
    stratum = describe_language_stratum(instance)
    assert stratum.gold_mismatch == 1.0
    assert stratum.gold_language_count == 2
    assert stratum.gold_entropy == 1.0
    assert stratum.script_relation == "different-script"
    assert stratum.distinct_candidate_language_count == 3
    assert stratum.condition == "full-mismatch-multilingual-evidence"


@pytest.mark.parametrize(
    ("value", "expected"),
    [(0.0, "zero"), (0.5, "partial"), (1.0, "full")],
)
def test_mismatch_bins(value: float, expected: str) -> None:
    assert mismatch_bin(value) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [(0.0, "zero"), (0.42, "intermediate"), (1.0, "maximal")],
)
def test_entropy_bins(value: float, expected: str) -> None:
    assert entropy_bin(value) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [(1, "one"), (2, "two-to-four"), (4, "two-to-four"), (8, "five-to-eight"), (9, "nine-or-more")],
)
def test_candidate_language_count_bins(value: int, expected: str) -> None:
    assert candidate_language_count_bin(value) == expected


@pytest.mark.parametrize("value", [-0.1, 1.1, float("inf")])
def test_unit_interval_bins_reject_invalid_values(value: float) -> None:
    with pytest.raises(ValueError):
        mismatch_bin(value)
    with pytest.raises(ValueError):
        entropy_bin(value)


@pytest.mark.parametrize("value", [0, -1, True])
def test_candidate_language_count_bin_rejects_invalid_values(value: int) -> None:
    with pytest.raises(ValueError):
        candidate_language_count_bin(value)
