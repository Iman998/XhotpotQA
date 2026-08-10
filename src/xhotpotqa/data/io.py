"""Streaming JSONL I/O with canonical serialization."""

from __future__ import annotations

import json
from collections.abc import Iterable, Iterator, Mapping
from pathlib import Path
from typing import Any

from xhotpotqa.data.models import XHotpotInstance


def canonical_json(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def read_jsonl(path: Path) -> Iterator[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, start=1):
            if not line.strip():
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError as error:
                raise ValueError(f"Invalid JSON at {path}:{line_number}: {error}") from error
            if not isinstance(item, dict):
                raise ValueError(f"Expected a JSON object at {path}:{line_number}")
            yield item


def read_instances(path: Path) -> Iterator[XHotpotInstance]:
    for payload in read_jsonl(path):
        instance = XHotpotInstance.from_dict(payload)
        instance.validate()
        yield instance


def write_instances(path: Path, instances: Iterable[XHotpotInstance]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with path.open("w", encoding="utf-8", newline="\n") as stream:
        for instance in instances:
            instance.validate()
            stream.write(canonical_json(instance.to_dict()) + "\n")
            count += 1
    return count
