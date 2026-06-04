# -*- coding:utf-8 -*-
"""签名函数测试：直接加载模块，避免 import app 触发 Flask/APScheduler 初始化。"""
import importlib.util
import os
import sys
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def _load_functions():
    path = os.path.join(ROOT, 'app/common/functions.py')
    spec = importlib.util.spec_from_file_location('cronpilot_functions_test', path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_functions = _load_functions()
get_cronpilot_sign = _functions.get_cronpilot_sign
md5 = _functions.md5


class TestCronpilotSign(unittest.TestCase):
    def test_sign_stable(self):
        data = {'cronpilot_log_id': 'abc-123', 'foo': 'bar'}
        s1 = get_cronpilot_sign(data, api_key='testkey')
        s2 = get_cronpilot_sign(data, api_key='testkey')
        self.assertEqual(s1, s2)
        self.assertEqual(len(s1), 32)

    def test_sign_changes_with_log_id(self):
        k = 'key'
        a = get_cronpilot_sign({'cronpilot_log_id': '1'}, api_key=k)
        b = get_cronpilot_sign({'cronpilot_log_id': '2'}, api_key=k)
        self.assertNotEqual(a, b)


if __name__ == '__main__':
    unittest.main()
