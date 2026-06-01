#!/bin/bash
# 本地冒烟：Python 3.11 + 项目根目录 conf.ini
set -e
cd "$(dirname "$0")/.."
PY="${PY:-python3.11}"
if [ ! -d .venv311 ]; then
  "$PY" -m venv .venv311
  .venv311/bin/pip install -q Flask==1.1.2 Flask-SQLAlchemy==2.4.4 Flask-APScheduler==1.11.0 \
    APScheduler==3.6.3 SQLAlchemy==1.3.19 Werkzeug==1.0.1 Jinja2==2.11.2 MarkupSafe==1.1.1 \
    itsdangerous==1.1.0 click==7.1.2 requests==2.24.0 redis==3.5.3 portalocker==2.6.0 \
    records==0.5.3 pytz==2020.1 tzlocal==2.1 setuptools
fi
export FLASK_CONFIG=development
echo "CronPilot 管理端: http://127.0.0.1:5001/  (密码见 conf.ini login_pwd)"
.venv311/bin/python -c "
from app import create_app
app = create_app('development')
app.run(host='127.0.0.1', port=5001, debug=False, use_reloader=False)
"
