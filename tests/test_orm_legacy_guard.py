# -*- coding:utf-8 -*-
"""静态门禁：禁止 app/ 回潮 ORM Legacy API（Phase C）。

对照 tests.test_ajax_form_guard。规则见 doc/PhaseC-ORM-Legacy-AST门禁设计.html。
"""
from __future__ import annotations

import ast
import os
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
APP_ROOT = os.path.join(ROOT, 'app')

# 路径级例外：首版空。条目形如 ('app/foo.py', 'L3')，须附拆除计划。
ALLOWLIST = ()


class Violation(object):
    __slots__ = ('rel_path', 'lineno', 'rule_id', 'snippet')

    def __init__(self, rel_path, lineno, rule_id, snippet):
        self.rel_path = rel_path
        self.lineno = lineno
        self.rule_id = rule_id
        self.snippet = snippet

    def format(self):
        return '%s:%s: %s — %s' % (
            self.rel_path, self.lineno, self.rule_id, self.snippet,
        )


def _attr_chain_names(node):
    """自内向外收集 Attribute/Name 的标识符，如 db.session.query → ['db','session','query']。"""
    names = []
    cur = node
    while isinstance(cur, ast.Attribute):
        names.append(cur.attr)
        cur = cur.value
    if isinstance(cur, ast.Name):
        names.append(cur.id)
    names.reverse()
    return names


def _chain_has_session(names):
    return 'session' in names


def _call_func_basename(func):
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return None


def find_violations(source, filename='<string>'):
    """解析 source，返回 Violation 列表（不含 allowlist 过滤）。"""
    try:
        tree = ast.parse(source, filename=filename)
    except SyntaxError:
        return []

    violations = []

    class Visitor(ast.NodeVisitor):
        def visit_Call(self, node):
            func = node.func
            base = _call_func_basename(func)
            if isinstance(func, ast.Attribute) and func.attr == 'query':
                names = _attr_chain_names(func)
                if _chain_has_session(names):
                    snippet = '.'.join(names) + '(...)'
                    violations.append(Violation(
                        filename, node.lineno, 'L2', snippet,
                    ))
            if base == 'paginate' and isinstance(func, ast.Attribute):
                # 仅拦 Query.paginate：session.query(...).paginate / Model.query.paginate
                # 允许 BaseRepository.paginate / repo.paginate / paginate_select
                recv = func.value
                is_query_paginate = False
                if (
                    isinstance(recv, ast.Call)
                    and isinstance(recv.func, ast.Attribute)
                    and recv.func.attr == 'query'
                ):
                    is_query_paginate = True
                elif isinstance(recv, ast.Attribute) and recv.attr == 'query':
                    is_query_paginate = True
                if is_query_paginate:
                    parent_names = _attr_chain_names(func)
                    snippet = '.'.join(parent_names) + '(...)' if parent_names else '….paginate(...)'
                    violations.append(Violation(
                        filename, node.lineno, 'L3', snippet,
                    ))
            elif isinstance(func, ast.Name) and func.id == 'paginate':
                # 裸 paginate(...) 极少见，仍拦
                violations.append(Violation(
                    filename, node.lineno, 'L3', 'paginate(...)',
                ))
            self.generic_visit(node)

        def visit_Attribute(self, node):
            if node.attr == 'query':
                names = _attr_chain_names(node)
                # session.query 由 visit_Call(L2) 覆盖；此处只拦 Model.query 等
                if not _chain_has_session(names):
                    # 跳过作为 Call.func 且已是 L2 的节点（无 session 则可能是 Model.query.filter）
                    snippet = '.'.join(names) if names else '?.query'
                    violations.append(Violation(
                        filename, node.lineno, 'L1', snippet,
                    ))
            self.generic_visit(node)

    Visitor().visit(tree)
    return violations


def _is_allowlisted(rel_path, rule_id):
    return (rel_path, rule_id) in ALLOWLIST


def scan_app(app_root=None):
    root = app_root or APP_ROOT
    found = []
    for dirpath, _dirnames, filenames in os.walk(root):
        for name in filenames:
            if not name.endswith('.py'):
                continue
            path = os.path.join(dirpath, name)
            rel = os.path.relpath(path, ROOT).replace(os.sep, '/')
            with open(path, 'r', encoding='utf-8') as f:
                source = f.read()
            for v in find_violations(source, filename=rel):
                if _is_allowlisted(v.rel_path, v.rule_id):
                    continue
                found.append(v)
    return found


class TestOrmLegacyGuard(unittest.TestCase):
    def test_no_legacy_orm_in_app(self):
        failures = scan_app()
        msg = (
            'ORM Legacy API 禁止进入 app/（Phase C）。\n'
            + '\n'.join(v.format() for v in failures)
            + '\n请改用 select() + paginate_select（见 app/services/pagination.py）。'
        )
        self.assertEqual(failures, [], msg)

    def test_detector_catches_l2_fixture(self):
        src = 'db.session.query(CronInfos).filter_by(id=1).all()\n'
        vs = find_violations(src, filename='fixture.py')
        rules = [v.rule_id for v in vs]
        self.assertIn('L2', rules)

    def test_detector_catches_l1_model_query(self):
        src = 'rows = CronInfos.query.filter_by(status=1).all()\n'
        vs = find_violations(src, filename='fixture.py')
        rules = [v.rule_id for v in vs]
        self.assertIn('L1', rules)

    def test_detector_catches_l3_paginate(self):
        src = 'page = db.session.query(CronInfos).paginate(page=1, per_page=20)\n'
        vs = find_violations(src, filename='fixture.py')
        rules = set(v.rule_id for v in vs)
        self.assertTrue('L2' in rules or 'L3' in rules)
        self.assertIn('L3', rules)

    def test_detector_allows_repo_paginate(self):
        src = 'page_data = self.paginate(stmt, page_query)\n'
        vs = find_violations(src, filename='fixture.py')
        self.assertEqual(vs, [])

    def test_detector_allows_paginate_select(self):
        src = (
            'from app.services.pagination import paginate_select\n'
            'page_data = paginate_select(db.session, stmt, page_query)\n'
        )
        vs = find_violations(src, filename='fixture.py')
        self.assertEqual(vs, [])

    def test_detector_ignores_string_literal(self):
        src = 'help_text = "do not use session.query or Model.query.paginate"\n'
        vs = find_violations(src, filename='fixture.py')
        self.assertEqual(vs, [])


if __name__ == '__main__':
    unittest.main()
