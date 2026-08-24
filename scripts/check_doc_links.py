#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""检查仓库根目录及规则文件中 doc/ 引用的链接可达性。

用法:
    python scripts/check_doc_links.py           # 交互式报告
    python scripts/check_doc_links.py --check   # CI 模式：broken links 则 exit 1

检查范围:
    1. README.md / INSTALL.md / AGENTS.md 中 Markdown 链接 (doc/...) 和反引号 `doc/...`
    2. .cursor/rules/*.mdc 中 `doc/...` 引用
    3. RELEASE_NOTES.md 中 Markdown 链接 (doc/...)
    4. doc/**/*.html 内部 href 交叉引用（排除 _pending_sync）

根因（2026-08 文档重组事件）：
    _migrate_doc_dirs.py 只更新了 doc/ 内部 HTML 的 href，未扫描仓库根目录文件，
    导致 README.md/INSTALL.md/.cursor/rules/ 中 13 处断链。
"""
import argparse
import glob
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / 'doc'

EXCLUDE_DIRS = {'_pending_sync', 'node_modules', '.git', '__pycache__'}


def _extract_md_doc_links(filepath):
    """从 Markdown 文件提取所有 doc/ 引用路径。"""
    if not filepath.exists():
        return []
    content = filepath.read_text(encoding='utf-8')
    links = []
    # Markdown links: [text](doc/...)
    for m in re.finditer(r'\((doc/[^\s)]+\.(?:html|md))\)', content):
        links.append((m.group(1), filepath))
    # Backtick references: `doc/...html` or `doc/...md`
    for m in re.finditer(r'`(doc/[^`]+\.(?:html|md))`', content):
        path = m.group(1)
        if '*' not in path and 'YYYY' not in path:  # skip glob patterns and template placeholders
            links.append((path, filepath))
    return links


def _extract_html_internal_links(html_dir):
    """从 doc/ 内部 HTML 提取所有 href 交叉引用。"""
    links = []
    for html_path in sorted(html_dir.rglob('*.html')):
        if any(p in html_path.parts for p in EXCLUDE_DIRS):
            continue
        content = html_path.read_text(encoding='utf-8')
        for m in re.finditer(r'href="([^"#]+\.(?:html|md))"', content):
            href = m.group(1)
            if href.startswith(('http://', 'https://', 'javascript:', 'mailto:')):
                continue
            links.append((href, html_path))
    return links


def check_all():
    """运行所有链接检查，返回 broken 列表。"""
    broken = []

    # 1. Root-level Markdown files
    root_md_files = [
        ROOT / 'README.md',
        ROOT / 'INSTALL.md',
        ROOT / 'AGENTS.md',
        ROOT / 'RELEASE_NOTES.md',
    ]
    for md_file in root_md_files:
        for path, src in _extract_md_doc_links(md_file):
            target = (ROOT / path).resolve()
            if not target.exists():
                broken.append((str(src.relative_to(ROOT)), path))

    # 2. .cursor/rules/*.mdc files
    rules_dir = ROOT / '.cursor' / 'rules'
    if rules_dir.exists():
        for mdc_file in sorted(rules_dir.glob('*.mdc')):
            for path, src in _extract_md_doc_links(mdc_file):
                target = (ROOT / path).resolve()
                if not target.exists():
                    broken.append((str(src.relative_to(ROOT)), path))

    # 3. doc/ internal cross-references
    for href, src_html in _extract_html_internal_links(DOC):
        target = (src_html.parent / href).resolve()
        if not target.exists():
            rel_src = str(src_html.relative_to(ROOT))
            # Filter known false positive: code example in <pre> block
            if '...' in href:
                continue
            broken.append((rel_src, href))

    return broken


def main():
    parser = argparse.ArgumentParser(description='检查文档链接可达性')
    parser.add_argument('--check', action='store_true', help='CI 模式：broken 则 exit 1')
    args = parser.parse_args()

    broken = check_all()

    if broken:
        print('发现 %d 个 broken 文档链接：\n' % len(broken))
        for src, href in broken:
            print('  ✗ [%s] → %s' % (src, href))
        print()
        if args.check:
            print('CI 检查失败：请修复上述 broken 链接。')
            sys.exit(1)
        else:
            print('建议：修复上述链接后提交。')
    else:
        total = sum(1 for _ in _extract_html_internal_links(DOC))
        total += sum(len(_extract_md_doc_links(ROOT / f))
                     for f in ['README.md', 'INSTALL.md', 'AGENTS.md', 'RELEASE_NOTES.md'])
        print('✓ 文档链接检查通过（扫描 %d 个引用，0 broken）。' % total)


if __name__ == '__main__':
    main()
