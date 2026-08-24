#!/usr/bin/env python3
"""Fail when likely credentials are present in tracked/current candidate files."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATTERNS = {
    "credential-bearing URL": re.compile(
        rb"[a-z][a-z0-9+.-]*://[^/@\s:]+:[^/@\s]+@", re.IGNORECASE
    ),
    "private key": re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "AWS access key": re.compile(rb"AKIA[0-9A-Z]{16}"),
}
ALLOWLIST = {
    ".env.example",
    "backend/alembic.ini",
    "backend/tests/test_secret_redaction.py",
    # Explicit disposable localhost-only CI database fixture.
    ".github/workflows/agents-browser.yml",
    # Redaction and production-validation test uses non-routable example values.
    "backend/tests/test_production_runtime.py",
}


def candidate_files() -> list[Path]:
    result = subprocess.run(
        [
            "git",
            "ls-files",
            "--cached",
            "--others",
            "--exclude-standard",
        ],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return [ROOT / name for name in result.stdout.splitlines() if name]


def main() -> int:
    findings: list[tuple[str, str]] = []
    for path in candidate_files():
        relative = path.relative_to(ROOT).as_posix()
        if relative in ALLOWLIST or not path.is_file():
            continue
        try:
            data = path.read_bytes()
        except OSError:
            continue
        for name, pattern in PATTERNS.items():
            if pattern.search(data):
                findings.append((relative, name))

    for relative, name in findings:
        print(f"{relative}: possible {name}")
    print(f"Secret scan: {len(findings)} finding(s)")
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
