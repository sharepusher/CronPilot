# -*- coding:utf-8 -*-
from sqlalchemy import desc, select

from datas.model.rbac_audit_log import RbacAuditLog

from app.repositories.base import BaseRepository


class RbacAuditLogRepository(BaseRepository):
    def paginate_all(self, page_query):
        stmt = select(RbacAuditLog).order_by(desc(RbacAuditLog.id))
        return self.paginate(stmt, page_query)
