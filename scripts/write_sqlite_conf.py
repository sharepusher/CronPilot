#!/usr/bin/env python
# -*- coding: utf-8
"""写入 SQLite 版 conf.ini（本地或 Docker 路径）。"""
import argparse
import sys
from configparser import ConfigParser
from pathlib import Path


CONTAINER_DATAS = '/opt/cronpilot/datas'


def sqlite_uri(db_file: Path) -> str:
    return 'sqlite:///' + str(db_file.resolve())


def main():
    parser = argparse.ArgumentParser(description='Write SQLite conf.ini')
    parser.add_argument('--out', required=True, help='Output conf.ini path')
    parser.add_argument('--datas-dir', required=True, help='Directory for *.sqlite files')
    parser.add_argument('--login-pwd', default='changeme')
    parser.add_argument('--template', default='conf.ini.example')
    parser.add_argument(
        '--container-paths',
        action='store_true',
        help='Use /opt/cronpilot/datas/*.sqlite paths for Docker volume mounts',
    )
    args = parser.parse_args()

    root = Path(args.datas_dir).resolve()
    root.mkdir(parents=True, exist_ok=True)
    (root / 'logs').mkdir(parents=True, exist_ok=True)

    template = Path(args.template)
    if not template.is_file():
        template = Path('conf.local.sqlite.example')
    cp = ConfigParser()
    cp.read(template, encoding='utf-8')
    cp.set('default', 'is_single', '1')
    if args.container_paths:
        cron_db_url = f'sqlite:///{CONTAINER_DATAS}/cron.sqlite'
        job_log_db_url = f'sqlite:///{CONTAINER_DATAS}/job_log.sqlite'
    else:
        cron_db_url = sqlite_uri(root / 'cron.sqlite')
        job_log_db_url = sqlite_uri(root / 'job_log.sqlite')
    cp.set('default', 'cron_db_url', cron_db_url)
    cp.set('default', 'cron_job_log_db_url', job_log_db_url)
    cp.set('default', 'login_pwd', args.login_pwd)

    out = Path(args.out)
    with open(out, 'w', encoding='utf-8') as f:
        cp.write(f)
    print(out)
    print('cron_db_url =', cp.get('default', 'cron_db_url'))
    print('login_pwd =', cp.get('default', 'login_pwd'))
    return 0


if __name__ == '__main__':
    sys.exit(main())
