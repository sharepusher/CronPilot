import uuid as _uuid

from flask import Flask
from flask_apscheduler import APScheduler
from flask_sqlalchemy import SQLAlchemy

from config import config
from app.logging_config import setup_logging, _ctx_trace_id

from app.CuBackgroundScheduler import CuBackgroundScheduler

scheduler = APScheduler(scheduler=CuBackgroundScheduler())

db = SQLAlchemy()

isCreate = False

def create_app(config_name):
    app = Flask(__name__)
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

    return app


def _register_metrics_endpoint(app):
    """Expose /metrics for Prometheus scraping (admin-only, multiprocess-aware)."""
    try:
        import prometheus_client
        from flask import Response, abort
        from flask_login import current_user

        @app.route('/metrics')
        def metrics():
            # Only allow logged-in admin users to scrape metrics.
            if not current_user.is_authenticated:
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