# -*- coding:utf-8 -*-
"""JobLog 列表查询。"""
from sqlalchemy import desc, func, select

from datas.model.cron_infos import CronInfos
from datas.model.job_log import JobLog
from datas.model.job_log_items import JobLogItems

from app.repositories.base import BaseRepository
from app.services.job_log_filter import job_log_outcome_clause


class JobLogRepository(BaseRepository):
    def paginate_for_cron(self, page_query, cron_info_id, outcome='all', content_keyword=None):
        """单任务执行记录；cron 不存在时用 cron_info_id=-1 得空页。"""
        outcome_clause = job_log_outcome_clause(outcome)
        stmt = select(JobLog).where(JobLog.cron_info_id == cron_info_id)
        if outcome_clause is not None:
            stmt = stmt.where(outcome_clause)
        if content_keyword:
            stmt = stmt.where(JobLog.content.like('%{}%'.format(content_keyword)))
        stmt = stmt.order_by(desc(JobLog.id))
        return self.paginate(stmt, page_query)

    def paginate_empty(self, page_query):
        return self.paginate_for_cron(page_query, -1, outcome='all')

    def paginate_all(self, page_query, filters=None):
        """全局执行记录联表；filters 含 Scope / outcome / 时间等。"""
        filters = list(filters or [])
        stmt = (
            select(JobLog, CronInfos)
            .join(CronInfos, CronInfos.id == JobLog.cron_info_id)
        )
        if filters:
            stmt = stmt.where(*filters)
        stmt = stmt.order_by(desc(JobLog.id))
        count_stmt = (
            select(func.count())
            .select_from(JobLog)
            .join(CronInfos, CronInfos.id == JobLog.cron_info_id)
        )
        if filters:
            count_stmt = count_stmt.where(*filters)
        return self.paginate(
            stmt, page_query, scalars=False, count_stmt=count_stmt,
        )

    def get_by_trace_id(self, trace_id):
        return self.scalars_first(
            select(JobLog).where(JobLog.trace_id == trace_id)
        )

    def items_for_trace_id(self, trace_id):
        if not trace_id:
            return []
        return self.scalars_all(
            select(JobLogItems).where(JobLogItems.trace_id == trace_id)
        )
