# -*- coding: utf-8 -*-
"""
Custom Gunicorn logger that writes access logs as one-JSON-per-line.

Usage: add one line to gun.py:
    logger_class = 'app.gunicorn_logger.CronPilotLogger'

Access log fields (all requests, written to datas/logs/access.log):
  timestamp / remote_addr / method / path / status /
  response_bytes / duration_ms / user_agent / referrer

Error/startup logs from Gunicorn itself continue to stderr (unchanged).
This class does NOT interfere with setup_logging() or the root logger.
"""
import json
import logging
import os
from datetime import datetime, timezone
from logging.handlers import TimedRotatingFileHandler

from gunicorn.glogging import Logger


_basedir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_ACCESS_LOG_PATH = os.path.join(_basedir, 'datas', 'logs', 'access.log')


def _ensure_log_dir():
    log_dir = os.path.join(_basedir, 'datas', 'logs')
    os.makedirs(log_dir, exist_ok=True)


def _build_access_handler() -> TimedRotatingFileHandler:
    _ensure_log_dir()
    handler = TimedRotatingFileHandler(
        _ACCESS_LOG_PATH,
        when='D', interval=1, backupCount=7,
        encoding='UTF-8', delay=False, utc=True,
    )
    handler.setFormatter(logging.Formatter('%(message)s'))
    return handler


class CronPilotLogger(Logger):
    """Gunicorn Logger subclass that emits access records as JSON lines."""

    def setup(self, cfg):
        super().setup(cfg)
        self._access_handler = _build_access_handler()

    def access(self, resp, req, environ, request_time):
        """Called once per HTTP request; emit a JSON line to access.log."""
        status = resp.status
        if isinstance(status, str):
            try:
                status_int = int(status.split(None, 1)[0])
            except (ValueError, AttributeError):
                status_int = 0
        else:
            status_int = int(status)

        response_length = getattr(resp, 'sent', None)
        if response_length is None:
            cl = resp.headers.get('content-length')
            try:
                response_length = int(cl) if cl else None
            except (TypeError, ValueError):
                response_length = None

        duration_ms = round(request_time.seconds * 1000 + request_time.microseconds / 1000, 1)

        record = {
            'timestamp': datetime.now(tz=timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.%f%z'),
            'level': 'INFO',
            'logger': 'gunicorn.access',
            'remote_addr': environ.get('REMOTE_ADDR', '-'),
            'method': environ.get('REQUEST_METHOD', '-'),
            'path': environ.get('PATH_INFO', '-') + (
                ('?' + environ['QUERY_STRING']) if environ.get('QUERY_STRING') else ''
            ),
            'status': status_int,
            'response_bytes': response_length,
            'duration_ms': duration_ms,
            'user_agent': environ.get('HTTP_USER_AGENT', ''),
            'referrer': environ.get('HTTP_REFERER', ''),
        }
        self._access_handler.emit(
            logging.makeLogRecord({'msg': json.dumps(record, ensure_ascii=False)})
        )
