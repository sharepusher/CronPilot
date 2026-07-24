import uuid as _uuid

from apiflask import APIFlask
from flask_apscheduler import APScheduler
from flask_sqlalchemy import SQLAlchemy

from config import config
from app.logging_config import setup_logging, _ctx_trace_id

from app.CuBackgroundScheduler import CuBackgroundScheduler

scheduler = APScheduler(scheduler=CuBackgroundScheduler())

db = SQLAlchemy()

isCreate = False

def create_app(config_name):
    app = APIFlask(
        __name__,
        title='CronPilot',
        version='1.0.0',
        spec_path='/api/openapi.json',
        docs_path='/api/swagger',
        docs_oauth2_redirect_path='/api/swagger/oauth2-redirect',
    )
    app.config['SPEC_FORMAT'] = 'json'
    app.config.from_object(config[config_name])
    config[config_name].init_app(app)

    setup_logging(app, config[config_name].BASEDIR)

    @app.before_request
    def _inject_trace_id():
        from flask import g, request as _req
        tid = _req.headers.get('X-Request-Id') or str(_uuid.uuid4())
        g.trace_id = tid
        _ctx_trace_id.set(tid)


    db.init_app(app)
    from app.services.job_log_display import job_log_badge, job_log_content_preview, job_log_status_line
    from app.services.cron_schedule_display import format_cron_expression, humanize_schedule

    app.jinja_env.filters['job_log_status_line'] = job_log_status_line
    app.jinja_env.filters['job_log_content_preview'] = job_log_content_preview
    app.jinja_env.filters['job_log_badge'] = job_log_badge
    app.jinja_env.filters['humanize_schedule'] = humanize_schedule
    app.jinja_env.filters['format_cron_expression'] = format_cron_expression
    scheduler.app = app
    scheduler.init_app(app)
    scheduler.start()

    from .main import main as main_blueprint
    app.register_blueprint(main_blueprint)

    from .docs import docs as docs_blueprint
    app.register_blueprint(docs_blueprint)

    #接口对接
    from .api import api as apis_bl
    app.register_blueprint(apis_bl, url_prefix='/api')

    from .rbac import rbac as rbac_blueprint
    app.register_blueprint(rbac_blueprint)

    from app.security.csrf import inject_csrf_context
    app.context_processor(inject_csrf_context)

    _register_metrics_endpoint(app)
    _register_api_error_handlers(app)

    return app


def _register_api_error_handlers(app):
    """将 apiflask HTTPError（含 422 ValidationError）包装成现有 {errcode, errmsg, data} 信封。

    apiflask 2.x 用 error_processor 而非 Flask 的 errorhandler(422) 来拦截所有 HTTPError。
    调用方感知不变（errcode != 0 即失败），data.fields 提供字段级验证错误详情。
    """
    @app.error_processor
    def _api_error_processor(error):
        """统一将 apiflask HTTPError 格式化为 {errcode, errmsg, data} 信封。"""
        detail = error.detail or {}
        # 422 ValidationError: detail = {'json': {...}} 或 {'form': {...}}
        fields = detail.get('form') or detail.get('json') or detail or {}
        body = {
            'errcode': 1,
            'errmsg': error.message if error.status_code != 422 else '参数校验失败',
            'data': {'fields': fields} if fields else '',
        }
        return body, error.status_code, error.headers


def _register_metrics_endpoint(app):
    """Expose /metrics for Prometheus scraping (login-required, multiprocess-aware).

    Auth precedence:
    1. Authorization: Bearer <metrics_token> — for Prometheus server scrape (no cookie needed).
    2. session['is_login'] — for web users browsing /metrics directly.
    If neither matches, returns 403.
    metrics_token is read from conf.ini [default] metrics_token; empty string disables token auth.
    """
    try:
        import prometheus_client
        from flask import Response, abort, request as _req, session

        @app.route('/metrics')
        def metrics():
            from configs import configs as _configs
            _token = _configs('metrics_token') or ''
            # Bearer token check (Prometheus server path)
            if _token:
                auth_header = _req.headers.get('Authorization', '')
                if auth_header == 'Bearer ' + _token:
                    pass  # authorised
                elif not session.get('is_login'):
                    abort(403)
            else:
                if not session.get('is_login'):
                    abort(403)

            prom_dir = __import__('os').environ.get('PROMETHEUS_MULTIPROC_DIR')
            if prom_dir:
                from prometheus_client import CollectorRegistry, generate_latest, CONTENT_TYPE_LATEST
                from prometheus_client.multiprocess import MultiProcessCollector
                registry = CollectorRegistry()
                MultiProcessCollector(registry)
                data = generate_latest(registry)
            else:
                from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
                data = generate_latest()
            return Response(data, mimetype=CONTENT_TYPE_LATEST)
    except ImportError:
        pass