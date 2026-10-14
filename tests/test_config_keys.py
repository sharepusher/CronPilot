"""Guard tests: conf.ini.example keys must actually reach runtime config."""

import configparser
import os
import shutil
import tempfile
import unittest

import configs as configs_module
from configs import configs

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXAMPLE = os.path.join(ROOT, 'conf.ini.example')

# 这些键不进 configs() 返回字典，改由 configs('<key>') 单键读取；
# 新增豁免必须在此写明消费位置。
SINGLE_KEY_READERS = {
    'api_access_token_required': 'config.py::_validate_api_token_opt_in',
    'health_failing_threshold': 'app/services/job_health_service.py::get_failing_threshold',
}

SSRF_KEYS = (
    'block_private_ip',
    'url_allow_hosts',
    'url_ssrf_observe_only',
)


def _configs_from_example():
    """用 conf.ini.example 当作 conf.ini 调用 configs()，避免依赖开发机配置。"""
    tmp = tempfile.mkdtemp()
    try:
        shutil.copy(EXAMPLE, os.path.join(tmp, 'conf.ini'))
        original = configs_module._proj_root
        configs_module._proj_root = tmp
        try:
            return configs()
        finally:
            configs_module._proj_root = original
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


class TestExampleConfigReachable(unittest.TestCase):

    def test_every_example_key_reaches_runtime_config(self):
        parser = configparser.ConfigParser()
        parser.read(EXAMPLE, encoding='utf-8')
        example_keys = set(parser.options('default'))
        runtime = _configs_from_example()

        unreachable = sorted(
            key for key in example_keys
            if key not in runtime and key not in SINGLE_KEY_READERS
        )
        self.assertEqual(
            unreachable, [],
            'conf.ini.example 中的键未进入 configs() 且无单键读取豁免：%s' % unreachable
        )

    def test_ssrf_keys_present_in_runtime_config(self):
        runtime = _configs_from_example()
        for key in SSRF_KEYS:
            self.assertIn(key, runtime, '%s 缺失于 configs() 返回值' % key)

if __name__ == '__main__':
    unittest.main()
