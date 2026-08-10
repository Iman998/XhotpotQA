"""Dataset-level validation and publication gates."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from xhotpotqa.data.checksum import compute_checksum
from xhotpotqa.data.models import XHotpotInstance

EXPECTED_SPLIT_COUNTS = {"train": 15_661, "validation": 7_405}


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
