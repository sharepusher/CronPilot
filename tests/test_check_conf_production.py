# -*- coding: utf-8 -*-
import configparser
import importlib.util
import os
import sys
import tempfile
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def _load_check_conf():
    path = os.path.join(ROOT, 'scripts', 'check_conf_production.py')
    spec = importlib.util.spec_from_file_location('check_conf_production_test', path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.check_conf


check_conf = _load_check_conf()


class TestCheckConfProduction(unittest.TestCase):
    def test_rejects_memory_sqlite(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, 'conf.ini')
            cp = configparser.ConfigParser()
            cp['default'] = {
                'cron_db_url': 'sqlite:///:memory:',
                'cron_job_log_db_url': 'sqlite:///:memory:',
            }
            with open(path, 'w', encoding='utf-8') as f:
                cp.write(f)
            self.assertEqual(check_conf(path), 1)

    def test_accepts_file_sqlite(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, 'conf.ini')
            cp = configparser.ConfigParser()
            cp['default'] = {
                'cron_db_url': 'sqlite:////opt/cronpilot/datas/cron.sqlite',
                'cron_job_log_db_url': 'sqlite:////opt/cronpilot/datas/job_log.sqlite',
            }
            with open(path, 'w', encoding='utf-8') as f:
                cp.write(f)
            self.assertEqual(check_conf(path), 0)


if __name__ == '__main__':
    unittest.main()
