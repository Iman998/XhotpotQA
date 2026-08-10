from pathlib import Path

import pytest

from xhotpotqa.data import release


def test_dataset_card_matches_uploaded_artifacts() -> None:
    release.validate_dataset_card(Path("dataset_card/README.md"))


def test_dataset_card_rejects_stale_data_path(tmp_path: Path) -> None:
    source = Path("dataset_card/README.md").read_text(encoding="utf-8")
    stale_card = tmp_path / "README.md"
    stale_card.write_text(
        source.replace("data/xhotpotqa/train.jsonl", "data/xhotpotqa/train-*.parquet"),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="paths must match"):
        release.validate_dataset_card(stale_card)


def test_dry_run_stops_before_credentials_or_hub_import(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(release, "validate_release_files", lambda *_: None)
    monkeypatch.delenv("HF_TOKEN", raising=False)
    monkeypatch.delenv("HUGGINGFACE_HUB_TOKEN", raising=False)

    release.upload_dataset(
        Path("train.jsonl"),
        Path("validation.jsonl"),
        Path("dataset_card/README.md"),
        dry_run=True,
    )


@pytest.mark.parametrize("repo_id", ["missing-owner", "owner/name/extra", "owner/../name"])
def test_invalid_repo_id_is_rejected_before_file_reads(repo_id: str) -> None:
    with pytest.raises(ValueError, match="owner/name"):
        release.upload_dataset(
            Path("missing-train"),
            Path("missing-validation"),
            Path("missing-card"),
            repo_id=repo_id,
            dry_run=True,
        )
