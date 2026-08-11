import hashlib
import sys
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from xhotpotqa.cli import main
from xhotpotqa.data import release
from xhotpotqa.data.checksum import with_checksum
from xhotpotqa.data.io import read_instances, write_instances
from xhotpotqa.data.models import (
    CandidateParagraph,
    Provenance,
    SupportingFact,
    XHotpotInstance,
)
from xhotpotqa.data.plus import QATranslation, expand_instance
from xhotpotqa.languages import LANGUAGE_CODES

CANONICAL_CARD_FIXTURE = Path(__file__).parent / "fixtures" / "canonical_release_card.md"


def _base(split: str) -> XHotpotInstance:
    return with_checksum(
        XHotpotInstance(
            id=f"xhp-{split}-source-{split}",
            source_id=f"source-{split}",
            source_split=split,
            question="Question in English?",
            answer="Answer",
            question_language="en",
            answer_language="en",
            candidates=(
                CandidateParagraph(
                    id="p00",
                    title="Title",
                    sentences=("Evidence.",),
                    language="de",
                    source_title="Title",
                    source_sentences=("Evidence.",),
                ),
            ),
            supporting_facts=(SupportingFact("p00", 0, "answer"),),
            question_type="bridge",
            difficulty="hard",
            provenance=Provenance(
                assignment_version="manifest-v1",
                translation_model="translator",
                translation_revision="immutable-revision",
                prompt_version="prompt-v1",
                prompt_hash="a" * 64,
                created_at="2026-08-10T00:00:00+00:00",
                validation_status="accepted",
            ),
        )
    )


def _views(base: XHotpotInstance) -> tuple[XHotpotInstance, ...]:
    translations = {
        language: QATranslation(
            question=f"question:{language}",
            answer=f"answer:{language}",
        )
        for language in LANGUAGE_CODES
    }
    return expand_instance(base, translations)


def test_canonical_dataset_card_fixture_matches_uploaded_artifacts() -> None:
    release.validate_dataset_card(CANONICAL_CARD_FIXTURE)


def test_canonical_dataset_card_rejects_stale_data_path(tmp_path: Path) -> None:
    source = CANONICAL_CARD_FIXTURE.read_text(encoding="utf-8")
    mutated = source.replace("data/xhotpotqa/train.jsonl", "data/xhotpotqa/train-*.parquet")
    assert mutated != source
    stale_card = tmp_path / "README.md"
    stale_card.write_text(mutated, encoding="utf-8")

    with pytest.raises(ValueError, match="paths must match"):
        release.validate_dataset_card(stale_card)


def test_canonical_dataset_card_rejects_missing_parallel_config(tmp_path: Path) -> None:
    source = CANONICAL_CARD_FIXTURE.read_text(encoding="utf-8")
    mutated = source.replace("- config_name: xhotpotqa_plus", "- config_name: undeclared")
    assert mutated != source
    stale_card = tmp_path / "README.md"
    stale_card.write_text(mutated, encoding="utf-8")

    with pytest.raises(ValueError, match="configs must match"):
        release.validate_dataset_card(stale_card)


