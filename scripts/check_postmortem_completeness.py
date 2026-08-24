#!/usr/bin/env python3
"""
CI Gate: Postmortem documentation completeness checker.

Checks:
1. Every doc/postmortem/*.html has a matching .md (HTML↔MD sync)
2. Every doc/postmortem/*.html is referenced in RELEASE_NOTES.md
3. If app/ files are modified (vs main branch), RELEASE_NOTES.md must also be modified

Usage:
    python scripts/check_postmortem_completeness.py --check
    python scripts/check_postmortem_completeness.py --verbose

Exit codes:
    0 = all checks pass
    1 = failures found
"""

import os
import sys
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
POSTMORTEM_DIR = ROOT / "doc" / "postmortem"
RELEASE_NOTES = ROOT / "RELEASE_NOTES.md"


def get_modified_files_vs_main():
    """Get files modified compared to main/master branch."""
    for branch in ["main", "master"]:
        try:
            result = subprocess.run(
                ["git", "diff", "--name-only", f"{branch}...HEAD"],
                capture_output=True, text=True, cwd=ROOT
            )
            if result.returncode == 0:
                return set(result.stdout.strip().split('\n')) if result.stdout.strip() else set()
        except Exception:
            continue
    # Fallback: check staged + unstaged
    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", "HEAD"],
            capture_output=True, text=True, cwd=ROOT
        )
        if result.returncode == 0:
            return set(result.stdout.strip().split('\n')) if result.stdout.strip() else set()
    except Exception:
        pass
    return set()


def check_html_md_sync():
    """Check every postmortem HTML has a corresponding MD."""
    errors = []
    if not POSTMORTEM_DIR.exists():
        return errors

    for html_file in sorted(POSTMORTEM_DIR.glob("*.html")):
        md_file = html_file.with_suffix(".md")
        if not md_file.exists():
            errors.append(f"Missing MD for: {html_file.relative_to(ROOT)}")
    return errors


def check_release_notes_references():
    """Check postmortem files are referenced in RELEASE_NOTES."""
    warnings = []
    if not RELEASE_NOTES.exists():
        return ["RELEASE_NOTES.md not found"]

    release_content = RELEASE_NOTES.read_text(encoding="utf-8")

    if not POSTMORTEM_DIR.exists():
        return warnings

    for html_file in sorted(POSTMORTEM_DIR.glob("*.html")):
        stem = html_file.stem
        # Check if any reasonable reference exists
        if stem not in release_content and html_file.name not in release_content:
            warnings.append(
                f"Postmortem not referenced in RELEASE_NOTES: {html_file.relative_to(ROOT)}"
            )
    return warnings


def check_app_changes_have_release_notes():
    """If app/ or .cursor/rules/ files changed, RELEASE_NOTES should too."""
    modified = get_modified_files_vs_main()
    if not modified:
        return []

    has_app_changes = any(
        f.startswith("app/") or f.startswith(".cursor/rules/")
        for f in modified
    )
    has_release_notes = "RELEASE_NOTES.md" in modified

    if has_app_changes and not has_release_notes:
        return [
            "Code changes detected in app/ or .cursor/rules/ but RELEASE_NOTES.md "
            "is not modified. Per documentation rules, changes must be reflected in "
            "RELEASE_NOTES."
        ]
    return []


def main():
    verbose = "--verbose" in sys.argv
    check_mode = "--check" in sys.argv

    all_errors = []
    all_warnings = []

    # Check 1: HTML↔MD sync
    errors = check_html_md_sync()
    if errors:
        all_errors.extend(errors)
    elif verbose:
        print("✓ All postmortem HTML files have matching MD")

    # Check 2: RELEASE_NOTES references
    warnings = check_release_notes_references()
    if warnings:
        all_warnings.extend(warnings)
    elif verbose:
        print("✓ All postmortem files referenced in RELEASE_NOTES")

    # Check 3: App changes → RELEASE_NOTES sync
    errors = check_app_changes_have_release_notes()
    if errors:
        all_errors.extend(errors)
    elif verbose:
        print("✓ RELEASE_NOTES in sync with code changes")

    # Report
    if all_errors:
        print(f"\n{'='*60}")
        print(f"POSTMORTEM COMPLETENESS CHECK: {len(all_errors)} ERROR(S)")
        print(f"{'='*60}")
        for e in all_errors:
            print(f"  ✗ {e}")

    if all_warnings:
        print(f"\n{'='*60}")
        print(f"WARNINGS: {len(all_warnings)}")
        print(f"{'='*60}")
        for w in all_warnings:
            print(f"  ⚠ {w}")

    if not all_errors and not all_warnings:
        if verbose or check_mode:
            print("All postmortem documentation checks passed ✓")

    if all_errors and check_mode:
        sys.exit(1)

    sys.exit(0)


if __name__ == "__main__":
    main()
