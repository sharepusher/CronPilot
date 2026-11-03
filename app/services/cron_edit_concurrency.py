"""Web 任务编辑：保密基线、当前授权、三方比较和版本条件写入。"""
import hashlib
import hmac
import json

from flask import current_app
from itsdangerous import BadData, URLSafeSerializer
from sqlalchemy import select
from sqlalchemy.orm.exc import StaleDataError

from app import db
from app.rbac.authorize import AuthorizationError, authorize
from app.services.cron_edit_apply import EditWriteError, apply_edit
from app.services.cron_validator import normalize_cron_form, validate_cron_form
from datas.model.cron_infos import CronInfos
from datas.model.rbac_user import RbacUser
from datas.model.resource_group import ResourceGroup
from datas.model.tag import Tag
from datas.model.task_group import TaskGroup
from datas.model.task_tag import TaskTag
from datas.model.user_group import UserGroup

UNITS = {
    'description': ('task_keyword',),
    'schedule': ('run_date', 'day_of_week', 'day', 'hour', 'minute', 'second'),
    'request': ('req_url', 'req_method', 'req_body'),
    'timeout': ('timeout_sec',),
    'scope': ('scope_type', 'group_id', 'tag_names'),
    'status': ('status',),
}
TOKEN_KEYS = {'schema', 'actor', 'task', 'revision', 'editor', 'name', 'units'}
CONFLICT = '任务已被修改，本次未保存。请重新加载后确认。'


class TaskEditError(ValueError):
    pass


def _serializer():
    return URLSafeSerializer(current_app.secret_key, salt='cron-edit-baseline-v1')


def _digest(actor_id, task_id, unit, value):
    payload = json.dumps([actor_id, task_id, unit, value], ensure_ascii=False,
                         sort_keys=True, separators=(',', ':')).encode()
    return hmac.new(str(current_app.secret_key).encode(), b'cron-edit-v1\0' + payload,
                    hashlib.sha256).hexdigest()


def _actor(actor_id, lock=False):
    stmt = select(RbacUser).where(RbacUser.id == actor_id).execution_options(populate_existing=True)
    if lock:
        stmt = stmt.with_for_update()
    actor = db.session.scalar(stmt)
    if not actor or not actor.is_active:
        raise TaskEditError('当前登录账号已失效，请重新登录')
    links = select(UserGroup.group_id).where(UserGroup.user_id == actor_id).order_by(UserGroup.group_id)
    if lock:
        links = links.with_for_update()
    gids = list(db.session.scalars(links))
    return actor, {'role': actor.role, 'username': actor.username, 'groups': gids}


def task_edit_values(task, lock=False):
    groups = select(TaskGroup.group_id).where(TaskGroup.task_id == task.id)
    tags = select(TaskTag.tag_id, Tag.name, Tag.group_id).outerjoin(
        Tag, TaskTag.tag_id == Tag.id).where(TaskTag.task_id == task.id)
    if lock:
        groups, tags = groups.with_for_update(), tags.with_for_update()
    gids = list(db.session.scalars(groups))
    if task.scope_type == 'GROUP':
        if len(gids) != 1 or db.session.get(ResourceGroup, gids[0]) is None:
            raise TaskEditError('任务业务组关联异常，请先检查配置')
    elif task.scope_type != 'GLOBAL' or gids:
        raise TaskEditError('任务业务组关联异常，请先检查配置')
    gid = gids[0] if gids else None
    rows = db.session.execute(tags).all()
    if any(name is None or namespace != gid for _id, name, namespace in rows):
        raise TaskEditError('任务标签关联异常，请先检查配置')
    names = [name.strip().lower() for _id, name, _gid in rows]
    if any(not name for name in names) or len(names) != len(set(names)):
        raise TaskEditError('任务标签关联异常，请先检查配置')
    values = {field: getattr(task, field) or '' for unit in ('description', 'schedule', 'request')
              for field in UNITS[unit]}
    values.update(task_name=task.task_name, timeout_sec=task.timeout_sec, status=task.status,
                  scope_type=task.scope_type, group_id=gid, tag_names=sorted(names))
    return values


def _unit(value, name):
    return {field: value[field] for field in UNITS[name]}


