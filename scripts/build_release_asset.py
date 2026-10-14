#!/usr/bin/env python3
"""Build a deterministic public CronPilot release asset from a Git commit."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import html
import io
import json
import os
import re
import subprocess
import tarfile
import tempfile
from pathlib import Path, PurePosixPath
from urllib.parse import quote, unquote, urlsplit


MARKDOWN_LINK_RE = re.compile(r"(?P<prefix>!??\[[^\]]*\]\()(?P<url>[^)]+)(?P<suffix>\))")
HTML_LINK_RE = re.compile(
    r"(?P<prefix>\b(?:href|src)\s*=\s*['\"])(?P<url>[^'\"]+)(?P<suffix>['\"])",
    re.IGNORECASE,
)
DOC_SUFFIXES = {".md", ".html", ".htm"}


def git(root: Path, *args: str, binary: bool = False) -> bytes | str:
    result = subprocess.run(
        ["git", *args], cwd=root, check=True, capture_output=True
    ).stdout
    return result if binary else result.decode("utf-8")


def read_allowlist(path: Path) -> tuple[list[str], list[str]]:
    exact: list[str] = []
    prefixes: list[str] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        value = raw.strip()
        if not value or value.startswith("#"):
            continue
        if value.startswith("/") or ".." in PurePosixPath(value).parts:
            raise SystemExit(f"unsafe package manifest entry: {value}")
        (prefixes if value.endswith("/") else exact).append(value)
    return exact, prefixes


def list_tree(root: Path, commit: str) -> dict[str, tuple[str, str]]:
    raw = git(root, "ls-tree", "-rz", "-r", commit, binary=True)
    result: dict[str, tuple[str, str]] = {}
    for record in raw.split(b"\0"):
        if not record:
            continue
        metadata, raw_path = record.split(b"\t", 1)
        mode, kind, object_id = metadata.decode("ascii").split()[:3]
        if kind != "blob":
            raise SystemExit(f"unsupported Git object in package candidate: {raw_path!r}")
        result[raw_path.decode("utf-8")] = (mode, object_id)
    return result


def select_paths(
    tree: dict[str, tuple[str, str]],
    exact: list[str],
    prefixes: list[str],
    allow_missing: bool,
) -> list[str]:
    missing = [path for path in exact if path not in tree]
    if missing and not allow_missing:
        raise SystemExit("package manifest paths absent from ref:\n  " + "\n  ".join(missing))
    selected = {
        path
        for path in tree
        if path in exact or any(path.startswith(prefix) for prefix in prefixes)
    }
    if not selected:
        raise SystemExit("package manifest selected no files")
    return sorted(selected)


def is_external(url: str) -> bool:
    parsed = urlsplit(html.unescape(url.strip().strip("<>")))
    return parsed.scheme in {"http", "https", "mailto", "tel", "data"} or url.startswith("//")


def resolved_repo_target(source_path: str, url: str) -> str | None:
    clean = html.unescape(url.strip().strip("<>"))
    if not clean or clean.startswith("#") or is_external(clean) or clean.startswith("/"):
        return None
    parsed = urlsplit(clean)
    target = PurePosixPath(source_path).parent / unquote(parsed.path)
    parts: list[str] = []
    for part in target.parts:
        if part in {"", "."}:
            continue
        if part == "..":
            if parts:
                parts.pop()
            continue
        parts.append(part)
    return "/".join(parts)


def public_url(
    repository_url: str, public_ref: str, target: str, original: str, is_directory: bool
) -> str:
    fragment = urlsplit(html.unescape(original.strip().strip("<>"))).fragment
    view = "tree" if is_directory else "blob"
    url = f"{repository_url.rstrip('/')}/{view}/{quote(public_ref, safe='')}/{quote(target, safe='/')}"
    return f"{url}#{quote(fragment)}" if fragment else url


def rewrite_links(
    source_path: str,
    data: bytes,
    selected: set[str],
    tree_paths: set[str],
    repository_url: str,
    public_ref: str,
) -> tuple[bytes, list[dict[str, str]]]:
    if Path(source_path).suffix.lower() not in DOC_SUFFIXES:
        return data, []
    text = data.decode("utf-8")
    pattern = MARKDOWN_LINK_RE if source_path.endswith(".md") else HTML_LINK_RE
    rewrites: list[dict[str, str]] = []

    def replace(match: re.Match[str]) -> str:
        original = match.group("url")
        target = resolved_repo_target(source_path, original)
        if target is None or target in selected:
            return match.group(0)
        is_directory = any(path.startswith(target.rstrip("/") + "/") for path in tree_paths)
        if target not in tree_paths and not is_directory:
            return match.group(0)
        replacement = public_url(repository_url, public_ref, target, original, is_directory)
        rewrites.append(
            {
                "source_path": source_path,
                "original_url": original,
                "resolved_repository_path": target,
                "replacement_url": replacement,
            }
        )
        return f"{match.group('prefix')}{replacement}{match.group('suffix')}"

    return pattern.sub(replace, text).encode("utf-8"), rewrites


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", required=True, help="release version without the v prefix")
    parser.add_argument("--ref", required=True, help="Git tag or commit used as the only input")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("release/package-manifest.txt"),
    )
    parser.add_argument(
        "--repository-url",
        default="https://github.com/sharepusher/CronPilot",
    )
    parser.add_argument(
        "--allow-missing",
        action="store_true",
        help="development-only: tolerate allowlist files not present in the selected ref",
    )
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    commit = str(git(root, "rev-parse", "--verify", f"{args.ref}^{{commit}}")).strip()
    commit_time = int(str(git(root, "show", "-s", "--format=%ct", commit)).strip())
    tree = list_tree(root, commit)
    exact, prefixes = read_allowlist((root / args.manifest).resolve())
    paths = select_paths(tree, exact, prefixes, args.allow_missing)
    selected = set(paths)
    public_ref = args.ref if re.fullmatch(r"v\d+\.\d+\.\d+", args.ref) else commit
    top = f"cronpilot-{args.version}"

    file_bytes: dict[str, bytes] = {}
    link_rewrites: list[dict[str, str]] = []
    for path in paths:
        mode, object_id = tree[path]
        if mode == "120000":
            raise SystemExit(f"symlinks are not permitted in the public package: {path}")
        data = git(root, "cat-file", "blob", object_id, binary=True)
        rewritten, rewrites = rewrite_links(
            path,
            data,
            selected,
            set(tree),
            args.repository_url,
            public_ref,
        )
        file_bytes[path] = rewritten
        link_rewrites.extend(rewrites)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(suffix=".tar") as raw_tar:
        with tarfile.open(fileobj=raw_tar, mode="w", format=tarfile.PAX_FORMAT) as archive:
            for path in paths:
                data = file_bytes[path]
                info = tarfile.TarInfo(f"{top}/{path}")
                info.size = len(data)
                info.mode = 0o755 if tree[path][0] == "100755" else 0o644
                info.mtime = commit_time
                info.uid = info.gid = 0
                info.uname = info.gname = "root"
                archive.addfile(info, io.BytesIO(data))
        raw_tar.flush()
        raw_tar.seek(0)
        with args.output.open("wb") as output_handle:
            with gzip.GzipFile(fileobj=output_handle, mode="wb", filename="", mtime=0) as compressed:
                while chunk := raw_tar.read(1024 * 1024):
                    compressed.write(chunk)

    archive_data = args.output.read_bytes()
    archive_sha = hashlib.sha256(archive_data).hexdigest()
    checksum_path = args.output.with_suffix(args.output.suffix + ".sha256")
    checksum_path.write_text(f"{archive_sha}  {args.output.name}\n", encoding="ascii")
    report = {
        "schema_version": 1,
        "version": args.version,
        "source_ref": args.ref,
        "source_commit": commit,
        "public_link_ref": public_ref,
        "top_level_directory": top,
        "file_count": len(paths),
        "archive_bytes": len(archive_data),
        "archive_sha256": archive_sha,
        "allow_missing": args.allow_missing,
        "files": [
            {
                "path": path,
                "bytes": len(file_bytes[path]),
                "git_mode": tree[path][0],
                "source_object": tree[path][1],
            }
            for path in paths
        ],
        "link_rewrites": link_rewrites,
    }
    args.output.with_suffix(args.output.suffix + ".build.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"built {args.output}: {len(paths)} files, {len(archive_data)} bytes, sha256={archive_sha}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
