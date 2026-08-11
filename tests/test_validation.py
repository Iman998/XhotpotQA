from dataclasses import replace

from test_models import make_instance

from xhotpotqa.data.checksum import with_checksum
from xhotpotqa.data.models import Provenance
from xhotpotqa.data.validation import validate_instances


def test_strict_release_requires_complete_provenance_and_source_text() -> None:
    instance = with_checksum(make_instance())

    report = validate_instances([instance], strict_release=True)

    assert not report.ok
    assert any("source_title" in error for error in report.errors)
    assert any("translation_model" in error for error in report.errors)


def test_strict_release_accepts_complete_record() -> None:
    base = make_instance()
    candidate = replace(
        base.candidates[0],
        source_title="Ada",
        source_sentences=("Ada wrote it.",),
    )
    instance = with_checksum(
        replace(
            base,
            question_type="bridge",
            difficulty="hard",
            candidates=(candidate,),
            provenance=Provenance(
                assignment_version="legacy-manifest-v1",
                seed=7,
                translation_model="translator",
                translation_revision="revision",
                prompt_version="prompt-v1",
                prompt_hash="a" * 64,
                created_at="2025-01-01T00:00:00Z",
                validation_status="structural-passed",
            ),
        )
    )

    report = validate_instances([instance], strict_release=True)

    assert report.ok


def test_strict_release_rejects_malformed_optional_assignment_manifest_hash() -> None:
    base = make_instance()
    candidate = replace(
        base.candidates[0],
        source_title="Ada",
        source_sentences=("Ada wrote it.",),
    )
    instance = with_checksum(
        replace(
            base,
            question_type="bridge",
            difficulty="hard",
            candidates=(candidate,),
            provenance=Provenance(
                assignment_version="xhotpotqa-v2-v1-assignment-replay-v1",
                assignment_manifest_sha256="not-a-sha256",
                translation_model="translator",
                translation_revision="revision",
                prompt_version="prompt-v1",
                prompt_hash="a" * 64,
                created_at="2025-01-01T00:00:00Z",
                validation_status="structural-passed",
            ),
        )
    )

    report = validate_instances([instance], strict_release=True)

    assert any("assignment_manifest_sha256" in error for error in report.errors)
