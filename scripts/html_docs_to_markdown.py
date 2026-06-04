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


def check_index_md() -> bool:
    """index.html 不参与自动生成，但 index.md 须与索引页版本信息一致。"""
    html = (DOC / 'index.html').read_text(encoding='utf-8')
    md_path = DOC / 'index.md'
    if not md_path.exists():
        print('OUT OF SYNC: doc/index.md missing (maintain alongside index.html)', file=sys.stderr)
        return False
    md = md_path.read_text(encoding='utf-8')
    # 从 HTML 提取 Release Notes 卡片中的版本标签（如 v0.1.1）
    import re as _re
    m = _re.search(r'Release Notes[^<]*</a></h2>\s*<p>[^<]*<span class="tag">(v[\d.]+)</span>', html, _re.DOTALL)
    if not m:
        m = _re.search(r'Release Notes（(v[\d.]+)）', html)
    if m:
        ver = m.group(1)
        if ver not in md:
            print(f'OUT OF SYNC: doc/index.md missing {ver} (see doc/index.html Release Notes card)', file=sys.stderr)
            return False
    return True


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
        index_ok = check_index_md()
        n = sync_markdown(check_only=True)
        if not index_ok:
            n += 1
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
