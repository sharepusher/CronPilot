# -*- coding:utf-8 -*-
from sqlalchemy import desc, select

from datas.model.rbac_user import RbacUser

from app.repositories.base import BaseRepository


class RbacUserRepository(BaseRepository):
    def paginate_all(self, page_query):
        stmt = select(RbacUser).order_by(desc(RbacUser.id))
        return self.paginate(stmt, page_query)
