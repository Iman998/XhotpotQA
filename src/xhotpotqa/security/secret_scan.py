"""Small, deterministic secret scanner for source and release automation."""

from __future__ import annotations

import argparse
import re
from collections.abc import Iterable, Iterator, Sequence
from dataclasses import dataclass
from pathlib import Path

_SKIPPED_DIRECTORIES = frozenset(
    {
        ".git",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        ".venv",
        "__pycache__",
        "build",
        "dist",
        "outputs",
        "processed",
        "raw",
    }
)
_MAX_TEXT_BYTES = 2 * 1024 * 1024
_PLACEHOLDERS = frozenset(
    {"", "empty", "example", "placeholder", "redacted", "replace-me", "unset"}
)


@dataclass(frozen=True, slots=True)
class SecretPattern:
    name: str
    regex: re.Pattern[str]
    value_group: str | None = None


@dataclass(frozen=True, slots=True)
class Finding:
    path: Path
    line: int
    kind: str

    def display(self, root: Path) -> str:
        try:
            shown_path = self.path.resolve().relative_to(root.resolve())
        except ValueError:
            shown_path = self.path
        return f"{shown_path}:{self.line}: potential {self.kind}"


_PATTERNS = (
    SecretPattern("Hugging Face token", re.compile(r"\bhf_[A-Za-z0-9]{20,}\b")),
    SecretPattern("OpenAI-style token", re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b")),
    SecretPattern(
        "GitHub fine-grained token",
        re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b"),
    ),
    SecretPattern("GitHub token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b")),
    SecretPattern("AWS access key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    SecretPattern(
        "private key",
        re.compile("-{5}BEGIN " + "(?:RSA |EC |OPENSSH )?PRIVATE KEY-{5}"),
    ),
    SecretPattern(
        "non-empty credential assignment",
        re.compile(
            r"(?i)\b(?:HF_TOKEN|HUGGINGFACE_HUB_TOKEN|OPENAI_API_KEY|GH_TOKEN|"
            r"GITHUB_TOKEN|AWS_SECRET_ACCESS_KEY)"
            r"\s*[:=]\s*[\"']?(?P<value>[^\s\"'#]+)"
        ),
        value_group="value",
    ),
)


def scan_paths(paths: Iterable[Path]) -> tuple[Finding, ...]:
    findings: list[Finding] = []
    seen: set[Path] = set()
    for path in _iter_files(paths):
        resolved = path.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        text = _read_text(path)
        if text is None:
            continue
        for line_number, line in enumerate(text.splitlines(), start=1):
            for pattern in _PATTERNS:
                match = pattern.regex.search(line)
                if match is None:
                    continue
                if pattern.value_group is not None and _is_placeholder(
                    match.group(pattern.value_group)
                ):
                    continue
                findings.append(Finding(path=path, line=line_number, kind=pattern.name))
    return tuple(findings)


def _iter_files(paths: Iterable[Path]) -> Iterator[Path]:
    for path in paths:
        if path.is_symlink():
            continue
        if path.is_file():
            yield path
            continue
        if not path.is_dir():
            raise FileNotFoundError(f"Scan path does not exist: {path}")
        for candidate in sorted(path.rglob("*")):
            if candidate.is_symlink() or not candidate.is_file():
                continue
            relative_parts = candidate.relative_to(path).parts[:-1]
            if any(part in _SKIPPED_DIRECTORIES for part in relative_parts):
                continue
            yield candidate


def _read_text(path: Path) -> str | None:
    if path.stat().st_size > _MAX_TEXT_BYTES:
        return None
    payload = path.read_bytes()
    if b"\x00" in payload:
        return None
    try:
        return payload.decode("utf-8")
    except UnicodeDecodeError:
        return None


def _is_placeholder(value: str) -> bool:
    normalized = value.strip().strip("<>[]{}()$%").casefold()
    return normalized in _PLACEHOLDERS or normalized.startswith(("your_", "your-"))


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="*", type=Path, default=[Path(".")])
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    root = Path.cwd()
    try:
        findings = scan_paths(args.paths)
    except OSError as error:
        print(f"secret scan failed: {error}")
        return 2
    for finding in findings:
        print(finding.display(root))
    if findings:
        print(f"secret scan found {len(findings)} potential secret(s)")
        return 1
    print("secret scan passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
