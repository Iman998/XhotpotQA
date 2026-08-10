"""Validated, credential-safe Hugging Face release helpers."""

from __future__ import annotations

import os
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any, cast

import yaml

from xhotpotqa.data.io import read_instances
from xhotpotqa.data.validation import (
    EXPECTED_SPLIT_COUNTS,
    require_release_ready,
    validate_instances,
)
from xhotpotqa.languages import LANGUAGE_CODES

DATASET_CONFIG_NAME = "xhotpotqa"
DATASET_REPO_PATHS = {
    "train": "data/xhotpotqa/train.jsonl",
    "validation": "data/xhotpotqa/validation.jsonl",
}
_REPO_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*/[A-Za-z0-9][A-Za-z0-9._-]*$")


def validate_release_files(train: Path, validation: Path) -> None:
    reports = {
        "train": validate_instances(
            read_instances(train),
            expected_count=EXPECTED_SPLIT_COUNTS["train"],
            expected_split="train",
        ),
        "validation": validate_instances(
            read_instances(validation),
            expected_count=EXPECTED_SPLIT_COUNTS["validation"],
            expected_split="validation",
        ),
    }
    require_release_ready(reports)


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
    if metadata.get("size_categories") != ["10K<n<100K"]:
        raise ValueError("Dataset card size category must match the 23,066-record release")

    configs = metadata.get("configs")
    if not isinstance(configs, list) or len(configs) != 1:
        raise ValueError("Dataset card must declare exactly one uploadable configuration")
    config = configs[0]
    if not isinstance(config, dict):
        raise ValueError("Dataset card configuration must be a mapping")
    if config.get("config_name") != DATASET_CONFIG_NAME or config.get("default") is not True:
        raise ValueError(f"Dataset card must mark {DATASET_CONFIG_NAME!r} as the default")
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
    if declared_paths != DATASET_REPO_PATHS:
        raise ValueError(f"Dataset card paths must match the uploader: {DATASET_REPO_PATHS!r}")


def upload_dataset(
    train: Path,
    validation: Path,
    dataset_card: Path,
    *,
    repo_id: str = "iman998/XHotpotQA",
    dry_run: bool = False,
) -> None:
    if not _REPO_ID.fullmatch(repo_id) or ".." in repo_id:
        raise ValueError("repo_id must have the form 'owner/name'")
    validate_release_files(train, validation)
    validate_dataset_card(dataset_card)
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
        CommitOperationAdd(path_in_repo=DATASET_REPO_PATHS["train"], path_or_fileobj=train),
        CommitOperationAdd(
            path_in_repo=DATASET_REPO_PATHS["validation"], path_or_fileobj=validation
        ),
    ]
    api.create_commit(
        repo_id=repo_id,
        repo_type="dataset",
        operations=operations,
        commit_message="Publish validated XHotpotQA release",
    )


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