def build_task_edit_snapshot(actor_id, task, *, return_values=False):
    actor, editor = _actor(actor_id)
    authorize(actor.role, 'cron:write', task, group_ids=editor['groups'], username=actor.username)
    values = task_edit_values(task)
    token = dict(schema=1, actor=actor_id, task=task.id, revision=task.edit_revision,
                 editor=editor, name=_digest(actor_id, task.id, 'name', task.task_name),
                 units={name: _digest(actor_id, task.id, name, _unit(values, name)) for name in UNITS})
    # SQLite 的驱动读事务未必提供跨 SELECT 的同一快照；不得签发混合版本。
    revision = db.session.scalar(select(CronInfos.edit_revision).where(CronInfos.id == task.id))
    if revision != token['revision']:
        raise TaskEditError('任务正在被修改，请重新加载页面')
    signed = _serializer().dumps(token)
    return (signed, values) if return_values else signed


def verify_task_edit_snapshot(token, actor_id, task_id):
    try:
        value = _serializer().loads(token)
    except (BadData, TypeError):
        raise TaskEditError('编辑基线已失效，请重新加载页面') from None
    if (not isinstance(value, dict) or set(value) != TOKEN_KEYS or type(value['schema']) is not int
            or value['schema'] != 1 or type(value['actor']) is not int or value['actor'] != actor_id
            or type(value['task']) is not int or value['task'] != task_id
            or type(value['revision']) is not int or value['revision'] < 0
            or not isinstance(value['units'], dict) or set(value['units']) != set(UNITS)
            or not isinstance(value['editor'], dict)
            or set(value['editor']) != {'role', 'username', 'groups'}
            or not isinstance(value['editor']['role'], str)
            or not isinstance(value['editor']['username'], str)
            or not isinstance(value['editor']['groups'], list)
            or any(type(gid) is not int or gid <= 0 for gid in value['editor']['groups'])
            or any(not isinstance(v, str) or len(v) != 64
                   or any(c not in '0123456789abcdef' for c in v)
                   for v in [value['name']] + list(value['units'].values()))):
        raise TaskEditError('编辑基线已失效，请重新加载页面')
    return value


def _result(outcome, msg, field=None, reload_required=False):
    return dict(outcome=outcome, msg=msg, field=field, reload_required=reload_required)


