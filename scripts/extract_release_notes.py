#!/usr/bin/env python3
"""Extract validated GitHub Release notes for a version."""

from __future__ import annotations

import argparse
import re
from pathlib import Path


SECTION_RE = re.compile(r"^## \[(?P<name>[^]]+)](?:\s.*)?$", re.MULTILINE)
REQUIRED_HEADINGS = (
    "### What changed",
    "### Why",
    "### Validation",
    "### Compatibility & Risk",
)


def extract_release_notes(text: str, version: str) -> str:
    """Return the version section, falling back to Unreleased before tagging."""
    matches = list(SECTION_RE.finditer(text))
    for target in (version, "Unreleased"):
        for index, match in enumerate(matches):
            if match.group("name") != target:
                continue
            end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
            body = text[match.end() : end].strip()
            missing = [heading for heading in REQUIRED_HEADINGS if heading not in body]
            if missing:
                raise ValueError(
                    f"release notes section [{target}] is missing: {', '.join(missing)}"
                )
            return f"# CronPilot {version}\n\n{body}\n"
    raise ValueError(f"no [{version}] or [Unreleased] release notes section found")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", required=True, help="release version without the v prefix")
    parser.add_argument("--input", type=Path, default=Path("RELEASE_NOTES.md"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    try:
        notes = extract_release_notes(args.input.read_text(encoding="utf-8"), args.version)
    except (OSError, ValueError) as exc:
        raise SystemExit(str(exc)) from exc
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(notes, encoding="utf-8")
    print(f"prepared release notes: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
