"""隔离 JobStore 机制实验：不连接业务库、不触发真实任务。"""
import json
import sys
import tempfile
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from apscheduler.events import EVENT_JOB_MODIFIED
from apscheduler.jobstores.base import JobLookupError
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.triggers.cron import CronTrigger
from flask_apscheduler import APScheduler
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.CuBackgroundScheduler import CuBackgroundScheduler


def experiment(url):
    base = CuBackgroundScheduler(jobstores={'default': SQLAlchemyJobStore(url=url)}, timezone='UTC')
    api = APScheduler(scheduler=base)
    observed = []
    base.start(paused=True)  # 全局暂停，绝不提交测试 job 至执行器。
    try:
        for trigger in ('cron', 'date'):
            args = {'trigger': trigger, 'next_run_time': None}
            args.update({'hour': '12'} if trigger == 'cron' else {
                'run_date': datetime.now(timezone.utc) + timedelta(days=3)})
            api.add_job('probe-' + trigger, func='app.crons:cron_do', args=[99999999], **args)
            assert api.get_job('probe-' + trigger).next_run_time is None
            new_args = dict(args, replace_existing=True)
            new_args.update({'hour': '13'} if trigger == 'cron' else {
                'run_date': datetime.now(timezone.utc) + timedelta(days=4)})
            api.add_job('probe-' + trigger, func='app.crons:cron_do', args=[99999999], **new_args)
            assert api.get_job('probe-' + trigger).next_run_time is None
            observed.append(trigger + '_replacement_paused')

        states = []

        def capture(event):
            if event.job_id == 'probe-cron':
                states.append(base.get_job(event.job_id).next_run_time is None)

        base.add_listener(capture, EVENT_JOB_MODIFIED)
        api.modify_job('probe-cron', trigger='cron', hour='14', next_run_time=None)
        base.remove_listener(capture)
        assert states == [False, True], states
        observed.append('wrapper_temporarily_unpaused')
        base.modify_job('probe-cron', trigger=CronTrigger(hour='15', timezone='UTC'), next_run_time=None)
        assert base.get_job('probe-cron').next_run_time is None
        observed.append('base_modify_paused')
        try:
            base.modify_job('absent', trigger=CronTrigger(hour='15', timezone='UTC'), next_run_time=None)
            raise AssertionError('missing job accepted')
        except JobLookupError:
            observed.append('missing_job_rejected')
    finally:
        base.shutdown(wait=True)
    restarted = CuBackgroundScheduler(jobstores={'default': SQLAlchemyJobStore(url=url)}, timezone='UTC')
    restarted.start(paused=True)
    try:
        assert restarted.get_job('probe-cron').next_run_time is None
        assert restarted.get_job('probe-date').next_run_time is None
        # 模拟 JobStore 已应用但调用方未收到成功结果。
        store = restarted._jobstores['default']
        real_update = store.update_job

        def applied_then_error(job):
            real_update(job)
            raise RuntimeError('injected lost acknowledgement')

        with patch.object(store, 'update_job', side_effect=applied_then_error):
            try:
                restarted.modify_job('probe-cron', trigger=CronTrigger(hour='16', timezone='UTC'),
                                     next_run_time=None)
                raise AssertionError('expected lost acknowledgement')
            except RuntimeError as exc:
                assert str(exc) == 'injected lost acknowledgement'
        assert '16' in str(restarted.get_job('probe-cron').trigger)
        observed.append('failed_ack_can_be_applied')

        # 两个独立调度器共享 JobStore：旧操作在恢复之后仍可覆盖暂停状态。
        second = CuBackgroundScheduler(jobstores={'default': SQLAlchemyJobStore(url=url)}, timezone='UTC')
        second.start(paused=True)
        try:
            assert restarted.get_job('probe-cron').next_run_time is None
            second.resume_job('probe-cron')
            assert second.get_job('probe-cron').next_run_time is not None
            restarted.modify_job('probe-cron', trigger=CronTrigger(hour='17', timezone='UTC'),
                                 next_run_time=None)
            assert second.get_job('probe-cron').next_run_time is None
            observed.append('stale_pause_can_override_concurrent_resume')
        finally:
            second.shutdown(wait=True)
        restarted.resume_job('probe-cron')
        assert restarted.get_job('probe-cron').next_run_time is not None
        restarted.resume_job('probe-date')
        assert restarted.get_job('probe-date').next_run_time is not None
        observed.extend(['restart_preserves_pause', 'explicit_resume_cron_and_date'])
    finally:
        restarted.shutdown(wait=True)
    return observed


def main():
    output = {}
    with tempfile.TemporaryDirectory(prefix='cronpilot-paused-w0-') as directory:
        output['sqlite'] = experiment('sqlite:///' + str(Path(directory) / 'jobs.sqlite'))
    mysql_url = make_url('mysql+pymysql://root@127.0.0.1:33089/?charset=utf8mb4')
    server = create_engine(mysql_url, connect_args={'connect_timeout': 5})
    name = 'cronpilot_w0_' + uuid.uuid4().hex
    created = False
    try:
        with server.begin() as connection:
            connection.execute(text('CREATE DATABASE `%s` CHARACTER SET utf8mb4' % name))
            created = True
        output['mysql'] = experiment(mysql_url.set(database=name))
    finally:
        if created:
            with server.begin() as connection:
                connection.execute(text('DROP DATABASE `%s`' % name))
        server.dispose()
    output['isolated_cleanup'] = True
    output['global_scheduler_paused'] = True
    print(json.dumps(output, ensure_ascii=False))


if __name__ == '__main__':
    main()
