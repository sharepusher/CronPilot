#!/usr/bin/python3
# -*- coding:utf-8 -*-
import os
from configparser import ConfigParser, NoOptionError, NoSectionError


_proj_root = os.path.dirname(os.path.abspath(__file__))


def _resolve_sqlite_url(url):
    """SQLite 相对路径转为绝对路径，避免 Flask-SQLAlchemy 路径解析问题"""
    if url.startswith('sqlite:///') and not url.startswith('sqlite:////'):
        path = url[10:]  # 去掉 'sqlite:///'
        if path and not path.startswith('/'):
            abs_path = os.path.join(_proj_root, path)
            return 'sqlite:///' + abs_path
    return url


def configs(key = None):
    cp = ConfigParser()
    cp.read('conf.ini',encoding='utf-8')
    if key:
        try:
            val = cp.get('default', key)
        except (NoOptionError, NoSectionError):
            return ''
        if key in ('cron_db_url', 'cron_job_log_db_url'):
            val = _resolve_sqlite_url(val)
        return val
    is_single = cp.get('default','is_single')
    redis_host = cp.get('default', 'redis_host')
    redis_pwd = cp.get('default', 'redis_pwd')
    redis_db = cp.get('default','redis_db')
    cron_db_url = _resolve_sqlite_url(cp.get('default', 'cron_db_url'))
    cron_job_log_db_url = _resolve_sqlite_url(cp.get('default', 'cron_job_log_db_url'))
    redis_port = cp.get('default','redis_port')
    login_pwd = cp.get('default','login_pwd')
    job_log_counts = cp.get('default','job_log_counts')
    operation_log_counts = '5000'
    if cp.has_option('default', 'operation_log_counts'):
        operation_log_counts = cp.get('default', 'operation_log_counts')
    api_access_token = cp.get('default','api_access_token')
    error_keyword = cp.get('default',"error_keyword")
    fail_on_http_4xx_5xx = '1'
    if cp.has_option('default', 'fail_on_http_4xx_5xx'):
        fail_on_http_4xx_5xx = cp.get('default', 'fail_on_http_4xx_5xx')
    is_dev = cp.get('default','is_dev') or 0
    api_key = cp.get('default', 'api_key') or 0
    qywechat_corpid = cp.get('default','qywechat_corpid')
    qywechat_corpsecret = cp.get('default','qywechat_corpsecret')
    qywechat_agentid = cp.get('default','qywechat_agentid')
    error_web_hook = cp.get('default','error_web_hook')
    dingding_webhook = cp.get('default','dingding_webhook')
    dingding_secret = cp.get('default','dingding_secret')
    block_private_ip = '1'
    url_allow_hosts = ''
    url_ssrf_observe_only = '0'
    if cp.has_option('default', 'block_private_ip'):
        block_private_ip = cp.get('default', 'block_private_ip')
    if cp.has_option('default', 'url_allow_hosts'):
        url_allow_hosts = cp.get('default', 'url_allow_hosts')
    if cp.has_option('default', 'url_ssrf_observe_only'):
        url_ssrf_observe_only = cp.get('default', 'url_ssrf_observe_only')

    pz = {
        'qywechat_corpid':qywechat_corpid,
        'qywechat_corpsecret':qywechat_corpsecret,
        'qywechat_agentid':qywechat_agentid,
        'api_key':api_key,
        'is_dev':is_dev,
        'is_single':is_single,
        'redis_host':redis_host,
        'redis_pwd':redis_pwd,
        'redis_db': redis_db,
        'cron_db_url': cron_db_url,
        'cron_job_log_db_url':cron_job_log_db_url,
        'redis_port':redis_port,
        'login_pwd':login_pwd,
        'job_log_counts':job_log_counts,
        'operation_log_counts': operation_log_counts,
        'api_access_token':api_access_token,
        'error_keyword':error_keyword,
        'fail_on_http_4xx_5xx': fail_on_http_4xx_5xx,
        'error_web_hook':error_web_hook,
        'dingding_webhook':dingding_webhook,
        'dingding_secret':dingding_secret,
        'block_private_ip': block_private_ip,
        'url_allow_hosts': url_allow_hosts,
        'url_ssrf_observe_only': url_ssrf_observe_only,
    }

    return pz