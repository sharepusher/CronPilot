# -*- coding: utf-8 -*-
import importlib.util
import os
import sys
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def _load_ensure():
    path = os.path.join(ROOT, 'scripts', 'ensure_business_tables.py')
    spec = importlib.util.spec_from_file_location('ensure_business_tables_test', path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestEnsureBusinessTablesBackend(unittest.TestCase):
    def test_backend_detection(self):
        mod = _load_ensure()
        self.assertEqual(mod.business_db_backend('sqlite:////tmp/x.db'), 'sqlite')
        self.assertEqual(mod.business_db_backend('sqlite:///:memory:'), 'sqlite')
        self.assertEqual(
            mod.business_db_backend('mysql+pymysql://u:p@127.0.0.1:3306/cron'),
            'mysql',
        )
        self.assertEqual(mod.business_db_backend('mysql://u:p@localhost/db'), 'mysql')
        self.assertEqual(mod.business_db_backend('postgresql://localhost/db'), '')
        self.assertEqual(mod.business_db_backend(''), '')


if __name__ == '__main__':
    unittest.main()
