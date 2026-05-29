# -*- coding:utf-8 -*-
"""回调 URL 安全校验：SSRF / 内网探测防护。"""
import ipaddress
import socket
from urllib.parse import urlparse


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
    校验回调 URL。
    返回 (ok: bool, message: str)
    """
    if not req_url:
        return False, '回调URL必填！'

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
        return False, '回调主机不在白名单内（url_allow_hosts）'

    if _block_private_ip_enabled(cron_config):
        if hostname in ('127.0.0.1', '0.0.0.0', '::1'):
            return _fail_or_observe(cron_config, '不允许回调本机地址（127.0.0.1 / ::1）')

        if hostname.startswith('169.254.'):
            return _fail_or_observe(cron_config, '不允许访问链路本地 / 云元数据地址段')

        try:
            ip = ipaddress.ip_address(hostname)
            if _is_private_or_reserved_ip(str(ip)):
                return _fail_or_observe(cron_config, '不允许回调内网或保留 IP 地址')
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