def test_dry_run_stops_before_credentials_or_hub_import(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(release, "validate_release_files", lambda *_: None)
    monkeypatch.setattr(release, "build_release_manifest", lambda *_: {})
    monkeypatch.delenv("HF_TOKEN", raising=False)
    monkeypatch.delenv("HUGGINGFACE_HUB_TOKEN", raising=False)

    release.upload_dataset(
        Path("train.jsonl"),
        Path("validation.jsonl"),
        Path("plus-train.jsonl"),
        Path("plus-validation.jsonl"),
        CANONICAL_CARD_FIXTURE,
        dry_run=True,
    )


@pytest.mark.parametrize("repo_id", ["missing-owner", "owner/name/extra", "owner/../name"])
def test_invalid_repo_id_is_rejected_before_file_reads(repo_id: str) -> None:
    with pytest.raises(ValueError, match="owner/name"):
        release.upload_dataset(
            Path("missing-train"),
            Path("missing-validation"),
            Path("missing-plus-train"),
            Path("missing-plus-validation"),
            Path("missing-card"),
            repo_id=repo_id,
            dry_run=True,
        )


def test_release_manifest_records_file_integrity(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    train = tmp_path / "train.jsonl"
    validation = tmp_path / "validation.jsonl"
    plus_train = tmp_path / "plus-train.jsonl"
    plus_validation = tmp_path / "plus-validation.jsonl"
    train.write_text("train\n", encoding="utf-8")
    validation.write_text("validation\n", encoding="utf-8")
    plus_train.write_text("plus train\n", encoding="utf-8")
    plus_validation.write_text("plus validation\n", encoding="utf-8")
    monkeypatch.setenv("XHOTPOTQA_CODE_COMMIT", "a" * 40)

    manifest = release.build_release_manifest(train, validation, plus_train, plus_validation)

    assert manifest["code_revision"] == "a" * 40
    assert manifest["manifest_version"] == "xhotpotqa-release-v2"
    base_train = manifest["configs"]["xhotpotqa"]["splits"]["train"]
    assert base_train["bytes"] == train.stat().st_size
    assert base_train["sha256"] == hashlib.sha256(train.read_bytes()).hexdigest()
    plus_config = manifest["configs"]["xhotpotqa_plus"]
    assert plus_config["records"] == 553_584
    assert plus_config["views_per_source"] == 24


def test_release_validation_checks_parallel_derivation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths: dict[str, Path] = {}
    for split in ("train", "validation"):
        base = _base(split)
        base_path = tmp_path / f"{split}.jsonl"
        plus_path = tmp_path / f"plus-{split}.jsonl"
        write_instances(base_path, [base])
        write_instances(plus_path, _views(base))
        paths[split] = base_path
        paths[f"plus-{split}"] = plus_path
    monkeypatch.setitem(release.EXPECTED_SPLIT_COUNTS, "train", 1)
    monkeypatch.setitem(release.EXPECTED_SPLIT_COUNTS, "validation", 1)
    monkeypatch.setitem(release.EXPECTED_PLUS_SPLIT_COUNTS, "train", 24)
    monkeypatch.setitem(release.EXPECTED_PLUS_SPLIT_COUNTS, "validation", 24)

    release.validate_release_files(
        paths["train"],
        paths["validation"],
        paths["plus-train"],
        paths["plus-validation"],
    )

    validation_views = list(read_instances(paths["plus-validation"]))
    changed_candidate = replace(
        validation_views[0].candidates[0],
        title="Changed evidence title",
    )
    validation_views[0] = with_checksum(
        replace(validation_views[0], candidates=(changed_candidate,))
    )
    write_instances(paths["plus-validation"], validation_views)
    with pytest.raises(ValueError, match="changed fixed field"):
        release.validate_release_files(
            paths["train"],
            paths["validation"],
            paths["plus-train"],
            paths["plus-validation"],
        )


def test_real_upload_commits_card_manifest_and_four_data_files_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: dict[str, Any] = {}

    class FakeOperation:
        def __init__(self, *, path_in_repo: str, path_or_fileobj: object) -> None:
            self.path_in_repo = path_in_repo
            self.path_or_fileobj = path_or_fileobj

    class FakeApi:
        def __init__(self, *, token: str) -> None:
            calls["token"] = token

        def create_repo(self, *args: object, **kwargs: object) -> None:
            calls["create_repo"] = (args, kwargs)

        def create_commit(self, *args: object, **kwargs: object) -> None:
            calls["create_commit"] = (args, kwargs)

    fake_hub = SimpleNamespace(CommitOperationAdd=FakeOperation, HfApi=FakeApi)
    monkeypatch.setitem(sys.modules, "huggingface_hub", fake_hub)
    monkeypatch.setattr(release, "validate_release_files", lambda *_: None)
    monkeypatch.setattr(release, "validate_dataset_card", lambda *_: None)
    monkeypatch.setattr(release, "build_release_manifest", lambda *_: {"valid": True})
    monkeypatch.setenv("HF_TOKEN", "test-only-secret")

    release.upload_dataset(
        Path("train.jsonl"),
        Path("validation.jsonl"),
        Path("plus-train.jsonl"),
        Path("plus-validation.jsonl"),
        Path("README.md"),
    )

    _, commit_kwargs = calls["create_commit"]
    operations = commit_kwargs["operations"]
    assert [operation.path_in_repo for operation in operations] == [
        "README.md",
        "manifest.json",
        "data/xhotpotqa/train.jsonl",
        "data/xhotpotqa/validation.jsonl",
        "data/xhotpotqa_plus/train.jsonl",
        "data/xhotpotqa_plus/validation.jsonl",
    ]


def test_upload_cli_forwards_both_configurations(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    captured: dict[str, object] = {}

    def fake_upload(*args: object, **kwargs: object) -> None:
        captured["args"] = args
        captured["kwargs"] = kwargs

    monkeypatch.setattr("xhotpotqa.cli.upload_dataset", fake_upload)

    exit_code = main(
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

    assert exit_code == 0
    assert captured["args"][:4] == (
        Path("train.jsonl"),
        Path("validation.jsonl"),
        Path("plus-train.jsonl"),
        Path("plus-validation.jsonl"),
    )
    assert '"uploaded": false' in capsys.readouterr().out
