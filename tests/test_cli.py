from pathlib import Path

import pytest

from xhotpotqa.cli import _parser


def test_generate_v2_accepts_optional_assignment_manifest() -> None:
    args = _parser().parse_args(
        [
            "generate-v2",
            "--input",
            "source.json",
            "--output",
            "v2.jsonl",
            "--config",
            "generation.yaml",
            "--split",
            "validation",
            "--assignment-manifest",
            "v1.assignments.json",
        ]
    )

    assert args.assignment_manifest == Path("v1.assignments.json")


def test_canonical_upload_requires_an_explicit_release_card() -> None:
    with pytest.raises(SystemExit):
        _parser().parse_args(
            [
                "upload-hf",
                "--train",
                "train.jsonl",
                "--validation",
                "validation.jsonl",
                "--plus-train",
                "plus-train.jsonl",
                "--plus-validation",
                "plus-validation.jsonl",
                "--dry-run",
            ]
        )
