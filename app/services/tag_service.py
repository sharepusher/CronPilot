# -*- coding:utf-8 -*-
"""标签服务（OPT-P1-11）。

用户自由输入标签 → 自动去重入库 → 后续可自动补全。
管理员可重命名、删除。
"""
from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError

from app import db
from datas.model.tag import Tag
from datas.model.task_tag import TaskTag
from datas.utils.times import get_now_time


def _build_tag_query(name, group_id):
    """构建按 name+group_id 查找 Tag 的查询（内部复用）。"""
    q = select(Tag).where(func.lower(Tag.name) == name.lower())
    if group_id is not None:
        q = q.where(Tag.group_id == int(group_id))
    else:
        q = q.where(Tag.group_id.is_(None))
    return q


def get_or_create_tag(name, created_by='', group_id=None):
    """按名称+group_id 查找或新建标签，返回 Tag 对象（不 commit）。

    group_id: 标签所属业务组 ID；None 表示全局标签（GLOBAL 任务）。
    同名标签在不同 group_id 下独立存在。

    并发安全：使用 SAVEPOINT 包裹 INSERT，若唯一约束冲突
    则回滚 SAVEPOINT 并重新查询已有记录，不影响外层事务。
    """
    name = (name or '').strip()
    if not name:
        return None
    q = _build_tag_query(name, group_id)
    tag = db.session.scalars(q).first()
    if tag:
        return tag
    now = get_now_time()
    tag = Tag(name=name, group_id=group_id, created_by=created_by,
              create_time=now, update_time=now)
    try:
        with db.session.begin_nested():
            db.session.add(tag)
    except IntegrityError:
        # 并发插入导致唯一约束冲突 → SAVEPOINT 已自动回滚
        tag = db.session.scalars(_build_tag_query(name, group_id)).first()
    return tag


def sync_task_tags(task_id, tag_names, created_by='', group_id=None):
    """同步任务的标签列表：删除旧关联、创建缺失标签、写入新关联。

    tag_names: 标签名列表（字符串）。
    group_id: 任务所属业务组 ID；None 表示 GLOBAL 任务。
    """
    db.session.execute(
        TaskTag.__table__.delete().where(TaskTag.task_id == task_id)
    )
    seen = set()
    for name in (tag_names or []):
        name = (name or '').strip()
        if not name or name.lower() in seen:
            continue
        seen.add(name.lower())
        tag = get_or_create_tag(name, created_by=created_by, group_id=group_id)
        if tag:
            db.session.add(TaskTag(task_id=task_id, tag_id=tag.id))


def get_task_tag_names(task_id):
    """返回任务关联的标签名称列表。"""
    rows = db.session.execute(
        select(Tag.name).join(TaskTag, Tag.id == TaskTag.tag_id).where(
            TaskTag.task_id == int(task_id)
        ).order_by(Tag.name)
    ).scalars().all()
    return list(rows)


def build_task_tag_map(task_ids):
    """批量返回 {task_id: [tag_name, ...]} 映射。"""
    if not task_ids:
        return {}
    rows = db.session.execute(
        select(TaskTag.task_id, Tag.name).join(
            Tag, Tag.id == TaskTag.tag_id
        ).where(TaskTag.task_id.in_(task_ids)).order_by(Tag.name)
    ).all()
    result = {}
    for tid, name in rows:
        result.setdefault(tid, []).append(name)
    return result


def suggest_tags(prefix='', limit=20, group_id=None):
    """标签自动补全：按前缀模糊匹配，限定业务组范围。

    group_id: 业务组 ID（仅返回该组标签）；None 返回全局标签。
              传 '__ALL__' 时返回所有标签（管理员场景）。
    """
    q = select(Tag.name, Tag.description).order_by(Tag.name).limit(limit)
    if prefix:
        q = q.where(Tag.name.ilike('%{}%'.format(prefix)))
    if group_id != '__ALL__':
        if group_id is not None:
            q = q.where(Tag.group_id == int(group_id))
        else:
            q = q.where(Tag.group_id.is_(None))
    rows = db.session.execute(q).all()
    return [{'name': r[0], 'description': r[1] or ''} for r in rows]


def all_tags(group_id=None):
    """返回标签列表 [{id, name, group_id, created_by, create_time}, ...]。

    group_id: 过滤业务组；None 返回全局标签；'__ALL__' 返回所有。
    """
    q = select(Tag).order_by(Tag.name)
    if group_id != '__ALL__':
        if group_id is not None:
            q = q.where(Tag.group_id == int(group_id))
        else:
            q = q.where(Tag.group_id.is_(None))
    rows = db.session.scalars(q).all()
    return [{
        'id': t.id,
        'name': t.name,
        'group_id': t.group_id,
        'created_by': t.created_by,
        'create_time': t.create_time,
    } for t in rows]


