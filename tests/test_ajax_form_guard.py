# -*- coding:utf-8 -*-
"""静态门禁：管理端 js-ajax-form 必须配对 js-ajax-submit。

simpleboot common.js 仅在 button.js-ajax-submit 点击后设置 $btn；
缺 class 会导致 Ajax 未接管、浏览器整页提交落在裸 JSON。
"""
import os
import re
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
TEMPLATES = os.path.join(ROOT, 'app', 'templates')

FORM_OPEN = re.compile(
    r'<form\b[^>]*\bjs-ajax-form\b[^>]*>',
    re.IGNORECASE,
)
FORM_CLOSE = re.compile(r'</form\s*>', re.IGNORECASE)
AJAX_SUBMIT = re.compile(r'\bjs-ajax-submit\b')


def _iter_html_templates():
    for dirpath, _dirnames, filenames in os.walk(TEMPLATES):
        for name in filenames:
            if name.endswith('.html'):
                yield os.path.join(dirpath, name)


def _ajax_forms_missing_submit(html):
    """返回 (start_index, snippet) 列表：js-ajax-form 块内无 js-ajax-submit。"""
    bad = []
    for m in FORM_OPEN.finditer(html):
        start = m.start()
        close = FORM_CLOSE.search(html, m.end())
        end = close.end() if close else len(html)
        block = html[start:end]
        if not AJAX_SUBMIT.search(block):
            bad.append((start, block[:120].replace('\n', ' ')))
    return bad


class TestAjaxFormGuard(unittest.TestCase):
    def test_every_js_ajax_form_has_js_ajax_submit(self):
        failures = []
        for path in _iter_html_templates():
            with open(path, 'r', encoding='utf-8') as f:
                html = f.read()
            if 'js-ajax-form' not in html:
                continue
            rel = os.path.relpath(path, ROOT)
            for _pos, snip in _ajax_forms_missing_submit(html):
                failures.append('%s: js-ajax-form without js-ajax-submit (%s…)' % (rel, snip))
        self.assertEqual(
            failures,
            [],
            '管理端 Ajax 表单须同时含 js-ajax-form 与 js-ajax-submit（对照 cron_add.html）。\n'
            + '\n'.join(failures),
        )

    def test_known_ajax_pages_still_guarded(self):
        """样板页与用户管理页须保留配对，防止误删提交按钮。"""
        must = (
            'cron_add.html',
            'cron_edit.html',
            'cron_retire.html',
            os.path.join('rbac', 'users_add.html'),
            os.path.join('rbac', 'users_edit.html'),
            os.path.join('rbac', 'users_set_active.html'),
            os.path.join('rbac', 'groups_add.html'),
            os.path.join('rbac', 'groups_edit.html'),
            os.path.join('rbac', 'change_password.html'),
        )
        for name in must:
            path = os.path.join(TEMPLATES, name)
            with open(path, 'r', encoding='utf-8') as f:
                html = f.read()
            self.assertIn('js-ajax-form', html, name)
            self.assertEqual(
                _ajax_forms_missing_submit(html),
                [],
                name,
            )


POST_FORM = re.compile(
    r'<form\b[^>]*\bmethod\s*=\s*["\']post["\'][^>]*>',
    re.IGNORECASE,
)


class TestAntiDoubleSubmitGuard(unittest.TestCase):
    """全局防重复提交门禁：所有含 POST 表单的模板必须加载 common.js。"""

    def test_common_js_has_global_guard(self):
        """common.js 须包含全局 POST 表单防重复提交守卫。"""
        path = os.path.join(ROOT, 'app', 'static', 'js', 'common.js')
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
        self.assertIn('cp-submitting', content,
                      'common.js 须包含全局防重复提交守卫（cp-submitting 标记）')

    def test_standalone_post_forms_include_common_js(self):
        """不继承 admin_base.html 的 POST 表单页须显式引入 common.js 或内联等效防重复提交守卫。"""
        failures = []
        for path in _iter_html_templates():
            basename = os.path.basename(path)
            if basename.startswith('_'):
                continue
            with open(path, 'r', encoding='utf-8') as f:
                html = f.read()
            if not POST_FORM.search(html):
                continue
            if 'admin_base.html' in html or "extends" in html:
                continue
            if 'common.js' in html:
                continue
            if '.disabled' in html and ('submitting' in html.lower() or '中…' in html):
                continue
            rel = os.path.relpath(path, ROOT)
            failures.append(rel)
        self.assertEqual(
            failures,
            [],
            '独立 POST 表单页须引入 common.js 或内联等效防重复提交守卫：\n'
            + '\n'.join(failures),
        )


if __name__ == '__main__':
    unittest.main()
