"""Opt-in private audit logging for model requests and raw responses."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock

from xhotpotqa.data.io import canonical_json


class PrivateJsonlAuditLog:
    """Append one UTF-8 JSON object per generation attempt.

    Logs contain source text and raw model output. They are intentionally opt-in,
    must stay outside the public dataset, and must be protected as research data.
    """

    def __init__(self, path: Path) -> None:
        if path.exists() and not path.is_file():
            raise ValueError(f"Audit log path is not a file: {path}")
        self._path = path
        self._lock = Lock()

    def __call__(self, record: Mapping[str, object]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "logged_at": datetime.now(timezone.utc).isoformat(),
            **dict(record),
        }
        with self._lock, self._path.open("a", encoding="utf-8", newline="\n") as stream:
            stream.write(canonical_json(payload) + "\n")
