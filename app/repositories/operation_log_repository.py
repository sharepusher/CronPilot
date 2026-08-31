# -*- coding:utf-8 -*-
"""OperationLog 列表查询。"""
from sqlalchemy import and_, desc, or_, select

from app.repositories.base import BaseRepository
from datas.model.cron_infos import CronInfos
from datas.model.operation_log import OperationLog


class OperationLogRepository(BaseRepository):
    def paginate_list(
        self,
        page_query,
        *,
        task_name=None,
        operator_name=None,
        keyword=None,
        action=None,
        beg_time=None,
        end_time=None,
        scope_clause=None,
        ui_scope_clause=None,
        bypass_scope=False,
    ):
        filters = []
        if keyword:
            filters.append(or_(
                OperationLog.task_name.like('%{}%'.format(keyword)),
                OperationLog.operator_name.like('%{}%'.format(keyword)),
            ))
        else:
            if task_name:
                filters.append(
                    OperationLog.task_name.like('%{}%'.format(task_name))
                )
            if operator_name:
                filters.append(
                    OperationLog.operator_name.like('%{}%'.format(operator_name))
                )
        if action:
            filters.append(OperationLog.action == action)
        if beg_time or end_time:
            from datas.utils.times import str_to_hms
        if beg_time:
            filters.append(OperationLog.create_time >= str_to_hms(beg_time + ' 00:00:00'))
        if end_time:
            filters.append(OperationLog.create_time <= str_to_hms(end_time + ' 23:59:59'))

        if not bypass_scope:
            visible_ids = select(CronInfos.id)
            if scope_clause is not None:
                visible_ids = visible_ids.where(scope_clause)
            filters.append(
                and_(
                    OperationLog.target_type == 'cron',
                    OperationLog.target_id.in_(visible_ids),
                )
            )
        elif ui_scope_clause is not None:
            cron_ids = select(CronInfos.id).where(ui_scope_clause)
            filters.append(
                and_(
                    OperationLog.target_type == 'cron',
                    OperationLog.target_id.in_(cron_ids),
                )
            )

        stmt = select(OperationLog)
        if filters:
            stmt = stmt.where(*filters)
        stmt = stmt.order_by(desc(OperationLog.id))
        return self.paginate(stmt, page_query)
