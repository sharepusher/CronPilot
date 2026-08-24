#!/usr/bin/env python3
"""CI gate: disallow deprecated Flat UI button classes in templates.

Usage:
    python scripts/audit_button_classes.py          # full report
    python scripts/audit_button_classes.py --check  # CI mode (exit 1 on violation)

Deprecated classes: btn-mini, btn-small (Flat UI / Bootstrap 2 remnants).
Use cp-btn-sm / cp-btn-base / cp-btn-lg instead.
"""
import os
import re
import sys

DEPRECATED = ['btn-mini', 'btn-small']
SCAN_DIRS = ['app/templates']
SCAN_EXTS = ['.html']


def scan():
    violations = []
    for scan_dir in SCAN_DIRS:
        for root, _dirs, files in os.walk(scan_dir):
            for fname in files:
                if not any(fname.endswith(ext) for ext in SCAN_EXTS):
                    continue
                fpath = os.path.join(root, fname)
                with open(fpath, 'r', encoding='utf-8') as f:
                    for lineno, line in enumerate(f, 1):
                        for cls in DEPRECATED:
                            if cls in line:
                                violations.append((fpath, lineno, cls, line.strip()))
    return violations


def main():
    check_mode = '--check' in sys.argv
    violations = scan()

    if not violations:
        print('OK: no deprecated button classes found.')
        sys.exit(0)

    print(f'Found {len(violations)} deprecated button class usage(s):')
    for fpath, lineno, cls, line in violations:
        print(f'  {fpath}:{lineno}  [{cls}]  {line[:100]}')

    if check_mode:
        print('\nCI check FAILED. Replace btn-mini/btn-small with cp-btn-sm/cp-btn-base/cp-btn-lg.')
        sys.exit(1)


if __name__ == '__main__':
    main()
