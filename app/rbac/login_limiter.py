# -*- coding:utf-8 -*-
"""登录失败限流器（OPT-P0-13）：基于内存的 IP + 用户名双维度防暴破。

策略：
- 同一 IP：50 次失败 / 15 分钟 → 锁定 5 分钟
- 同一用户名：50 次失败 / 30 分钟 → 锁定 10 分钟
- 登录成功后清除该维度的失败记录

限制：
- 进程内有效（gunicorn 多 worker 不共享）
- 进程重启后计数器清零
- 如需跨进程共享，未来可升级为 Redis 后端
"""
import threading
import time
from collections import defaultdict

# ========== 可调配置 ==========
MAX_FAILURES_PER_IP = 50
IP_WINDOW_SEC = 900          # 15 分钟滑动窗口
IP_LOCKOUT_SEC = 300         # 锁定 5 分钟

MAX_FAILURES_PER_USER = 50
USER_WINDOW_SEC = 1800       # 30 分钟滑动窗口
USER_LOCKOUT_SEC = 600       # 锁定 10 分钟


class LoginLimiter:
    """线程安全的滑动窗口限流器。"""

    def __init__(self):
        self._lock = threading.Lock()
        self._ip_failures = defaultdict(list)
        self._user_failures = defaultdict(list)
        self._ip_locked_until = {}
        self._user_locked_until = {}

    def is_locked(self, ip, username):
        """检查是否被锁定。

        返回 (locked: bool, reason: str, retry_after_sec: int)
        """
        now = time.time()

        # IP 维度检查
        if ip in self._ip_locked_until:
            if now < self._ip_locked_until[ip]:
                retry = int(self._ip_locked_until[ip] - now)
                mins = retry // 60 + 1
                return True, '登录尝试过于频繁，请 %d 分钟后再试' % mins, retry
            else:
                del self._ip_locked_until[ip]

        # 用户名维度检查
        if username and username in self._user_locked_until:
            if now < self._user_locked_until[username]:
                retry = int(self._user_locked_until[username] - now)
                mins = retry // 60 + 1
                return True, '该账号登录尝试过于频繁，请 %d 分钟后再试' % mins, retry
            else:
                del self._user_locked_until[username]

        return False, '', 0

    def record_failure(self, ip, username):
        """记录一次失败；若超限则自动触发锁定。"""
        now = time.time()
        with self._lock:
            # IP 维度
            self._ip_failures[ip] = [
                t for t in self._ip_failures[ip] if now - t < IP_WINDOW_SEC
            ]
            self._ip_failures[ip].append(now)
            if len(self._ip_failures[ip]) >= MAX_FAILURES_PER_IP:
                self._ip_locked_until[ip] = now + IP_LOCKOUT_SEC
                self._ip_failures[ip] = []

            # 用户名维度
            if username:
                self._user_failures[username] = [
                    t for t in self._user_failures[username]
                    if now - t < USER_WINDOW_SEC
                ]
                self._user_failures[username].append(now)
                if len(self._user_failures[username]) >= MAX_FAILURES_PER_USER:
                    self._user_locked_until[username] = now + USER_LOCKOUT_SEC
                    self._user_failures[username] = []

    def record_success(self, ip, username):
        """登录成功：清除该 IP 和用户的失败记录。"""
        with self._lock:
            self._ip_failures.pop(ip, None)
            self._ip_locked_until.pop(ip, None)
            if username:
                self._user_failures.pop(username, None)
                self._user_locked_until.pop(username, None)

    def reset(self):
        """清空全部状态（仅用于测试）。"""
        with self._lock:
            self._ip_failures.clear()
            self._user_failures.clear()
            self._ip_locked_until.clear()
            self._user_locked_until.clear()


# 全局单例
_limiter = LoginLimiter()


def check_login_limit(ip, username=''):
    """检查登录是否被限流。

    返回 (locked: bool, reason: str, retry_after_sec: int)
    """
    return _limiter.is_locked(ip, username)


def record_login_failure(ip, username=''):
    """记录登录失败。"""
    _limiter.record_failure(ip, username)


def record_login_success(ip, username=''):
    """登录成功后清除失败记录。"""
    _limiter.record_success(ip, username)


def get_limiter():
    """获取全局限流器实例（仅用于测试）。"""
    return _limiter
