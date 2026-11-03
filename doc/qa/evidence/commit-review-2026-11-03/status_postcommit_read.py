"""Memory-only evidence for a committed status change followed by a failed read.

This reports the current defect; it is not a green acceptance test for a fix.
"""
import json
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))
from sqlalchemy import event

from app import db
from app.services.cron_status_apply import save_status
from datas.model.cron_infos import CronInfos
from tests.test_cron_edit_noop import TestCronEditNoop


def reproduce():
    fixture = TestCronEditNoop()
    fixture.setUp()
    committed, injected, context = [], [], {}
    escaped = None

    def mark(_session):
        committed.append(True)

    def fail(_conn, _cursor, sql, _params, _ctx, _many):
        if committed and not injected and sql.lstrip().startswith('SELECT cron_infos.'):
            injected.append(True)
            raise RuntimeError('fixed post-commit read failure')

    event.listen(db.session(), 'after_commit', mark)
    event.listen(db.engine, 'before_cursor_execute', fail)
    try:
        with patch('app.services.cron_status_apply.apply_status', return_value='已启动') as apply:
            try:
                save_status(fixture.task_id, 1, context=context)
            except Exception as error:
                escaped = type(error).__name__
            calls = apply.call_count
    finally:
        event.remove(db.session(), 'after_commit', mark)
        event.remove(db.engine, 'before_cursor_execute', fail)
    try:
        db.session.rollback()
        db.session.expire_all()
        return dict(commit_completed=bool(committed), post_commit_read_failed=bool(injected),
                    exception_escaped=escaped, stored_status=db.session.get(CronInfos, fixture.task_id).status,
                    scheduler_apply_calls=calls, retry_context=context)
    finally:
        fixture.tearDown()


if __name__ == '__main__':
    print(json.dumps(reproduce(), ensure_ascii=False, indent=2))
