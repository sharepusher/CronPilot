# -*- coding:utf-8 -*-
"""OPT-P0-13: 登录防暴破限流器单元测试。"""
import os
import sys
import time
import unittest
from unittest.mock import patch

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from app.rbac.login_limiter import (
    LoginLimiter,
    MAX_FAILURES_PER_IP,
    MAX_FAILURES_PER_USER,
    IP_WINDOW_SEC,
    IP_LOCKOUT_SEC,
    USER_LOCKOUT_SEC,
    check_login_limit,
    record_login_failure,
    record_login_success,
    get_limiter,
)


class TestLoginLimiter(unittest.TestCase):
    """LoginLimiter 核心逻辑测试。"""

    def setUp(self):
        self.limiter = LoginLimiter()

    def test_allows_normal_login(self):
        """正常登录不被限制。"""
        locked, msg, retry = self.limiter.is_locked('1.2.3.4', 'alice')
        self.assertFalse(locked)
        self.assertEqual(msg, '')
        self.assertEqual(retry, 0)

    def test_locks_after_max_failures_per_ip(self):
        """同一 IP 连续失败 N 次后锁定。"""
        ip = '10.0.0.1'
        for i in range(MAX_FAILURES_PER_IP):
            self.limiter.record_failure(ip, 'user%d' % i)

        locked, msg, retry = self.limiter.is_locked(ip, 'anyone')
        self.assertTrue(locked)
        self.assertIn('频繁', msg)
        self.assertGreater(retry, 0)

    def test_locks_after_max_failures_per_user(self):
        """同一用户名连续失败 N 次后锁定（不同 IP）。"""
        username = 'target_user'
        for i in range(MAX_FAILURES_PER_USER):
            self.limiter.record_failure('ip_%d' % i, username)

        locked, msg, retry = self.limiter.is_locked('new_ip', username)
        self.assertTrue(locked)
        self.assertIn('账号', msg)

    def test_unlocks_after_lockout_expires(self):
        """锁定时间过后自动解锁。"""
        ip = '10.0.0.2'
        for i in range(MAX_FAILURES_PER_IP):
            self.limiter.record_failure(ip, '')

        # 模拟时间经过锁定期
        self.limiter._ip_locked_until[ip] = time.time() - 1

        locked, msg, retry = self.limiter.is_locked(ip, '')
        self.assertFalse(locked)

    def test_success_clears_failures(self):
        """登录成功后清除失败记录。"""
        ip = '10.0.0.3'
        username = 'bob'
        # 记录几次失败（但不超限）
        for _ in range(MAX_FAILURES_PER_IP - 1):
            self.limiter.record_failure(ip, username)

        # 成功登录
        self.limiter.record_success(ip, username)

        # 再记录一次失败不应触发锁定（因为之前的记录已清除）
        self.limiter.record_failure(ip, username)
        locked, _, _ = self.limiter.is_locked(ip, username)
        self.assertFalse(locked)

    def test_ip_and_user_dimensions_independent(self):
        """IP 维度和用户名维度独立判定。"""
        ip = '10.0.0.4'
        username = 'charlie'

        # 触发 IP 锁定
        for _ in range(MAX_FAILURES_PER_IP):
            self.limiter.record_failure(ip, 'different_user')

        # 该 IP 被锁，但换 IP 后同用户不受影响
        locked_ip, _, _ = self.limiter.is_locked(ip, username)
        self.assertTrue(locked_ip)

        locked_other_ip, _, _ = self.limiter.is_locked('other_ip', username)
        self.assertFalse(locked_other_ip)

    def test_sliding_window_evicts_old_failures(self):
        """滑动窗口外的旧失败记录不计入。"""
        ip = '10.0.0.5'
        # 用 patch 模拟时间
        base_time = time.time()

        with patch('app.rbac.login_limiter.time.time', return_value=base_time):
            for _ in range(MAX_FAILURES_PER_IP - 1):
                self.limiter.record_failure(ip, '')

        # 窗口过后再记录一次，不应触发锁定
        future_time = base_time + IP_WINDOW_SEC + 1
        with patch('app.rbac.login_limiter.time.time', return_value=future_time):
            self.limiter.record_failure(ip, '')
            locked, _, _ = self.limiter.is_locked(ip, '')
        self.assertFalse(locked)

    def test_reset_clears_all(self):
        """reset() 清空全部状态。"""
        ip = '10.0.0.6'
        for _ in range(MAX_FAILURES_PER_IP):
            self.limiter.record_failure(ip, 'user')

        self.limiter.reset()
        locked, _, _ = self.limiter.is_locked(ip, 'user')
        self.assertFalse(locked)


class TestGlobalInterface(unittest.TestCase):
    """全局接口函数测试。"""

    def setUp(self):
        get_limiter().reset()

    def tearDown(self):
        get_limiter().reset()

    def test_check_and_record_cycle(self):
        """check → record_failure → check locked 完整周期。"""
        ip = '192.168.1.1'
        username = 'admin'

        locked, _, _ = check_login_limit(ip, username)
        self.assertFalse(locked)

        for _ in range(MAX_FAILURES_PER_IP):
            record_login_failure(ip, username)

        locked, msg, _ = check_login_limit(ip, username)
        self.assertTrue(locked)

        # 成功后解锁
        record_login_success(ip, username)
        locked, _, _ = check_login_limit(ip, username)
        self.assertFalse(locked)


if __name__ == '__main__':
    unittest.main()
