#!/usr/bin/env python
# -*- coding: utf-8
"""Block production when conf.ini uses SQLite :memory: (CI / unittest only)."""
import configparser
import os
import sys
from pathlib import Path


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


def main():
    root = Path(__file__).resolve().parent.parent
    conf_path = Path(os.environ.get('CRONPILOT_CONF', root / 'conf.ini'))
    return check_conf(conf_path)


if __name__ == '__main__':
    sys.exit(main())
