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
    3. 手工维护的索引页块级标签必须闭合配对（防止批量编辑剪贴造成结构损坏）
    4. 每篇 doc/postmortem/*.html 须同时登记在 index.html 与 index.md，
       且 index.html 的「共 N 篇」与实际文件数一致
"""
import argparse
import os
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / 'doc'
INDEX = DOC / 'index.html'

EXCLUDE_DIRS = {'_pending_sync'}
SELF_FILES = {'index.html'}

# 手工维护、结构易在批量编辑中被剪贴破坏的索引页
STRUCTURED_INDEXES = ('index.html', 'postmortem/index.html')
# 仅校验这些块级标签的配对，避免误报省略闭合标签的合法写法
BALANCED_TAGS = {'ul', 'ol', 'li', 'div', 'section'}


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


class _BlockBalanceParser(HTMLParser):
    """追踪块级标签配对，并捕获裸露的属性文本（剪贴断裂的典型残留）。"""

    # 这些容器内的文本是展示用的代码片段，不能按属性残留判定
    RAW_TEXT_TAGS = {'pre', 'code', 'script', 'style', 'textarea'}

    def __init__(self):
        HTMLParser.__init__(self, convert_charrefs=True)
        self.stack = []
        self.errors = []
        self.raw_depth = 0

    def handle_starttag(self, tag, attrs):
        if tag in self.RAW_TEXT_TAGS:
            self.raw_depth += 1
        for name, _value in attrs:
            if name.startswith('<'):
                self.errors.append(
                    '第 %d 行 <%s> 的属性里嵌入了标签 %s（剪贴断裂）'
                    % (self.getpos()[0], tag, name)
                )
        if tag in BALANCED_TAGS:
            self.stack.append((tag, self.getpos()[0]))

    def handle_endtag(self, tag):
        if tag in self.RAW_TEXT_TAGS:
            self.raw_depth = max(0, self.raw_depth - 1)
        if tag not in BALANCED_TAGS:
            return
        if not self.stack:
            self.errors.append('第 %d 行 </%s> 没有对应的开标签' % (self.getpos()[0], tag))
            return
        open_tag, open_line = self.stack.pop()
        if open_tag != tag:
            self.errors.append(
                '第 %d 行 </%s> 与第 %d 行的 <%s> 不配对'
                % (self.getpos()[0], tag, open_line, open_tag)
            )

    def handle_data(self, data):
        if self.raw_depth:
            return
        if re.match(r'\s*(?:class|href|id|src|style)\s*=\s*"', data):
            self.errors.append(
                '第 %d 行出现裸露的属性文本（开标签被截断）' % self.getpos()[0]
            )

    def close(self):
        HTMLParser.close(self)
        for tag, line in self.stack:
            self.errors.append('第 %d 行的 <%s> 未闭合' % (line, tag))


def find_structure_errors(text):
    """返回块级结构错误列表；结构完好时返回空列表。"""
    parser = _BlockBalanceParser()
    parser.feed(text)
    parser.close()
    return parser.errors


def check_index_structure():
    """校验手工维护索引页的块级结构。"""
    problems = []
    for rel in STRUCTURED_INDEXES:
        path = DOC / rel
        if not path.exists():
            continue
        for err in find_structure_errors(path.read_text(encoding='utf-8')):
            problems.append('doc/%s: %s' % (rel, err))
    return problems


def check_postmortem_index_pair():
    """校验每篇复盘都登记在 index.html 与 index.md，且篇数声明准确。"""
    pm = DOC / 'postmortem'
    if not pm.exists():
        return []

    files = {p.name for p in pm.glob('*.html') if p.name not in SELF_FILES}
    problems = []

    index_html = pm / 'index.html'
    index_md = pm / 'index.md'
    html_text = index_html.read_text(encoding='utf-8') if index_html.exists() else ''
    md_text = index_md.read_text(encoding='utf-8') if index_md.exists() else ''

    for name in sorted(files):
        if name not in html_text:
            problems.append('doc/postmortem/index.html 未登记 %s' % name)
        if name not in md_text:
            problems.append('doc/postmortem/index.md 未登记 %s' % name)

    declared = re.search(r'共\s*(\d+)\s*篇', html_text)
    if declared and int(declared.group(1)) != len(files):
        problems.append(
            'doc/postmortem/index.html 声明「共 %s 篇」，实际 %d 篇'
            % (declared.group(1), len(files))
        )
    return problems


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

    structure = check_index_structure()
    if structure:
        ok = False
        print('STRUCTURE (索引页块级标签不配对):')
        for f in structure:
            print('  %s' % f)

    pm_problems = check_postmortem_index_pair()
    if pm_problems:
        ok = False
        print('POSTMORTEM INDEX (复盘索引登记不完整):')
        for f in pm_problems:
            print('  %s' % f)

    if ok:
        print('OK: %d HTML files all registered in index.html, 0 broken refs' % len(doc_files))

    if args.check and not ok:
        sys.exit(1)


if __name__ == '__main__':
    main()
