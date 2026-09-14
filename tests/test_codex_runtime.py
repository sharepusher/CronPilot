import os
import subprocess
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
SCRIPT = os.path.join(ROOT, 'scripts', 'cronpilot_codex.sh')


class TestCodexRuntimeScript(unittest.TestCase):
    def run_script(self, *args):
        return subprocess.run(
            [SCRIPT, *args], cwd=ROOT, text=True,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        )

    def test_shell_syntax(self):
        result = subprocess.run(['bash', '-n', SCRIPT], cwd=ROOT)
        self.assertEqual(result.returncode, 0)

    def test_offline_check_does_not_require_network(self):
        result = self.run_script('check')
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn('offline validation', result.stdout)

    def test_unknown_command_has_usage_exit_code(self):
        result = self.run_script('unknown')
        self.assertEqual(result.returncode, 2)
        self.assertIn('用法', result.stdout)
