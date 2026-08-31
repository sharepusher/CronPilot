# -*- coding:utf-8 -*-
"""回调 URL 安全校验：SSRF / 内网探测防护。"""
import ipaddress
import socket
from urllib.parse import urlparse, urlunparse

import requests
from requests.adapters import HTTPAdapter

_BLOCKED_HOSTS = frozenset({
    'localhost',
    'metadata.google.internal',
})


def _parse_allow_hosts(cron_config):
    raw = (cron_config or {}).get('url_allow_hosts') or ''
    raw = str(raw).strip()
    if not raw:
        return None
    return {h.strip().lower() for h in raw.split(',') if h.strip()}


def _block_private_ip_enabled(cron_config):
    val = (cron_config or {}).get('block_private_ip', '1')
    return str(val).strip() not in ('0', 'false', 'False', 'no', 'NO')


def _observe_only(cron_config):
    val = (cron_config or {}).get('url_ssrf_observe_only', '0')
    return str(val).strip() in ('1', 'true', 'True', 'yes', 'YES')


def _is_private_or_reserved_ip(addr):
    try:
        ip = ipaddress.ip_address(addr)
    except ValueError:
        return False
    return (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_reserved
        or ip.is_multicast
    )


def _resolve_host_ips(hostname):
    try:
        infos = socket.getaddrinfo(hostname, None)
    except socket.gaierror:
        return None
    ips = set()
    for info in infos:
        ips.add(info[4][0])
    return ips


def validate_callback_url(req_url, cron_config=None):
    """
    校验触发 URL（调度器到点发起的 GET 目标地址）。
    返回 (ok: bool, message: str)
    """
    if not req_url:
        return False, '触发 URL 必填！'

    req_url = req_url.strip()
    lower = req_url.lower()
    if not (lower.startswith('http://') or lower.startswith('https://')):
        return False, 'URL格式有误！须为 http 或 https'

    parsed = urlparse(req_url)
    hostname = (parsed.hostname or '').strip().lower()
    if not hostname:
        return False, 'URL格式有误！无法解析主机名'

    if hostname in _BLOCKED_HOSTS:
        return False, '不允许访问的主机名：%s' % hostname

    allow_hosts = _parse_allow_hosts(cron_config)
    if allow_hosts is not None and hostname not in allow_hosts:
        return False, '触发 URL 主机不在白名单内（url_allow_hosts）'

    if _block_private_ip_enabled(cron_config):
        if hostname in ('127.0.0.1', '0.0.0.0', '::1'):
            return _fail_or_observe(cron_config, '不允许触发本机地址（127.0.0.1 / ::1）')

        if hostname.startswith('169.254.'):
            return _fail_or_observe(cron_config, '不允许访问链路本地 / 云元数据地址段')

        try:
            ip = ipaddress.ip_address(hostname)
            if _is_private_or_reserved_ip(str(ip)):
                return _fail_or_observe(cron_config, '不允许触发内网或保留 IP 地址')
        except ValueError:
            ips = _resolve_host_ips(hostname)
            if ips is None:
                # DNS 暂不可用时放行主机名校验，由执行阶段再次校验
                return True, ''
            for addr in ips:
                if _is_private_or_reserved_ip(addr):
                    return _fail_or_observe(
                        cron_config,
                        '域名 %s 解析到内网/保留地址 %s，已拒绝' % (hostname, addr),
                    )

    return True, ''


def _fail_or_observe(cron_config, message):
    if _observe_only(cron_config):
        return True, ''
    return False, message


# ---------------------------------------------------------------------------
# DNS-pinning layer (OPT-P0-12): eliminate TOCTOU between validation & request
# ---------------------------------------------------------------------------

def validate_and_resolve_url(req_url, cron_config=None):
    """
    执行阶段校验：验证 URL 安全性并返回已解析的安全 IP。

    返回 (ok: bool, message: str, resolved_ip: str | None)
    - resolved_ip 为通过校验的 IP（可用于 DNS pinning）
    - 若 hostname 本身是 IP 字面量或 DNS 不可用，resolved_ip 为 None
    """
    ok, msg = validate_callback_url(req_url, cron_config)
    if not ok:
        return False, msg, None

    parsed = urlparse(req_url)
    hostname = (parsed.hostname or '').strip().lower()

    # hostname 已是 IP 字面量：无需 pin（请求不会二次 DNS 解析）
    try:
        ipaddress.ip_address(hostname)
        return True, '', hostname
    except ValueError:
        pass

    # 域名：解析并返回第一个安全 IP 供 pinning
    ips = _resolve_host_ips(hostname)
    if ips is None:
        return True, '', None
    # 选取第一个通过校验的 IP
    for addr in ips:
        if not _is_private_or_reserved_ip(addr):
            return True, '', addr
    # 全部 IP 为内网（理论上上面 validate_callback_url 已拦截）
    return True, '', None


class _PinnedIPAdapter(HTTPAdapter):
    """强制将 HTTP(S) 请求连接到指定 IP，防止 DNS Rebinding。

    原理：重写 URL 中的 hostname 为已验证的 IP，通过 Host header
    保持服务端虚拟主机路由和 TLS SNI 正确性。
    """

    def __init__(self, pinned_ip, original_hostname, **kwargs):
        self.pinned_ip = pinned_ip
        self.original_hostname = original_hostname
        super().__init__(**kwargs)

    def send(self, request, **kwargs):
        parsed = urlparse(request.url)
        if parsed.hostname and parsed.hostname != self.pinned_ip:
            request.headers.setdefault('Host', self.original_hostname)
            port_suffix = ':%d' % parsed.port if parsed.port else ''
            request.url = urlunparse(parsed._replace(
                netloc=self.pinned_ip + port_suffix
            ))
        return super().send(request, **kwargs)

    def init_poolmanager(self, connections, maxsize, block=False, **kwargs):
        # HTTPS: 让 TLS 对原始主机名做 SNI 和证书校验
        if self.original_hostname:
            kwargs.setdefault('assert_hostname', self.original_hostname)
            kwargs.setdefault('server_hostname', self.original_hostname)
        super().init_poolmanager(connections, maxsize, block, **kwargs)


def make_pinned_session(pinned_ip, original_hostname, scheme='http'):
    """创建一个 DNS-pinned requests.Session，所有请求强制连接到 pinned_ip。

    用法：
        session = make_pinned_session('93.184.216.34', 'example.com', 'https')
        resp = session.get('https://example.com/path', timeout=10)
    """
    session = requests.Session()
    adapter = _PinnedIPAdapter(pinned_ip, original_hostname)
    prefix = '%s://' % scheme
    session.mount(prefix, adapter)
    return session
