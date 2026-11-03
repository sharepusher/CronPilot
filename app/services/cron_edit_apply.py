"""编辑提交后的有限冲突检测；正常同步返回不查询 JobStore。"""
import logging

from apscheduler.schedulers.base import STATE_STOPPED
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from sqlalchemy import select

from app import db, scheduler
from datas.model.cron_infos import CronInfos

logger = logging.getLogger(__name__)


class EditWriteError(RuntimeError):
    """仅携带可公开的业务消息。"""


def current_version(task_id):
    with db.engine.connect() as connection:
        return connection.execute(select(CronInfos.edit_revision, CronInfos.status).where(
            CronInfos.id == task_id)).first()


def check_version(task_id, revision, status, *, applied=False):
    try:
        actual = current_version(task_id)
    except Exception:
        logger.exception('edit version read failed task_id=%s revision=%s', task_id, revision)
        message = ('配置已保存，调度调用成功，但无法完成并发核验，请刷新核实' if applied
                   else '配置已保存，但无法完成并发核验，请刷新核实')
        raise EditWriteError(message) from None
    if actual is None or tuple(actual) != (revision, status):
        raise EditWriteError('配置已保存，但任务有后续变更，请刷新核实')


def _same_trigger(actual, expected):
    if type(actual) is not type(expected):
        return False
    if isinstance(expected, DateTrigger):
        return actual.run_date == expected.run_date
    if isinstance(expected, CronTrigger):
        return ([(f.name, str(f)) for f in actual.fields] == [(f.name, str(f)) for f in expected.fields]
                and str(actual.timezone) == str(expected.timezone)
                and (actual.start_date, actual.end_date, actual.jitter)
                == (expected.start_date, expected.end_date, expected.jitter))
    return False


def query_target(task_id, target):
    if scheduler.state == STATE_STOPPED:
        return None
    job = scheduler.get_job('cron_%s' % task_id, jobstore='default')
    if job is None:
        # 已到期一次性任务可能正常移除，缺少本次执行证据时不能断定失败。
        return None if target.get('run_date') else False
    return job_matches_target(job, task_id, target)


def job_matches_target(job, task_id, target):
    """Compare an already-read job without another JobStore lookup."""
    from app.services.cron_service import build_scheduler_kwargs

    kwargs = dict(build_scheduler_kwargs(target))
    kind = kwargs.pop('trigger')
    trigger = (DateTrigger if kind == 'date' else CronTrigger)(
        timezone=scheduler.scheduler.timezone, **kwargs)
    defaults = scheduler.app.config.get('SCHEDULER_JOB_DEFAULTS', {})
    policy = all(getattr(job, field) == defaults.get(field, fallback) for field, fallback in (
        ('misfire_grace_time', 1), ('coalesce', True), ('max_instances', 1)))
    return (job.id == 'cron_%s' % task_id and job.func_ref == 'app.crons:cron_do'
            and tuple(job.args) == (task_id,) and job.kwargs == {} and job.executor == 'default'
            and policy and _same_trigger(job.trigger, trigger)
            and ((job.next_run_time is None) == (target['status'] == 0)))


def apply_edit(task_id, revision, target):
    from app.services.cron_service import register_cron_job

    target = dict(target)
    check_version(task_id, revision, target['status'])
    if scheduler.state == STATE_STOPPED:
        raise EditWriteError('配置已保存，但调度器未启动，调度更新未执行')
    try:
        job = register_cron_job(task_id, target, paused=target['status'] == 0)
    except Exception:
        logger.exception('edit scheduler call uncertain task_id=%s revision=%s', task_id, revision)
        check_version(task_id, revision, target['status'])
        try:
            matched = query_target(task_id, target)
        except Exception:
            logger.exception('edit scheduler query failed task_id=%s revision=%s', task_id, revision)
            matched = None
        check_version(task_id, revision, target['status'])
        if matched is not True:
            message = ('配置已保存，当前调度与目标不一致，请核实' if matched is False
                       else '配置已保存，调度结果待核实，请勿重复提交')
            raise EditWriteError(message) from None
        return
    # add_job 在停止状态可能只暂存；不得将 pending 当持久化成功。
    if getattr(job, 'pending', False) is True:
        raise EditWriteError('配置已保存，但调度任务仅暂存，尚未持久化应用')
    check_version(task_id, revision, target['status'], applied=True)
