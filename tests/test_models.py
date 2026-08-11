import hashlib
from dataclasses import replace

from xhotpotqa.data.checksum import compute_checksum, with_checksum
from xhotpotqa.data.io import canonical_json
from xhotpotqa.data.models import CandidateParagraph, Provenance, SupportingFact, XHotpotInstance


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


def test_semantic_checksum_excludes_volatile_provenance() -> None:
    first = make_instance()
    second = replace(
        first,
        provenance=Provenance(
            created_at="2026-08-10T10:00:00Z",
            retry_count=7,
            validation_status="revalidated",
        ),
    )

    assert compute_checksum(first) == compute_checksum(second)


def test_empty_manifest_hash_preserves_pre_manifest_checksum_contract() -> None:
    instance = make_instance()
    legacy_payload = instance.to_dict()
    del legacy_payload["provenance"]["assignment_manifest_sha256"]
    expected = hashlib.sha256(canonical_json(legacy_payload).encode()).hexdigest()

    assert compute_checksum(instance) == expected
