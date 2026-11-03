"""关系-only 修改也必须在同一事务中保护父任务版本。"""
from sqlalchemy import select

from app import db
from datas.model.cron_infos import CronInfos


def touch_task_revisions(task_ids):
    ids = sorted(set(task_ids))
    if not ids:
        return
    tasks = db.session.scalars(select(CronInfos).where(
        CronInfos.id.in_(ids)
    ).order_by(CronInfos.id).with_for_update()).all()
    for task in tasks:
        task.edit_revision += 1
    db.session.flush()
