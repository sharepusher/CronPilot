# -*- coding:utf-8 -*-
"""Phase A0：Query Contract（PageQuery / PaginationResult / paginate_select）。"""
import os
import sys
import tempfile
import unittest

from sqlalchemy import Column, Integer, String, create_engine, select
from sqlalchemy.orm import declarative_base, sessionmaker

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from app.services.pagination import (  # noqa: E402
    PageQuery,
    PaginationResult,
    paginate_select,
)

Base = declarative_base()


class _Item(Base):
    __tablename__ = 'pagination_items'
    id = Column(Integer, primary_key=True)
    name = Column(String(32))


class TestPageQuery(unittest.TestCase):
    def test_from_args_defaults(self):
        pq = PageQuery.from_args({})
        self.assertEqual(pq.page, 1)
        self.assertEqual(pq.per_page, 20)

    def test_from_args_clamps_page(self):
        self.assertEqual(PageQuery.from_args({'page': '0'}).page, 1)
        self.assertEqual(PageQuery.from_args({'page': '-3'}).page, 1)
        self.assertEqual(PageQuery.from_args({'page': '2'}).page, 2)

    def test_from_args_bad_page(self):
        self.assertEqual(PageQuery.from_args({'page': 'x'}).page, 1)


class TestPaginationResult(unittest.TestCase):
    def test_empty_total(self):
        p = PaginationResult(items=[], page=1, per_page=20, total=0)
        self.assertEqual(p.pages, 0)
        self.assertFalse(p.has_prev)
        self.assertFalse(p.has_next)
        self.assertIsNone(p.prev_num)
        self.assertIsNone(p.next_num)
        self.assertEqual(list(p.iter_pages()), [])

    def test_single_page(self):
        p = PaginationResult(items=[1, 2], page=1, per_page=20, total=2)
        self.assertEqual(p.pages, 1)
        self.assertFalse(p.has_prev)
        self.assertFalse(p.has_next)

    def test_multi_page_middle(self):
        p = PaginationResult(items=[], page=3, per_page=10, total=100)
        self.assertEqual(p.pages, 10)
        self.assertTrue(p.has_prev)
        self.assertTrue(p.has_next)
        self.assertEqual(p.prev_num, 2)
        self.assertEqual(p.next_num, 4)

    def test_iter_pages_first(self):
        p = PaginationResult(items=[], page=1, per_page=10, total=100)
        # pages=10; left_edge + window + right_edge
        pages = list(p.iter_pages())
        self.assertEqual(pages[0], 1)
        self.assertIn(10, pages)

    def test_iter_pages_gap_none(self):
        p = PaginationResult(items=[], page=1, per_page=1, total=20)
        pages = list(p.iter_pages())
        self.assertIn(None, pages)


class TestPaginateSelect(unittest.TestCase):
    def setUp(self):
        self._fd, self._path = tempfile.mkstemp(suffix='.db')
        os.close(self._fd)
        self.engine = create_engine('sqlite:///' + self._path)
        Base.metadata.create_all(self.engine)
        Session = sessionmaker(bind=self.engine)
        self.session = Session()
        for i in range(1, 26):
            self.session.add(_Item(id=i, name='n%d' % i))
        self.session.commit()

    def tearDown(self):
        self.session.close()
        self.engine.dispose()
        try:
            os.unlink(self._path)
        except OSError:
            pass

    def test_first_page(self):
        pq = PageQuery(page=1, per_page=10)
        result = paginate_select(
            self.session,
            select(_Item).order_by(_Item.id),
            pq,
        )
        self.assertEqual(result.total, 25)
        self.assertEqual(result.pages, 3)
        self.assertEqual(len(result.items), 10)
        self.assertEqual(result.items[0].id, 1)
        self.assertFalse(result.has_prev)
        self.assertTrue(result.has_next)

    def test_last_page(self):
        pq = PageQuery(page=3, per_page=10)
        result = paginate_select(
            self.session,
            select(_Item).order_by(_Item.id),
            pq,
        )
        self.assertEqual(len(result.items), 5)
        self.assertEqual(result.items[-1].id, 25)
        self.assertTrue(result.has_prev)
        self.assertFalse(result.has_next)

    def test_page_clamp_via_from_args(self):
        pq = PageQuery.from_args({'page': '0'})
        result = paginate_select(
            self.session,
            select(_Item).order_by(_Item.id),
            pq,
            )
        self.assertEqual(result.page, 1)
        self.assertEqual(len(result.items), 20)

    def test_empty_table(self):
        self.session.query(_Item).delete()
        self.session.commit()
        result = paginate_select(
            self.session,
            select(_Item),
            PageQuery(1, 20),
        )
        self.assertEqual(result.total, 0)
        self.assertEqual(result.pages, 0)
        self.assertEqual(result.items, [])

    def test_scalars_false_rows(self):
        result = paginate_select(
            self.session,
            select(_Item.id, _Item.name).order_by(_Item.id),
            PageQuery(1, 5),
            scalars=False,
        )
        self.assertEqual(len(result.items), 5)
        row0 = result.items[0]
        self.assertEqual(row0[0], 1)
        self.assertEqual(row0[1], 'n1')


if __name__ == '__main__':
    unittest.main()
