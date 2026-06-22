#!/usr/bin/env python3
"""Guard: doc/_pending_sync 目录卫生（防陈旧主文档副本覆盖仓库）。"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PENDING = ROOT / "doc" / "_pending_sync"
INDEX = PENDING / "INDEX.md"
ARCHIVE = PENDING / "已合并补丁记录.md"
MANIFEST = PENDING / "pending_apply.manifest"

FORBIDDEN_MANIFEST = {
    "doc/_pending_sync/INDEX.md",
    "doc/_pending_sync/已合并补丁记录.md",
    "INDEX.md",
    "已合并补丁记录.md",
}


def fail(msg: str) -> None:
    print(f"FAIL: {msg}", file=sys.stderr)
    sys.exit(1)


def main() -> int:
    if not PENDING.is_dir():
        print("OK: pending_sync (no directory)")
        return 0

    if not INDEX.is_file():
        fail("缺少 doc/_pending_sync/INDEX.md（目录说明；勿用 README.md 作目录说明）")

    index_text = INDEX.read_text(encoding="utf-8")
    if "目录说明" not in index_text:
        fail("doc/_pending_sync/INDEX.md 须为目录说明")

    legacy = PENDING / "README.md"
    if legacy.is_file() and "doc/_pending_sync/` 目录" in legacy.read_text(encoding="utf-8"):
        fail(
            "doc/_pending_sync/README.md 仍为目录说明；已改为 INDEX.md，"
            "README.md 仅用于根 README 的 pending 副本"
        )

    manifest_paths: set[str] = set()
    if MANIFEST.is_file():
        for line in MANIFEST.read_text(encoding="utf-8").splitlines():
            line = line.split("#", 1)[0].strip()
            if not line:
                continue
            if line in FORBIDDEN_MANIFEST:
                fail(f"manifest 不得登记元数据: {line}")
            manifest_paths.add(line)

    for path in PENDING.rglob("*"):
        if not path.is_file():
            continue
        if path in (INDEX, ARCHIVE, MANIFEST):
            continue
        rel = path.relative_to(PENDING).as_posix()
        if rel not in manifest_paths:
            fail(
                f"孤立 pending 文件: doc/_pending_sync/{rel} "
                f"(未在 pending_apply.manifest)；勿提交到 Git"
            )
        dest = ROOT / rel
        if dest.is_file() and path.stat().st_mtime < dest.stat().st_mtime:
            print(f"WARN: 主文件较新，apply 将跳过: {rel}", file=sys.stderr)

    print("OK: pending_sync guards")
    return 0


if __name__ == "__main__":
    main()
