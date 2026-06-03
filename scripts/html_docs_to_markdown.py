#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""将 doc/*.html 转为同名 .md（需 markdownify: pip install markdownify）。"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / 'doc'

try:
    from markdownify import markdownify as md
except ImportError:
    print('请先安装: pip install markdownify', file=sys.stderr)
    sys.exit(1)


def extract_body(html: str) -> str:
    m = re.search(r'<body[^>]*>(.*)</body>', html, re.DOTALL | re.IGNORECASE)
    if not m:
        return html
    body = m.group(1)
    body = re.sub(r'<script[^>]*>.*?</script>', '', body, flags=re.DOTALL | re.IGNORECASE)
    body = re.sub(r'<style[^>]*>.*?</style>', '', body, flags=re.DOTALL | re.IGNORECASE)
    return body


def html_to_md(html_path: Path) -> str:
    html = html_path.read_text(encoding='utf-8')
    title_m = re.search(r'<title>([^<]+)</title>', html, re.IGNORECASE)
    title = title_m.group(1).strip() if title_m else html_path.stem
    body = extract_body(html)
    text = md(body, heading_style='ATX', bullets='-', strip=['style', 'script'])
    text = re.sub(r'\n{3,}', '\n\n', text).strip()
    base = html_path.name
    header = (
        f'# {title}\n\n'
        f'> HTML 版：[{base}]({base}) · [文档索引](index.html) · [索引 Markdown](index.md)\n\n'
    )
    footer = (
        f'\n\n---\n\n'
        f'[← 文档索引（HTML）](index.html) · '
        f'[← 文档索引（Markdown）](index.md)\n'
    )
    return header + text + footer


def inject_md_footer(html_path: Path) -> bool:
    html = html_path.read_text(encoding='utf-8')
    md_name = html_path.with_suffix('.md').name
    marker = f'href="{md_name}">Markdown'
    if marker in html:
        return False
    link = f' · <a href="{md_name}">Markdown</a> · <a href="index.html">索引</a>'
    if '</footer>' in html:
        html = html.replace('</footer>', link + '</footer>', 1)
    else:
        html = html.replace(
            '</body>',
            f'<footer style="text-align:center;padding:1.5rem;color:#64748b;font-size:.85rem">'
            f'<a href="index.html">文档索引</a>{link}</footer>\n</body>',
            1,
        )
    html_path.write_text(html, encoding='utf-8')
    return True


def iter_html_sources():
    for html_path in sorted(DOC.glob('*.html')):
        if html_path.name == 'index.html':
            continue
        yield html_path


def sync_markdown(check_only: bool) -> int:
    """返回不同步的文件数量。"""
    stale = 0
    for html_path in iter_html_sources():
        out = html_path.with_suffix('.md')
        expected = html_to_md(html_path)
        current = out.read_text(encoding='utf-8') if out.exists() else None
        if current != expected:
            stale += 1
            rel = out.relative_to(ROOT)
            if check_only:
                print(f'OUT OF SYNC: {rel}', file=sys.stderr)
            else:
                out.write_text(expected, encoding='utf-8')
                print('wrote', rel)
    return stale


def main():
    argv = set(sys.argv[1:])
    if '--check' in argv:
        n = sync_markdown(check_only=True)
        if n:
            print(
                f'\n{n} Markdown file(s) out of date. Run:\n'
                '  pip install markdownify\n'
                '  python scripts/html_docs_to_markdown.py',
                file=sys.stderr,
            )
            sys.exit(1)
        print('OK: all generated doc/*.md match HTML sources')
        return

    inject_only = '--footers-only' in argv
    if not inject_only:
        sync_markdown(check_only=False)
    for html_path in iter_html_sources():
        if inject_md_footer(html_path):
            print('footer', html_path.relative_to(ROOT))


if __name__ == '__main__':
    main()
