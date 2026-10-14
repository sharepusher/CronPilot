# -*- coding:utf-8 -*-
"""触发 URL 安全校验：SSRF / 内网探测防护。"""
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


def _is_hard_blocked_ip(addr):
    """Return whether an address is never a valid execution-time target.

    RFC1918 and IPv6 ULA are intentionally not in this baseline: CronPilot
    supports deployment-controlled internal DNS.  IPv4-mapped IPv6 must be
    evaluated as its embedded IPv4 address so it cannot bypass loopback or
    link-local checks.
    """
    try:
        ip = ipaddress.ip_address(addr)
    except ValueError:
        return True
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        ip = ip.ipv4_mapped
    return (
        ip.is_loopback
        or ip.is_link_local
        or ip.is_reserved
        or ip.is_multicast
        or ip.is_unspecified
    )


def _url_structure_error(req_url, cron_config):
    """Validate URL syntax and hostname policy without performing DNS I/O."""
    if not req_url:
        return '触发 URL 必填！', None

    req_url = req_url.strip()
    lower = req_url.lower()
    if not (lower.startswith('http://') or lower.startswith('https://')):
        return 'URL格式有误！须为 http 或 https', None

    parsed = urlparse(req_url)
    hostname = (parsed.hostname or '').strip().lower()
    if not hostname:
        return 'URL格式有误！无法解析主机名', None

    if hostname in _BLOCKED_HOSTS:
        return '不允许访问的主机名：%s' % hostname, None

    allow_hosts = _parse_allow_hosts(cron_config)
    if allow_hosts is not None and hostname not in allow_hosts:
        return '触发 URL 主机不在白名单内（url_allow_hosts）', None
    return None, hostname


def _hard_block_message(hostname, addr=None):
    if addr:
        return '域名 %s 解析到禁止地址 %s，已拒绝' % (hostname, addr)
    return '不允许触发禁止地址：%s' % hostname


def _resolve_host_ips(hostname, retries=1):
    import time as _time
    for attempt in range(1 + retries):
        try:
            infos = socket.getaddrinfo(hostname, None)
            ips = set()
            for info in infos:
                ips.add(info[4][0])
            return ips
        except socket.gaierror:
            if attempt < retries:
                _time.sleep(0.5)
    return None


def validate_trigger_url(req_url, cron_config=None):
    """
    校验触发 URL（调度器到点发起的 GET 目标地址）。
    返回 (ok: bool, message: str)
    """
    error, hostname = _url_structure_error(req_url, cron_config)
    if error:
        return False, error

    # Network zone is determined by the deployment DNS boundary.  Private
    # answers are valid for internal DNS names; pinning prevents post-check
    # DNS drift.  Public-DNS split-horizon isolation remains a deployment
    # contract rather than an application-maintained hostname/CIDR list.
    if _block_private_ip_enabled(cron_config):
        try:
            ip = ipaddress.ip_address(hostname)
            if _is_hard_blocked_ip(str(ip)):
                return _fail_or_observe(cron_config, _hard_block_message(hostname))
        except ValueError:
            ips = _resolve_host_ips(hostname)
            if ips is None:
                return False, 'DNS 解析失败（%s），请确认域名正确后重试' % hostname
            for addr in ips:
                if _is_hard_blocked_ip(addr):
                    return _fail_or_observe(
                        cron_config,
                        _hard_block_message(hostname, addr),
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
    - 执行期硬禁止地址与 DNS 失败始终 fail-closed，不受观测/兼容开关影响
    - 一个域名在单次调用内只进行一次 DNS 解析
    """
    error, hostname = _url_structure_error(req_url, cron_config)
    if error:
        return False, error, None

    # hostname 已是 IP 字面量：无需 DNS；硬禁止集合不允许任何开关绕过。
    try:
        ipaddress.ip_address(hostname)
        if _is_hard_blocked_ip(hostname):
            return False, _hard_block_message(hostname), None
        return True, '', hostname
    except ValueError:
        pass

    # 域名：只解析一次。任何危险或无效回答均使整次执行失败，避免
    # 多 A/AAAA 记录中选择一个地址绕过同一 hostname 的安全判定。
    ips = _resolve_host_ips(hostname)
    if ips is None:
        return False, 'DNS 解析失败（%s），拒绝执行' % hostname, None
    if not ips:
        return False, 'DNS 未返回可用地址，拒绝执行', None
    normalized_ips = []
    for addr in ips:
        if _is_hard_blocked_ip(addr):
            return False, _hard_block_message(hostname, addr), None
        normalized_ips.append(str(ipaddress.ip_address(addr)))
    return True, '', sorted(normalized_ips)[0]


class _PinnedIPAdapter(HTTPAdapter):
    """强制将 HTTP(S) 请求连接到指定 IP，防止 DNS Rebinding。

    原理：重写 URL 中的 hostname 为已验证的 IP，通过 Host header
    保持服务端虚拟主机路由和 TLS SNI 正确性。
    """

    def __init__(self, pinned_ip, original_hostname, scheme='https', **kwargs):
        self.pinned_ip = pinned_ip
        self.original_hostname = original_hostname
        self.scheme = (scheme or 'https').lower()
        super().__init__(**kwargs)

    def send(self, request, **kwargs):
        parsed = urlparse(request.url)
        if parsed.hostname and parsed.hostname != self.pinned_ip:
            request.headers.setdefault('Host', self.original_hostname)
            port_suffix = ':%d' % parsed.port if parsed.port else ''
            pinned_host = self.pinned_ip
            if ipaddress.ip_address(pinned_host).version == 6:
                pinned_host = '[%s]' % pinned_host
            request.url = urlunparse(parsed._replace(
                netloc=pinned_host + port_suffix
            ))
        return super().send(request, **kwargs)

    def init_poolmanager(self, connections, maxsize, block=False, **kwargs):
        # TLS 参数只适用于 HTTPS；HTTPConnection 不接受这些参数。
        if self.scheme == 'https' and self.original_hostname:
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
    adapter = _PinnedIPAdapter(pinned_ip, original_hostname, scheme=scheme)
    prefix = '%s://' % scheme
    session.mount(prefix, adapter)
    return session
