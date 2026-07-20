# -*- coding: utf-8 -*-
"""Phase D2：datas/model 须使用 Mapped / mapped_column（SA 2.0 声明式）。"""
from __future__ import annotations

import ast
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODEL_DIR = ROOT / 'datas' / 'model'


class TestMappedModelGuard(unittest.TestCase):
    def test_all_model_modules_use_mapped_column(self):
        py_files = sorted(p for p in MODEL_DIR.glob('*.py') if p.name != '__init__.py')
        self.assertTrue(py_files, 'expected model modules under datas/model')
        for path in py_files:
            tree = ast.parse(path.read_text(encoding='utf-8'), filename=str(path))
            has_mapped_import = False
            has_mapped_column_import = False
            legacy_column_assigns = []
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and node.module == 'sqlalchemy.orm':
                    names = {a.name for a in node.names}
                    if 'Mapped' in names:
                        has_mapped_import = True
                    if 'mapped_column' in names:
                        has_mapped_column_import = True
                if isinstance(node, ast.Assign):
                    for target in node.targets:
                        if not isinstance(target, ast.Name):
                            continue
                        if isinstance(node.value, ast.Call):
                            func = node.value.func
                            # db.Column(...)
                            if (
                                isinstance(func, ast.Attribute)
                                and func.attr == 'Column'
                            ):
                                legacy_column_assigns.append(target.id)
            self.assertTrue(
                has_mapped_import and has_mapped_column_import,
                '%s must import Mapped and mapped_column from sqlalchemy.orm' % path.name,
            )
            self.assertEqual(
                legacy_column_assigns,
                [],
                '%s still assigns classic Column: %s'
                % (path.name, legacy_column_assigns),
            )


if __name__ == '__main__':
    unittest.main()
