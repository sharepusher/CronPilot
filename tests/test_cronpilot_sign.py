# -*- coding:utf-8 -*-
import os
import sys
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, ROOT)

from app.common.functions import get_cronpilot_sign, md5


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