def all_tags_with_count(group_id=None):
    """返回标签及其关联任务数。

    group_id: 过滤业务组；None 返回全局标签；'__ALL__' 返回所有。
    """
    q = (
        select(Tag, func.count(TaskTag.task_id).label('task_count'))
        .outerjoin(TaskTag, Tag.id == TaskTag.tag_id)
        .group_by(Tag.id)
        .order_by(Tag.name)
    )
    if group_id != '__ALL__':
        if group_id is not None:
            q = q.where(Tag.group_id == int(group_id))
        else:
            q = q.where(Tag.group_id.is_(None))
    rows = db.session.execute(q).all()
    return [{
        'id': tag.id,
        'name': tag.name,
        'group_id': tag.group_id,
        'description': tag.description,
        'created_by': tag.created_by,
        'create_time': tag.create_time,
        'task_count': cnt,
    } for tag, cnt in rows]


def create_tag(name, group_id=None, description='', created_by=''):
    """管理端新建标签（含同组唯一性检查）。返回 (ok, msg)。"""
    name = (name or '').strip()
    if not name:
        return False, '标签名称不能为空'
    if len(name) > 64:
        return False, '标签名称最长 64 字符'
    description = (description or '').strip()
    if len(description) > 255:
        return False, '标签说明最长 255 字符'
    q = select(Tag).where(func.lower(Tag.name) == name.lower())
    if group_id is not None:
        q = q.where(Tag.group_id == int(group_id))
    else:
        q = q.where(Tag.group_id.is_(None))
    if db.session.scalars(q).first():
        return False, '同组内已存在同名标签「{}」'.format(name)
    now = get_now_time()
    tag = Tag(name=name, group_id=group_id, description=description,
              created_by=created_by, create_time=now, update_time=now)
    db.session.add(tag)
    db.session.commit()
    return True, '创建成功'


def update_tag(tag_id, new_name=None, description=None):
    """编辑标签（名称 + 说明），同组内唯一性检查。返回 (ok, msg)。"""
    tag = db.session.get(Tag, int(tag_id))
    if not tag:
        return False, '标签不存在'
    changed = False
    if new_name is not None:
        new_name = new_name.strip()
        if not new_name:
            return False, '标签名称不能为空'
        if len(new_name) > 64:
            return False, '标签名称最长 64 字符'
        if new_name.lower() != tag.name.lower():
            q = select(Tag).where(
                func.lower(Tag.name) == new_name.lower(), Tag.id != tag.id
            )
            if tag.group_id is not None:
                q = q.where(Tag.group_id == tag.group_id)
            else:
                q = q.where(Tag.group_id.is_(None))
            if db.session.scalars(q).first():
                return False, '同组内已存在同名标签「{}」'.format(new_name)
        tag.name = new_name
        changed = True
    if description is not None:
        description = description.strip()
        if len(description) > 255:
            return False, '标签说明最长 255 字符'
        tag.description = description
        changed = True
    if changed:
        tag.update_time = get_now_time()
        db.session.commit()
    return True, '保存成功'


def rename_tag(tag_id, new_name):
    """兼容旧调用：重命名标签。"""
    return update_tag(tag_id, new_name=new_name)


def delete_tag(tag_id, force=False):
    """删除标签。

    返回 (ok, msg, extra)：
    - 有关联任务且 force=False → (False, 提示, {'task_count', 'tasks', 'need_confirm'})
    - force=True 或无关联 → 执行删除，(True, 成功信息, None)
    """
    from datas.model.cron_infos import CronInfos
    tag = db.session.get(Tag, int(tag_id))
    if not tag:
        return False, '标签不存在', None
    name = tag.name
    # 查询关联任务（名称 + ID，最多展示 20 条）
    rows = db.session.execute(
        select(CronInfos.id, CronInfos.task_name).join(
            TaskTag, CronInfos.id == TaskTag.task_id
        ).where(TaskTag.tag_id == tag.id).limit(20)
    ).all()
    count = db.session.scalar(
        select(func.count()).where(TaskTag.tag_id == tag.id)
    )
    if count > 0 and not force:
        tasks = [{'id': r[0], 'name': r[1]} for r in rows]
        return False, '标签「{}」仍有 {} 个任务在使用'.format(name, count), \
            {'task_count': count, 'tasks': tasks, 'need_confirm': True}
    db.session.execute(TaskTag.__table__.delete().where(TaskTag.tag_id == tag.id))
    db.session.delete(tag)
    db.session.commit()
    return True, '已删除标签「{}」（清除 {} 个任务关联）'.format(name, count), None


def get_tag_tasks(tag_id, limit=100):
    """查询标签关联的任务列表（ID + 名称 + 状态）。"""
    from datas.model.cron_infos import CronInfos
    tag = db.session.get(Tag, int(tag_id))
    if not tag:
        return None, []
    rows = db.session.execute(
        select(CronInfos.id, CronInfos.task_name, CronInfos.status).join(
            TaskTag, CronInfos.id == TaskTag.task_id
        ).where(TaskTag.tag_id == tag.id).order_by(CronInfos.id.desc()).limit(limit)
    ).all()
    tasks = [{'id': r[0], 'name': r[1], 'status': r[2]} for r in rows]
    return tag.name, tasks
