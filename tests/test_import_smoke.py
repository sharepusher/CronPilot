# -*- coding:utf-8 -*-
"""Import 冒烟测试：确保所有 Blueprint 路由模块可成功 import。

防止 ImportError 仅在运行时暴露（如 2026-08 tag_manage session_group_ids 事件）。
"""
import unittest
import sys
import os

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, ROOT)


class TestImportSmoke(unittest.TestCase):
    """逐一 import 关键模块，确保无 ImportError。"""

    def test_import_main_views(self):
        import app.main.views  # noqa: F401

    def test_import_rbac_views(self):
        import app.rbac.views  # noqa: F401

    def test_import_api_views(self):
        import app.api.views  # noqa: F401

    def test_import_rbac_scope(self):
        import app.rbac.scope  # noqa: F401

    def test_import_rbac_policy(self):
        import app.rbac.policy  # noqa: F401

    def test_import_rbac_services(self):
        import app.rbac.services  # noqa: F401

    def test_import_cron_service(self):
        import app.services.cron_service  # noqa: F401

    def test_import_tag_service(self):
        import app.services.tag_service  # noqa: F401

    def test_import_cron_validator(self):
        import app.services.cron_validator  # noqa: F401


if __name__ == '__main__':
    unittest.main()
