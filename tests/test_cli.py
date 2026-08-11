from pathlib import Path

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
