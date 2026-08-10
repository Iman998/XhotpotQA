from xhotpotqa.data.models import CandidateParagraph, SupportingFact, XHotpotInstance
from xhotpotqa.evaluation.stratification import describe_language_stratum


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
    assert stratum.condition == "full-mismatch-multilingual-evidence"
