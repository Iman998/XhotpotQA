"""Deterministic and manifest-backed language-assignment strategies."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType
from typing import Any, Protocol

from xhotpotqa.languages import LANGUAGE_CODES, require_language

HASH_ASSIGNMENT_VERSION = "sha256-hash-v1"
MANIFEST_SCHEMA_VERSION = "xhotpotqa-assignment-manifest-v1"
QUESTION_ANSWER_UNIT_ID = "question-answer"
_PARAGRAPH_UNIT = re.compile(r"^paragraph:(0|[1-9][0-9]*)$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class LanguageAssignmentStrategy(Protocol):
    """Assignment behavior and immutable provenance required by generation."""

    @property
    def assignment_version(self) -> str: ...

    @property
    def assignment_manifest_sha256(self) -> str: ...

    @property
    def seed(self) -> int | None: ...

    def validate_source(self, source_id: str, unit_ids: Sequence[str]) -> None:
        """Validate that this strategy can assign every requested source unit."""

    def assign(self, source_id: str, unit_id: str) -> str:
        """Return the target language for one immutable source unit."""


@dataclass(frozen=True, slots=True)
class LanguageAssigner:
    """Shard-independent assignment derived from a seed and immutable IDs."""

    seed: int
    languages: tuple[str, ...] = LANGUAGE_CODES

    @property
    def assignment_version(self) -> str:
        return HASH_ASSIGNMENT_VERSION

    @property
    def assignment_manifest_sha256(self) -> str:
        return ""

    def validate_source(self, source_id: str, unit_ids: Sequence[str]) -> None:
        if not source_id:
            raise ValueError("source_id must be non-empty")
        if not unit_ids:
            raise ValueError(f"Source {source_id!r} has no assignable units")

    def assign(self, source_id: str, unit_id: str) -> str:
        """Map an immutable unit ID to a language without mutable RNG state."""
        key = f"{self.seed}\x1f{source_id}\x1f{unit_id}".encode()
        digest = hashlib.sha256(key).digest()
        index = int.from_bytes(digest[:8], "big") % len(self.languages)
        return self.languages[index]


@dataclass(frozen=True, slots=True)
class ManifestLanguageAssigner:
    """Replay a frozen source/unit/language assignment manifest exactly."""

    assignment_version: str
    assignment_manifest_sha256: str
    _assignments: Mapping[str, Mapping[str, str]] = field(repr=False)
    seed: None = field(default=None, init=False)

    @classmethod
    def from_path(cls, path: Path) -> ManifestLanguageAssigner:
        """Read, hash, and strictly validate a UTF-8 JSON manifest."""
        raw = path.read_bytes()
        try:
            payload = json.loads(raw, object_pairs_hook=_object_without_duplicate_keys)
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ValueError(f"Invalid assignment manifest JSON in {path}: {error}") from error
        digest = hashlib.sha256(raw).hexdigest()
        return cls.from_mapping(payload, manifest_sha256=digest)

    @classmethod
    def from_mapping(
        cls,
        payload: object,
        *,
        manifest_sha256: str,
    ) -> ManifestLanguageAssigner:
        """Validate a decoded manifest and construct an immutable assigner."""
        if not isinstance(payload, Mapping):
            raise ValueError("Assignment manifest root must be a JSON object")
        expected_root_keys = {"schema_version", "assignment_version", "assignments"}
        if set(payload) != expected_root_keys:
            raise ValueError(
                "Assignment manifest must contain exactly schema_version, "
                "assignment_version, and assignments"
            )
        if payload["schema_version"] != MANIFEST_SCHEMA_VERSION:
            raise ValueError(
                f"Unsupported assignment manifest schema_version: {payload['schema_version']!r}"
            )
        assignment_version = payload["assignment_version"]
        if not isinstance(assignment_version, str) or not assignment_version.strip():
            raise ValueError("assignment_version must be a non-empty string")
        if not _SHA256.fullmatch(manifest_sha256):
            raise ValueError("manifest_sha256 must be a lowercase SHA-256 digest")

        raw_assignments = payload["assignments"]
        if not isinstance(raw_assignments, Mapping) or not raw_assignments:
            raise ValueError("assignments must be a non-empty source-ID mapping")
        assignments: dict[str, Mapping[str, str]] = {}
        for source_id, raw_units in raw_assignments.items():
            if not isinstance(source_id, str) or not source_id:
                raise ValueError("Every assignment source_id must be a non-empty string")
            assignments[source_id] = _validate_unit_assignments(source_id, raw_units)
        return cls(
            assignment_version=assignment_version,
            assignment_manifest_sha256=manifest_sha256,
            _assignments=MappingProxyType(assignments),
        )

    def validate_source(self, source_id: str, unit_ids: Sequence[str]) -> None:
        units = self._source_assignments(source_id)
        requested = set(unit_ids)
        available = set(units)
        if requested != available:
            missing = sorted(requested - available)
            unexpected = sorted(available - requested)
            raise ValueError(
                f"Assignment manifest units do not match source {source_id!r}: "
                f"missing={missing}, unexpected={unexpected}"
            )

    def assign(self, source_id: str, unit_id: str) -> str:
        units = self._source_assignments(source_id)
        try:
            return units[unit_id]
        except KeyError as error:
            raise ValueError(
                f"Assignment manifest has no unit {unit_id!r} for source {source_id!r}"
            ) from error

    def iter_assignments(self) -> tuple[tuple[str, str, str], ...]:
        """Return stable ``(source_id, unit_id, target_language)`` audit keys."""
        return tuple(
            (source_id, unit_id, units[unit_id])
            for source_id, units in sorted(self._assignments.items())
            for unit_id in _ordered_unit_ids(units)
        )

    def _source_assignments(self, source_id: str) -> Mapping[str, str]:
        try:
            return self._assignments[source_id]
        except KeyError as error:
            raise ValueError(f"Assignment manifest has no source_id {source_id!r}") from error


def _validate_unit_assignments(source_id: str, payload: Any) -> Mapping[str, str]:
    if not isinstance(payload, Mapping):
        raise ValueError(f"Assignments for source {source_id!r} must be a JSON object")
    if QUESTION_ANSWER_UNIT_ID not in payload:
        raise ValueError(f"Assignments for source {source_id!r} lack {QUESTION_ANSWER_UNIT_ID!r}")
    paragraph_indices: set[int] = set()
    normalized: dict[str, str] = {}
    for unit_id, language in payload.items():
        if not isinstance(unit_id, str):
            raise ValueError(f"Source {source_id!r} contains a non-string unit ID")
        if unit_id != QUESTION_ANSWER_UNIT_ID:
            match = _PARAGRAPH_UNIT.fullmatch(unit_id)
            if match is None:
                raise ValueError(f"Source {source_id!r} has invalid unit ID {unit_id!r}")
            paragraph_indices.add(int(match.group(1)))
        if not isinstance(language, str):
            raise ValueError(f"Language for ({source_id!r}, {unit_id!r}) must be a string")
        require_language(language)
        normalized[unit_id] = language
    if not paragraph_indices:
        raise ValueError(f"Source {source_id!r} must assign at least paragraph:0")
    expected_indices = set(range(max(paragraph_indices) + 1))
    if paragraph_indices != expected_indices:
        missing = sorted(expected_indices - paragraph_indices)
        raise ValueError(
            f"Source {source_id!r} has non-contiguous paragraph units: missing={missing}"
        )
    return MappingProxyType(normalized)


def _ordered_unit_ids(units: Mapping[str, str]) -> tuple[str, ...]:
    paragraphs = sorted(
        (unit_id for unit_id in units if unit_id != QUESTION_ANSWER_UNIT_ID),
        key=lambda unit_id: int(unit_id.partition(":")[2]),
    )
    return (QUESTION_ANSWER_UNIT_ID, *paragraphs)


def _object_without_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Assignment manifest contains duplicate JSON key {key!r}")
        result[key] = value
    return result
