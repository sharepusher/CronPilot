#!/usr/bin/env python
# -*- coding: utf-8
"""Block production when conf.ini uses SQLite :memory: or SECRET_KEY is weak."""
import configparser
import os
import sys
from pathlib import Path

# Keep in sync with config.DEFAULT_SECRET_KEY / MIN_SECRET_KEY_LEN / is_weak_secret_key
# (do not import config.py here — it loads SQLAlchemy JobStore + conf.ini side effects)
DEFAULT_SECRET_KEY = 'hard to guess string'
MIN_SECRET_KEY_LEN = 16


def is_weak_secret_key(key):
    if key is None:
        return True
    text = str(key).strip()
    if not text:
        return True
    if text == DEFAULT_SECRET_KEY:
        return True
    if len(text) < MIN_SECRET_KEY_LEN:
        return True
    return False


# Keep in sync with config.is_api_token_required_but_missing (do not import config.py here)
def is_api_token_required_but_missing(required_flag, token):
    flag = str(required_flag or '').strip().lower()
    if flag not in ('1', 'true', 'yes'):
        return False
    return not str(token or '').strip()


def check_conf(conf_path) -> int:
    conf_path = Path(conf_path)
    if not conf_path.is_file():
        print('ERROR: missing conf.ini at %s' % conf_path, file=sys.stderr)
        print('  Docker SQLite: python3 scripts/write_sqlite_conf.py '
              '--out conf.ini --datas-dir datas --container-paths', file=sys.stderr)
        return 1

    cp = configparser.ConfigParser()
    cp.read(conf_path, encoding='utf-8')
    if not cp.has_section('default'):
        print('ERROR: conf.ini missing [default] section', file=sys.stderr)
        return 1

    bad = []
    for key in ('cron_db_url', 'cron_job_log_db_url'):
        val = cp.get('default', key, fallback='')
        if ':memory:' in val:
            bad.append('%s=%s' % (key, val))

    if bad:
        print('ERROR: production 不可使用 SQLite :memory:（仅 conf.ci.ini / 单测）', file=sys.stderr)
        for line in bad:
            print('  %s' % line, file=sys.stderr)
        print('  Docker: python3 scripts/write_sqlite_conf.py '
              '--out conf.ini --datas-dir datas --container-paths', file=sys.stderr)
        print('  裸机 SQLite: python3 scripts/write_sqlite_conf.py '
              '--out conf.ini --datas-dir datas', file=sys.stderr)
        return 1
    return 0


def check_api_access_token(conf_path) -> int:
    """API 层最小 Scope 止损（见 doc/RBAC与群组权限管理评审报告.html）。

    opt-in：仅当 conf.ini 显式设置 api_access_token_required=1 时才拒绝空 api_access_token 启动；
    默认（0/未设置）零行为变化，避免破坏现有依赖空 token 的调用方集成。
    """
    conf_path = Path(conf_path)
    if not conf_path.is_file():
        return 0  # 缺文件已由 check_conf() 先行报错
    cp = configparser.ConfigParser()
    cp.read(conf_path, encoding='utf-8')
    if not cp.has_section('default'):
        return 0
    required = cp.get('default', 'api_access_token_required', fallback='0')
    token = cp.get('default', 'api_access_token', fallback='')
    if not is_api_token_required_but_missing(required, token):
        return 0
    print('ERROR: api_access_token_required=1 但 api_access_token 为空', file=sys.stderr)
    print('  开启该开关前，请先在 conf.ini 配置非空 api_access_token 并同步给所有 API 调用方', file=sys.stderr)
    print('  生成示例: python -c "import secrets; print(secrets.token_hex(32))"', file=sys.stderr)
    print('  尚未准备好迁移调用方时，请先将 api_access_token_required 改回 0', file=sys.stderr)
    return 1


def check_secret_key(environ=None) -> int:
    """OPT-P0-10: reject missing / default / short SECRET_KEY for production start."""
    env = environ if environ is not None else os.environ
    key = env.get('SECRET_KEY')
    # Unset → Flask config falls back to DEFAULT_SECRET_KEY (weak)
    effective = key if key is not None else DEFAULT_SECRET_KEY
    if is_weak_secret_key(effective):
        print('ERROR: production requires a strong SECRET_KEY environment variable',
              file=sys.stderr)
        print('  Rejected: empty, the built-in default (%r), or length < %d'
              % (DEFAULT_SECRET_KEY, MIN_SECRET_KEY_LEN), file=sys.stderr)
        print('  Generate: python -c "import secrets; print(secrets.token_hex(32))"',
              file=sys.stderr)
        print('  Or run via scripts/run_production.sh (auto-writes datas/.flask_secret_key)',
              file=sys.stderr)
        return 1
    return 0


def main():
    root = Path(__file__).resolve().parent.parent
    conf_path = Path(os.environ.get('CRONPILOT_CONF', root / 'conf.ini'))
    rc = check_conf(conf_path)
    if rc:
        return rc
    rc = check_api_access_token(conf_path)
    if rc:
        return rc
    return check_secret_key()


if __name__ == '__main__':
    sys.exit(main())
