"""Validated, credential-safe Hugging Face release helpers."""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
from collections.abc import Iterator, Mapping
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from typing import Any, cast

import yaml

from xhotpotqa import __version__
from xhotpotqa.data.io import read_instances
from xhotpotqa.data.models import XHotpotInstance
from xhotpotqa.data.plus import EXPECTED_PLUS_SPLIT_COUNTS, LANGUAGES_PER_INSTANCE, variant_id
from xhotpotqa.data.validation import (
    EXPECTED_SPLIT_COUNTS,
    ValidationReport,
    require_release_ready,
    validate_instances,
)
from xhotpotqa.languages import LANGUAGE_CODES

BASE_DATASET_CONFIG_NAME = "xhotpotqa"
PLUS_DATASET_CONFIG_NAME = "xhotpotqa_plus"
MANIFEST_REPO_PATH = "manifest.json"
DATASET_CONFIG_PATHS = {
    BASE_DATASET_CONFIG_NAME: {
        "train": "data/xhotpotqa/train.jsonl",
        "validation": "data/xhotpotqa/validation.jsonl",
    },
    PLUS_DATASET_CONFIG_NAME: {
        "train": "data/xhotpotqa_plus/train.jsonl",
        "validation": "data/xhotpotqa_plus/validation.jsonl",
    },
}
DATASET_CONFIG_COUNTS = {
    BASE_DATASET_CONFIG_NAME: EXPECTED_SPLIT_COUNTS,
    PLUS_DATASET_CONFIG_NAME: EXPECTED_PLUS_SPLIT_COUNTS,
}
_REPO_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*/[A-Za-z0-9][A-Za-z0-9._-]*$")


def validate_release_files(
    train: Path,
    validation: Path,
    plus_train: Path,
    plus_validation: Path,
) -> None:
    """Validate both Hub configurations and their one-to-24 derivation relation."""

    reports = {
        "train": validate_instances(
            read_instances(train),
            expected_count=EXPECTED_SPLIT_COUNTS["train"],
            expected_split="train",
            strict_release=True,
        ),
        "validation": validate_instances(
            read_instances(validation),
            expected_count=EXPECTED_SPLIT_COUNTS["validation"],
            expected_split="validation",
            strict_release=True,
        ),
    }
    require_release_ready(reports)

    base_paths = {"train": train, "validation": validation}
    plus_paths = {"train": plus_train, "validation": plus_validation}
    plus_reports = {
        split: validate_instances(
            _iter_verified_plus_views(base_paths[split], plus_paths[split], split=split),
            expected_count=EXPECTED_PLUS_SPLIT_COUNTS[split],
            expected_split=split,
            strict_release=True,
        )
        for split in ("train", "validation")
    }
    _require_reports_ready(
        PLUS_DATASET_CONFIG_NAME,
        plus_reports,
        EXPECTED_PLUS_SPLIT_COUNTS,
    )


def validate_dataset_card(dataset_card: Path) -> None:
    """Require Hub metadata to describe exactly what this uploader publishes."""
    metadata = _read_card_metadata(dataset_card)
    if metadata.get("license") != "cc-by-sa-4.0":
        raise ValueError("Dataset card license must be cc-by-sa-4.0")
    languages = metadata.get("language")
    if (
        not isinstance(languages, list)
        or not all(isinstance(item, str) for item in languages)
        or len(languages) != len(set(languages))
        or set(languages) != set(LANGUAGE_CODES)
    ):
        raise ValueError("Dataset card must list each canonical language exactly once")
    size_categories = metadata.get("size_categories")
    if (
        not isinstance(size_categories, list)
        or not all(isinstance(item, str) for item in size_categories)
        or len(size_categories) != len(set(size_categories))
        or set(size_categories) != {"10K<n<100K", "100K<n<1M"}
    ):
        raise ValueError("Dataset card size categories must describe both release configurations")

    configs = metadata.get("configs")
    if not isinstance(configs, list) or len(configs) != len(DATASET_CONFIG_PATHS):
        raise ValueError("Dataset card must declare exactly the base and parallel configurations")
    declared_configs: dict[str, dict[str, Any]] = {}
    for config in configs:
        if not isinstance(config, dict):
            raise ValueError("Dataset card configuration must be a mapping")
        config_name = config.get("config_name")
        if not isinstance(config_name, str) or config_name in declared_configs:
            raise ValueError("Dataset card config_name values must be unique strings")
        declared_configs[config_name] = config
    if set(declared_configs) != set(DATASET_CONFIG_PATHS):
        raise ValueError(f"Dataset card configs must match the uploader: {DATASET_CONFIG_PATHS!r}")
    if declared_configs[BASE_DATASET_CONFIG_NAME].get("default") is not True:
        raise ValueError(f"Dataset card must mark {BASE_DATASET_CONFIG_NAME!r} as the default")
    if declared_configs[PLUS_DATASET_CONFIG_NAME].get("default") is True:
        raise ValueError("Only the base dataset configuration may be the default")
    for config_name, expected_paths in DATASET_CONFIG_PATHS.items():
        declared_paths = _declared_data_files(declared_configs[config_name])
        if declared_paths != expected_paths:
            raise ValueError(
                f"Dataset card paths must match the uploader for {config_name!r}: "
                f"{expected_paths!r}"
            )


