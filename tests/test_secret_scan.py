from pathlib import Path

import pytest

from xhotpotqa.security.secret_scan import main, scan_paths


def test_repository_has_no_committed_secrets() -> None:
    assert scan_paths([Path(".")]) == ()


@pytest.mark.parametrize(
    ("token", "kind"),
    [
        ("hf_" + "a" * 24, "Hugging Face token"),
        ("github_pat_" + "A1_" * 10, "GitHub fine-grained token"),
        ("ghp_" + "a" * 36, "GitHub token"),
    ],
)
def test_known_token_shapes_are_detected(tmp_path: Path, token: str, kind: str) -> None:
    candidate = tmp_path / "credentials.txt"
    candidate.write_text(token, encoding="utf-8")

    findings = scan_paths([candidate])

    assert len(findings) == 1
    assert findings[0].kind == kind


def test_empty_example_assignments_are_allowed(tmp_path: Path) -> None:
    candidate = tmp_path / ".env.example"
    candidate.write_text(
        "\n".join(
            (
                "HF_TOKEN" + "=",
                "OPENAI_API_KEY" + "=EMPTY",
                "GITHUB_TOKEN" + "=<replace-me>",
                "",
            )
        ),
        encoding="utf-8",
    )

    assert scan_paths([candidate]) == ()


def test_non_empty_github_token_assignment_is_detected(tmp_path: Path) -> None:
    candidate = tmp_path / ".env"
    candidate.write_text("GITHUB_TOKEN" + "=not-a-placeholder\n", encoding="utf-8")

    findings = scan_paths([candidate])

    assert len(findings) == 1
    assert findings[0].kind == "non-empty credential assignment"


def test_missing_scan_path_is_an_operational_error(tmp_path: Path) -> None:
    assert main([str(tmp_path / "missing")]) == 2
