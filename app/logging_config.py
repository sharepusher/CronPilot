# -*- coding: utf-8 -*-
"""
Structured JSON logging for CronPilot.

Provides:
  - ContextVar-based fields shared across HTTP requests and scheduler jobs
  - JSON formatter via python-json-logger (pythonjsonlogger)
  - setup_logging() to replace the inline handler block in create_app()

Field contract (every log record):
  timestamp / level / logger / message / filename / lineno / thread
  trace_id    — UUID4 per HTTP request (X-Request-Id header or auto-generated)
                or cronpilot_log_id for scheduler invocations
  cron_id     — numeric cron task id (scheduler jobs only)
  task_name   — human-readable task name (scheduler jobs only)
  duration_ms — wall-clock ms for a completed scheduler invocation
  status      — "ok" | "error" | "timeout" (scheduler jobs only)

Fields absent from context are emitted as JSON null, which ELK / Loki can
filter with an `exists` query.
"""
import logging
import uuid
from contextvars import ContextVar
from logging.handlers import TimedRotatingFileHandler

from pythonjsonlogger import jsonlogger

from configs import configs

# ---------------------------------------------------------------------------
# Shared context variables — set per HTTP request or per scheduler invocation.
# gevent 23.9.1 propagates ContextVar across greenlets correctly (Python 3.7+).
# ---------------------------------------------------------------------------
_ctx_trace_id: ContextVar[str] = ContextVar('trace_id', default='')
_ctx_cron_id: ContextVar[str] = ContextVar('cron_id', default='')
_ctx_task_name: ContextVar[str] = ContextVar('task_name', default='')
_ctx_duration_ms: ContextVar[int] = ContextVar('duration_ms', default=-1)
_ctx_status: ContextVar[str] = ContextVar('status', default='')


class _LevelFilter(logging.Filter):
    """Allow only records at exactly one log level."""

    def __init__(self, level: int) -> None:
        super().__init__()
        self._level = level

    def filter(self, record: logging.LogRecord) -> bool:
        return record.levelno == self._level


class _ContextInjectFilter(logging.Filter):
    """Read ContextVar values and inject them into every LogRecord."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.trace_id = _ctx_trace_id.get() or None
        record.cron_id = _ctx_cron_id.get() or None
        record.task_name = _ctx_task_name.get() or None
        duration = _ctx_duration_ms.get()
        record.duration_ms = duration if duration >= 0 else None
        record.status = _ctx_status.get() or None
        return True


class _CronPilotJsonFormatter(jsonlogger.JsonFormatter):
    """Stable-field-order JSON formatter for ELK / Loki ingestion."""

    def add_fields(
        self,
        log_record: dict,
        record: logging.LogRecord,
        message_dict: dict,
    ) -> None:
        super().add_fields(log_record, record, message_dict)
        # Rename asctime → timestamp for Loki/ELK conventions
        log_record['timestamp'] = log_record.pop('asctime', None)
        # Rename levelname → level and name → logger for ELK field conventions
        if 'levelname' in log_record:
            log_record['level'] = log_record.pop('levelname')
        if 'name' in log_record:
            log_record['logger'] = log_record.pop('name')
        # Ensure structured keys are always present (null when not set)
        for key in ('trace_id', 'cron_id', 'task_name', 'duration_ms', 'status'):
            log_record.setdefault(key, getattr(record, key, None))


def setup_logging(app, base_dir: str) -> None:
    """Configure root logger with JSON handlers; wire app.logger to propagate.

    Reads log_level and log_json_enabled from conf.ini ([default] section).
    Defaults: log_level=INFO, log_json_enabled=1.

    Must be called once inside create_app() after config is loaded.
    All module loggers that propagate to root automatically gain file output,
    closing the previous logging blind-spot for getLogger(__name__) callers.
    """
    raw_level = configs('log_level') or 'INFO'
    numeric_level = getattr(logging, raw_level.upper(), logging.INFO)
    json_enabled = (configs('log_json_enabled') or '1') != '0'

    root = logging.getLogger()
    root.setLevel(numeric_level)
    # Clear any handlers added by basicConfig or previous calls to avoid duplicates.
    root.handlers.clear()

    fmt_str = (
        '%(asctime)s %(levelname)s %(name)s %(filename)s %(lineno)d %(thread)d %(message)s'
    )
    if json_enabled:
        formatter: logging.Formatter = _CronPilotJsonFormatter(
            fmt_str, datefmt='%Y-%m-%dT%H:%M:%S.%f%z'
        )
    else:
        formatter = logging.Formatter(
            '[%(asctime)s][%(filename)s:%(lineno)d][%(levelname)s][%(thread)d] - %(message)s'
        )

    ctx_filter = _ContextInjectFilter()

    info_handler = TimedRotatingFileHandler(
        '%s/datas/logs/info.log' % base_dir,
        when='H', interval=1, backupCount=7, encoding='UTF-8', delay=False, utc=True,
    )
    info_handler.addFilter(_LevelFilter(logging.INFO))
    info_handler.addFilter(ctx_filter)
    info_handler.setFormatter(formatter)

    error_handler = TimedRotatingFileHandler(
        '%s/datas/logs/error.log' % base_dir,
        when='D', interval=1, backupCount=15, encoding='UTF-8', delay=False, utc=True,
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.addFilter(ctx_filter)
    error_handler.setFormatter(formatter)

    root.addHandler(info_handler)
    root.addHandler(error_handler)

    # app.logger propagates to root by default in Flask; clear any local handlers
    # Flask may have added (e.g. default StreamHandler in development).
    app.logger.handlers.clear()
    app.logger.propagate = True
    app.logger.setLevel(logging.DEBUG)
