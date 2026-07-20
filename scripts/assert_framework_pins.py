#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Phase D3：断言 Framework Generation 核心 pin 与当前解释器环境一致。

从 requirements.txt（或 --requirements）解析期望版本，经 pip show 比对。
用法:
  python scripts/assert_framework_pins.py
  python scripts/assert_framework_pins.py --python .venv-py311/bin/python
  docker compose exec -T cronpilot bash -c \\
    'cd /opt/cronpilot && source scripts/lib/python.sh && cronpilot_load_runtime \\
     && \"$CRONPILOT_VENV/bin/python\" scripts/assert_framework_pins.py'
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Framework Generation 硬门（Phase D1 同窗；包名列表固定，版本以 requirements 为准）
FRAMEWORK_PIN_NAMES = (
    'Flask',
    'Werkzeug',
    'Jinja2',
    'SQLAlchemy',
    'Flask-SQLAlchemy',
    'alembic',
    'Flask-Migrate',
    'blinker',
)

_PIN_RE = re.compile(
    r'^(?P<name>[A-Za-z0-9_.\-]+)\s*==\s*(?P<ver>[^\s#]+)\s*(?:#.*)?$'
)


def parse_expected_pins(req_path: Path):
    """Return {normalized_name: version} for FRAMEWORK_PIN_NAMES found in file."""
    text = req_path.read_text(encoding='utf-8')
    by_lower = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        m = _PIN_RE.match(line)
        if not m:
            continue
        by_lower[m.group('name').lower()] = (m.group('name'), m.group('ver'))

    expected = {}
    missing = []
    for name in FRAMEWORK_PIN_NAMES:
        hit = by_lower.get(name.lower())
        if not hit:
            missing.append(name)
            continue
        _canon, ver = hit
        expected[name] = ver
    if missing:
        raise SystemExit(
            'requirements 缺少 Framework pin: %s (%s)'
            % (', '.join(missing), req_path)
        )
    return expected


def pip_show_version(python: str, package: str):
    """Return installed version string or None."""
    proc = subprocess.run(
        [python, '-m', 'pip', 'show', package],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        return None
    for line in proc.stdout.splitlines():
        if line.lower().startswith('version:'):
            return line.split(':', 1)[1].strip()
    return None


def main(argv=None):
    parser = argparse.ArgumentParser(description='Assert Framework Generation pins')
    parser.add_argument(
        '--requirements',
        type=Path,
        default=ROOT / 'requirements.txt',
        help='pin 来源（默认仓库根 requirements.txt）',
    )
    parser.add_argument(
        '--python',
        default=sys.executable,
        help='用于 pip show 的解释器（默认当前 Python）',
    )
    args = parser.parse_args(argv)

    req_path = args.requirements
    if not req_path.is_file():
        print('ERROR: requirements 不存在: %s' % req_path, file=sys.stderr)
        return 2

    expected = parse_expected_pins(req_path)
    python = args.python
    mismatches = []
    rows = []

    for name, want in expected.items():
        got = pip_show_version(python, name)
        ok = got == want
        rows.append((name, want, got or '(missing)', 'OK' if ok else 'FAIL'))
        if not ok:
            mismatches.append((name, want, got))

    width = max(len(r[0]) for r in rows)
    print('Framework pins vs %s (python=%s)' % (req_path.name, python))
    for name, want, got, status in rows:
        print('  %s  want=%-10s got=%-10s %s' % (name.ljust(width), want, got, status))

    if mismatches:
        print('FAIL: %d pin mismatch(es)' % len(mismatches), file=sys.stderr)
        return 1
    print('OK: all %d Framework pins match' % len(expected))
    return 0


if __name__ == '__main__':
    sys.exit(main())
