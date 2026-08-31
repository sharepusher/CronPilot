#!/usr/bin/env python3
"""
check_dead_css.py — Detect unreferenced CSS classes in redesign-components.css.

Usage:
    python scripts/check_dead_css.py          # report mode
    python scripts/check_dead_css.py --check  # CI gate (exit 1 if violations > threshold)

Checks every class selector in redesign-components.css against:
  - app/templates/redesign/*.html
  - app/static/js/redesign-*.js
  - app/static/js/common-redesign.js

Classes that are ONLY referenced internally (e.g. keyframe names used within
the same file, or nested selectors like `.parent .child` where .child never
appears alone in templates) are exempt via the INTERNAL_ALLOWLIST.
"""

import argparse
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSS_FILE = os.path.join(ROOT, 'app', 'static', 'css', 'redesign-components.css')
TEMPLATE_DIR = os.path.join(ROOT, 'app', 'templates', 'redesign')
JS_DIR = os.path.join(ROOT, 'app', 'static', 'js')

THRESHOLD = 0

INTERNAL_ALLOWLIST = frozenset([
    'toast-exit',
    'open',
    'disabled',
    'active',
    'success',
    'error',
    'warning',
    'focused',
])

CLASS_SELECTOR_RE = re.compile(r'\.([\w-]+)')


def extract_classes(css_path):
    """Extract all class selectors from CSS file, skipping comments and @rules."""
    classes = set()
    with open(css_path, 'r', encoding='utf-8') as f:
        content = f.read()

    content = re.sub(r'/\*.*?\*/', '', content, flags=re.DOTALL)

    for line in content.split('\n'):
        stripped = line.strip()
        if stripped.startswith('@') or stripped.startswith('from') or stripped.startswith('to'):
            continue
        if not stripped or ':' in stripped.split('{')[0].split(',')[0] and '{' not in stripped:
            continue
        if '{' in line:
            selector_part = line.split('{')[0]
            matches = CLASS_SELECTOR_RE.findall(selector_part)
            for cls in matches:
                if cls not in INTERNAL_ALLOWLIST and not re.match(r'^\d', cls):
                    classes.add(cls)

    return classes


def search_references(class_name, search_files):
    """Check if a class name appears in any of the search files."""
    patterns = [
        class_name,
        f'"{class_name}"',
        f"'{class_name}'",
    ]

    for fpath in search_files:
        try:
            with open(fpath, 'r', encoding='utf-8') as f:
                content = f.read()
        except (OSError, UnicodeDecodeError):
            continue

        for pattern in patterns:
            if pattern in content:
                return True

    return False


def collect_search_files():
    """Collect all template and JS files to search."""
    files = []

    if os.path.isdir(TEMPLATE_DIR):
        for fname in os.listdir(TEMPLATE_DIR):
            if fname.endswith('.html'):
                files.append(os.path.join(TEMPLATE_DIR, fname))

    js_patterns = ['redesign-shell.js', 'redesign-theme.js',
                   'redesign-toast.js', 'redesign-confirm.js', 'common-redesign.js']
    for fname in js_patterns:
        fpath = os.path.join(JS_DIR, fname)
        if os.path.isfile(fpath):
            files.append(fpath)

    return files


def main():
    parser = argparse.ArgumentParser(description='Check for dead CSS classes')
    parser.add_argument('--check', action='store_true',
                        help='Exit 1 if violations exceed threshold')
    args = parser.parse_args()

    if not os.path.isfile(CSS_FILE):
        print(f'CSS file not found: {CSS_FILE}')
        sys.exit(1)

    classes = extract_classes(CSS_FILE)
    search_files = collect_search_files()

    dead_classes = []
    for cls in sorted(classes):
        if not search_references(cls, search_files):
            dead_classes.append(cls)

    if dead_classes:
        print(f'Dead CSS classes in redesign-components.css ({len(dead_classes)}):')
        for cls in dead_classes:
            print(f'  .{cls}')
    else:
        print('No dead CSS classes found.')

    if args.check:
        if len(dead_classes) > THRESHOLD:
            print(f'\n✗ {len(dead_classes)} dead class(es) exceed threshold ({THRESHOLD})')
            sys.exit(1)
        else:
            print(f'\n✓ Dead CSS check passed (≤{THRESHOLD})')
            sys.exit(0)


if __name__ == '__main__':
    main()
