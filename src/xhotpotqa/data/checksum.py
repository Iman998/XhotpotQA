"""Semantic record checksums."""

from __future__ import annotations

import hashlib
from dataclasses import replace

from xhotpotqa.data.io import canonical_json
from xhotpotqa.data.models import XHotpotInstance


def compute_checksum(instance: XHotpotInstance) -> str:
    # These fields describe execution history, not the record's semantic content.
    stable_provenance = replace(
        instance.provenance,
        created_at="",
        retry_count=0,
        validation_status="",
    )
    payload = replace(instance, checksum="", provenance=stable_provenance).to_dict()
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


def with_checksum(instance: XHotpotInstance) -> XHotpotInstance:
    return replace(instance, checksum=compute_checksum(instance))
