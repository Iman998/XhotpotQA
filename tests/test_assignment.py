import hashlib
import json
from pathlib import Path

import pytest

from xhotpotqa.data.assignment import (
    HASH_ASSIGNMENT_VERSION,
    MANIFEST_SCHEMA_VERSION,
    LanguageAssigner,
    ManifestLanguageAssigner,
)


def _manifest() -> dict[str, object]:
    return {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "assignment_version": "xhotpotqa-v1-preserved-v2",
        "assignments": {
            "source-1": {
                "question-answer": "fa",
                "paragraph:0": "en",
                "paragraph:1": "de",
            }
        },
    }


def _write_manifest(path: Path, payload: object | None = None) -> bytes:
    raw = json.dumps(payload if payload is not None else _manifest(), sort_keys=True).encode()
    path.write_bytes(raw)
    return raw


def test_hash_assignment_is_stable_and_unit_specific() -> None:
    assigner = LanguageAssigner(seed=42)
    first = assigner.assign("source-1", "question-answer")
    assert first == assigner.assign("source-1", "question-answer")
    assert assigner.assignment_version == HASH_ASSIGNMENT_VERSION
    assert assigner.assignment_manifest_sha256 == ""
    assignments = {assigner.assign("source-1", f"paragraph:{index}") for index in range(30)}
    assert len(assignments) > 1


def test_manifest_assignment_replays_exact_languages_and_hash(tmp_path: Path) -> None:
    path = tmp_path / "assignments.json"
    raw = _write_manifest(path)

    assigner = ManifestLanguageAssigner.from_path(path)

    assert assigner.assignment_version == "xhotpotqa-v1-preserved-v2"
    assert assigner.assignment_manifest_sha256 == hashlib.sha256(raw).hexdigest()
    assert assigner.seed is None
    assert assigner.assign("source-1", "question-answer") == "fa"
    assert assigner.assign("source-1", "paragraph:1") == "de"
    assert assigner.iter_assignments() == (
        ("source-1", "question-answer", "fa"),
        ("source-1", "paragraph:0", "en"),
        ("source-1", "paragraph:1", "de"),
    )
    assigner.validate_source("source-1", ("question-answer", "paragraph:0", "paragraph:1"))


def test_manifest_source_units_must_match_before_generation(tmp_path: Path) -> None:
    path = tmp_path / "assignments.json"
    _write_manifest(path)
    assigner = ManifestLanguageAssigner.from_path(path)

    with pytest.raises(ValueError, match="units do not match"):
        assigner.validate_source("source-1", ("question-answer", "paragraph:0"))
    with pytest.raises(ValueError, match="no source_id"):
        assigner.assign("missing", "question-answer")
    with pytest.raises(ValueError, match="no unit"):
        assigner.assign("source-1", "paragraph:2")


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        ({"assignments": {}}, "exactly schema_version"),
        (
            {
                "schema_version": "unknown",
                "assignment_version": "v1",
                "assignments": {"source-1": {"question-answer": "fa", "paragraph:0": "en"}},
            },
            "Unsupported",
        ),
        (
            {
                "schema_version": MANIFEST_SCHEMA_VERSION,
                "assignment_version": "v1",
                "assignments": {"source-1": {"paragraph:0": "en"}},
            },
            "question-answer",
        ),
        (
            {
                "schema_version": MANIFEST_SCHEMA_VERSION,
                "assignment_version": "v1",
                "assignments": {
                    "source-1": {
                        "question-answer": "fa",
                        "paragraph:0": "en",
                        "paragraph:2": "de",
                    }
                },
            },
            "non-contiguous",
        ),
        (
            {
                "schema_version": MANIFEST_SCHEMA_VERSION,
                "assignment_version": "v1",
                "assignments": {
                    "source-1": {"question-answer": "not-a-language", "paragraph:0": "en"}
                },
            },
            "Unsupported language",
        ),
    ],
)
def test_invalid_manifest_is_rejected(tmp_path: Path, payload: object, message: str) -> None:
    path = tmp_path / "assignments.json"
    _write_manifest(path, payload)

    with pytest.raises(ValueError, match=message):
        ManifestLanguageAssigner.from_path(path)


def test_duplicate_json_keys_are_rejected(tmp_path: Path) -> None:
    path = tmp_path / "assignments.json"
    path.write_text(
        '{"schema_version":"xhotpotqa-assignment-manifest-v1",'
        '"assignment_version":"v1","assignments":{"source-1":{'
        '"question-answer":"fa","paragraph:0":"en","paragraph:0":"de"}}}',
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="duplicate JSON key"):
        ManifestLanguageAssigner.from_path(path)
