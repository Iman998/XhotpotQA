import json
from pathlib import Path

from xhotpotqa.generation.audit import PrivateJsonlAuditLog


def test_private_audit_log_appends_jsonl(tmp_path: Path) -> None:
    path = tmp_path / "private" / "audit.jsonl"
    writer = PrivateJsonlAuditLog(path)

    writer({"status": "accepted", "raw_response": "{}"})

    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["status"] == "accepted"
    assert payload["raw_response"] == "{}"
    assert payload["logged_at"].endswith("+00:00")
