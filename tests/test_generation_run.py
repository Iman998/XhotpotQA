from dataclasses import replace
from pathlib import Path

import pytest
from test_models import make_instance

from xhotpotqa.data.checksum import with_checksum
from xhotpotqa.data.io import canonical_json
from xhotpotqa.data.models import Provenance, XHotpotInstance
from xhotpotqa.generation.run import completed_source_ids


def _write(path: Path, instance: XHotpotInstance) -> None:
    path.write_text(canonical_json(instance.to_dict()) + "\n", encoding="utf-8")


def test_resume_rejects_incompatible_provenance(tmp_path: Path) -> None:
    instance = with_checksum(
        replace(
            make_instance(),
            provenance=Provenance(
                assignment_version="sha256-hash-v1",
                seed=42,
                translation_model="model-a",
                translation_revision="rev-a",
                prompt_version="prompt-a",
                prompt_hash="hash-a",
                decoding={"temperature": 0.0},
            ),
        )
    )
    output = tmp_path / "validation.jsonl"
    _write(output, instance)

    with pytest.raises(ValueError, match="incompatible provenance"):
        completed_source_ids(
            output,
            expected_split="validation",
            expected_signature={"translation_model": "model-b"},
        )


def test_resume_accepts_matching_provenance(tmp_path: Path) -> None:
    instance = with_checksum(make_instance())
    output = tmp_path / "validation.jsonl"
    _write(output, instance)

    assert completed_source_ids(output, expected_split="validation") == {"1"}
