#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Fail CI when deprecated trigger terminology appears in first-party files."""

from __future__ import annotations

import argparse
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INCLUDE_DIRS = (
    "app",
    "tests",
    "scripts",
    "doc",
    ".cursor/rules",
)
INCLUDE_FILES = (
    "README.md",
    "RELEASE_NOTES.md",
    "AGENTS.md",
    "conf.example.ini",
    "conf.ini.example",
)
EXCLUDE_PARTS = (
    "app/static/js/jquery.js",
    "app/static/dist/",
    "doc/archive/",
)
EXCLUDE_FILES = {
    # This document names the deprecated terms in order to define the policy.
    "doc/design/全仓术语治理设计-2026-09.html",
    "doc/design/全仓术语治理设计-2026-09.md",
    # This document describes APScheduler's callback API, not CronPilot's
    # business HTTP terminology.
    "doc/design/任务执行链路可观测性增强方案.html",
    "doc/design/任务执行链路可观测性增强方案.md",
    # Published changelog keeps the wording that version actually shipped.
    "doc/RELEASE_NOTES.html",
    "doc/RELEASE_NOTES.md",
    "doc/postmortem/2026-09-trigger-terminology-cleanup.html",
    "doc/postmortem/2026-09-trigger-terminology-cleanup.md",
    "doc/postmortem/2026-09-任务链路日志Bug修复复盘.html",
    "doc/postmortem/2026-09-任务链路日志Bug修复复盘.md",
    # The checker and its tests must contain the deprecated words to test them.
    "scripts/check_terminology.py",
    "tests/test_check_terminology.py",
}
ALLOW_SUFFIX = {".py", ".md", ".html", ".json", ".ini", ".mdc"}
PATTERN = re.compile(("c" + "allback") + "|" + ("\u56de" + "\u8c03"), re.IGNORECASE)
TECHNICAL_LINE = re.compile(
    r"(?:add_done_callback|callback\s*\(|success/error callback|"
    r"future.{0,80}callback|callback.{0,80}future|beforeSubmit)",
    re.IGNORECASE,
)
# 引用旧文案的兼容分支、复盘、防护测试，不是把业务模型叫回「回调」
HISTORICAL_LINE = re.compile(
    r"(?:旧文案|BLOCKED_URL_PREFIXES|违反教训|单向改|changed from|"
    r"['`「\"]回调URL安全校验未通过)"
)


def is_business_terminology_violation(line):
    """Return True for deprecated business wording, not technical or historical citations."""
    if not PATTERN.search(line):
        return False
    if TECHNICAL_LINE.search(line) or HISTORICAL_LINE.search(line):
        return False
    return True


def _iter_files():
    for rel in INCLUDE_DIRS:
        base = ROOT / rel
        if not base.exists():
            continue
        for p in base.rglob("*"):
            if not p.is_file():
                continue
            rel_path = p.relative_to(ROOT).as_posix()
            if any(part in rel_path for part in EXCLUDE_PARTS):
                continue
            if rel_path in EXCLUDE_FILES:
                continue
            if p.suffix in ALLOW_SUFFIX:
                yield p

    for name in INCLUDE_FILES:
        p = ROOT / name
        if p.exists() and p.is_file():
            yield p


def find_violations():
    """Return business-terminology hits, preserving legitimate technical callbacks."""
    hits = []
    for p in sorted(set(_iter_files())):
        try:
            text = p.read_text(encoding="utf-8")
        except Exception:
            continue
        rel_path = p.relative_to(ROOT).as_posix()
        for idx, line in enumerate(text.splitlines(), 1):
            if is_business_terminology_violation(line):
                hits.append((rel_path, idx, line.strip()))
    return hits


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="Only report violations and exit non-zero.")
    args = parser.parse_args()

    hits = find_violations()

    if hits:
        print("FAIL: found inaccurate terminology in first-party files:")
        for f, line_no, line in hits[:200]:
            print(f"  {f}:{line_no}: {line}")
        if len(hits) > 200:
            print(f"  ... {len(hits) - 200} more")
        return 1

    print("OK: no deprecated trigger terminology found in first-party files.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
