#!/usr/bin/env python3
"""
check_brand_svg_consistency.py — Verify brand SVG include chain is intact.

Usage:
    python scripts/check_brand_svg_consistency.py          # report
    python scripts/check_brand_svg_consistency.py --check  # CI gate (exit 1 on violation)

Checks:
  1. _brand_paths.html exists and contains expected SVG path data
  2. _brand_block.html includes _brand_paths.html
  3. _sidebar.html includes _brand_paths.html
  4. All 4 auth templates include _brand_block.html
  5. No auth template contains inline SVG brand paths (should use include)
"""

import argparse
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATE_DIR = os.path.join(ROOT, 'app', 'templates', 'redesign')

BRAND_PATHS_FILE = '_brand_paths.html'
BRAND_BLOCK_FILE = '_brand_block.html'
SIDEBAR_FILE = '_sidebar.html'
AUTH_TEMPLATES = ['login.html', 'register.html', 'forgot_password.html', 'complete_profile.html']

EXPECTED_PATH_SIGNATURES = [
    'M6 3H3v18h3',
    'M18 3h3v18h-3',
    'points="12 7 12 12 15.5 14"',
]

PATHS_INCLUDE_PATTERN = re.compile(r"{%\s*include\s+['\"]redesign/_brand_paths\.html['\"]\s*%}")
BLOCK_INCLUDE_PATTERN = re.compile(r"{%\s*include\s+['\"]redesign/_brand_block\.html['\"]\s*%}")


def read_file(filename):
    path = os.path.join(TEMPLATE_DIR, filename)
    if not os.path.exists(path):
        return None
    with open(path, encoding='utf-8') as f:
        return f.read()


def check():
    violations = []

    paths_content = read_file(BRAND_PATHS_FILE)
    if paths_content is None:
        violations.append(f'MISSING: {BRAND_PATHS_FILE} does not exist')
    else:
        for sig in EXPECTED_PATH_SIGNATURES:
            if sig not in paths_content:
                violations.append(f'INCOMPLETE: {BRAND_PATHS_FILE} missing path signature "{sig}"')

    block_content = read_file(BRAND_BLOCK_FILE)
    if block_content is None:
        violations.append(f'MISSING: {BRAND_BLOCK_FILE} does not exist')
    elif not PATHS_INCLUDE_PATTERN.search(block_content):
        violations.append(f'INCLUDE_MISSING: {BRAND_BLOCK_FILE} does not include {BRAND_PATHS_FILE}')

    sidebar_content = read_file(SIDEBAR_FILE)
    if sidebar_content is None:
        violations.append(f'MISSING: {SIDEBAR_FILE} does not exist')
    elif not PATHS_INCLUDE_PATTERN.search(sidebar_content):
        violations.append(f'INCLUDE_MISSING: {SIDEBAR_FILE} does not include {BRAND_PATHS_FILE}')

    for tmpl in AUTH_TEMPLATES:
        content = read_file(tmpl)
        if content is None:
            violations.append(f'MISSING: {tmpl} does not exist')
            continue
        if not BLOCK_INCLUDE_PATTERN.search(content):
            violations.append(f'INCLUDE_MISSING: {tmpl} does not include {BRAND_BLOCK_FILE}')
        for sig in EXPECTED_PATH_SIGNATURES:
            if sig in content:
                violations.append(f'INLINE_SVG: {tmpl} contains inline brand SVG path "{sig}" — should use include')

    return violations


def main():
    parser = argparse.ArgumentParser(description='Check brand SVG include chain consistency')
    parser.add_argument('--check', action='store_true', help='Exit 1 on any violation (CI gate)')
    args = parser.parse_args()

    violations = check()

    if violations:
        for v in violations:
            print(f'  ✗ {v}')
        print(f'\n{len(violations)} violation(s) found.')
        if args.check:
            sys.exit(1)
    else:
        print(f'✓ Brand SVG consistency: include chain intact ({len(AUTH_TEMPLATES)} auth + sidebar + paths)')

    return len(violations)


if __name__ == '__main__':
    main()
