#!/usr/bin/env python3
"""
check_css_token_reachability.py — CronPilot CSS Token & Keyframe Reachability Guard

Detects two classes of CSS "silent failures":
  1. var(--cp-*) references to undefined custom properties
  2. animation-name references to undefined @keyframes

Usage:
  python scripts/check_css_token_reachability.py          # report mode
  python scripts/check_css_token_reachability.py --check  # CI mode (exit 1 on violations)
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CSS_DIR = ROOT / "app" / "static" / "css"

THEME_FILE = CSS_DIR / "console-theme.css"
REDESIGN_FILES = sorted(CSS_DIR.glob("redesign-*.css"))

_VAR_REF = re.compile(r'var\(\s*(--cp-[a-z0-9-]+)')
_PROP_DEF = re.compile(r'(--cp-[a-z0-9-]+)\s*:')
_KEYFRAME_DEF = re.compile(r'@keyframes\s+([\w-]+)')
_ANIMATION_REF = re.compile(r'animation(?:-name)?\s*:\s*([^;{]+)')
_ANIMATION_NAME = re.compile(r'[a-zA-Z][\w-]*')

BUILTIN_ANIMATIONS = {'none', 'initial', 'inherit', 'unset', 'revert'}
TIMING_KEYWORDS = {
    'ease', 'ease-in', 'ease-out', 'ease-in-out', 'linear',
    'step-start', 'step-end', 'infinite', 'alternate', 'reverse',
    'alternate-reverse', 'normal', 'forwards', 'backwards', 'both',
    'running', 'paused',
}
CSS_UNITS_AND_NOISE = {
    's', 'ms', 'important',
}
_IMPORTANT_RE = re.compile(r'!important')


def collect_definitions():
    """Collect all --cp-* definitions and @keyframes from theme + redesign files."""
    defined_tokens = set()
    defined_keyframes = set()

    all_files = [THEME_FILE] + REDESIGN_FILES
    for f in all_files:
        if not f.exists():
            continue
        text = f.read_text(encoding='utf-8')
        for m in _PROP_DEF.finditer(text):
            defined_tokens.add(m.group(1))
        for m in _KEYFRAME_DEF.finditer(text):
            defined_keyframes.add(m.group(1))

    return defined_tokens, defined_keyframes


def collect_references():
    """Collect all var(--cp-*) references and animation-name usages in redesign files."""
    token_refs = []
    animation_refs = []

    for f in REDESIGN_FILES:
        if not f.exists():
            continue
        lines = f.read_text(encoding='utf-8').splitlines()
        relpath = f.relative_to(ROOT)

        for lineno, line in enumerate(lines, 1):
            for m in _VAR_REF.finditer(line):
                token_refs.append((str(relpath), lineno, m.group(1)))

            for m in _ANIMATION_REF.finditer(line):
                val = _IMPORTANT_RE.sub('', m.group(1)).strip()
                for name_m in _ANIMATION_NAME.finditer(val):
                    name = name_m.group(0)
                    if name.lower() in BUILTIN_ANIMATIONS:
                        continue
                    if name.lower() in TIMING_KEYWORDS:
                        continue
                    if name.lower() in CSS_UNITS_AND_NOISE:
                        continue
                    if name.replace('.', '').replace('-', '').isdigit():
                        continue
                    animation_refs.append((str(relpath), lineno, name))

    return token_refs, animation_refs


def scan():
    defined_tokens, defined_keyframes = collect_definitions()
    token_refs, animation_refs = collect_references()

    violations = []

    for filepath, lineno, token in token_refs:
        if token not in defined_tokens:
            fallback_token = None
            violations.append({
                'file': filepath,
                'line': lineno,
                'type': 'undefined-token',
                'detail': f'var({token}) references undefined custom property',
            })

    for filepath, lineno, name in animation_refs:
        if name not in defined_keyframes:
            violations.append({
                'file': filepath,
                'line': lineno,
                'type': 'undefined-keyframe',
                'detail': f'animation references undefined @keyframes "{name}"',
            })

    return violations


def main():
    check_mode = '--check' in sys.argv
    violations = scan()

    if not violations:
        print("✓ All CSS token references and animation names are reachable.")
        return 0

    by_file = {}
    for v in violations:
        by_file.setdefault(v['file'], []).append(v)

    for filepath in sorted(by_file):
        print(f"\n{filepath}:")
        for v in sorted(by_file[filepath], key=lambda x: x['line']):
            print(f"  [{v['type']}] line {v['line']}: {v['detail']}")

    print(f"\n{'✗' if check_mode else '!'} {len(violations)} reachability violation(s) found")

    if check_mode:
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
