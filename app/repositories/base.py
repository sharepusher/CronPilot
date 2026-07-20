# -*- coding:utf-8 -*-
"""薄 BaseRepository：会话原语 + 分页委托；业务 SQL 仅在具体 Repository。"""
from __future__ import annotations

from app.services.pagination import paginate_select


class BaseRepository(object):
    """默认不 commit；事务边界由 Service / 调用方控制。"""

    def __init__(self, session):
        self.session = session

    def get(self, model, pk):
        return self.session.get(model, pk)

    def scalar(self, stmt):
        return self.session.scalar(stmt)

    def scalars_all(self, stmt):
        return list(self.session.scalars(stmt).all())

    def scalars_first(self, stmt):
        return self.session.scalars(stmt).first()

    def execute_all(self, stmt):
        return list(self.session.execute(stmt).all())

    def paginate(self, stmt, page_query, scalars=True, count_stmt=None):
        return paginate_select(
            self.session,
            stmt,
            page_query,
            scalars=scalars,
            count_stmt=count_stmt,
        )

    def add(self, entity):
        self.session.add(entity)
        return entity

    def flush(self):
        self.session.flush()

    def commit(self):
        self.session.commit()

    def rollback(self):
        self.session.rollback()
