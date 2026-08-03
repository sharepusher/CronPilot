# -*- coding:utf-8 -*-
"""静态门禁：模板中硬编码的 /api/ 路径必须在实际路由中存在。

根因（2026-08 api_token.html 事件）：
  模板 curl 示例引用了 /api/cron/list（不存在），实际端点为 /api/cron/query。
  此测试防止模板中出现不可达的 API 路径。
"""
import os
import re
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
TEMPLATES_DIR = os.path.join(ROOT, 'app', 'templates')
API_VIEWS = os.path.join(ROOT, 'app', 'api', 'views.py')
DOC_CATALOG = os.path.join(ROOT, 'app', 'api', 'doc_catalog.py')


def _collect_template_api_paths():
    """从所有模板中提取 /api/... 路径引用。"""
    paths = {}
    for dirpath, _dirs, filenames in os.walk(TEMPLATES_DIR):
        for fn in filenames:
            if not fn.endswith('.html'):
                continue
            fpath = os.path.join(dirpath, fn)
            with open(fpath, encoding='utf-8') as f:
                content = f.read()
            for m in re.finditer(r'/api/[a-z][a-z0-9_/]*', content):
                p = m.group(0).rstrip('/')
                if p not in paths:
                    paths[p] = []
                relpath = os.path.relpath(fpath, ROOT)
                if relpath not in paths[p]:
                    paths[p].append(relpath)
    return paths


def _collect_registered_api_paths():
    """从 api/views.py 提取已注册的路由路径（@api.get/post/route）。"""
    registered = set()
    with open(API_VIEWS, encoding='utf-8') as f:
        content = f.read()
    for m in re.finditer(
        r"@api\.(?:get|post|put|delete|patch|route)\(\s*['\"]([^'\"]+)['\"]",
        content,
    ):
        path = '/api' + m.group(1).rstrip('/')
        registered.add(path)
    # Also include well-known framework paths
    registered.add('/api/openapi.json')
    return registered


class TestTemplateApiPathGuard(unittest.TestCase):
    """模板中引用的 /api/xxx 路径必须在路由注册表中存在。"""

    def test_all_template_api_paths_are_registered(self):
        template_paths = _collect_template_api_paths()
        registered = _collect_registered_api_paths()

        orphans = {}
        for path, files in template_paths.items():
            if path not in registered:
                orphans[path] = files

        self.assertEqual(
            orphans, {},
            '模板中引用了不存在的 API 路径:\n' + '\n'.join(
                '  %s (引用自: %s)' % (p, ', '.join(f))
                for p, f in sorted(orphans.items())
            ),
        )


if __name__ == '__main__':
    unittest.main()
