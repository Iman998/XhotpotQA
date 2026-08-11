"""Dataset-level validation and publication gates."""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass

from xhotpotqa.data.checksum import compute_checksum
from xhotpotqa.data.models import XHotpotInstance

EXPECTED_SPLIT_COUNTS = {"train": 15_661, "validation": 7_405}
_QUESTION_TYPES = {"bridge", "comparison"}
_DIFFICULTIES = {"easy", "medium", "hard"}
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True, slots=True)
class ValidationReport:
    count: int
    duplicate_ids: int
    invalid_checksums: int
    errors: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return not self.errors and self.duplicate_ids == 0 and self.invalid_checksums == 0


def validate_instances(
    instances: Iterable[XHotpotInstance],
    *,
    expected_count: int | None = None,
    expected_split: str | None = None,
    strict_release: bool = False,
) -> ValidationReport:
    seen: set[str] = set()
    count = duplicate_ids = invalid_checksums = 0
    errors: list[str] = []
    for instance in instances:
        count += 1
        try:
            instance.validate()
        except ValueError as error:
            errors.append(f"{instance.id}: {error}")
            continue
        if strict_release:
            errors.extend(_strict_release_errors(instance))
        if expected_split is not None and instance.source_split != expected_split:
            errors.append(
                f"{instance.id}: expected split {expected_split!r}, found {instance.source_split!r}"
            )
        if instance.id in seen:
            duplicate_ids += 1
        seen.add(instance.id)
        if not instance.checksum or instance.checksum != compute_checksum(instance):
            invalid_checksums += 1
    if expected_count is not None and count != expected_count:
        errors.append(f"Expected {expected_count:,} records, found {count:,}")
    return ValidationReport(count, duplicate_ids, invalid_checksums, tuple(errors))


def _strict_release_errors(instance: XHotpotInstance) -> list[str]:
    errors: list[str] = []
    prefix = f"{instance.id}: "
    if instance.question_type not in _QUESTION_TYPES:
        errors.append(prefix + f"unsupported question_type {instance.question_type!r}")
    if instance.difficulty not in _DIFFICULTIES:
        errors.append(prefix + f"unsupported difficulty {instance.difficulty!r}")
    for candidate in instance.candidates:
        if candidate.source_title is None or not candidate.source_title.strip():
            errors.append(prefix + f"candidate {candidate.id!r} lacks source_title")
        if candidate.source_sentences is None:
            errors.append(prefix + f"candidate {candidate.id!r} lacks source_sentences")

    provenance = instance.provenance
    required_text = {
        "schema_version": provenance.schema_version,
        "source_dataset": provenance.source_dataset,
        "source_license": provenance.source_license,
        "assignment_version": provenance.assignment_version,
        "translation_model": provenance.translation_model,
        "translation_revision": provenance.translation_revision,
        "prompt_version": provenance.prompt_version,
        "created_at": provenance.created_at,
        "validation_status": provenance.validation_status,
    }
    for field_name, value in required_text.items():
        if not value.strip():
            errors.append(prefix + f"provenance.{field_name} is required")
    if not _SHA256.fullmatch(provenance.prompt_hash):
        errors.append(prefix + "provenance.prompt_hash must be a lowercase SHA-256 digest")
    if provenance.assignment_manifest_sha256 and not _SHA256.fullmatch(
        provenance.assignment_manifest_sha256
    ):
        errors.append(
            prefix + "provenance.assignment_manifest_sha256 must be a lowercase SHA-256 digest"
        )
    if provenance.retry_count < 0:
        errors.append(prefix + "provenance.retry_count cannot be negative")
    return errors


def require_release_ready(reports: dict[str, ValidationReport]) -> None:
    problems: list[str] = []
    for split, expected in EXPECTED_SPLIT_COUNTS.items():
        report = reports.get(split)
        if report is None:
            problems.append(f"Missing required split: {split}")
        elif report.count != expected or not report.ok:
            problems.append(
                f"{split}: count={report.count:,}, expected={expected:,}, "
                f"duplicates={report.duplicate_ids}, bad_checksums={report.invalid_checksums}, "
                f"errors={len(report.errors)}"
            )
    if problems:
        raise ValueError("Release validation failed:\n- " + "\n- ".join(problems))
