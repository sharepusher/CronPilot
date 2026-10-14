#!/usr/bin/env python3
"""Independently validate a CronPilot public release archive."""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import re
import sys
import tarfile
from pathlib import Path, PurePosixPath
from urllib.parse import unquote, urlsplit


MARKDOWN_LINK_RE = re.compile(r"!??\[[^\]]*\]\((?P<url>[^)]+)\)")
HTML_LINK_RE = re.compile(r"\b(?:href|src)\s*=\s*['\"](?P<url>[^'\"]+)['\"]", re.IGNORECASE)
DOC_SUFFIXES = {".md", ".html", ".htm"}
REQUIRED = {"README.md", "INSTALL.md", "LICENSE", "RELEASE_NOTES.md", "manage.py", "requirements.txt"}
PROHIBITED_PREFIXES = (
    "doc/assets/screenshots/",
    "doc/qa/assets/",
    "tests/visual_regression/baseline/",
    "tests/",
    ".git/",
)
PROHIBITED_NAMES = {"conf.ini", ".env", "scheduler.lock"}
PROHIBITED_SUFFIXES = {".sqlite", ".sqlite3", ".db", ".pyc", ".log", ".pid"}


def normalize_target(source: str, url: str) -> str | None:
    clean = html.unescape(url.strip().strip("<>"))
    parsed = urlsplit(clean)
    if (
        not clean
        or clean.startswith("#")
        or clean.startswith("/")
        or clean.startswith("//")
        or parsed.scheme in {"http", "https", "mailto", "tel", "data"}
    ):
        return None
    target = PurePosixPath(source).parent / unquote(parsed.path)
    parts: list[str] = []
    for part in target.parts:
        if part in {"", "."}:
            continue
        if part == "..":
            if not parts:
                return "__ESCAPES_PACKAGE__"
            parts.pop()
        else:
            parts.append(part)
    return "/".join(parts)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument(
        "--image-manifest",
        type=Path,
        default=Path("doc/assets/screenshots/manifest.json"),
    )
    args = parser.parse_args()

    errors: list[str] = []
    expected_top = f"cronpilot-{args.version}"
    screenshot_hashes: set[str] = set()
    if args.image_manifest.is_file():
        manifest = json.loads(args.image_manifest.read_text(encoding="utf-8"))
        screenshot_hashes = {entry["sha256"] for entry in manifest.get("assets", [])}

    files: dict[str, bytes] = {}
    with tarfile.open(args.archive, "r:gz") as archive:
        for member in archive.getmembers():
            path = PurePosixPath(member.name)
            if path.is_absolute() or ".." in path.parts:
                errors.append(f"unsafe archive path: {member.name}")
                continue
            if not path.parts or path.parts[0] != expected_top:
                errors.append(f"unexpected top-level path: {member.name}")
                continue
            if member.issym() or member.islnk() or not member.isfile():
                errors.append(f"non-regular archive entry: {member.name}")
                continue
            relative = PurePosixPath(*path.parts[1:]).as_posix()
            handle = archive.extractfile(member)
            if handle is None:
                errors.append(f"unreadable archive entry: {member.name}")
                continue
            data = handle.read()
            files[relative] = data
            if any(relative.startswith(prefix) for prefix in PROHIBITED_PREFIXES):
                errors.append(f"prohibited package path: {relative}")
            if Path(relative).name in PROHIBITED_NAMES or Path(relative).suffix.lower() in PROHIBITED_SUFFIXES:
                errors.append(f"runtime/local artifact in package: {relative}")
            if hashlib.sha256(data).hexdigest() in screenshot_hashes:
                errors.append(f"historical screenshot bytes present in package: {relative}")

    for required in sorted(REQUIRED - set(files)):
        errors.append(f"required package file missing: {required}")

    for path, data in sorted(files.items()):
        if "/" in path and not path.startswith("doc/"):
            continue
        if Path(path).suffix.lower() not in DOC_SUFFIXES:
            continue
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            errors.append(f"documentation file is not UTF-8: {path}")
            continue
        pattern = MARKDOWN_LINK_RE if path.endswith(".md") else HTML_LINK_RE
        for match in pattern.finditer(text):
            target = normalize_target(path, match.group("url"))
            if target is not None and target not in files:
                errors.append(f"broken package-local link: {path} -> {match.group('url')}")

    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        print(f"release asset check failed: {len(errors)} error(s)", file=sys.stderr)
        return 1
    size = args.archive.stat().st_size
    print(f"release asset check passed: {len(files)} files, {size} bytes ({size / 1024 / 1024:.2f} MiB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
