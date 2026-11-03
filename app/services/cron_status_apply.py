"""启停目标保存与有限核实；已提交后不反向补偿。"""
import hashlib
import hmac
import json
import logging

from apscheduler.schedulers.base import STATE_STOPPED
from flask import current_app
from sqlalchemy import select
from sqlalchemy.orm.exc import StaleDataError

from app import db, scheduler
from app.services.cron_edit_apply import EditWriteError, check_version, job_matches_target
from datas.model.cron_infos import CronInfos

logger = logging.getLogger(__name__)


def status_config(task):
    fields = ('run_date', 'day_of_week', 'day', 'hour', 'minute', 'second')
    data = json.dumps({k: getattr(task, k) or '' for k in fields}, sort_keys=True).encode()
    return hmac.new(str(current_app.secret_key).encode(), data, hashlib.sha256).hexdigest()


def apply_status(task_id, revision, target, *, retry=False):
    """仅在重试和异常时读取 JobStore；不重新注册缺失任务。"""
    status = target['status']
    check_version(task_id, revision, status)
    if scheduler.state == STATE_STOPPED:
        raise EditWriteError('目标状态已保存，调度器未启动，可稍后重试明确目标')
    if retry:
        job = scheduler.get_job('cron_%s' % task_id, jobstore='default')
        check_version(task_id, revision, status)
        if job is None:
            raise EditWriteError('调度任务不存在，请检查任务生命周期，未重新注册')
        if job_matches_target(job, task_id, target):
            return '当前已暂停' if status == 0 else '当前已启动'
        if not job_matches_target(job, task_id, dict(target, status=1-status)):
            raise EditWriteError('调度配置与目标不一致，请刷新检查，未执行启停')
    if status == 1 and target.get('run_date'):
        from datetime import datetime
        if target['run_date'][:16] <= datetime.now(scheduler.scheduler.timezone).strftime('%Y-%m-%d %H:%M'):
            raise EditWriteError('一次性调度时间已过，未重新触发，请检查任务生命周期')
    try:
        job = (scheduler.scheduler.resume_job if status else scheduler.scheduler.pause_job)(
            'cron_%s' % task_id, jobstore='default')
    except Exception:
        logger.exception('status application uncertain task_id=%s revision=%s', task_id, revision)
        check_version(task_id, revision, status)
        try:
            observed = scheduler.get_job('cron_%s' % task_id, jobstore='default')
            matched = observed is not None and job_matches_target(observed, task_id, target)
        except Exception:
            logger.exception('status observation unavailable task_id=%s', task_id)
            matched = False
        check_version(task_id, revision, status)
        if matched:
            return '当前已观察到目标状态'
        raise EditWriteError('调度结果暂时无法确认，可稍后重试明确目标') from None
    if job is None or getattr(job, 'pending', False) is True:
        raise EditWriteError('目标状态已保存，但未确认可调度任务，请核实任务是否已结束')
    check_version(task_id, revision, status, applied=True)
    return '已启动' if status else '已暂停'


def save_status(task_id, target_status=None, *, expected_revision=None, context=None, actor_id=None, expected_config=None):
    """context 仅在提交成功后携带本次版本，调用方可绑定签名重试。"""
    task = db.session.scalar(select(CronInfos).where(CronInfos.id == task_id)
                             .execution_options(populate_existing=True))
    if task is None:
        db.session.rollback()
        return False, '任务不存在', None, None
    if task.status not in (0, 1):
        db.session.rollback()
        return False, '任务已下线，不能启动或暂停', None, None
    if actor_id is not None:
        from app.rbac.authorize import AuthorizationError, authorize
        from app.services.cron_edit_concurrency import TaskEditError, _actor
        try:
            actor, scope = _actor(actor_id, lock=True)
            authorize(actor.role, 'cron:write', task, group_ids=scope['groups'], username=actor.username)
        except (AuthorizationError, TaskEditError):
            db.session.rollback()
            return False, '当前权限不允许此操作', None, None
    old = task.status
    if target_status is None:
        target = 1-old
    elif type(target_status) not in (int, str) or str(target_status) not in ('0', '1'):
        db.session.rollback()
        return False, '无效的目标状态', None, None
    else:
        target = int(target_status)
    retry = expected_revision is not None
    if expected_config is not None and expected_config != status_config(task):
        db.session.rollback()
        return False, '任务配置已有变化，请刷新确认', None, None
    if retry and (task.edit_revision != expected_revision or task.status != target):
        db.session.rollback()
        return False, '任务已有后续修改，旧重试已拒绝，请刷新确认', None, None
    if old == target and not retry:
        db.session.rollback()
        return True, '配置状态未变化，未执行新的调度操作', old, target
    snapshot = {key: getattr(task, key) or '' for key in (
        'run_date', 'day_of_week', 'day', 'hour', 'minute', 'second')}
    snapshot['status'] = target
    name = task.task_name
    committing = False
    try:
        if not retry:
            task.status = target
            db.session.flush()
        revision = task.edit_revision
        committing = True
        db.session.commit()  # 结束读取事务，再进行独立版本核验。
    except StaleDataError:
        db.session.rollback()
        return False, '任务已被修改，本次未保存，请刷新确认', None, None
    except Exception:
        logger.exception('status persistence failed task_id=%s', task_id)
        db.session.rollback()
        return False, '状态保存结果待核实，请刷新确认' if committing else '状态保存失败，请稍后重试', None, None
    if context is not None:
        context.update(task=task_id, revision=revision, target=target, config=status_config(task))
    try:
        message = apply_status(task_id, revision, snapshot, retry=retry)
    except EditWriteError as exc:
        return False, str(exc), old, target
    except Exception:
        logger.exception('status retry unavailable task_id=%s', task_id)
        return False, '调度结果暂时无法确认，可稍后重试明确目标', old, target
    try:
        from app.services.operation_log_service import record_operation
        logger.info('status applied task_id=%s revision=%s target=%s', task_id, revision, target)
        if (old != target or retry) and not (retry and message in ('当前已暂停', '当前已启动')):
            record_operation(action='toggle_status', target_id=task_id, task_name=name,
                             detail={'status': {'old': old, 'new': target}, 'retry': retry})
    except Exception:
        pass  # best-effort 日志不能将已知成功结果改判失败。
    return True, message, old, target
