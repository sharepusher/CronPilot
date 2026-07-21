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
    return check_secret_key()


if __name__ == '__main__':
    sys.exit(main())
