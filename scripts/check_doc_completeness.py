#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""检查 doc/ 目录下 HTML 文件是否在 index.html 中注册。

用法:
    python scripts/check_doc_completeness.py           # 交互式报告
    python scripts/check_doc_completeness.py --check   # CI 模式：缺失则 exit 1

检查规则:
    1. doc/ 及其子目录（排除 _pending_sync）中的每个 *.html 文件
       都应在 doc/index.html 中被引用（href 包含该文件名）
    2. doc/index.html 中引用的 *.html 都应实际存在
"""
import argparse
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / 'doc'
INDEX = DOC / 'index.html'

EXCLUDE_DIRS = {'_pending_sync'}
SELF_FILES = {'index.html'}


def get_doc_html_files():
    """收集 doc/ 下所有 HTML 文件（排除 _pending_sync 和 index.html）。"""
    files = set()
    for html_path in DOC.rglob('*.html'):
        rel = html_path.relative_to(DOC)
        parts = rel.parts
        if any(p in EXCLUDE_DIRS for p in parts):
            continue
        if rel.name in SELF_FILES:
            continue
        files.add(str(rel))
    return files


def get_index_references():
    """从 index.html 提取所有 href 引用的 .html 文件路径。"""
    content = INDEX.read_text(encoding='utf-8')
    refs = set()
    for m in re.finditer(r'href="([^"#]+\.html)"', content):
        href = m.group(1)
        if href.startswith(('http://', 'https://')):
            continue
        refs.add(os.path.normpath(href))
    return refs


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true', help='CI 模式')
    args = parser.parse_args()

    doc_files = get_doc_html_files()
    index_refs = get_index_references()

    unregistered = sorted(doc_files - index_refs)
    broken = sorted(r for r in index_refs if not (DOC / r).exists())

    ok = True
    if unregistered:
        ok = False
        print('UNREGISTERED (doc/*.html not in index.html):')
        for f in unregistered:
            print('  %s' % f)

    if broken:
        ok = False
        print('BROKEN (index.html references non-existent file):')
        for f in broken:
            print('  %s' % f)

    if ok:
        print('OK: %d HTML files all registered in index.html, 0 broken refs' % len(doc_files))

    if args.check and not ok:
        sys.exit(1)


if __name__ == '__main__':
    main()
