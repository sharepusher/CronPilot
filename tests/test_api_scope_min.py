# -*- coding: utf-8 -*-
"""API 层最小 Scope 止损（见 doc/RBAC与群组权限管理评审报告.html）。

覆盖三批实现：
1. `_api_token_guard` 鉴权失败写 rbac_audit_logs（action='api:deny'）。
2. `api_access_token_required` opt-in fail-fast（config.py + scripts/check_conf_production.py）。
3. 审计文案（audit_action_label / audit_resource_label）。
"""
import importlib.util
import os
import sys
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def _load_check_mod():
    path = os.path.join(ROOT, 'scripts', 'check_conf_production.py')
    spec = importlib.util.spec_from_file_location('check_conf_production_test_api', path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_check_mod = _load_check_mod()


class TestIsApiTokenRequiredButMissing(unittest.TestCase):
    """纯函数：config.is_api_token_required_but_missing。"""

    def test_default_off_never_blocks(self):
        from config import is_api_token_required_but_missing

        self.assertFalse(is_api_token_required_but_missing('', ''))
        self.assertFalse(is_api_token_required_but_missing('0', ''))
        self.assertFalse(is_api_token_required_but_missing(None, None))

    def test_enabled_but_empty_token_blocks(self):
        from config import is_api_token_required_but_missing

        self.assertTrue(is_api_token_required_but_missing('1', ''))
        self.assertTrue(is_api_token_required_but_missing('true', '   '))

    def test_enabled_with_token_passes(self):
        from config import is_api_token_required_but_missing

        self.assertFalse(is_api_token_required_but_missing('1', 'secret-token'))


class TestProductionInitAppApiToken(unittest.TestCase):
    """ProductionConfig.init_app 的第二层校验（与 configs() 联动）。"""

    def test_rejects_when_required_but_empty(self):
        from unittest.mock import patch

        from flask import Flask

        from config import ProductionConfig, DEFAULT_SECRET_KEY, MIN_SECRET_KEY_LEN

        app = Flask(__name__)
        app.config.from_object(ProductionConfig)
        app.config['SECRET_KEY'] = 'k' * MIN_SECRET_KEY_LEN
        self.assertNotEqual(app.config['SECRET_KEY'], DEFAULT_SECRET_KEY)

        def _fake_configs(key=None):
            return {'api_access_token_required': '1', 'api_access_token': ''}.get(key, '')

        with patch('config.configs', side_effect=_fake_configs):
            with self.assertRaises(RuntimeError) as ctx:
                ProductionConfig.init_app(app)
            self.assertIn('api_access_token_required', str(ctx.exception))

    def test_accepts_when_required_and_token_set(self):
        from unittest.mock import patch

        from flask import Flask

        from config import ProductionConfig, MIN_SECRET_KEY_LEN

        app = Flask(__name__)
        app.config.from_object(ProductionConfig)
        app.config['SECRET_KEY'] = 'k' * MIN_SECRET_KEY_LEN

        def _fake_configs(key=None):
            return {'api_access_token_required': '1', 'api_access_token': 'secret'}.get(key, '')

        with patch('config.configs', side_effect=_fake_configs):
            ProductionConfig.init_app(app)  # must not raise

    def test_accepts_when_disabled_regardless_of_token(self):
        from unittest.mock import patch

        from flask import Flask

        from config import ProductionConfig, MIN_SECRET_KEY_LEN

        app = Flask(__name__)
        app.config.from_object(ProductionConfig)
        app.config['SECRET_KEY'] = 'k' * MIN_SECRET_KEY_LEN

        def _fake_configs(key=None):
            return {'api_access_token_required': '0', 'api_access_token': ''}.get(key, '')

        with patch('config.configs', side_effect=_fake_configs):
            ProductionConfig.init_app(app)  # must not raise


class TestCheckConfProductionApiToken(unittest.TestCase):
    """scripts/check_conf_production.py 预检脚本（run_production.sh / verify_docker_compose.sh 用）。"""

    def _write_conf(self, tmp, **overrides):
        import configparser

        path = os.path.join(tmp, 'conf.ini')
        cp = configparser.ConfigParser()
        cp['default'] = {
            'cron_db_url': 'sqlite:////opt/cronpilot/datas/cron.sqlite',
            'cron_job_log_db_url': 'sqlite:////opt/cronpilot/datas/job_log.sqlite',
        }
        cp['default'].update(overrides)
        with open(path, 'w', encoding='utf-8') as f:
            cp.write(f)
        return path

    def test_default_off_passes(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            path = self._write_conf(tmp)
            self.assertEqual(_check_mod.check_api_access_token(path), 0)

    def test_required_but_empty_blocks(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            path = self._write_conf(
                tmp, api_access_token_required='1', api_access_token='',
            )
            self.assertEqual(_check_mod.check_api_access_token(path), 1)

    def test_required_with_token_passes(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            path = self._write_conf(
                tmp, api_access_token_required='1', api_access_token='abc123',
            )
            self.assertEqual(_check_mod.check_api_access_token(path), 0)

    def test_main_flow_blocks_before_secret_key_check(self):
        """main() 应在 SECRET_KEY 校验之前先拦截 api_access_token_required 缺口。"""
        import tempfile
        from unittest.mock import patch

        with tempfile.TemporaryDirectory() as tmp:
            path = self._write_conf(
                tmp, api_access_token_required='1', api_access_token='',
            )
            with patch.dict(os.environ, {'CRONPILOT_CONF': path, 'SECRET_KEY': 'k' * 32}):
                self.assertEqual(_check_mod.main(), 1)


class TestApiDenyAudit(unittest.TestCase):
    """`_api_token_guard` 鉴权失败写 rbac_audit_logs。"""

    def setUp(self):
        from flask import Flask

        from app import db
        import app.api as api_pkg

        app = Flask(__name__)
        app.secret_key = 'test'
        app.config['TESTING'] = True
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
        db.init_app(app)
        app.register_blueprint(api_pkg.api, url_prefix='/api')
        self.app = app
        self.db = db
        self.client = app.test_client()
        with app.app_context():
            from datas.model.rbac_audit_log import RbacAuditLog  # noqa: F401
            db.create_all()

    def test_wrong_token_denied_and_audited(self):
        from unittest.mock import patch

        with patch('configs.configs', return_value='secret-token'):
            resp = self.client.post(
                '/api/cron/status',
                data={'task_name': 'x'},
                headers={'Authorization': 'Bearer wrong-token'},
            )
        self.assertEqual(resp.status_code, 401)
        self.assertEqual(resp.get_json().get('errcode'), 1)
        with self.app.app_context():
            from sqlalchemy import select

            from datas.model.rbac_audit_log import RbacAuditLog

            rows = self.db.session.scalars(
                select(RbacAuditLog).where(RbacAuditLog.action == 'api:deny')
            ).all()
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0].status, 'deny')
            self.assertIn('/api/cron/status', rows[0].resource)

    def test_empty_configured_token_not_audited(self):
        """api_access_token 未配置时按现有语义直接放行，不触发鉴权失败审计。"""
        from unittest.mock import patch

        with patch('configs.configs', return_value=''):
            resp = self.client.post('/api/cron/status', data={'task_name': 'nonexistent'})
        # 未配置 token 时放行进入视图；因任务不存在返回业务错误而非 401
        self.assertNotEqual(resp.status_code, 401)
        with self.app.app_context():
            from sqlalchemy import select

            from datas.model.rbac_audit_log import RbacAuditLog

            rows = self.db.session.scalars(
                select(RbacAuditLog).where(RbacAuditLog.action == 'api:deny')
            ).all()
            self.assertEqual(len(rows), 0)


class TestAuditLabels(unittest.TestCase):
    def test_api_deny_labels(self):
        from app.rbac.services import audit_action_label, audit_resource_label

        self.assertEqual(audit_action_label('api:deny'), 'API 鉴权失败')
        self.assertEqual(
            audit_resource_label('api:deny', '/api/cron/status'),
            '接口 /api/cron/status 鉴权失败',
        )


if __name__ == '__main__':
    unittest.main()
