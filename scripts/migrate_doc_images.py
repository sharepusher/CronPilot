#!/usr/bin/env python3
"""One-time migration of documentation screenshots to content-addressed assets.

The command is intentionally explicit about redacted derivatives.  It never
silently changes the bytes of a review-approved image: callers must map each
sensitive legacy path to a reviewed replacement with ``--redaction``.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import re
import subprocess
from collections import defaultdict
from pathlib import Path
from urllib.parse import unquote, urlsplit


IMG_RE = re.compile(
    r"<img\b(?P<before>[^>]*?\bsrc\s*=\s*)(?P<quote>['\"])(?P<src>.*?)(?P=quote)(?P<after>[^>]*)>",
    re.IGNORECASE | re.DOTALL,
)
DATA_RE = re.compile(r"^data:(image/(?:png|jpeg));base64,(.+)$", re.DOTALL)
MARKDOWN_IMAGE_RE = re.compile(r"!\[[^\]]*\]\((?P<src>[^)]+)\)")
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
UNAVAILABLE = (
    '<p class="image-unavailable" data-image-governance="missing-original">'
    "历史截图原文件未入库（旧引用为开发机临时绝对路径），无法可靠恢复；"
    "本节文字验收记录予以保留。</p>"
)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def repo_path(root: Path, path: Path) -> str:
    return path.relative_to(root).as_posix()


def provenance_for(legacy_paths: list[str]) -> dict[str, str]:
    joined = "\n".join(legacy_paths)
    if "doc/qa/assets/ui-compare-2026-09/up-" in joined:
        return {
            "owner": "aniu-lee/xiaoniu_cron",
            "source": "https://github.com/aniu-lee/xiaoniu_cron",
            "source_ref": "0883731",
            "basis": "public upstream UI comparison documentation",
        }
    if "doc/qa/assets/ui-compare-2026-09/cp-" in joined:
        return {
            "owner": "CronPilot",
            "source": "local CronPilot v4 Redesign capture",
            "source_ref": "captured 2026-09-24",
            "basis": "project-owned comparative documentation",
        }
    if any(item.startswith("embedded:") for item in legacy_paths):
        return {
            "owner": "CronPilot",
            "source": "historical HTML embedded screenshot",
            "source_ref": "repository documentation",
            "basis": "project-owned historical UI evidence",
        }
    return {
        "owner": "CronPilot",
        "source": "historical repository screenshot",
        "source_ref": "repository documentation",
        "basis": "project-owned historical UI evidence",
    }


def parse_redactions(root: Path, values: list[str]) -> dict[Path, Path]:
    result: dict[Path, Path] = {}
    for value in values:
        if "=" not in value:
            raise SystemExit(f"invalid --redaction value: {value!r}")
        old, replacement = value.split("=", 1)
        old_path = (root / old).resolve()
        replacement_path = Path(replacement).expanduser().resolve()
        if not old_path.is_file() or not replacement_path.is_file():
            raise SystemExit(f"redaction input missing: {value!r}")
        result[old_path] = replacement_path
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument(
        "--redaction",
        action="append",
        default=[],
        metavar="LEGACY_PATH=REVIEWED_PNG",
    )
    parser.add_argument(
        "--recover-embedded-ref",
        help="recover original data-URI bytes from HTML files in this Git ref",
    )
    args = parser.parse_args()

    root = args.root.resolve()
    doc = root / "doc"
    asset_dir = doc / "assets" / "screenshots"
    redactions = parse_redactions(root, args.redaction)

    old_pngs = sorted(
        path.resolve()
        for path in doc.rglob("*.png")
        if asset_dir.resolve() not in path.resolve().parents
    )
    old_png_set = set(old_pngs)
    aliases: dict[str, set[str]] = defaultdict(set)
    original_bytes: dict[str, bytes] = {}
    redacted_from: dict[str, str] = {}
    old_to_digest: dict[Path, str] = {}

    existing_manifest_path = asset_dir / "manifest.json"
    if existing_manifest_path.is_file():
        existing_manifest = json.loads(existing_manifest_path.read_text(encoding="utf-8"))
        for entry in existing_manifest.get("assets", []):
            canonical = root / entry["canonical_path"]
            data = canonical.read_bytes()
            digest = sha256(data)
            if digest != entry["sha256"]:
                raise SystemExit(f"existing canonical asset hash mismatch: {canonical}")
            original_bytes[digest] = data
            aliases[digest].update(entry.get("legacy_paths", []))
            if entry.get("redacted_from_sha256"):
                redacted_from[digest] = entry["redacted_from_sha256"]

    if args.recover_embedded_ref:
        names = subprocess.run(
            ["git", "ls-tree", "-rz", "--name-only", args.recover_embedded_ref, "--", "doc"],
            cwd=root,
            check=True,
            capture_output=True,
        ).stdout.decode("utf-8").split("\0")
        for name in sorted(item for item in names if item.endswith(".html")):
            historical = subprocess.run(
                ["git", "show", f"{args.recover_embedded_ref}:{name}"],
                cwd=root,
                check=True,
                capture_output=True,
            ).stdout.decode("utf-8")
            number = 0
            for match in IMG_RE.finditer(historical):
                number += 1
                data_match = DATA_RE.match(match.group("src"))
                if not data_match:
                    continue
                mime, payload = data_match.groups()
                data = base64.b64decode(re.sub(r"\s+", "", payload), validate=True)
                if mime != "image/png" or not data.startswith(PNG_SIGNATURE):
                    raise SystemExit(f"unsupported embedded image in {args.recover_embedded_ref}:{name}")
                digest = sha256(data)
                original_bytes.setdefault(digest, data)
                aliases[digest].add(f"embedded:{name}#image-{number:03d}")

    for old_path in old_pngs:
        source = redactions.get(old_path, old_path)
        data = source.read_bytes()
        if not data.startswith(PNG_SIGNATURE):
            raise SystemExit(f"not a PNG: {source}")
        digest = sha256(data)
        original_bytes.setdefault(digest, data)
        legacy = repo_path(root, old_path)
        aliases[digest].add(legacy)
        old_to_digest[old_path] = digest
        if source != old_path:
            redacted_from[digest] = sha256(old_path.read_bytes())

    references: dict[str, set[str]] = defaultdict(set)
    embedded_counter = 0
    missing_absolute = 0
    changed_html = 0

    for html_path in sorted(doc.rglob("*.html")):
        text = html_path.read_text(encoding="utf-8")
        image_number = 0

        def replace(match: re.Match[str]) -> str:
            nonlocal embedded_counter, image_number, missing_absolute
            image_number += 1
            src = match.group("src")
            data_match = DATA_RE.match(src)
            digest: str | None = None

            if data_match:
                mime, payload = data_match.groups()
                data = base64.b64decode(re.sub(r"\s+", "", payload), validate=True)
                if mime != "image/png" or not data.startswith(PNG_SIGNATURE):
                    raise SystemExit(f"unsupported embedded image in {html_path}")
                digest = sha256(data)
                original_bytes.setdefault(digest, data)
                alias = f"embedded:{repo_path(root, html_path)}#image-{image_number:03d}"
                aliases[digest].add(alias)
                embedded_counter += 1
            else:
                parsed = urlsplit(src)
                if parsed.scheme in {"http", "https"} or src.startswith("//"):
                    return match.group(0)
                if os.path.isabs(unquote(parsed.path)):
                    missing_absolute += 1
                    return UNAVAILABLE
                relative_path = Path(unquote(parsed.path))
                candidate = (html_path.parent / relative_path).resolve()
                fallback = (html_path.parent.parent / relative_path).resolve()
                archive_screenshot_fallback = (doc / "archive" / "screenshots" / relative_path).resolve()
                archived_design_fallback = (doc / "design" / relative_path).resolve()
                if candidate in old_to_digest:
                    digest = old_to_digest[candidate]
                elif fallback in old_to_digest:
                    # Several archived reports were moved one directory deeper
                    # without updating their screenshot-relative paths.
                    digest = old_to_digest[fallback]
                elif archive_screenshot_fallback in old_to_digest:
                    digest = old_to_digest[archive_screenshot_fallback]
                elif archived_design_fallback in old_to_digest:
                    # Early design reports were later archived without their
                    # relative screenshot links being rebased.
                    digest = old_to_digest[archived_design_fallback]
                elif asset_dir.resolve() in candidate.parents and re.fullmatch(
                    r"[0-9a-f]{64}", candidate.stem
                ):
                    digest = candidate.stem
                elif Path(parsed.path).suffix.lower() in {".png", ".jpg", ".jpeg", ".gif", ".webp"}:
                    raise SystemExit(f"missing local image: {repo_path(root, html_path)} -> {src}")
                else:
                    return match.group(0)

            canonical = asset_dir / f"{digest}.png"
            relative = os.path.relpath(canonical, html_path.parent).replace(os.sep, "/")
            references[digest].add(repo_path(root, html_path))
            return (
                f"<img{match.group('before')}{match.group('quote')}{relative}"
                f"{match.group('quote')}{match.group('after')}>"
            )

        updated = IMG_RE.sub(replace, text)
        if updated != text:
            html_path.write_text(updated, encoding="utf-8")
            changed_html += 1

    for markdown_path in sorted(doc.rglob("*.md")):
        text = markdown_path.read_text(encoding="utf-8")
        for match in MARKDOWN_IMAGE_RE.finditer(text):
            src = match.group("src").strip().strip("<>")
            parsed = urlsplit(src)
            if parsed.scheme in {"http", "https"} or src.startswith("//"):
                continue
            candidate = (markdown_path.parent / unquote(parsed.path)).resolve()
            if asset_dir.resolve() in candidate.parents and re.fullmatch(
                r"[0-9a-f]{64}", candidate.stem
            ):
                references[candidate.stem].add(repo_path(root, markdown_path))

    asset_dir.mkdir(parents=True, exist_ok=True)
    for digest, data in sorted(original_bytes.items()):
        destination = asset_dir / f"{digest}.png"
        destination.write_bytes(data)

    assets = []
    for digest, data in sorted(original_bytes.items()):
        legacy_paths = sorted(aliases[digest])
        entry: dict[str, object] = {
            "sha256": digest,
            "canonical_path": f"doc/assets/screenshots/{digest}.png",
            "byte_size": len(data),
            "mime": "image/png",
            "legacy_paths": legacy_paths,
            "referenced_by": sorted(references[digest]),
            "provenance": provenance_for(legacy_paths),
            "content_review": {
                "reviewed_on": "2026-10-13",
                "status": "reviewed-no-obvious-sensitive-content",
            },
        }
        if digest in redacted_from:
            entry["content_review"] = {
                "reviewed_on": "2026-10-13",
                "status": "redacted-sensitive-credential",
                "reason": "API credential and command-line bearer value replaced before publication",
            }
            entry["redacted_from_sha256"] = redacted_from[digest]
        assets.append(entry)

    manifest = {
        "schema_version": 1,
        "baseline_commit": "0e1cc411abd60353929065e8618c7193ba077082",
        "reviewed_on": "2026-10-13",
        "policy": "content-addressed PNG assets; reviewed derivatives are explicit",
        "assets": assets,
    }
    (asset_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    for old_path in old_pngs:
        old_path.unlink()
    for directory in sorted({path.parent for path in old_pngs}, key=lambda p: len(p.parts), reverse=True):
        try:
            directory.rmdir()
        except OSError:
            pass

    print(f"legacy PNG files migrated: {len(old_pngs)}")
    print(f"canonical PNG assets: {len(assets)}")
    print(f"embedded image references externalized: {embedded_counter}")
    print(f"HTML files changed: {changed_html}")
    print(f"unrecoverable absolute image references documented: {missing_absolute}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
