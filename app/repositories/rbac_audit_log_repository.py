# -*- coding:utf-8 -*-
from sqlalchemy import desc, or_, select

from datas.model.rbac_audit_log import RbacAuditLog

from app.repositories.base import BaseRepository


class RbacAuditLogRepository(BaseRepository):
    def paginate_all(self, page_query):
        stmt = select(RbacAuditLog).order_by(desc(RbacAuditLog.id))
        return self.paginate(stmt, page_query)

    def paginate_by_scope(self, page_query, viewer_group_ids):
        """按组管理员：仅展示 actor_group_ids 与 viewer_group_ids 有交集的审计记录。

        存储格式为逗号包围（如 ',1,3,'），使用 LIKE '%,1,%' 精确匹配。
        """
        if not viewer_group_ids:
            stmt = (
                select(RbacAuditLog)
                .where(RbacAuditLog.id < 0)
                .order_by(desc(RbacAuditLog.id))
            )
            return self.paginate(stmt, page_query)

        filters = [
            RbacAuditLog.actor_group_ids.like('%,{},%'.format(int(gid)))
            for gid in viewer_group_ids
        ]
        stmt = (
            select(RbacAuditLog)
            .where(or_(*filters))
            .order_by(desc(RbacAuditLog.id))
        )
        return self.paginate(stmt, page_query)
