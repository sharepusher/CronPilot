# -*- coding: utf-8 -*-
"""Best-effort execution events; failures never affect the trigger request."""
import json
import time

from app import db
from app.metrics import EXECUTION_EVENT_WRITE_FAILED
from datas.model.job_log_event import JobLogEvent
from datas.utils.id_generator import next_id

_DETAIL_KEYS = {
    'task.enqueued': {'trigger_source', 'scheduled_delay_ms'},
    'ssrf.check': {'block_type', 'block_detail'},
    'http.start': {'method'},
    'http.complete': {'http_status'},
    'http.timeout': {'exc_type', 'exc_detail'},
    'http.error': {'exc_type', 'exc_detail'},
    'db.write_log': {'status', 'fail_reason'},
}
_MAX_EVENTS_PER_EXECUTION = 16
_WRITE_BUDGET_MS = 200


class ExecutionTracer:
    def __init__(self, trace_id, cron_id):
        self.trace_id = trace_id
        self.cron_id = cron_id
        self._started = time.monotonic()
        self._seq = 0
        self._write_elapsed_ms = 0
        self._disabled = False

    @staticmethod
    def _safe_detail(event_type, detail):
        allowed = _DETAIL_KEYS.get(event_type, set())
        return {key: value for key, value in (detail or {}).items() if key in allowed}

    def emit(self, event_type, outcome='ok', detail=None, duration_ms=None):
        if self._disabled:
            return False
        if self._seq >= _MAX_EVENTS_PER_EXECUTION:
            self._disabled = True
            EXECUTION_EVENT_WRITE_FAILED.labels(reason='event_budget').inc()
            return False
        self._seq += 1
        write_started = time.monotonic()
        try:
            event = JobLogEvent(
                trace_id=self.trace_id,
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
                }
                # SQLAlchemy's Python-side default is applied during an ORM
                # flush; this best-effort writer intentionally uses its own
                # connection, so supply the primary key explicitly.
                values['id'] = next_id()
                conn.execute(JobLogEvent.__table__.insert(), values)
        except Exception:
            # The business db.session must remain untouched by observability failures.
            self._disabled = True
            EXECUTION_EVENT_WRITE_FAILED.labels(reason='database_error').inc()
            return False
        self._write_elapsed_ms += int((time.monotonic() - write_started) * 1000)
        if self._write_elapsed_ms > _WRITE_BUDGET_MS:
            self._disabled = True
            EXECUTION_EVENT_WRITE_FAILED.labels(reason='write_budget').inc()
        return True
