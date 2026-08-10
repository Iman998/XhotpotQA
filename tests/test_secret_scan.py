from pathlib import Path

from xhotpotqa.security.secret_scan import main, scan_paths


def test_repository_has_no_committed_secrets() -> None:
    assert scan_paths([Path(".")]) == ()


def test_known_token_shape_is_detected(tmp_path: Path) -> None:
    candidate = tmp_path / "credentials.txt"
    candidate.write_text("hf_" + "a" * 24, encoding="utf-8")

    findings = scan_paths([candidate])

    assert len(findings) == 1
    assert findings[0].kind == "Hugging Face token"


def test_empty_example_assignments_are_allowed(tmp_path: Path) -> None:
    candidate = tmp_path / ".env.example"
    candidate.write_text("HF_TOKEN=" + "\n" + "OPENAI_API_KEY=" + "EMPTY\n", encoding="utf-8")

    assert scan_paths([candidate]) == ()


def test_missing_scan_path_is_an_operational_error(tmp_path: Path) -> None:
    assert main([str(tmp_path / "missing")]) == 2