def save_task_edit(actor_id, task_id, token, raw, is_dev, config):
    """本服务拥有独立请求的保存事务；禁止嵌入未完成的其他写事务。"""
    if db.session.new or db.session.dirty or db.session.deleted:
        raise RuntimeError('task edit requires a clean request transaction')
    try:
        original = verify_task_edit_snapshot(token, actor_id, task_id)
    except TaskEditError as exc:
        db.session.rollback()
        return _result('failed', str(exc), reload_required=True)
    db.session.rollback()  # 只结束路由阶段的只读事务，不丢弃待写工作。
    for attempt in range(2):
        attempting_commit = False
        try:
            actor, editor = _actor(actor_id, lock=True)
            task = db.session.scalar(select(CronInfos).where(CronInfos.id == task_id)
                                     .with_for_update().execution_options(populate_existing=True))
            if not task or task.status == -1:
                raise TaskEditError('任务不存在或已下线，不能编辑')
            authorize(actor.role, 'cron:write', task, group_ids=editor['groups'], username=actor.username)
            if editor != original['editor']:
                raise TaskEditError('当前可编辑范围已变化，请重新加载页面')
            current = task_edit_values(task, lock=True)
            err, requested, field = normalize_cron_form(raw, is_dev, mode='edit')
            if err:
                db.session.rollback()
                return _result('failed', err, field)
            if not hmac.compare_digest(original['name'], _digest(actor_id, task_id, 'name', requested['task_name'])):
                raise TaskEditError('任务名称不可修改')
            if 'scope_type' not in raw or 'tag_names' not in raw:
                raise TaskEditError('编辑字段不完整，请重新加载页面')
            scope = (raw['scope_type'] or '').upper()
            try:
                gid = int(raw.get('group_id')) if scope == 'GROUP' else None
            except (ValueError, TypeError):
                raise TaskEditError('业务组无效') from None
            if scope not in ('GROUP', 'GLOBAL') or (scope == 'GROUP' and not gid):
                raise TaskEditError('业务组无效')
            requested.update(scope_type=scope, group_id=gid,
                             tag_names=sorted({v.strip().lower() for v in raw['tag_names'] if v.strip()}),
                             status=0)  # 未提交恢复意图时，状态单元不参与写入。
            resume = str(raw.get('resume_after_save', '')).strip() in ('1', 'on', 'true', 'True')
            intended = []
            effective = []
            candidate = dict(current)
            for name in UNITS:
                if name == 'status':
                    if not resume:
                        continue
                    requested['status'] = 1
                target = _unit(requested, name)
                old_hash = original['units'][name]
                if hmac.compare_digest(old_hash, _digest(actor_id, task_id, name, target)):
                    continue
                intended.append(name)
                if target == _unit(current, name):
                    continue
                if not hmac.compare_digest(old_hash, _digest(actor_id, task_id, name, _unit(current, name))):
                    db.session.rollback()
                    return _result('conflict', CONFLICT)
                candidate.update(target)
                effective.append(name)
            if not effective:
                db.session.rollback()
                return _result('already_applied' if intended else 'no_change',
                               '目标值已存在，无需重复保存' if intended else '未检测到变更，无需保存')
            if 'scope' in effective:
                from app.rbac.policy import user_bypasses_scope
                bypass = user_bypasses_scope(actor.role, username=actor.username, group_ids=editor['groups'])
                if (not bypass and (candidate['scope_type'] != 'GROUP'
                                    or candidate['group_id'] not in editor['groups'])):
                    raise TaskEditError('只能将任务放在当前授权业务组内')
                if candidate['group_id'] is not None and db.session.get(ResourceGroup, candidate['group_id']) is None:
                    raise TaskEditError('目标业务组不存在')
            check = dict(candidate, ds_ms='1' if candidate['run_date'] else '2',
                         timeout_sec='' if candidate['timeout_sec'] is None else str(candidate['timeout_sec']))
            err, _normalized, field = validate_cron_form(check, is_dev, config, mode='edit', cron_id=task_id)
            if err:
                db.session.rollback()
                return _result('failed', err, field)
            before = dict(current)
            for name in effective:
                for field in UNITS[name]:
                    if field not in ('group_id', 'tag_names'):
                        setattr(task, field, candidate[field])
            from app.services.cron_service import stamp_last_operator
            from datas.utils.times import utc_now_hms
            task.updated_at = utc_now_hms()
            stamp_last_operator(task)
            task.edit_revision += 1
            db.session.flush()  # ORM WHERE id AND old edit_revision，冲突先于关系 DML。
            applied_revision = task.edit_revision
            if 'scope' in effective:
                db.session.execute(TaskGroup.__table__.delete().where(TaskGroup.task_id == task_id))
                if candidate['group_id'] is not None:
                    db.session.add(TaskGroup(task_id=task_id, group_id=candidate['group_id']))
                from app.services.tag_service import sync_task_tags
                sync_task_tags(task_id, candidate['tag_names'], created_by=actor.username,
                               group_id=candidate['group_id'], bump_revision=False)
            attempting_commit = True
            db.session.commit()
        except StaleDataError:
            db.session.rollback()
            if attempt == 0:
                continue
            return _result('conflict', CONFLICT)
        except (TaskEditError, AuthorizationError) as exc:
            db.session.rollback()
            return _result('failed', str(exc))
        except Exception:
            current_app.logger.exception('task edit save failed task_id=%s', task_id)
            db.session.rollback()
            return _result('commit_unknown' if attempting_commit else 'failed',
                           '保存结果待核实，请勿重复提交' if attempting_commit else '保存失败，请稍后重试')
        # 外部副作用发生在提交后，保持既有失败边界，不冒称跨库原子。
        if 'schedule' in effective or 'status' in effective:
            try:
                apply_edit(task_id, applied_revision, candidate)
            except EditWriteError as exc:
                return _result('saved_scheduler_error', str(exc))
        from app.services.operation_log_service import record_operation
        # 原值中可能有凭据；只记录安全字段及敏感字段已变化的事实。
        changes = {field: {'old': before[field], 'new': candidate[field]}
                   for name in effective for field in UNITS[name]
                   if field not in ('req_url', 'req_body') and before[field] != candidate[field]}
        for field in ('req_url', 'req_body'):
            if before[field] != candidate[field]:
                changes[field] = {'changed': True}
        record_operation(action='update_cron', target_id=task_id, task_name=candidate['task_name'], detail=changes)
        return _result('updated', '修改成功！')
