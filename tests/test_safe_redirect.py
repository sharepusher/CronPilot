"""Tests for app.rbac.safe_redirect — open redirect prevention (P0-2)."""

import importlib
import importlib.util
import os
import sys
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def _load_module(mod_name, rel_path):
    path = os.path.join(ROOT, rel_path)
    spec = importlib.util.spec_from_file_location(mod_name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


safe_redirect = _load_module('safe_redirect', 'app/rbac/safe_redirect.py')
safe_next_url = safe_redirect.safe_next_url


class TestSafeNextUrl(unittest.TestCase):
    """Ensure safe_next_url blocks malicious redirect targets."""

    # ---- should allow (safe relative paths) ----

    def test_relative_path(self):
        self.assertEqual(safe_next_url('/cron_list'), '/cron_list')

    def test_relative_path_with_query(self):
        self.assertEqual(safe_next_url('/cron_list?page=2'), '/cron_list?page=2')

    def test_relative_subpath(self):
        self.assertEqual(safe_next_url('/rbac/users'), '/rbac/users')

    # ---- should reject (dangerous targets) ----

    def test_reject_absolute_http(self):
        self.assertEqual(safe_next_url('http://evil.com/steal'), '/cron_list')

    def test_reject_absolute_https(self):
        self.assertEqual(safe_next_url('https://evil.com/steal'), '/cron_list')

    def test_reject_protocol_relative(self):
        self.assertEqual(safe_next_url('//evil.com/steal'), '/cron_list')

    def test_reject_javascript_scheme(self):
        self.assertEqual(safe_next_url('javascript:alert(1)'), '/cron_list')

    def test_reject_data_scheme(self):
        self.assertEqual(safe_next_url('data:text/html,<h1>x</h1>'), '/cron_list')

    # ---- edge cases ----

    def test_empty_string_returns_default(self):
        self.assertEqual(safe_next_url(''), '/cron_list')

    def test_none_returns_default(self):
        self.assertEqual(safe_next_url(None), '/cron_list')

    def test_custom_default(self):
        self.assertEqual(safe_next_url('https://evil.com', default='/dashboard'), '/dashboard')


if __name__ == '__main__':
    unittest.main()
