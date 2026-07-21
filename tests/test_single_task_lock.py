# -*- coding: utf-8 -*-
"""OPT-P0-09: Redis task lock acquire/release (atomic SET NX EX + token Lua)."""
import os
import sys
import unittest
from unittest import mock

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from app.common.functions import acquire_task_lock, release_task_lock, single_task


class _FakeRedis(object):
    """Minimal in-memory Redis for SET NX EX + eval compare-and-del."""

    def __init__(self):
        self.store = {}

    def set(self, name, value, nx=False, ex=None):
        if nx and name in self.store:
            return None
        self.store[name] = value
        return True

    def get(self, name):
        return self.store.get(name)

    def eval(self, script, numkeys, *args):
        key = args[0]
        token = args[1]
        if self.store.get(key) == token:
            del self.store[key]
            return 1
        return 0


class TestAcquireReleaseLock(unittest.TestCase):
    def test_second_acquire_fails(self):
        r = _FakeRedis()
        t1 = acquire_task_lock(r, 'task:cron_do:1')
        self.assertIsNotNone(t1)
        t2 = acquire_task_lock(r, 'task:cron_do:1')
        self.assertIsNone(t2)

    def test_wrong_token_does_not_release(self):
        r = _FakeRedis()
        t1 = acquire_task_lock(r, 'task:cron_do:1')
        self.assertEqual(release_task_lock(r, 'task:cron_do:1', 'other-token'), 0)
        self.assertEqual(r.get('task:cron_do:1'), t1)
        self.assertEqual(release_task_lock(r, 'task:cron_do:1', t1), 1)
        self.assertIsNone(r.get('task:cron_do:1'))

    def test_after_release_another_can_acquire(self):
        r = _FakeRedis()
        t1 = acquire_task_lock(r, 'task:cron_do:1')
        release_task_lock(r, 'task:cron_do:1', t1)
        t2 = acquire_task_lock(r, 'task:cron_do:1')
        self.assertIsNotNone(t2)
        self.assertNotEqual(t1, t2)


class TestSingleTaskDecorator(unittest.TestCase):
    def test_is_single_skips_redis(self):
        calls = []

        @single_task()
        def sample(cron_id):
            calls.append(cron_id)
            return 'ok'

        with mock.patch('app.common.functions.configs', return_value={'is_single': '1'}):
            with mock.patch('app.common.functions.redis.Redis') as redis_cls:
                self.assertEqual(sample(42), 'ok')
                redis_cls.assert_not_called()
        self.assertEqual(calls, [42])

    def test_cluster_skips_when_lock_held(self):
        @single_task()
        def sample(cron_id):
            return 'ran'

        fake = _FakeRedis()
        acquire_task_lock(fake, 'task:sample:7')

        cfg = {
            'is_single': '0',
            'redis_host': '127.0.0.1',
            'redis_port': 6379,
            'redis_db': 0,
            'redis_pwd': '',
        }
        with mock.patch('app.common.functions.configs', return_value=cfg):
            with mock.patch('app.common.functions.redis.ConnectionPool'):
                with mock.patch('app.common.functions.redis.Redis', return_value=fake):
                    self.assertIsNone(sample(7))


if __name__ == '__main__':
    unittest.main()
