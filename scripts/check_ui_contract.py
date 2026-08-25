#!/usr/bin/env python3
"""
check_ui_contract.py — CronPilot Redesign UI Contract Guard

Scans app/templates/redesign/ for violations:
  1. Inline style attributes that are NOT pure CSS-variable references or
     layout-only shortcuts (display/width/height/position).
  2. Legacy Bootstrap / Simpleboot class usage.
  3. Hardcoded hex colors inside style="" HTML attributes.

Usage:
  python scripts/check_ui_contract.py          # full report (exit 0 always)
  python scripts/check_ui_contract.py --check  # CI mode (exit 1 on violations)

Design Source: doc/design/CronPilot-2026-redesign-mockup.html
Maintained as: Phase 1C guard per UI Migration Engineering Plan
"""

import re
import sys
from pathlib import Path

# ── Paths ──────────────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent.parent
REDESIGN_DIR = ROOT / "app" / "templates" / "redesign"

# ── Allowed inline-style patterns (not reported) ───────────────────────────
# These are safe exceptions:
#   - Pure CSS-variable values:  style="color:var(--cp-signal)"
#   - display shorthand:         style="display:none"  (idiomatic Jinja toggle)
#   - width/height 100%:         style="width:100%"    (fill-container idiom)
#   - display:contents:          style="display:contents" (Jinja form trick)
#   - Any combination of above   (separated by ;)
_VAR_ONLY_RE = re.compile(
    r'^(?:[\w-]+\s*:\s*var\(--[\w-]+\)(?:\s*,\s*[^;,"]+)?\s*;?\s*)+$'
)
_DISPLAY_ONLY_RE = re.compile(
    r'^display\s*:\s*(none|block|inline|inline-block|flex|grid|'
    r'inline-flex|inline-grid|contents|table(?:-\w+)?)\s*;?\s*$'
)
_DIMENSION_ONLY_RE = re.compile(
    r'^(width|height|max-width|max-height|min-width|min-height)'
    r'\s*:\s*(100%|auto|0)\s*;?\s*$'
)
_POSITION_ONLY_RE = re.compile(
    r'^position\s*:\s*(relative|absolute|fixed|sticky)\s*;?\s*$'
)


def _is_allowed_style(value: str) -> bool:
    """Return True if the inline style value is in the allowed exception list."""
    value = value.strip()
    if not value:
        return True
    # Check each ; segment individually
    parts = [p.strip() for p in value.split(';') if p.strip()]
    for part in parts:
        if (
            _VAR_ONLY_RE.match(part) or
            _DISPLAY_ONLY_RE.match(part) or
            _DIMENSION_ONLY_RE.match(part) or
            _POSITION_ONLY_RE.match(part)
        ):
            continue
        return False
    return True


# ── Legacy class patterns (reported as violations) ─────────────────────────
# These classes belong to Bootstrap / old Simpleboot and must not appear in
# redesign templates.  Partial prefix matches (e.g. 'col-md-') are detected
# via substring search inside class="..." values.
LEGACY_CLASSES = [
    # Bootstrap grid
    'col-md-', 'col-sm-', 'col-xs-', 'col-lg-', 'col-xl-',
    # Bootstrap button variants
    'btn-primary', 'btn-default', 'btn-danger', 'btn-success',
    'btn-warning', 'btn-info', 'btn-link',
    # Bootstrap form helpers
    'form-group', 'form-control', 'form-horizontal', 'form-inline',
    # Simpleboot
    'control-group', 'controls',
    # Old Bootstrap layout
    'navbar-', 'nav-tabs', 'nav-pills',
    'panel-heading', 'panel-body', 'panel-footer',
    'well', 'jumbotron',
    # NOTE: js-ajax-form / js-ajax-submit are intentional CronPilot patterns
    # from common.js AJAX form guard — do NOT add them here.
]

# Regex to match class attributes containing any legacy string
_CLASS_ATTR_RE = re.compile(r'class=["\']([^"\']+)["\']')


def check_inline_styles(lines: list, filepath: str) -> list:
    """Find style="" attributes that are not in the allowed exception list."""
    violations = []
    style_attr_re = re.compile(r'\bstyle="([^"]*)"')
    for lineno, line in enumerate(lines, 1):
        # Skip lines inside {% block css %} / <style> blocks — those are CSS
        # text, not HTML attributes; handled by audit_hardcoded_colors.py
        for m in style_attr_re.finditer(line):
            value = m.group(1)
            if not _is_allowed_style(value):
                snippet = value[:80] + ('...' if len(value) > 80 else '')
                violations.append({
                    'file': filepath,
                    'line': lineno,
                    'type': 'inline-style',
                    'detail': f'style="{snippet}"',
                })
    return violations


