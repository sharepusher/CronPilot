# -*- coding:utf-8 -*-
"""Query Contract：管理端列表分页入参/出参 DTO（与 FSA Query.paginate 解耦）。

模板契约见 app/templates/admin_page.html：
items / page / pages / has_prev / has_next / prev_num / next_num / iter_pages()
"""
from __future__ import division

import math

from sqlalchemy import func, select


class PageQuery(object):
    """分页入参。"""

    __slots__ = ('page', 'per_page')

    def __init__(self, page=1, per_page=20):
        self.page = page
        self.per_page = per_page

    @classmethod
    def from_args(cls, mapping, default_per_page=20):
        raw = mapping.get('page') if mapping is not None else None
        try:
            page = int(raw or 1)
        except (TypeError, ValueError):
            page = 1
        if page < 1:
            page = 1
        try:
            per_page = int(
                (mapping.get('per_page') if mapping is not None else None)
                or default_per_page
            )
        except (TypeError, ValueError):
            per_page = default_per_page
        if per_page < 1:
            per_page = default_per_page
        return cls(page=page, per_page=per_page)


class PaginationResult(object):
    """分页出参；兼容 admin_page.html 宏（对齐 FSA 2.x Pagination 语义）。"""

    __slots__ = (
        'items', 'page', 'per_page', 'total', 'pages',
        'has_prev', 'has_next', 'prev_num', 'next_num',
    )

    def __init__(self, items, page, per_page, total):
        self.items = items
        self.page = page
        self.per_page = per_page
        self.total = total
        if per_page == 0 or total == 0:
            self.pages = 0
        else:
            self.pages = int(math.ceil(total / float(per_page)))
        self.has_prev = page > 1
        self.prev_num = (page - 1) if self.has_prev else None
        self.has_next = self.pages > 0 and page < self.pages
        self.next_num = (page + 1) if self.has_next else None

    def iter_pages(self, left_edge=2, left_current=2, right_current=5, right_edge=2):
        """与 Flask-SQLAlchemy 2.x Pagination.iter_pages 同窗口规则。"""
        last = 0
        for num in range(1, self.pages + 1):
            if (
                num <= left_edge
                or (
                    num > self.page - left_current - 1
                    and num < self.page + right_current
                )
                or num > self.pages - right_edge
            ):
                if last + 1 != num:
                    yield None
                yield num
                last = num


def paginate_select(
    session,
    stmt,
    page_query,
    scalars=True,
    count_stmt=None,
):
    """对 Select 做 count + limit/offset，返回 PaginationResult。

    scalars=True  → items 为实体列表（单列/单实体）
    scalars=False → items 为 Row 列表（多实体联表，如 JobLog+CronInfos）
    """
    if not isinstance(page_query, PageQuery):
        page_query = PageQuery.from_args({'page': page_query})

    page = page_query.page
    per_page = page_query.per_page

    if count_stmt is None:
        # 去掉 ORDER BY，避免部分方言 count 子查询报错
        count_inner = stmt.order_by(None)
        count_stmt = select(func.count()).select_from(count_inner.subquery())

    total = session.scalar(count_stmt)
    if total is None:
        total = 0
    else:
        total = int(total)

    offset = (page - 1) * per_page
    page_stmt = stmt.limit(per_page).offset(offset)
    if scalars:
        items = session.scalars(page_stmt).all()
    else:
        items = session.execute(page_stmt).all()

    return PaginationResult(
        items=items,
        page=page,
        per_page=per_page,
        total=total,
    )
