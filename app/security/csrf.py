# -*- coding: utf-8 -*-
"""OPT-P0-11: Session synchronizer-token CSRF for admin (Cookie session) writes."""
import hmac
import secrets
from functools import wraps

from flask import current_app, request, session

CSRF_SESSION_KEY = 'csrf_token'
CSRF_PARAM = 'csrf_token'
CSRF_HEADER_NAMES = ('X-CSRFToken', 'X-CSRF-Token')


def ensure_csrf_token():
    token = session.get(CSRF_SESSION_KEY)
    if not token:
        token = secrets.token_urlsafe(32)
        session[CSRF_SESSION_KEY] = token
    return token


def inject_csrf_context():
    """Jinja: csrf_token + csrf_param for meta / hidden fields."""
    return {
        'csrf_token': ensure_csrf_token(),
        'csrf_param': CSRF_PARAM,
    }


def _extract_request_token():
    token = request.form.get(CSRF_PARAM)
    if token:
        return token
    for name in CSRF_HEADER_NAMES:
        token = request.headers.get(name)
        if token:
            return token
    if request.is_json:
        data = request.get_json(silent=True) or {}
        token = data.get(CSRF_PARAM)
        if token:
            return token
    return None


def validate_csrf():
    expected = session.get(CSRF_SESSION_KEY)
    provided = _extract_request_token()
    if not expected or not provided:
        return False
    return hmac.compare_digest(str(expected), str(provided))


def csrf_failure_response():
    from app.common.functions import web_api_return

    return web_api_return(code=1, msg='CSRF 校验失败，请刷新页面重试')


def csrf_protect(view):
    """Validate CSRF on unsafe methods. Safe methods (GET/HEAD/OPTIONS) pass."""

    @wraps(view)
    def wrapped(*args, **kwargs):
        if request.method in ('POST', 'PUT', 'PATCH', 'DELETE'):
            bypass = current_app.config.get('CSRF_BYPASS_IN_TESTING')
            if bypass is None:
                bypass = bool(current_app.config.get('TESTING'))
            if bypass:
                ensure_csrf_token()
            elif not validate_csrf():
                return csrf_failure_response()
        return view(*args, **kwargs)

    return wrapped