def check_legacy_classes(lines: list, filepath: str) -> list:
    """Find legacy Bootstrap/Simpleboot classes in class="" attributes."""
    violations = []
    for lineno, line in enumerate(lines, 1):
        for m in _CLASS_ATTR_RE.finditer(line):
            # Split class attribute into tokens so "btn-danger-c" != "btn-danger"
            tokens = set(m.group(1).split())
            for legacy in LEGACY_CLASSES:
                if legacy in tokens:
                    violations.append({
                        'file': filepath,
                        'line': lineno,
                        'type': 'legacy-class',
                        'detail': f'class contains "{legacy}"',
                    })
                    break  # one report per occurrence is enough
    return violations


def check_hex_in_style_attr(lines: list, filepath: str) -> list:
    """Find hardcoded hex colors inside style="" HTML attributes."""
    violations = []
    # Match hex color NOT preceded by an identifier char (to avoid catching
    # hex digits in var() names — though var names can't start with #)
    hex_in_style = re.compile(
        r'\bstyle="[^"]*(?<![a-zA-Z0-9_-])#([0-9a-fA-F]{3,8})\b[^"]*"'
    )
    for lineno, line in enumerate(lines, 1):
        if hex_in_style.search(line):
            violations.append({
                'file': filepath,
                'line': lineno,
                'type': 'hardcoded-color',
                'detail': 'hex color value in style="" attribute — use var(--cp-*)',
            })
    return violations


INLINE_CSS_MAX_LINES = 3


def check_inline_css_volume(lines: list, filepath: str) -> list:
    """Flag <style> blocks with more than INLINE_CSS_MAX_LINES of actual CSS.

    Counts non-empty, non-comment lines inside each <style>...</style> block.
    Allows small overrides (e.g. Jinja-injected CSS variables) but blocks
    structural CSS that should live in an external file.
    """
    violations = []
    in_style = False
    css_lines = 0
    style_start = 0

    for lineno, line in enumerate(lines, 1):
        stripped = line.strip()
        lower = stripped.lower()

        if '<style' in lower and '</style' not in lower:
            in_style = True
            css_lines = 0
            style_start = lineno
        elif '</style' in lower:
            if in_style and css_lines > INLINE_CSS_MAX_LINES:
                violations.append({
                    'file': filepath,
                    'line': style_start,
                    'type': 'inline-css-volume',
                    'detail': (
                        f'<style> block has {css_lines} CSS lines '
                        f'(max {INLINE_CSS_MAX_LINES}) — '
                        f'move to redesign-pages.css with .cp-page-xxx scope'
                    ),
                })
            in_style = False
        elif in_style:
            if not stripped:
                continue
            # Skip single-line comments: /* ... */
            if stripped.startswith('/*') and stripped.endswith('*/'):
                continue
            # Skip comment-only lines (// style)
            if stripped.startswith('//'):
                continue
            css_lines += 1

    return violations


def scan() -> list:
    """Run all checks on every .html file in REDESIGN_DIR."""
    if not REDESIGN_DIR.exists():
        print(f'ERROR: redesign template dir not found: {REDESIGN_DIR}', file=sys.stderr)
        sys.exit(2)

    all_violations = []
    for filepath in sorted(REDESIGN_DIR.glob('*.html')):
        try:
            lines = filepath.read_text(encoding='utf-8').splitlines()
        except Exception as exc:
            print(f'WARNING: cannot read {filepath}: {exc}', file=sys.stderr)
            continue

        rel = str(filepath.relative_to(ROOT))
        all_violations.extend(check_inline_styles(lines, rel))
        all_violations.extend(check_legacy_classes(lines, rel))
        all_violations.extend(check_hex_in_style_attr(lines, rel))
        all_violations.extend(check_inline_css_volume(lines, rel))

    return all_violations


def main():
    check_mode = '--check' in sys.argv

    violations = scan()

    if not violations:
        print('✓ check_ui_contract: 0 violations in app/templates/redesign/')
        sys.exit(0)

    # Group and sort by file → line
    by_file: dict = {}
    for v in violations:
        by_file.setdefault(v['file'], []).append(v)

    for filepath in sorted(by_file):
        print(f'\n{filepath}:')
        for v in sorted(by_file[filepath], key=lambda x: x['line']):
            print(f"  [{v['type']}] line {v['line']}: {v['detail']}")

    print(f'\n✗ check_ui_contract: {len(violations)} violation(s) found')

    if check_mode:
        sys.exit(1)
    sys.exit(0)


if __name__ == '__main__':
    main()
