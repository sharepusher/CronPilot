import logging
import traceback

from flask import render_template, session

from . import main

logger = logging.getLogger(__name__)


@main.app_errorhandler(404)
def page_not_found(e):
    is_login = session.get('is_login')
    return render_template(
        'errors/error.html',
        icon='fa-search',
        title='页面不存在',
        description='请求的页面地址无效或已被移除。',
        show_nav=False,
        home_url='/rbac/login' if not is_login else '/cron_list',
        home_text='前往登录' if not is_login else '返回任务中心',
    ), 404


@main.app_errorhandler(500)
def internal_server_error(e):
    logger.error('500 Internal Server Error: %s\n%s', e, traceback.format_exc())
    try:
        is_login = session.get('is_login')
    except Exception:
        is_login = False
    return render_template(
        'errors/error.html',
        icon='fa-exclamation-triangle',
        title='系统繁忙',
        description='系统遇到临时问题，请稍后重试。如持续出现请联系管理员。',
        show_nav=False,
        home_url='/rbac/login' if not is_login else '/cron_list',
        home_text='前往登录' if not is_login else '返回任务中心',
    ), 500
