# -*- coding: utf-8 -*-
"""Best-effort execution events; failures never affect the trigger request.

Display-path summaries: ``app.services.run_inspector_presenter._SUMMARY_KEYS``
must remain a subset of ``_DETAIL_KEYS``
(see ``tests/test_execution_observability_contract.py``).
"""
import json
import time
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from app import db
from app.metrics import EXECUTION_EVENT_WRITE_FAILED
from datas.model.job_log_event import JobLogEvent

_DETAIL_KEYS = {
    'task.enqueued': {'trigger_source', 'scheduled_delay_ms', 'scheduled_at'},
    'ssrf.check': {'block_type', 'block_detail'},
    'http.start': {'method', 'display_url', 'timeout_sec', 'transport_state', 'response_received'},
    'http.complete': {'http_status', 'response_bytes', 'transport_state', 'response_received'},
    'http.timeout': {'exc_type', 'exc_detail', 'timeout_sec', 'failure_stage', 'fail_reason', 'transport_state', 'response_received'},
    'http.error': {'exc_type', 'exc_detail', 'failure_stage', 'fail_reason', 'transport_state', 'response_received'},
    'db.write_log': {'status', 'fail_reason'},
}
_MAX_EVENTS_PER_EXECUTION = 16
_WRITE_BUDGET_MS = 200


def sanitize_event_url(raw_url):
    """Persist a display-safe URL; query values are never retained."""
    if not raw_url:
        return ''
    try:
        parts = urlsplit(str(raw_url))
        if not parts.scheme or not parts.hostname:
            return ''
        host = parts.hostname
        if ':' in host and not host.startswith('['):
            host = '[{}]'.format(host)
        netloc = host
        if parts.port is not None:
            netloc = '{}:{}'.format(host, parts.port)
        if parts.username is not None or parts.password is not None:
            netloc = '***:***@' + netloc
        query = urlencode(
            [(key, '***') for key, _value in parse_qsl(parts.query, keep_blank_values=True)],
            doseq=True,
            safe='*',
        )
        return urlunsplit((parts.scheme, netloc, parts.path, query, ''))
    except (TypeError, ValueError, UnicodeError):
        return ''


class ExecutionTracer:
    def __init__(self, trace_id, cron_id, run_id=None):
        self.trace_id = trace_id
        self.cron_id = cron_id
        self.run_id = run_id
        self._started = time.monotonic()
        self._seq = 0
        self._write_elapsed_ms = 0
        self._disabled = False
        self.disabled_reason = None

    @staticmethod
    def _safe_detail(event_type, detail):
        allowed = _DETAIL_KEYS.get(event_type, set())
        return {key: value for key, value in (detail or {}).items() if key in allowed}

    def emit(self, event_type, outcome='ok', detail=None, duration_ms=None):
        if self._disabled:
            return False
        if self._seq >= _MAX_EVENTS_PER_EXECUTION:
            self._disabled = True
            self.disabled_reason = 'event_budget'
            EXECUTION_EVENT_WRITE_FAILED.labels(reason='event_budget').inc()
            return False
        self._seq += 1
        write_started = time.monotonic()
        try:
            event = JobLogEvent(
                trace_id=self.trace_id,
                run_id=self.run_id,
                cron_id=self.cron_id,
                seq=self._seq,
                event_type=event_type,
                # JobLog uses the project's historical "hms" (100 ms) format.
                # Events are intentionally different: their field contract is
                # Unix epoch milliseconds, so they can represent ordering and
                # sub-second stages without an implicit unit conversion.
                occurred_at_ms=int(time.time() * 1000),
                offset_ms=int((time.monotonic() - self._started) * 1000),
                duration_ms=duration_ms,
                outcome=outcome,
                detail=json.dumps(self._safe_detail(event_type, detail), ensure_ascii=False),
            )
            with db.engine.begin() as conn:
                values = {
                    column.name: getattr(event, column.name)
                    for column in JobLogEvent.__table__.columns
                    if column.name != 'id'
                }
                if values.get('schema_version') is None:
                    values['schema_version'] = 1
                # The database owns primary-key allocation.  Do not include
                # ``id`` in this Core INSERT: an explicit NULL would disable
                # SQLite rowid allocation and diverge from the ORM path.
                conn.execute(JobLogEvent.__table__.insert(), values)
        except Exception:
            # The business db.session must remain untouched by observability failures.
            self._disabled = True
            self.disabled_reason = 'database_error'
            EXECUTION_EVENT_WRITE_FAILED.labels(reason='database_error').inc()
            return False
        self._write_elapsed_ms += int((time.monotonic() - write_started) * 1000)
        if self._write_elapsed_ms > _WRITE_BUDGET_MS:
            self._disabled = True
            self.disabled_reason = 'write_budget'
            EXECUTION_EVENT_WRITE_FAILED.labels(reason='write_budget').inc()
        return True
