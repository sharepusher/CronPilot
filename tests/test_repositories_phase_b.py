# -*- coding:utf-8 -*-
"""Phase B：views 列表路径不得直接调用 paginate_select（须经 Repository）。"""
import os
import re
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
VIEW_FILES = (
    os.path.join(ROOT, 'app', 'main', 'views.py'),
    os.path.join(ROOT, 'app', 'rbac', 'views.py'),
)

PAGINATE_SELECT_CALL = re.compile(r'\bpaginate_select\s*\(')
PAGINATE_SELECT_IMPORT = re.compile(
    r'from\s+app\.services\.pagination\s+import\s+[^\n]*\bpaginate_select\b'
)


class TestViewsUseRepositories(unittest.TestCase):
    def test_views_do_not_call_paginate_select(self):
        failures = []
        for path in VIEW_FILES:
            with open(path, 'r', encoding='utf-8') as f:
                src = f.read()
            rel = os.path.relpath(path, ROOT)
            if PAGINATE_SELECT_IMPORT.search(src):
                failures.append('%s: still imports paginate_select' % rel)
            for i, line in enumerate(src.splitlines(), 1):
                if PAGINATE_SELECT_CALL.search(line):
                    failures.append('%s:%s: %s' % (rel, i, line.strip()))
        self.assertEqual(
            failures,
            [],
            '列表分页须经 Repository.paginate（Phase B）。\n'
            + '\n'.join(failures),
        )


if __name__ == '__main__':
    unittest.main()
