"""Isolated MySQL bulk tag deletion and lock-wait verification."""
import json
import sys
import time
import uuid
from pathlib import Path

from flask import Flask
from sqlalchemy import create_engine, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import OperationalError

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import db
from app.services.tag_service import delete_tag
from datas.model.cron_infos import CronInfos
from datas.model.tag import Tag
from datas.model.task_tag import TaskTag


def main():
    database = 'cronpilot_tag_verify_' + uuid.uuid4().hex
    url = make_url('mysql+pymysql://root@127.0.0.1:33089/?charset=utf8mb4')
    server = create_engine(url, connect_args={'connect_timeout': 5})
    created = False
    result = {}
    try:
        with server.begin() as connection:
            connection.execute(text('CREATE DATABASE `%s` CHARACTER SET utf8mb4' % database))
            created = True
        app = Flask(__name__)
        app.config.update(SQLALCHEMY_DATABASE_URI=url.set(database=database), SQLALCHEMY_TRACK_MODIFICATIONS=False)
        db.init_app(app)
        with app.app_context():
            db.metadata.create_all(db.engine, tables=[CronInfos.__table__, Tag.__table__, TaskTag.__table__])
            tasks = [CronInfos(task_name='verify-%04d' % i, task_keyword='verify', status=0,
                               scope_type='GLOBAL', created_at=1, updated_at=1,
                               last_operator_name='', last_operated_at=0) for i in range(1000)]
            tag = Tag(name='verify', group_id=None)
            db.session.add_all(tasks + [tag])
            db.session.flush()
            task_ids = [task.id for task in tasks]
            tag_id = tag.id
            db.session.execute(TaskTag.__table__.insert(), [{'task_id': i, 'tag_id': tag_id} for i in task_ids])
            db.session.commit()
            with db.engine.connect() as connection:
                plan = connection.execute(text('EXPLAIN SELECT task_id FROM task_tags WHERE tag_id=:tag'),
                                          {'tag': tag_id}).mappings().all()
                result['plan'] = [dict(row) for row in plan]
            with db.engine.connect() as locker:
                locker.execute(text('SELECT id FROM cron_infos WHERE id=:id FOR UPDATE'), {'id': task_ids[0]})
                db.session.execute(text('SET SESSION innodb_lock_wait_timeout=1'))
                start = time.perf_counter()
                try:
                    delete_tag(tag_id, force=True)
                    raise AssertionError('expected a lock timeout')
                except OperationalError as exc:
                    assert exc.orig.args[0] == 1205
                    db.session.rollback()
                result['blocked_ms'] = round((time.perf_counter() - start) * 1000, 2)
                locker.rollback()
            assert db.session.scalar(select(db.func.count()).select_from(TaskTag)) == len(task_ids)
            assert db.session.scalar(select(db.func.count()).select_from(CronInfos).where(
                CronInfos.edit_revision != 0)) == 0
            start = time.perf_counter()
            assert delete_tag(tag_id, force=True)[0]
            result['delete_ms'] = round((time.perf_counter() - start) * 1000, 2)
            assert db.session.scalar(select(db.func.count()).select_from(TaskTag)) == 0
            assert db.session.scalar(select(db.func.count()).select_from(CronInfos).where(
                CronInfos.edit_revision == 1)) == len(task_ids)
            result.update(tasks=len(task_ids), lock_timeout_rollback=True, all_revisions_incremented=True)
            db.session.remove()
            db.engine.dispose()
    finally:
        if created:
            with server.begin() as connection:
                connection.execute(text('DROP DATABASE `%s`' % database))
        server.dispose()
    result['isolated_database_removed'] = True
    print(json.dumps(result, ensure_ascii=False, default=str))


if __name__ == '__main__':
    main()