def upload_dataset(
    train: Path,
    validation: Path,
    plus_train: Path,
    plus_validation: Path,
    dataset_card: Path,
    *,
    repo_id: str = "iman998/XHotpotQA",
    dry_run: bool = False,
) -> None:
    if not _REPO_ID.fullmatch(repo_id) or ".." in repo_id:
        raise ValueError("repo_id must have the form 'owner/name'")
    validate_release_files(train, validation, plus_train, plus_validation)
    validate_dataset_card(dataset_card)
    manifest = build_release_manifest(train, validation, plus_train, plus_validation)
    if dry_run:
        return
    token = os.environ.get("HF_TOKEN") or os.environ.get("HUGGINGFACE_HUB_TOKEN")
    if not token:
        raise RuntimeError("Set HF_TOKEN through a secure environment or secret manager")
    try:
        from huggingface_hub import CommitOperationAdd, HfApi
    except ImportError as error:
        raise RuntimeError(
            'Install release dependencies with pip install -e ".[release]"'
        ) from error
    api = HfApi(token=token)
    api.create_repo(repo_id, repo_type="dataset", exist_ok=True, private=False)
    operations = [
        CommitOperationAdd(path_in_repo="README.md", path_or_fileobj=dataset_card),
        CommitOperationAdd(
            path_in_repo=MANIFEST_REPO_PATH,
            path_or_fileobj=BytesIO(
                (json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode(
                    "utf-8"
                )
            ),
        ),
        CommitOperationAdd(
            path_in_repo=DATASET_CONFIG_PATHS[BASE_DATASET_CONFIG_NAME]["train"],
            path_or_fileobj=train,
        ),
        CommitOperationAdd(
            path_in_repo=DATASET_CONFIG_PATHS[BASE_DATASET_CONFIG_NAME]["validation"],
            path_or_fileobj=validation,
        ),
        CommitOperationAdd(
            path_in_repo=DATASET_CONFIG_PATHS[PLUS_DATASET_CONFIG_NAME]["train"],
            path_or_fileobj=plus_train,
        ),
        CommitOperationAdd(
            path_in_repo=DATASET_CONFIG_PATHS[PLUS_DATASET_CONFIG_NAME]["validation"],
            path_or_fileobj=plus_validation,
        ),
    ]
    api.create_commit(
        repo_id=repo_id,
        repo_type="dataset",
        operations=operations,
        commit_message="Publish validated XHotpotQA and XHotpotQA+ release",
    )


def build_release_manifest(
    train: Path,
    validation: Path,
    plus_train: Path,
    plus_validation: Path,
) -> dict[str, Any]:
    """Build the integrity manifest committed beside a validated public release."""

    files = {
        BASE_DATASET_CONFIG_NAME: {"train": train, "validation": validation},
        PLUS_DATASET_CONFIG_NAME: {"train": plus_train, "validation": plus_validation},
    }
    return {
        "manifest_version": "xhotpotqa-release-v2",
        "data_version": __version__,
        "toolkit_version": __version__,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "code_revision": _code_revision(),
        "environment_spec": _environment_spec(),
        "configs": {
            config_name: {
                "default": config_name == BASE_DATASET_CONFIG_NAME,
                "records": sum(DATASET_CONFIG_COUNTS[config_name].values()),
                "splits": {
                    split: {
                        "path": DATASET_CONFIG_PATHS[config_name][split],
                        "records": DATASET_CONFIG_COUNTS[config_name][split],
                        "bytes": path.stat().st_size,
                        "sha256": _file_sha256(path),
                    }
                    for split, path in splits.items()
                },
                **(
                    {
                        "derived_from": BASE_DATASET_CONFIG_NAME,
                        "views_per_source": LANGUAGES_PER_INSTANCE,
                    }
                    if config_name == PLUS_DATASET_CONFIG_NAME
                    else {}
                ),
            }
            for config_name, splits in files.items()
        },
    }


def _iter_verified_plus_views(
    base_path: Path,
    plus_path: Path,
    *,
    split: str,
) -> Iterator[XHotpotInstance]:
    """Yield a parallel split after checking its exact relation to the canonical base."""

    views = iter(read_instances(plus_path))
    for base in read_instances(base_path):
        if base.source_split != split:
            raise ValueError(
                f"Base {base.id!r} belongs to {base.source_split!r}, expected {split!r}"
            )
        for language in LANGUAGE_CODES:
            try:
                view = next(views)
            except StopIteration as error:
                raise ValueError(
                    f"XHotpotQA+ {split!r} ended before {variant_id(base.id, language)!r}"
                ) from error
            _require_derived_view(base, view, language)
            yield view
    try:
        extra = next(views)
    except StopIteration:
        return
    raise ValueError(f"XHotpotQA+ {split!r} contains unexpected trailing view {extra.id!r}")


def _require_derived_view(base: XHotpotInstance, view: XHotpotInstance, language: str) -> None:
    expected_id = variant_id(base.id, language)
    if view.id != expected_id:
        raise ValueError(f"Expected parallel view {expected_id!r}, found {view.id!r}")
    if view.question_language != language or view.answer_language != language:
        raise ValueError(f"Parallel view {view.id!r} must use {language!r} for question and answer")
    fixed_fields = (
        "source_id",
        "source_split",
        "candidates",
        "supporting_facts",
        "question_type",
        "difficulty",
        "provenance",
    )
    changed = [field for field in fixed_fields if getattr(view, field) != getattr(base, field)]
    if changed:
        raise ValueError(f"Parallel view {view.id!r} changed fixed field(s): {changed}")


def _require_reports_ready(
    config_name: str,
    reports: Mapping[str, ValidationReport],
    expected_counts: Mapping[str, int],
) -> None:
    problems: list[str] = []
    for split, expected in expected_counts.items():
        report = reports.get(split)
        if report is None:
            problems.append(f"missing split {split!r}")
        elif report.count != expected or not report.ok:
            problems.append(
                f"{split}: count={report.count:,}, expected={expected:,}, "
                f"duplicates={report.duplicate_ids}, bad_checksums={report.invalid_checksums}, "
                f"errors={len(report.errors)}"
            )
    if problems:
        raise ValueError(
            f"Release validation failed for {config_name!r}:\n- " + "\n- ".join(problems)
        )


def _declared_data_files(config: Mapping[str, Any]) -> dict[str, str]:
    data_files = config.get("data_files")
    if not isinstance(data_files, list):
        raise ValueError("Dataset card data_files must be a list")
    declared_paths: dict[str, str] = {}
    for item in data_files:
        if not isinstance(item, dict):
            raise ValueError("Each dataset card data_files entry must be a mapping")
        split, path = item.get("split"), item.get("path")
        if not isinstance(split, str) or not isinstance(path, str) or split in declared_paths:
            raise ValueError("Dataset card split/path entries must be unique strings")
        declared_paths[split] = path
    return declared_paths


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _code_revision() -> str:
    supplied = os.environ.get("XHOTPOTQA_CODE_COMMIT", "").strip().lower()
    if re.fullmatch(r"[0-9a-f]{40}", supplied):
        return supplied
    repository = Path(__file__).resolve().parents[3]
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repository,
            check=True,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return "unavailable"
    revision = completed.stdout.strip().lower()
    return revision if re.fullmatch(r"[0-9a-f]{40}", revision) else "unavailable"


def _environment_spec() -> dict[str, str]:
    repository = Path(__file__).resolve().parents[3]
    pyproject = repository / "pyproject.toml"
    if not pyproject.is_file():
        return {"path": "pyproject.toml", "sha256": "unavailable"}
    return {"path": "pyproject.toml", "sha256": _file_sha256(pyproject)}


def _read_card_metadata(dataset_card: Path) -> Mapping[str, Any]:
    try:
        lines = dataset_card.read_text(encoding="utf-8").splitlines()
    except OSError as error:
        raise ValueError(f"Could not read dataset card {dataset_card}: {error}") from error
    if not lines or lines[0].strip() != "---":
        raise ValueError("Dataset card must start with YAML front matter")
    try:
        closing_index = next(
            index for index, line in enumerate(lines[1:], start=1) if line.strip() == "---"
        )
    except StopIteration as error:
        raise ValueError("Dataset card YAML front matter is not closed") from error
    try:
        loaded: object = yaml.safe_load("\n".join(lines[1:closing_index]))
    except yaml.YAMLError as error:
        raise ValueError(f"Dataset card contains invalid YAML: {error}") from error
    if not isinstance(loaded, dict) or not all(isinstance(key, str) for key in loaded):
        raise ValueError("Dataset card YAML front matter must be a mapping")
    return cast(dict[str, Any], loaded)
