#!/usr/bin/env python3
"""Validate content-addressed documentation image assets and references."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import struct
import sys
import zlib
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit


PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
HASH_NAME_RE = re.compile(r"^[0-9a-f]{64}\.png$")
MARKDOWN_IMAGE_RE = re.compile(r"!\[[^\]]*\]\((?P<src>[^)]+)\)")
BITMAP_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".webp"}
REVIEW_STATUSES = {
    "reviewed-no-obvious-sensitive-content",
    "redacted-sensitive-credential",
}


class ImageSourceParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.sources: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "img":
            return
        values = dict(attrs)
        if values.get("src") is not None:
            self.sources.append(values["src"] or "")


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def png_dimensions(data: bytes) -> tuple[int, int]:
    if not data.startswith(PNG_SIGNATURE):
        raise ValueError("invalid PNG signature")
    offset = len(PNG_SIGNATURE)
    width = height = bit_depth = color_type = interlace = None
    idat = bytearray()
    saw_iend = False
    while offset + 12 <= len(data):
        length = struct.unpack(">I", data[offset : offset + 4])[0]
        chunk_type = data[offset + 4 : offset + 8]
        chunk_end = offset + 12 + length
        if chunk_end > len(data):
            raise ValueError("truncated PNG chunk")
        payload = data[offset + 8 : offset + 8 + length]
        expected_crc = struct.unpack(">I", data[offset + 8 + length : chunk_end])[0]
        if zlib.crc32(chunk_type + payload) & 0xFFFFFFFF != expected_crc:
            raise ValueError("PNG chunk CRC mismatch")
        if chunk_type == b"IHDR":
            if length != 13 or width is not None:
                raise ValueError("invalid PNG IHDR")
            width, height, bit_depth, color_type, _, _, interlace = struct.unpack(
                ">IIBBBBB", payload
            )
        elif chunk_type == b"IDAT":
            idat.extend(payload)
        elif chunk_type == b"IEND":
            saw_iend = True
            offset = chunk_end
            break
        offset = chunk_end
    if not saw_iend or offset != len(data) or width is None or not idat:
        raise ValueError("incomplete PNG structure")
    try:
        pixels = zlib.decompress(bytes(idat))
    except zlib.error as exc:
        raise ValueError(f"invalid PNG compressed data: {exc}") from exc
    channels = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}.get(color_type)
    if channels is None or bit_depth not in {1, 2, 4, 8, 16}:
        raise ValueError("unsupported PNG color format")
    if interlace == 0:
        row_bytes = (width * channels * bit_depth + 7) // 8
        if len(pixels) != height * (row_bytes + 1):
            raise ValueError("PNG pixel stream length mismatch")
    elif interlace != 1 or not pixels:
        raise ValueError("invalid PNG interlace or empty pixels")
    return width, height


def repo_path(root: Path, path: Path) -> str:
    return path.relative_to(root).as_posix()


def local_target(source_file: Path, src: str) -> Path | None:
    src = src.strip().strip("<>")
    parsed = urlsplit(src)
    if parsed.scheme in {"http", "https", "mailto"} or src.startswith("//"):
        return None
    if parsed.scheme == "data":
        raise ValueError("embedded data URI")
    path = unquote(parsed.path)
    if os.path.isabs(path):
        raise ValueError("absolute local path")
    return (source_file.parent / path).resolve()


def collect_references(root: Path, errors: list[str]) -> dict[str, set[str]]:
    doc = root / "doc"
    asset_dir = (doc / "assets" / "screenshots").resolve()
    references: dict[str, set[str]] = {}

    def inspect(source_file: Path, src: str) -> None:
        try:
            target = local_target(source_file, src)
        except ValueError as exc:
            errors.append(f"{repo_path(root, source_file)}: {exc}: {src[:96]}")
            return
        if target is None:
            return
        suffix = Path(urlsplit(src).path).suffix.lower()
        if suffix not in BITMAP_SUFFIXES:
            return
        if not target.is_file():
            errors.append(f"{repo_path(root, source_file)}: missing image: {src}")
            return
        try:
            target.relative_to(asset_dir)
        except ValueError:
            errors.append(
                f"{repo_path(root, source_file)}: non-canonical documentation image: {src}"
            )
            return
        references.setdefault(repo_path(root, target), set()).add(repo_path(root, source_file))

    for html_path in sorted(doc.rglob("*.html")):
        parser = ImageSourceParser()
        try:
            parser.feed(html_path.read_text(encoding="utf-8"))
        except Exception as exc:  # pragma: no cover - defensive parser boundary
            errors.append(f"{repo_path(root, html_path)}: HTML parse failed: {exc}")
            continue
        for src in parser.sources:
            inspect(html_path, src)

    for markdown_path in sorted(doc.rglob("*.md")):
        text = markdown_path.read_text(encoding="utf-8")
        for match in MARKDOWN_IMAGE_RE.finditer(text):
            inspect(markdown_path, match.group("src"))
    return references


def check(root: Path) -> list[str]:
    root = root.resolve()
    errors: list[str] = []
    doc = root / "doc"
    asset_dir = doc / "assets" / "screenshots"
    manifest_path = asset_dir / "manifest.json"
    if not manifest_path.is_file():
        return ["missing doc/assets/screenshots/manifest.json"]

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [f"invalid image manifest: {exc}"]

    entries = manifest.get("assets")
    if manifest.get("schema_version") != 1 or not isinstance(entries, list):
        errors.append("manifest schema_version/assets contract is invalid")
        entries = []

    manifest_paths: set[str] = set()
    manifest_hashes: set[str] = set()
    for entry in entries:
        canonical = entry.get("canonical_path", "")
        sha = entry.get("sha256", "")
        if canonical in manifest_paths:
            errors.append(f"duplicate manifest path: {canonical}")
        if sha in manifest_hashes:
            errors.append(f"duplicate manifest hash: {sha}")
        manifest_paths.add(canonical)
        manifest_hashes.add(sha)
        expected = f"doc/assets/screenshots/{sha}.png"
        if canonical != expected or not HASH_NAME_RE.fullmatch(Path(canonical).name):
            errors.append(f"non-content-addressed manifest path: {canonical}")
            continue
        path = root / canonical
        if not path.is_file():
            errors.append(f"manifest asset missing: {canonical}")
            continue
        data = path.read_bytes()
        actual = digest(data)
        if actual != sha:
            errors.append(f"asset hash mismatch: {canonical}: {actual}")
        try:
            width, height = png_dimensions(data)
            if width <= 0 or height <= 0:
                raise ValueError("zero dimensions")
        except ValueError as exc:
            errors.append(f"asset is not a decodable PNG: {canonical}: {exc}")
        if entry.get("mime") != "image/png" or entry.get("byte_size") != len(data):
            errors.append(f"manifest metadata mismatch: {canonical}")
        review = entry.get("content_review", {})
        if review.get("status") not in REVIEW_STATUSES or not review.get("reviewed_on"):
            errors.append(f"missing/invalid content review: {canonical}")
        if review.get("status") == "redacted-sensitive-credential":
            original = entry.get("redacted_from_sha256", "")
            if not re.fullmatch(r"[0-9a-f]{64}", original) or original == sha:
                errors.append(f"invalid redaction provenance: {canonical}")
        provenance = entry.get("provenance", {})
        if not all(provenance.get(key) for key in ("owner", "source", "source_ref", "basis")):
            errors.append(f"incomplete provenance: {canonical}")

    disk_paths = {
        repo_path(root, path)
        for path in asset_dir.glob("*.png")
        if path.is_file()
    }
    if disk_paths != manifest_paths:
        for path in sorted(disk_paths - manifest_paths):
            errors.append(f"canonical asset absent from manifest: {path}")
        for path in sorted(manifest_paths - disk_paths):
            errors.append(f"manifest path absent from disk: {path}")

    for path in sorted(doc.rglob("*.png")):
        if path.parent.resolve() != asset_dir.resolve():
            errors.append(f"legacy documentation PNG remains: {repo_path(root, path)}")

    references = collect_references(root, errors)
    for canonical, source_files in sorted(references.items()):
        if canonical not in manifest_paths:
            errors.append(f"referenced canonical asset absent from manifest: {canonical}")
            continue
        entry = next(item for item in entries if item.get("canonical_path") == canonical)
        declared = set(entry.get("referenced_by", []))
        if declared != source_files:
            errors.append(
                f"manifest references stale for {canonical}: "
                f"declared={sorted(declared)} actual={sorted(source_files)}"
            )
    for entry in entries:
        canonical = entry.get("canonical_path", "")
        if canonical not in references and entry.get("referenced_by"):
            errors.append(f"manifest declares references for unused asset: {canonical}")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="retained for CI command clarity")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    errors = check(args.root.resolve())
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        print(f"documentation image asset check failed: {len(errors)} error(s)", file=sys.stderr)
        return 1
    print("documentation image asset check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
