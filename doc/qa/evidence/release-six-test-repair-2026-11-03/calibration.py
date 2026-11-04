"""Prove negative authorization and CSRF tests detect deliberately disabled guards."""
import io
import json
import unittest
from unittest.mock import patch


def rejects_mutation(test_name, patch_target, replacement):
    suite = unittest.defaultTestLoader.loadTestsFromName(test_name)
    with patch(patch_target, replacement):
        result = unittest.TextTestRunner(stream=io.StringIO()).run(suite)
    if result.testsRun != 1 or len(result.failures) != 1 or result.errors:
        raise AssertionError('negative control did not yield exactly one assertion failure')
    return True


result = {
    'scope_bypass_detected': rejects_mutation(
        'tests.test_api_scope_s6.TestScopeIsolation.test_other_group_denied',
        'app.api.check_api_scope', lambda _task: None),
    'csrf_bypass_detected': rejects_mutation(
        'tests.test_csrf.TestCsrfOnUpdateStatus.test_post_wrong_token_rejected_without_writes',
        'app.security.csrf.validate_csrf', lambda: True),
}
print(json.dumps(result, sort_keys=True))
