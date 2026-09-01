#!/usr/bin/env python3
"""
compare_visual_regression.py — Phase 3B
Takes current screenshots of all redesign pages and compares them to the
baseline.  Exits non-zero (CI failure) when any page diff exceeds THRESHOLD.

Usage:
    python scripts/compare_visual_regression.py [--base-url URL]
                                                [--baseline-dir PATH]
                                                [--threshold PERCENT]
                                                [--update-baseline]

Options:
    --threshold     Max allowed diff % per page (default: 0.5)
    --update-baseline  Overwrite baseline with current screenshots on success
"""
import argparse
import os
import sys
import time
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
BASELINE_DIR = BASE_DIR / "tests" / "visual_regression" / "baseline"
CURRENT_DIR  = BASE_DIR / "tests" / "visual_regression" / "current"

PAGES = [
    ("dashboard",           "/"),
    ("execution_logs",      "/job_log_all_list"),
    ("task_form",           "/cron_add"),
    ("tags",                "/rbac/tags"),
    ("groups",              "/rbac/groups"),
    ("users",               "/rbac/users"),
    ("registration_review", "/rbac/registration_review"),
    ("audit_logs",          "/rbac/audit-logs"),
    ("operation_log",       "/operation_log_list"),
    ("api_token",           "/rbac/api_token"),
    ("change_password",     "/rbac/password"),
    ("groups_form",         "/rbac/groups/add"),
]


def pixel_diff_percent(img_a_path: Path, img_b_path: Path) -> float:
    """Returns percentage of pixels that differ between two images."""
    from PIL import Image, ImageChops
    import math

    a = Image.open(img_a_path).convert("RGB")
    b = Image.open(img_b_path).convert("RGB")

    # Resize to the smaller dimensions to handle minor size differences
    w = min(a.width, b.width)
    h = min(a.height, b.height)
    if (a.width, a.height) != (w, h):
        a = a.crop((0, 0, w, h))
    if (b.width, b.height) != (w, h):
        b = b.crop((0, 0, w, h))

    diff = ImageChops.difference(a, b)
    total_pixels = w * h
    # Count pixels with any channel difference > 5 (tolerance for anti-aliasing).
    # Use tobytes() to avoid Pillow 14 getdata() deprecation.
    import struct
    raw = diff.tobytes()
    step = 3  # RGB channels
    diff_count = sum(
        1
        for i in range(0, len(raw), step)
        if max(raw[i], raw[i+1], raw[i+2]) > 5
    )
    return (diff_count / total_pixels) * 100.0


def _read_password():
    """Read login password from env or conf.ini."""
    pwd = os.environ.get('CRONPILOT_PASS', '')
    if pwd:
        return pwd
    ini = BASE_DIR / "conf.ini"
    if ini.exists():
        import configparser
        cp = configparser.ConfigParser()
        cp.read(str(ini))
        pwd = cp.get('default', 'login_pwd', fallback='')
        if pwd:
            return pwd
    return 'changeme'


def login(page, base_url: str, username: str = "admin", password: str = ""):
    if not password:
        password = _read_password()
    page.goto(f"{base_url}/rbac/login")
    page.fill('input[name="username"]', username)
    page.fill('input[name="password"]', password)
    page.click('button[type="submit"], input[type="submit"]')
    page.wait_for_url(f"{base_url}/**", timeout=5000)
    if "/rbac/login" in page.url:
        raise RuntimeError(f"Login failed: still on login page ({page.url})")


def run_comparison(
    base_url: str,
    baseline_dir: Path,
    threshold: float,
    update_baseline: bool,
    width: int = 1280,
    height: int = 900,
) -> bool:
    from playwright.sync_api import sync_playwright

    if not baseline_dir.exists():
        print(f"ERROR: baseline directory not found: {baseline_dir}")
        print("  Run: python scripts/capture_visual_baseline.py --base-url <url>")
        return False

    CURRENT_DIR.mkdir(parents=True, exist_ok=True)

    results = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": width, "height": height})
        context.add_cookies([
            {"name": "cp_ui_version", "value": "v2",   "domain": "127.0.0.1", "path": "/"},
            {"name": "cp_theme",      "value": "dark",  "domain": "127.0.0.1", "path": "/"},
        ])
        page = context.new_page()

        try:
            login(page, base_url)
        except Exception as exc:
            print(f"ERROR: login failed: {exc}")
            browser.close()
            return False

        for slug, path in PAGES:
            url = f"{base_url}{path}"
            current_path = CURRENT_DIR / f"{slug}.png"
            baseline_path = baseline_dir / f"{slug}.png"

            if not baseline_path.exists():
                results.append((slug, None, "NO_BASELINE"))
                continue

            try:
                page.goto(url, wait_until="networkidle", timeout=10000)
                time.sleep(0.3)
                page.screenshot(path=str(current_path), full_page=True)
                diff_pct = pixel_diff_percent(baseline_path, current_path)
                status = "PASS" if diff_pct <= threshold else "FAIL"
                results.append((slug, diff_pct, status))
            except Exception as exc:
                results.append((slug, None, f"ERROR: {exc}"))

        browser.close()

    # Print report
    max_slug = max(len(r[0]) for r in results)
    passed = 0
    failed = 0
    print(f"\n{'Page':{max_slug}}  {'Diff %':>8}  Status")
    print("-" * (max_slug + 20))
    for slug, diff_pct, status in results:
        if diff_pct is None:
            print(f"  {slug:{max_slug}}  {'N/A':>8}  {status}")
            failed += 1
        else:
            marker = "✓" if status == "PASS" else "✗"
            print(f"  {marker} {slug:{max_slug}}  {diff_pct:>7.3f}%  {status}")
            if status == "PASS":
                passed += 1
            else:
                failed += 1
    print("-" * (max_slug + 20))
    print(f"  {passed} passed, {failed} failed  (threshold: {threshold}%)")

    all_pass = (failed == 0)
    if all_pass and update_baseline:
        print("\n  --update-baseline: copying current → baseline")
        for slug, _, _ in results:
            src = CURRENT_DIR / f"{slug}.png"
            dst = baseline_dir / f"{slug}.png"
            if src.exists():
                import shutil
                shutil.copy2(src, dst)
        print("  Baseline updated.")

    return all_pass


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url",        default="http://127.0.0.1:5001")
    parser.add_argument("--baseline-dir",    default=str(BASELINE_DIR))
    parser.add_argument("--threshold",       type=float, default=0.5,
                        help="Max allowed diff %% per page (default 0.5)")
    parser.add_argument("--update-baseline", action="store_true",
                        help="Overwrite baseline when all pages pass")
    parser.add_argument("--width",           type=int, default=1280)
    parser.add_argument("--height",          type=int, default=900)
    args = parser.parse_args()

    ok = run_comparison(
        base_url        = args.base_url,
        baseline_dir    = Path(args.baseline_dir),
        threshold       = args.threshold,
        update_baseline = args.update_baseline,
        width           = args.width,
        height          = args.height,
    )
    if ok:
        print("\n✓ Visual regression: all pages within threshold")
    else:
        print("\n✗ Visual regression: one or more pages exceed threshold")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
