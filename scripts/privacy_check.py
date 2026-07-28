#!/usr/bin/env python3
"""Fail when publishable Git files look private or contain credentials."""

import argparse
import re
import subprocess
from pathlib import Path


PRIVATE_SUFFIXES = {
    ".db",
    ".sqlite",
    ".sqlite3",
    ".pdf",
    ".docx",
    ".odt",
    ".rtf",
    ".epub",
}
PRIVATE_PREFIXES = (
    "local-data/",
    "cv/",
    "backend/static/documents/",
)
ALLOWED_PRIVATE_PATH_EXCEPTIONS = {
    "backend/static/.gitkeep",
}
SECRET_PATTERNS = {
    "provider credential": re.compile(
        r"(?:sk-[A-Za-z0-9_-]{16,}|AIza[A-Za-z0-9_-]{20,}|"
        r"gh[pousr]_[A-Za-z0-9_]{20,})"
    ),
    "private key material": re.compile(
        r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"
    ),
    "absolute home path": re.compile(
        r"(?:/" + r"home/|/" + r"Users/)[^/\s]+/"
    ),
}


def git_paths(staged_only: bool) -> list[Path]:
    if staged_only:
        command = [
            "git",
            "diff",
            "--cached",
            "--name-only",
            "--diff-filter=ACMR",
            "-z",
        ]
    else:
        command = [
            "git",
            "ls-files",
            "--cached",
            "--others",
            "--exclude-standard",
            "-z",
        ]
    output = subprocess.check_output(command)
    return [Path(item) for item in output.decode().split("\0") if item]


def private_path_reason(path: Path) -> str | None:
    normalized = path.as_posix()
    if normalized in ALLOWED_PRIVATE_PATH_EXCEPTIONS:
        return None
    if path.name == ".env" or (
        path.name.startswith(".env.") and path.name != ".env.example"
    ):
        return "environment file"
    if path.suffix.lower() in PRIVATE_SUFFIXES:
        return f"private document or database ({path.suffix.lower()})"
    if normalized == "backend/static/profile.jpg":
        return "profile photo"
    if any(normalized.startswith(prefix) for prefix in PRIVATE_PREFIXES):
        return "private data directory"
    return None


def scan(paths: list[Path]) -> list[str]:
    findings = []
    for path in paths:
        reason = private_path_reason(path)
        if reason:
            findings.append(f"{path}: blocked path ({reason})")
            continue

        try:
            content = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue

        for line_number, line in enumerate(content.splitlines(), 1):
            for label, pattern in SECRET_PATTERNS.items():
                if pattern.search(line):
                    findings.append(f"{path}:{line_number}: {label}")
    return findings


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--staged",
        action="store_true",
        help="scan only files currently staged for commit",
    )
    args = parser.parse_args()

    paths = git_paths(args.staged)
    findings = scan(paths)
    if findings:
        print("Privacy check failed:")
        for finding in findings:
            print(f"  - {finding}")
        return 1

    scope = "staged" if args.staged else "publishable"
    print(f"Privacy check passed for {len(paths)} {scope} files.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
