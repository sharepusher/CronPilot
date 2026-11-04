"""Regression tests for the business terminology gate."""

import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from scripts import check_terminology as gate
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


class TestPreciseEvidenceExceptions(unittest.TestCase):
    path = 'doc/qa/evidence/commit-review-2026-11-03/gates.json'
    command = '.venv-py311/bin/python scripts/check_terminology.py --check'

    def scan(self, text, path=None):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / (path or self.path)
            source.parent.mkdir(parents=True)
            source.write_text(text, encoding='utf-8')
            with patch.object(gate, 'ROOT', root), patch.object(gate, '_iter_files', return_value=[source]):
                return gate.find_violations()

    def record(self, **changes):
        return dict(command=self.command, exit_code=1, output_tail='HTTP callback failed', **changes)

    def test_exact_identifier_is_technical_but_not_a_line_exemption(self):
        self.assertFalse(is_business_terminology_violation('"callback_executed": false'))
        self.assertTrue(is_business_terminology_violation(
            '"callback_executed": false, "message": "HTTP callback failed"'))
        for text in ('callback_executed_extra', 'prefix_callback_executed', 'callback execution failed'):
            self.assertTrue(is_business_terminology_violation(text))

    def test_frozen_diagnostic_value_is_allowed_in_both_json_encodings(self):
        record = self.record()
        record['output_tail'] += '\n回调请求失败，"output_tail": "quoted"'
        for ascii_encoding in (True, False):
            self.assertEqual(self.scan(json.dumps([record], ensure_ascii=ascii_encoding, indent=2)), [])

    def test_other_paths_commands_and_success_records_remain_checked(self):
        text = json.dumps([self.record()])
        self.assertTrue(self.scan(text, 'doc/qa/evidence/other/gates.json'))
        for field, value in (('command', 'python scripts/other.py'), ('exit_code', 0),
                             ('exit_code', True), ('exit_code', '1')):
            record = self.record()
            record[field] = value
            self.assertTrue(self.scan(json.dumps([record])))

    def test_adjacent_record_is_checked_and_keeps_original_line_number(self):
        text = json.dumps([self.record(), dict(command='other', exit_code=1,
                                             output_tail='HTTP callback failed')], indent=2)
        expected = next(i for i, line in enumerate(text.splitlines(), 1)
                        if 'output_tail' in line and i > 5)
        hits = self.scan(text)
        self.assertEqual([hit[1] for hit in hits], [expected])
        self.assertIn('HTTP callback failed', hits[0][2])

    def test_other_fields_and_malformed_records_are_not_hidden(self):
        record = self.record()
        record['notes'] = 'HTTP callback failed'
        self.assertTrue(self.scan(json.dumps([record])))
        for text in ('[{"output_tail": "HTTP callback failed"',
                     '{"output_tail": "HTTP callback failed"}',
                     json.dumps([dict(command=self.command, exit_code=1, output_tail=None,
                                      notes='HTTP callback failed')])):
            self.assertTrue(self.scan(text))

    def test_duplicate_json_keys_do_not_create_an_exemption(self):
        text = ('[{"command": ' + json.dumps(self.command)
                + ', "exit_code": 1, "output_tail": "HTTP callback failed", "output_tail": "ok"}]')
        self.assertTrue(self.scan(text))

    def test_real_cli_exit_code_with_a_business_violation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'README.md'
            source.write_text('HTTP callback failed\n', encoding='utf-8')
            with patch.object(gate, 'ROOT', root), patch.object(gate, '_iter_files', return_value=[source]), \
                    patch('sys.argv', ['check_terminology.py', '--check']), redirect_stdout(io.StringIO()):
                self.assertEqual(gate.main(), 1)
            source.write_text('触发请求失败\n', encoding='utf-8')
            with patch.object(gate, 'ROOT', root), patch.object(gate, '_iter_files', return_value=[source]), \
                    patch('sys.argv', ['check_terminology.py', '--check']), redirect_stdout(io.StringIO()):
                self.assertEqual(gate.main(), 0)

    def test_current_repository_has_no_business_terminology_violations(self):
        self.assertEqual(gate.find_violations(), [])


if __name__ == "__main__":
    unittest.main()
