"""Semantic record checksums."""

from __future__ import annotations

import hashlib
from dataclasses import replace

from xhotpotqa.data.io import canonical_json
from xhotpotqa.data.models import XHotpotInstance


def compute_checksum(instance: XHotpotInstance) -> str:
    payload = replace(instance, checksum="").to_dict()
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


def with_checksum(instance: XHotpotInstance) -> XHotpotInstance:
    return replace(instance, checksum=compute_checksum(instance))
