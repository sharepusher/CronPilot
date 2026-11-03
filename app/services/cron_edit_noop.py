"""任务编辑只读比较。禁止在这里赋值 ORM、创建标签、提交或操作调度器。"""
from sqlalchemy import select

from app import db
from datas.model.resource_group import ResourceGroup
from datas.model.tag import Tag
from datas.model.task_group import TaskGroup
from datas.model.task_tag import TaskTag

TEXT_FIELDS = (
    'task_name', 'task_keyword', 'run_date', 'day_of_week', 'day', 'hour',
    'minute', 'second', 'req_url', 'req_method', 'req_body',
)


def cron_edit_is_noop(cif, normalized, resume_after_save=False):
    """按入口传入字段判断目标是否已存在；异常关联拒绝而非顺手清理。"""
    if cif.status == -1:
        raise ValueError('任务已下线，不能编辑')
    # 当前比较不应把调用者的待写对象提前 flush。
    with db.session.no_autoflush:
        gids = list(db.session.scalars(select(TaskGroup.group_id).where(TaskGroup.task_id == cif.id)))
        if cif.scope_type == 'GLOBAL':
            valid = not gids
        elif cif.scope_type == 'GROUP':
            valid = len(gids) == 1 and db.session.get(ResourceGroup, gids[0]) is not None
        else:
            valid = False
        if not valid:
            raise ValueError('任务业务组关联异常，请先检查配置')
        rows = db.session.execute(
            select(TaskTag.tag_id, Tag.name, Tag.group_id).outerjoin(
                Tag, TaskTag.tag_id == Tag.id
            ).where(TaskTag.task_id == cif.id)
        ).all()
        namespace = gids[0] if gids else None
        names = []
        for tag_id, name, group_id in rows:
            if name is None or not name.strip() or group_id != namespace:
                raise ValueError('任务标签关联异常，请先检查配置')
            names.append(name.strip().lower())
        if len(set(names)) != len(names):
            raise ValueError('任务标签关联异常，请先检查配置')
        for field in TEXT_FIELDS:
            # 与实际 apply 的缺省一致；不擅自规范化已存非空文本。
            default = 'GET' if field == 'req_method' else ''
            if (getattr(cif, field) or '') != normalized.get(field, default):
                return False
        if cif.timeout_sec != normalized.get('timeout_sec'):
            return False
        if resume_after_save and cif.status == 0:
            return False
        if 'scope_type' in normalized or normalized.get('group_id') is not None:
            scope = (normalized['scope_type'] or 'GLOBAL') if 'scope_type' in normalized else cif.scope_type
            raw_gid = normalized.get('group_id')
            try:
                desired_gids = [int(raw_gid)] if raw_gid else []
            except (TypeError, ValueError):
                raise ValueError('业务组无效')
            if scope != cif.scope_type or desired_gids != gids:
                return False
        if 'tag_names' in normalized:
            desired_names = {name.strip().lower() for name in normalized['tag_names'] if name.strip()}
            if desired_names != set(names):
                return False
        return True
