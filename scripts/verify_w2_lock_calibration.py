"""隔离 C-0 锁校准：SQLite 写锁与 MySQL advisory lock 失联反例。"""
import json
import multiprocessing as mp
import sqlite3
import sys
import tempfile
import uuid
from pathlib import Path

from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from flask_apscheduler import APScheduler
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import OperationalError

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.CuBackgroundScheduler import CuBackgroundScheduler


def sqlite_owner(path, events, proceed):
    connection = sqlite3.connect(path, timeout=1)
    connection.execute('BEGIN IMMEDIATE')
    events.put('sqlite_locked')
    assert proceed.get(timeout=15) == 'release'
    connection.rollback()
    connection.close()


def mysql_old_writer(url, lock_name, events, proceed):
    engine = create_engine(url, pool_pre_ping=True)
    lock_connection = engine.connect()
    scheduler = CuBackgroundScheduler(jobstores={'default': SQLAlchemyJobStore(url=url)}, timezone='UTC')
    api = APScheduler(scheduler=scheduler)
    try:
        assert lock_connection.execute(text('SELECT GET_LOCK(:name, 1)'), {'name': lock_name}).scalar_one() == 1
        connection_id = lock_connection.execute(text('SELECT CONNECTION_ID()')).scalar_one()
        scheduler.start(paused=True)
        api.add_job('probe', func='app.crons:cron_do', args=[999999], trigger='cron',
                    hour='12', next_run_time=None, replace_existing=True)
        events.put(('mysql_old_locked', connection_id))
        assert proceed.get(timeout=20) == 'write_old'
        # 专门模拟进程未察觉锁连接已被断开，继续用另一连接写 JobStore。
        api.add_job('probe', func='app.crons:cron_do', args=[999999], trigger='cron',
                    hour='13', next_run_time=None, replace_existing=True)
        events.put('old_write_completed')
    finally:
        scheduler.shutdown(wait=True)
        try:
            lock_connection.close()
        except OperationalError as exc:
            if exc.orig.args[0] not in (2006, 2013):
                raise
        engine.dispose()


def main():
    ctx = mp.get_context('spawn')
    output = {}
    with tempfile.TemporaryDirectory(prefix='cronpilot-w2-lock-') as directory:
        path = str(Path(directory) / 'business.sqlite')
        with sqlite3.connect(path) as connection:
            connection.execute('CREATE TABLE marker (id INTEGER PRIMARY KEY)')
        events, proceed = ctx.Queue(), ctx.Queue()
        owner = ctx.Process(target=sqlite_owner, args=(path, events, proceed))
        owner.start()
        try:
            assert events.get(timeout=15) == 'sqlite_locked'
            contender = sqlite3.connect(path, timeout=0.2)
            try:
                try:
                    contender.execute('BEGIN IMMEDIATE')
                    raise AssertionError('expected locked database')
                except sqlite3.OperationalError as exc:
                    assert 'locked' in str(exc).lower()
            finally:
                contender.close()
            proceed.put('release')
            owner.join(timeout=15)
            assert owner.exitcode == 0
            with sqlite3.connect(path, timeout=1) as connection:
                connection.execute('BEGIN IMMEDIATE')
                connection.rollback()
            owner2 = ctx.Process(target=sqlite_owner, args=(path, events, proceed))
            owner2.start()
            try:
                assert events.get(timeout=15) == 'sqlite_locked'
                owner2.terminate()
                owner2.join(timeout=10)
                assert not owner2.is_alive()
                with sqlite3.connect(path, timeout=1) as connection:
                    connection.execute('BEGIN IMMEDIATE')
                    connection.rollback()
            finally:
                if owner2.is_alive():
                    owner2.terminate()
                    owner2.join(timeout=5)
            output['sqlite'] = {'other_process_blocked': True, 'released_after_rollback': True,
                                'released_after_process_exit': True}
        finally:
            if owner.is_alive():
                owner.terminate()
                owner.join(timeout=5)
        # 同文件 JobStore 使用独立连接；持有业务写锁期间直接调用可能自阻塞。
        job_url = 'sqlite:///' + path
        scheduler = CuBackgroundScheduler(jobstores={'default': SQLAlchemyJobStore(
            url=job_url, engine_options={'connect_args': {'timeout': 0.2}})}, timezone='UTC')
        scheduler.start(paused=True)
        try:
            lock_connection = sqlite3.connect(path, timeout=1)
            lock_connection.execute('BEGIN IMMEDIATE')
            try:
                try:
                    scheduler.add_job('app.crons:cron_do', 'cron', hour='12', id='self-block', args=[999999],
                                      next_run_time=None, replace_existing=True)
                    raise AssertionError('expected same-file jobstore write to block')
                except OperationalError as exc:
                    assert 'locked' in str(exc).lower()
            finally:
                lock_connection.rollback()
                lock_connection.close()
            scheduler.add_job('app.crons:cron_do', 'cron', hour='12', id='self-block', args=[999999],
                              next_run_time=None, replace_existing=True)
            assert scheduler.get_job('self-block').next_run_time is None
            output['sqlite']['same_file_jobstore_separate_connection_blocked'] = True
        finally:
            scheduler.shutdown(wait=True)

    server_url = make_url('mysql+pymysql://root@127.0.0.1:33089/?charset=utf8mb4')
    server = create_engine(server_url, connect_args={'connect_timeout': 5})
    database = 'cronpilot_w2_' + uuid.uuid4().hex
    lock_name = 'cpw2_' + uuid.uuid4().hex
    created = False
    worker = None
    try:
        with server.begin() as connection:
            connection.execute(text('CREATE DATABASE `%s` CHARACTER SET utf8mb4' % database))
            created = True
        url = str(server_url.set(database=database))
        events, proceed = ctx.Queue(), ctx.Queue()
        worker = ctx.Process(target=mysql_old_writer, args=(url, lock_name, events, proceed))
        worker.start()
        event, connection_id = events.get(timeout=20)
        assert event == 'mysql_old_locked'
        with server.connect() as coordinator:
            assert coordinator.execute(text('SELECT GET_LOCK(:name, 0)'), {'name': lock_name}).scalar_one() == 0
            coordinator.execute(text('KILL CONNECTION %d' % int(connection_id)))
            assert coordinator.execute(text('SELECT GET_LOCK(:name, 5)'), {'name': lock_name}).scalar_one() == 1
            fresh = CuBackgroundScheduler(jobstores={'default': SQLAlchemyJobStore(url=url)}, timezone='UTC')
            fresh.start(paused=True)
            try:
                fresh.resume_job('probe')
                assert fresh.get_job('probe').next_run_time is not None
                proceed.put('write_old')
                assert events.get(timeout=20) == 'old_write_completed'
                assert fresh.get_job('probe').next_run_time is None
            finally:
                fresh.shutdown(wait=True)
                coordinator.execute(text('SELECT RELEASE_LOCK(:name)'), {'name': lock_name})
        worker.join(timeout=15)
        assert worker.exitcode == 0
        output['mysql'] = {'lock_excludes_contender': True, 'disconnect_releases_lock': True,
                           'old_process_still_overwrites_jobstore': True}
    finally:
        if worker and worker.is_alive():
            worker.terminate()
            worker.join(timeout=5)
        if created:
            with server.begin() as connection:
                connection.execute(text('DROP DATABASE `%s`' % database))
        server.dispose()
    output['isolated_cleanup'] = True
    print(json.dumps(output, ensure_ascii=False))


if __name__ == '__main__':
    main()
