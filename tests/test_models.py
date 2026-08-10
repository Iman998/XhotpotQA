from dataclasses import replace

from xhotpotqa.data.checksum import with_checksum
from xhotpotqa.data.models import CandidateParagraph, SupportingFact, XHotpotInstance


def make_instance() -> XHotpotInstance:
    return XHotpotInstance(
        id="xhp-validation-1",
        source_id="1",
        source_split="validation",
        question="Who?",
        answer="Ada",
        question_language="en",
        answer_language="en",
        candidates=(CandidateParagraph("p00", "Ada", ("Ada wrote it.",), "en"),),
        supporting_facts=(SupportingFact("p00", 0),),
    )


def test_checksum_roundtrip() -> None:
    instance = with_checksum(make_instance())
    instance.validate()
    restored = XHotpotInstance.from_dict(instance.to_dict())
    assert restored == instance


def test_broken_support_index_is_rejected() -> None:
    instance = make_instance()
    broken = replace(instance, supporting_facts=(SupportingFact("p00", 3),))
    try:
        broken.validate()
    except ValueError as error:
        assert "outside" in str(error)
    else:
        raise AssertionError("broken support index was accepted")
