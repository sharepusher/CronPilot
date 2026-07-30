import os
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore

from configs import configs

basedir = os.path.abspath(os.path.dirname(__file__))

redis_host = configs('redis_host')

# OPT-P0-10：公开默认值；生产路径须拒绝（见 is_weak_secret_key / ProductionConfig.init_app）
DEFAULT_SECRET_KEY = 'hard to guess string'
MIN_SECRET_KEY_LEN = 16


def is_weak_secret_key(key):
    """True if key is missing, the public default, or shorter than MIN_SECRET_KEY_LEN."""
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


def is_api_token_required_but_missing(required_flag, token):
    """API 层最小 Scope 止损（见 doc/RBAC与群组权限管理评审报告.html）：

    opt-in 开关；仅当 conf.ini 显式设置 api_access_token_required=1 时，
    才要求 api_access_token 非空，默认（0/未设置）保持向后兼容、零行为变化。
    """
    flag = str(required_flag or '').strip().lower()
    if flag not in ('1', 'true', 'yes'):
        return False
    return not str(token or '').strip()


class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or DEFAULT_SECRET_KEY
    SQLALCHEMY_COMMIT_ON_TEARDOWN = False
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_POOL_RECYCLE = 3000
    # Phase D1：SA 2.0 默认 future 语义；池回收仍经 ENGINE_OPTIONS
    SQLALCHEMY_ENGINE_OPTIONS = {'pool_recycle': 3000}

    SCHEDULER_API_ENABLED = False

    CRON_DB_URL = configs('cron_db_url')

    BASEDIR = basedir

    SCHEDULER_JOBSTORES = {
        'default': SQLAlchemyJobStore(url=configs('cron_db_url'),engine_options={'pool_recycle':30})
    }
    SCHEDULER_EXECUTORS = {
        'default': {
            'type': 'threadpool',
            'max_workers': 30
        }
    }
    # 'misfire_grace_time':30
    SCHEDULER_JOB_DEFAULTS = {
        'coalesce': False,
        'max_instances': 20,
        'misfire_grace_time': 50
    }

    JOBS = [
        {
            'id': 'cron_check',
            'func': 'app.crons:cron_check',
            'args': None,
            'replace_existing': True,
            'trigger': 'cron',
            'day_of_week': "*",
            'day': '*',
            'hour': '*',
            'minute': '*/30'
        },
        {
            'id': 'cron_del_job_log',
            'func': 'app.crons:cron_del_job_log',
            'args': None,
            'replace_existing': True,
            'trigger': 'cron',
            'day_of_week': "*",
            'day': '*',
            'hour':'*/8'
        },
        {
            'id': 'cron_del_operation_log',
            'func': 'app.crons:cron_del_operation_log',
            'args': None,
            'replace_existing': True,
            'trigger': 'cron',
            'day_of_week': "*",
            'day': '*',
            'hour': '*/8'
        },
        {
            'id': 'cron_check_db_sleep',
            'func': 'app.crons:cron_check_db_sleep',
            'args': None,
            'replace_existing': True,
            'trigger': 'cron',
            'day_of_week': "*",
            'day': '*',
            'hour': '*',
            'minute': '*',
            'second':'*/15'
        }
    ]

    LOGIN_PWD = configs('login_pwd')
    CRON_CONFIG = configs()

    @staticmethod
    def init_app(app):
        logs_path = os.path.join(basedir, 'datas/logs')
        if not os.path.exists(logs_path):
            os.mkdir(logs_path)

class DevelopmentConfig(Config):
    DEBUG = True

    SQLALCHEMY_DATABASE_URI = configs('cron_job_log_db_url')

class TestingConfig(Config):
    TESTING = True
    # Legacy unit tests POST without tokens; dedicated tests.test_csrf sets False.
    CSRF_BYPASS_IN_TESTING = True
    SQLALCHEMY_DATABASE_URI = os.environ.get('TEST_DATABASE_URL') or \
        'sqlite:///' + os.path.join(basedir, 'data-test.sqlite')


class ProductionConfig(Config):
    DEBUG = False
    SQLALCHEMY_DATABASE_URI = configs('cron_job_log_db_url')

    @staticmethod
    def init_app(app):
        Config.init_app(app)
        key = app.config.get('SECRET_KEY')
        if is_weak_secret_key(key):
            raise RuntimeError(
                'production requires a strong SECRET_KEY via environment variable '
                '(not the built-in default, not empty, length >= %d). '
                'Generate one: python -c "import secrets; print(secrets.token_hex(32))" '
                'Or let scripts/run_production.sh bootstrap datas/.flask_secret_key.'
                % MIN_SECRET_KEY_LEN
            )
        if is_api_token_required_but_missing(
            configs('api_access_token_required'), configs('api_access_token')
        ):
            raise RuntimeError(
                'conf.ini sets api_access_token_required=1 but api_access_token is empty. '
                'Configure a non-empty api_access_token and share it with all API callers, '
                'or set api_access_token_required back to 0.'
            )


config = {
    'development': DevelopmentConfig,
    'testing': TestingConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}
