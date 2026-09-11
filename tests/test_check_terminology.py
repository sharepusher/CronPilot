"""Regression tests for the business terminology gate."""

import unittest

from scripts.check_terminology import is_business_terminology_violation


class TestTerminologyGate(unittest.TestCase):

    def test_detects_business_callback_wording(self):
        self.assertTrue(is_business_terminology_violation("HTTP callback failed"))
        self.assertTrue(is_business_terminology_violation("回调URL安全校验未通过"))

    def test_allows_scheduler_callback_api(self):
        self.assertFalse(is_business_terminology_violation("future.add_done_callback(callback)"))
        self.assertFalse(is_business_terminology_violation("one success/error callback per future"))
        self.assertFalse(is_business_terminology_violation("未在 beforeSubmit 回调中注入 csrf_token"))

    def test_allows_historical_citations(self):
        self.assertFalse(is_business_terminology_violation(
            "旧文案 `回调URL安全校验未通过` 仍须识别"
        ))
        self.assertFalse(is_business_terminology_violation(
            "BLOCKED_URL_PREFIXES = ('触发URL安全校验未通过', '回调URL安全校验未通过')"
        ))
        self.assertFalse(is_business_terminology_violation(
            "label changed from \"回调: <url>\" to \"触发 URL: <url>\""
        ))

    def test_allows_unrelated_trigger_wording(self):
        self.assertFalse(is_business_terminology_violation("sending trigger request"))


if __name__ == "__main__":
    unittest.main()
