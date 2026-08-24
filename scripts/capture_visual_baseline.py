#!/usr/bin/env python3
"""
capture_visual_baseline.py — Phase 3B
Captures screenshots of all 13 redesign pages (v2 UI) and saves them
as the visual regression baseline in tests/visual_regression/baseline/.

Usage:
    python scripts/capture_visual_baseline.py [--base-url URL]

Requires:
    pip install playwright Pillow
    playwright install chromium
"""
import argparse
import sys
import time
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
BASELINE_DIR = BASE_DIR / "tests" / "visual_regression" / "baseline"

PAGES = [
    # (slug, path_with_query)
    ("dashboard",           "/?cp_ui_version=v2"),
    ("execution_logs",      "/execution_logs?cp_ui_version=v2"),
    ("run_inspector",       "/run_inspector?cp_ui_version=v2"),
    ("task_form",           "/cron_add?cp_ui_version=v2"),
    ("tags",                "/rbac/tags?cp_ui_version=v2"),
    ("groups",              "/rbac/groups?cp_ui_version=v2"),
    ("users",               "/rbac/users?cp_ui_version=v2"),
    ("registration_review", "/rbac/registration_review?cp_ui_version=v2"),
    ("audit_logs",          "/rbac/audit_logs?cp_ui_version=v2"),
    ("operation_log",       "/rbac/operation_log?cp_ui_version=v2"),
    ("api_token",           "/rbac/api_token?cp_ui_version=v2"),
    ("change_password",     "/rbac/change_password?cp_ui_version=v2"),
    ("groups_form",         "/rbac/groups/new?cp_ui_version=v2"),
]


def login(page, base_url: str, username: str = "admin", password: str = "changeme"):
    """Log in to CronPilot and set the v2 cookie via URL param."""
    page.goto(f"{base_url}/rbac/login")
    page.fill('input[name="username"]', username)
    page.fill('input[name="password"]', password)
    page.click('button[type="submit"], input[type="submit"]')
    page.wait_for_url(f"{base_url}/**", timeout=5000)


def capture_baseline(base_url: str, width: int = 1280, height: int = 900):
    from playwright.sync_api import sync_playwright

    BASELINE_DIR.mkdir(parents=True, exist_ok=True)

    captured = []
    skipped = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={"width": width, "height": height},
        )
        # Pre-set cookies so v2 UI and dark theme are active from the first request.
        # cp_ui_version=v2 selects the redesign dual-track; cp_theme=dark matches
        # the Mockup dark palette.
        context.add_cookies([
            {"name": "cp_ui_version", "value": "v2",   "domain": "127.0.0.1", "path": "/"},
            {"name": "cp_theme",      "value": "dark",  "domain": "127.0.0.1", "path": "/"},
        ])
        page = context.new_page()

        print(f"[capture_baseline] Logging in to {base_url} ...")
        try:
            login(page, base_url)
        except Exception as exc:
            print(f"  ERROR: login failed: {exc}")
            browser.close()
            return False

        for slug, path in PAGES:
            url = f"{base_url}{path}"
            try:
                page.goto(url, wait_until="networkidle", timeout=10000)
                time.sleep(0.3)  # let CSS animations settle
                out = BASELINE_DIR / f"{slug}.png"
                page.screenshot(path=str(out), full_page=True)
                size_kb = out.stat().st_size // 1024
                print(f"  ✓ {slug:25s} → {out.name} ({size_kb} KB)")
                captured.append(slug)
            except Exception as exc:
                print(f"  ⚠ {slug:25s} skipped: {exc}")
                skipped.append(slug)

        browser.close()

    print(f"\n[capture_baseline] Done: {len(captured)} captured, {len(skipped)} skipped.")
    if skipped:
        print(f"  Skipped: {skipped}")
    return len(captured) > 0


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:5001")
    parser.add_argument("--width",    type=int, default=1280)
    parser.add_argument("--height",   type=int, default=900)
    args = parser.parse_args()

    ok = capture_baseline(args.base_url, args.width, args.height)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
