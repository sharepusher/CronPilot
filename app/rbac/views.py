from urllib.parse import quote

from flask import current_app, jsonify, redirect, render_template, request, session
from sqlalchemy import select

from app import db
from app.common.functions import web_api_return
from app.repositories.rbac_audit_log_repository import RbacAuditLogRepository
from app.repositories.rbac_user_repository import RbacUserRepository
from app.security.csrf import csrf_protect, ensure_csrf_token
from app.services.pagination import PageQuery

from . import rbac
from .decorators import require_login, require_permission
from .login_limiter import check_login_limit, record_login_failure, record_login_success
from .policy import is_seed_admin_username, user_bypasses_scope
from .safe_redirect import safe_next_url
from .services import (
    AUDIT_ACTION_LABELS,
    DEFAULT_USER_PASSWORD,
    JOB_TITLE_CHOICES,
    REGISTRATION_ROLES,
    ROLE_ORDER,
    VALID_ROLES,
    approve_registration,
    audit_action_label,
    audit_resource_label,
    audit_status_label,
    authenticate_user,
    change_own_password,
    check_registration_status,
    create_resource_group,
    create_user,
    get_resource_group,
    get_user_by_id,
    get_user_group_ids_for_user,
    list_resource_groups,
    reject_registration,
    save_profile_completion,
    set_user_active,
    set_user_groups,
    submit_registration,
    trigger_password_reset,
    update_own_profile,
    update_resource_group,
    update_user,
    user_in_management_scope,
    user_must_reset_password,
    user_needs_profile_completion,
    validate_groups_for_role,
    write_audit_log,
)


def _actor_bypasses_scope():
    """当前登录管理员是否绕过 Scope（种子 admin 或全局管理员 admin）。"""
    return user_bypasses_scope(
        session.get('role') or '',
        username=session.get('username') or '',
        group_ids=session.get('group_ids') or [],
    )


def _get_locked_group(bypass, groups):
    """R2: 非全局权限用户只属于一个业务组时，返回该组对象（锁定）；否则返回 None。"""
    if bypass:
        return None
    if len(groups) == 1:
        return groups[0]
    return None


def _check_management_scope(target_user_id):
    """按组管理员是否可操作目标用户。返回 None 可操作；返回 Response 表示被拦截。"""
    if _actor_bypasses_scope():
        return None
    target = get_user_by_id(target_user_id)
    if target and is_seed_admin_username(target.username):
        return _users_form_response(False, '按组管理员不可操作系统管理员账号', url='/rbac/users')
    actor_gids = session.get('group_ids') or []
    if not user_in_management_scope(actor_gids, target_user_id):
        return _users_form_response(False, '该用户不在您的管理范围内', url='/rbac/users')
    return None


def _build_user_groups_map(user_ids):
    """批量获取用户 → 业务组名列表映射，避免 N+1。"""
    from datas.model.resource_group import ResourceGroup
    from datas.model.user_group import UserGroup

    rows = db.session.execute(
        select(UserGroup.user_id, ResourceGroup.name)
        .join(ResourceGroup, ResourceGroup.id == UserGroup.group_id)
        .where(UserGroup.user_id.in_(user_ids))
    ).all()
    result = {}
    for uid, gname in rows:
        result.setdefault(uid, []).append(gname)
    return result


def _wants_ajax_json():
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return True
    accept = request.headers.get('Accept') or ''
    return 'application/json' in accept


def _users_form_response(ok, msg, url='/rbac/users', template=None, **ctx):
    """Ajax → JSON（含 url 跳转）；普通 POST → 成功重定向 / 失败回渲染表单。"""
    if _wants_ajax_json():
        return web_api_return(code=0 if ok else 1, msg=msg, url=url if ok else '')
    if ok:
        return redirect(url)
    if template:
        return render_template(template, form_msg=msg, roles=ROLE_ORDER, **ctx)
    return redirect(url)


def _password_force_reset(user_id=None):
    return user_must_reset_password(
        user_id if user_id is not None else session.get('user_id')
    )


def _force_reset_allowed_path(path):
    if path.startswith('/static/'):
        return True
    if path in ('/rbac/password', '/rbac/logout', '/rbac/login'):
        return True
    return False


def _profile_completion_allowed_path(path):
    if path.startswith('/static/'):
        return True
    if path in ('/rbac/complete_profile', '/rbac/logout', '/rbac/login', '/rbac/password'):
        return True
    return False


@rbac.before_app_request
def enforce_password_reset():
    """待重置用户访问受保护页时强制改密；改密后若缺个人信息则强制补全。"""
    if 'is_login' not in session:
        return None
    path = request.path or ''
    # 第一优先级：强制改密
    if _force_reset_allowed_path(path):
        return None
    if _password_force_reset():
        reset_url = '/rbac/password'
        msg = '请先修改密码后再继续使用'
        if _wants_ajax_json():
            return web_api_return(code=1, msg=msg, url=reset_url)
        return redirect(reset_url)
    # 第二优先级：个人信息补全（测试模式跳过；通过 TestProfileCompletionGate 专项测试）
    if not current_app.config.get('TESTING'):
        if _profile_completion_allowed_path(path):
            return None
        if user_needs_profile_completion(session.get('user_id')):
            complete_url = '/rbac/complete_profile'
            msg = '请先补全个人信息后再继续使用'
            if _wants_ajax_json():
                return web_api_return(code=1, msg=msg, url=complete_url)
            return redirect(complete_url)


@rbac.route('/login', methods=['GET', 'POST'])
@csrf_protect
def login():
    if request.method == 'GET':
        # 检查注册状态提示
        reg_status = None
        msg = request.args.get('msg', '')
        reg_username = request.args.get('reg_username', '')
        if reg_username:
            reg_status = check_registration_status(reg_username)
        return render_template(
            'redesign/login.html',
            next_url=safe_next_url(request.args.get('next', '')),
            msg=msg,
            reg_status=reg_status,
        )
    username = request.values.get('username', '').strip()
    next_url = safe_next_url(request.values.get('next', ''))
    # 前置检查：pending/rejected 注册申请直接回显状态，不触发认证和限流计数
    reg_status = check_registration_status(username) if username else None
    if reg_status:
        return redirect(
            '/rbac/login?reg_username=%s&next=%s' % (quote(username), quote(next_url))
        )
    # OPT-P0-13: 登录防暴破 — 先检查是否被锁定
    client_ip = request.remote_addr or '0.0.0.0'
    locked, lock_msg, _retry = check_login_limit(client_ip, username)
    if locked:
        return redirect(
            '/rbac/login?msg=%s&next=%s' % (quote(lock_msg), quote(next_url))
        )
    result = authenticate_user(
        username,
        request.values.get('password', ''),
    )
    if not result['ok']:
        record_login_failure(client_ip, username)
        return redirect(
            '/rbac/login?msg=%s&next=%s' % (quote(result['msg']), quote(next_url))
        )
    session['is_login'] = True
    record_login_success(client_ip, username)
    session['username'] = result['username']
    session['role'] = result['role']
    if result.get('user_id') is not None:
        session['user_id'] = result['user_id']
        from .scope import get_user_group_ids
        session['group_ids'] = get_user_group_ids(result['user_id'])
        # B3: update last_login_at
        try:
            from datas.model.rbac_user import RbacUser
            from datas.utils.times import utc_now_hms
            _u = db.session.get(RbacUser, result['user_id'])
            if _u is not None:
                _u.last_login_at = utc_now_hms()
                db.session.commit()
        except Exception:
            current_app.logger.warning('last_login_at update failed for user_id=%s', result.get('user_id'), exc_info=True)
            db.session.rollback()
    else:
        session.pop('user_id', None)
        session['group_ids'] = []
    # Rotate CSRF after privilege change
    session.pop('csrf_token', None)
    ensure_csrf_token()
    write_audit_log(action='user:login', resource=result['username'])
    if result.get('must_reset_password'):
        return redirect('/rbac/password')
    return redirect(next_url)


@rbac.route('/logout', methods=['POST'])
@csrf_protect
def logout():
    if session.get('is_login'):
        write_audit_log(action='user:logout', resource=session.get('username', ''))
    session.clear()
    return redirect('/rbac/login')


@rbac.route('/register', methods=['GET', 'POST'])
@csrf_protect
def register():
    """用户注册申请页面（OPT-P1-10）。"""
    groups = list_resource_groups()
    if request.method == 'GET':
        return render_template(
            'redesign/register.html',
            roles=REGISTRATION_ROLES,
            groups=groups,
            job_title_choices=JOB_TITLE_CHOICES,
        )
    # 岗位类型：如果选了 "other"，拼接自定义内容
    raw_job_title = request.values.get('job_title', '')
    if raw_job_title == 'other':
        custom = request.values.get('job_title_other', '').strip()
        raw_job_title = 'other:' + custom
    result = submit_registration(
        email=request.values.get('email', ''),
        password=request.values.get('password', ''),
        confirm_password=request.values.get('confirm_password', ''),
        role=request.values.get('role', 'viewer'),
        group_ids=request.values.getlist('group_ids'),
        reason=request.values.get('reason', ''),
        job_title=raw_job_title,
        nickname=request.values.get('nickname', ''),
    )
    if result['ok']:
        return redirect('/rbac/login?msg=%s' % quote(result['msg']))
    return render_template(
        'redesign/register.html',
        roles=REGISTRATION_ROLES,
        groups=groups,
        job_title_choices=JOB_TITLE_CHOICES,
        form_msg=result['msg'],
        form_data=request.values,
    )


@rbac.route('/forgot_password', methods=['GET'])
def forgot_password():
    """忘记密码提示页面（OPT-P1-10）。"""
    return render_template('redesign/forgot_password.html')


@rbac.route('/password', methods=['GET', 'POST'])
@require_login
@csrf_protect
def change_password():
    """任意已登录用户修改自己的密码；成功后清空会话并要求重新登录。"""
    force_reset = _password_force_reset()
    if request.method == 'GET':
        return render_template('redesign/change_password.html', force_reset=force_reset, active_nav='password')
    result = change_own_password(
        session.get('user_id'),
        request.values.get('old_password', ''),
        request.values.get('new_password', ''),
        request.values.get('confirm_password', ''),
    )
    login_url = '/rbac/login?msg=%s' % quote('密码已修改，请重新登录')
    if result['ok']:
        session.clear()
    if _wants_ajax_json():
        return web_api_return(
            code=0 if result['ok'] else 1,
            msg=result['msg'] if not result['ok'] else '密码已修改，请重新登录',
            url=login_url if result['ok'] else '',
        )
    if result['ok']:
        return redirect(login_url)
    return render_template('redesign/change_password.html', form_msg=result['msg'], force_reset=force_reset, active_nav='password')


@rbac.route('/profile', methods=['GET', 'POST'])
@require_login
@csrf_protect
def edit_profile():
    """当前登录用户自助修改花名、邮箱、岗位类型（Y1）。"""
    from datas.model.rbac_user import RbacUser
    from datas.model.resource_group import ResourceGroup
    user = db.session.get(RbacUser, session.get('user_id'))
    if not user:
        return redirect('/rbac/login')

    def _user_groups_display():
        from app.rbac.policy import user_bypasses_scope
        gids = get_user_group_ids_for_user(user.id)
        if not gids:
            if user_bypasses_scope(user.role, user.username, group_ids=gids):
                return '全局（不受组限制）'
            return '未分配'
        groups = db.session.scalars(
            select(ResourceGroup).where(ResourceGroup.id.in_(gids))
        ).all()
        names = [g.name for g in groups if g.name]
        return ', '.join(names) if names else '未分配'

    if request.method == 'GET':
        return render_template(
            'redesign/user_profile.html',
            user=user,
            job_title_choices=JOB_TITLE_CHOICES,
            active_nav='profile',
            user_groups_display=_user_groups_display(),
        )
    raw_job_title = request.values.get('job_title', '')
    if raw_job_title == 'other':
        custom = request.values.get('job_title_other', '').strip()
        raw_job_title = 'other:' + custom
    result = update_own_profile(
        user.id,
        email=request.values.get('email', ''),
        nickname=request.values.get('nickname', ''),
        job_title=raw_job_title,
    )
    if _wants_ajax_json():
        return web_api_return(
            code=0 if result['ok'] else 1,
            msg=result['msg'],
            url='' if not result['ok'] else '',
        )
    db.session.refresh(user)
    return render_template(
        'redesign/user_profile.html',
        user=user,
        job_title_choices=JOB_TITLE_CHOICES,
        active_nav='profile',
        form_msg=result['msg'],
        form_ok=result['ok'],
        user_groups_display=_user_groups_display(),
    )


@rbac.route('/complete_profile', methods=['GET', 'POST'])
@require_login
@csrf_protect
def complete_profile():
    """首次登录后强制补全个人信息（一次性门禁）。"""
    from datas.model.rbac_user import RbacUser
    user = db.session.get(RbacUser, session.get('user_id'))
    if not user or not user_needs_profile_completion(user.id):
        return redirect('/')
    msg = ''
    if request.method == 'POST':
        raw_jt = request.values.get('job_title', '')
        if raw_jt == 'other':
            raw_jt = 'other:' + request.values.get('job_title_other', '').strip()
        result = save_profile_completion(
            user.id,
            email=request.values.get('email', ''),
            nickname=request.values.get('nickname', ''),
            job_title=raw_jt,
        )
        if result['ok']:
            if _wants_ajax_json():
                return web_api_return(code=0, msg='个人信息已补全', url='/')
            return redirect('/')
        msg = result['msg']
        if _wants_ajax_json():
            return web_api_return(code=1, msg=msg)
        db.session.refresh(user)
    return render_template(
        'redesign/complete_profile.html',
        user=user,
        job_title_choices=JOB_TITLE_CHOICES,
        form_msg=msg,
    )


@rbac.route('/api_token', methods=['GET'])
@require_login
def api_token_page():
    """展示当前用户的 API Token（独立页面）。"""
    from datas.model.rbac_user import RbacUser
    me = db.session.get(RbacUser, session.get('user_id'))
    return render_template(
        'redesign/api_token.html',
        api_token=me.api_token if me else '',
        api_token_expires_at=me.api_token_expires_at if me else '',
        active_nav='api-token',
    )


@rbac.route('/api_token/reset', methods=['POST'])
@require_login
@csrf_protect
def api_token_reset():
    """当前登录用户自助重置 API Token。"""
    from .services import issue_user_api_token
    result = issue_user_api_token(session.get('user_id'))
    return _users_form_response(
        result['ok'],
        result['msg'],
        url='/rbac/api_token',
    )


@rbac.route('/users', methods=['GET'])
@require_permission('user:manage')
def users_list():
    page_query = PageQuery.from_args(request.args)
    search_username = (request.args.get('username') or '').strip()
    chip = (request.args.get('chip') or '').strip()

    # Translate chip preset into is_active filter.
    is_active = None
    if chip == 'active':
        is_active = 1
    elif chip == 'inactive':
        is_active = 0

    repo = RbacUserRepository(db.session)
    if _actor_bypasses_scope():
        page_data = repo.paginate_all(
            page_query, username=search_username or None, is_active=is_active)
        cnt_total, cnt_active, cnt_inactive = repo.count_by_status()
    else:
        actor_gids = session.get('group_ids') or []
        page_data = repo.paginate_by_groups(
            page_query, actor_gids, username=search_username or None, is_active=is_active)
        cnt_total, cnt_active, cnt_inactive = repo.count_by_status(group_ids=actor_gids)
    user_ids = [u.id for u in page_data.items]
    user_groups_map = _build_user_groups_map(user_ids) if user_ids else {}
    job_title_map = dict(JOB_TITLE_CHOICES)

    # OPT-P1-19: AJAX partial refresh for user management filters
    if request.args.get('partial') == '1':
        partial_ctx = dict(
            page_data=page_data,
            user_groups_map=user_groups_map,
            search_username=search_username,
            job_title_map=job_title_map,
            chip=chip,
            cnt_total=cnt_total,
            cnt_active=cnt_active,
            cnt_inactive=cnt_inactive,
        )
        rows_html = render_template('redesign/_users_rows.html', **partial_ctx)
        pagination_html = render_template('redesign/_users_pagination.html', **partial_ctx)
        return jsonify({
            'rows': rows_html,
            'pagination': pagination_html,
            'total': page_data.total,
            'counts': {
                'total': cnt_total,
                'active': cnt_active,
                'inactive': cnt_inactive,
            },
        })
    return render_template(
        'redesign/users.html',
        active_nav='users',
        page_data=page_data,
        user_groups_map=user_groups_map,
        search_username=search_username,
        job_title_map=job_title_map,
        chip=chip,
        cnt_total=cnt_total,
        cnt_active=cnt_active,
        cnt_inactive=cnt_inactive,
    )


@rbac.route('/users/add', methods=['GET', 'POST'])
@require_permission('user:manage')
@csrf_protect
def users_add():
    bypass = _actor_bypasses_scope()
    if bypass:
        groups = list_resource_groups()
    else:
        actor_gids = set(session.get('group_ids') or [])
        groups = [g for g in list_resource_groups() if g.id in actor_gids]
    locked_group = _get_locked_group(bypass, groups)
    if request.method == 'GET':
        return render_template(
            'redesign/user_form.html',
            roles=ROLE_ORDER,
            groups=groups,
            locked_group=locked_group,
            default_password=DEFAULT_USER_PASSWORD,
            job_title_choices=JOB_TITLE_CHOICES,
        )
    role = request.values.get('role', 'viewer')
    target_username = request.values.get('username', '').strip()
    group_ids = request.values.getlist('group_ids')
    if locked_group:
        group_ids = [str(locked_group.id)]
    # 非 admin 不允许选择全局
    if role != 'admin' and '__ALL__' in group_ids:
        return _users_form_response(
            False,
            '仅 admin 角色可选择「全部（全局权限）」',
            template='redesign/user_form.html',
            groups=groups,
            default_password=DEFAULT_USER_PASSWORD,
            job_title_choices=JOB_TITLE_CHOICES,
        )
    groups_err = validate_groups_for_role(role, group_ids, username=target_username)
    if groups_err:
        return _users_form_response(
            False,
            groups_err,
            template='redesign/user_form.html',
            groups=groups,
            default_password=DEFAULT_USER_PASSWORD,
            job_title_choices=JOB_TITLE_CHOICES,
        )
    if not groups and role != 'admin':
        return _users_form_response(
            False,
            '请先创建业务组，再添加非管理员用户',
            template='redesign/user_form.html',
            groups=groups,
            default_password=DEFAULT_USER_PASSWORD,
            job_title_choices=JOB_TITLE_CHOICES,
        )
    # 岗位类型：必填验证
    add_job_title = request.values.get('job_title', '').strip()
    if not add_job_title:
        return _users_form_response(
            False,
            '岗位类型为必填项，请选择岗位',
            template='redesign/user_form.html',
            groups=groups,
            default_password=DEFAULT_USER_PASSWORD,
            job_title_choices=JOB_TITLE_CHOICES,
        )
    if add_job_title == 'other':
        custom = request.values.get('job_title_other', '').strip()
        if custom:
            add_job_title = 'other:' + custom[:20]
        else:
            return _users_form_response(
                False,
                '选择「其他」时须填写自定义岗位名称',
                template='redesign/user_form.html',
                groups=groups,
                default_password=DEFAULT_USER_PASSWORD,
                job_title_choices=JOB_TITLE_CHOICES,
            )
    result = create_user(
        target_username,
        role,
        email=request.values.get('email', '').strip(),
        nickname=request.values.get('nickname', '').strip(),
        job_title=add_job_title,
    )
    if result.get('ok') and result.get('user_id'):
        bound = set_user_groups(result['user_id'], group_ids, role=role, username=target_username)
        if not bound['ok']:
            orphan = get_user_by_id(result['user_id'])
            if orphan:
                try:
                    db.session.delete(orphan)
                    db.session.commit()
                except Exception:
                    db.session.rollback()
            return _users_form_response(
                False,
                bound['msg'],
                template='redesign/user_form.html',
                groups=groups,
                default_password=DEFAULT_USER_PASSWORD,
            )
    return _users_form_response(
        result['ok'],
        result['msg'],
        template='redesign/user_form.html',
        groups=groups,
        default_password=DEFAULT_USER_PASSWORD,
    )


@rbac.route('/users/edit', methods=['GET', 'POST'])
@require_permission('user:manage')
@csrf_protect
def users_edit():
    user_id = request.values.get('id')
    try:
        user_id = int(user_id)
    except (TypeError, ValueError):
        return _users_form_response(False, '参数错误', url='/rbac/users')
    user = get_user_by_id(user_id)
    if not user:
        return _users_form_response(False, '用户不存在', url='/rbac/users')
    denied = _check_management_scope(user_id)
    if denied:
        return denied
    session_uid = session.get('user_id')
    if session_uid is not None and int(session_uid) == int(user.id):
        msg = '不能在用户管理中编辑自己的账号；请使用「修改密码」调整密码'
        if _wants_ajax_json():
            return web_api_return(code=1, msg=msg, url='/rbac/password')
        return redirect('/rbac/password')
    bypass = _actor_bypasses_scope()
    groups = list_resource_groups() if bypass else [
        g for g in list_resource_groups() if g.id in set(session.get('group_ids') or [])
    ]
    locked_group = _get_locked_group(bypass, groups)
    edit_ctx = dict(
        groups=groups,
        locked_group=locked_group,
        user_group_ids=get_user_group_ids_for_user(user.id),
        default_password=DEFAULT_USER_PASSWORD,
        job_title_choices=JOB_TITLE_CHOICES,
    )
    if request.method == 'GET':
        return render_template(
            'redesign/user_form.html',
            user=user,
            roles=ROLE_ORDER,
            **edit_ctx,
        )
    new_role = request.values.get('role', user.role)
    group_ids = request.values.getlist('group_ids')
    if locked_group:
        group_ids = [str(locked_group.id)]
    # 非 admin 不允许选择全局
    if new_role != 'admin' and '__ALL__' in group_ids:
        return _users_form_response(
            False,
            '仅 admin 角色可选择「全部（全局权限）」',
            template='redesign/user_form.html',
            user=user,
            **edit_ctx,
        )
    groups_err = validate_groups_for_role(new_role, group_ids, username=user.username)
    if groups_err:
        return _users_form_response(
            False,
            groups_err,
            template='redesign/user_form.html',
            user=user,
            **edit_ctx,
        )
    result = update_user(
        user_id,
        role=new_role,
        is_active=request.values.get('is_active', user.is_active),
    )
    if result['ok']:
        bound = set_user_groups(user_id, group_ids, role=new_role, username=user.username)
        if not bound['ok']:
            result = bound
    # 保存个人信息字段（email / nickname / job_title）
    if result['ok']:
        raw_jt = request.values.get('job_title', '').strip()
        if raw_jt == 'other':
            custom_jt = request.values.get('job_title_other', '').strip()
            if not custom_jt:
                return _users_form_response(
                    False,
                    '选择「其他」时须填写自定义岗位名称',
                    template='redesign/user_form.html',
                    user=user,
                    **edit_ctx,
                )
            raw_jt = 'other:' + custom_jt[:20]
        if not raw_jt:
            return _users_form_response(
                False,
                '岗位类型为必填项，请选择岗位',
                template='redesign/user_form.html',
                user=user,
                **edit_ctx,
            )
        email_val = (request.values.get('email') or '').strip()
        nick_val = (request.values.get('nickname') or '').strip()
        user.email = email_val or user.email
        user.nickname = nick_val or None
        user.job_title = raw_jt
        try:
            db.session.commit()
        except Exception:
            current_app.logger.warning('profile commit failed for user_id=%s', user.id, exc_info=True)
            db.session.rollback()
    if not result['ok']:
        user.role = request.values.get('role', user.role)
        try:
            user.is_active = int(request.values.get('is_active', user.is_active))
        except (TypeError, ValueError):
            pass
    # 刷新编辑上下文（业务组可能已变更）
    edit_ctx['user_group_ids'] = get_user_group_ids_for_user(user.id)
    return _users_form_response(
        result['ok'],
        result['msg'],
        template='redesign/user_form.html',
        user=user,
        **edit_ctx,
    )


@rbac.route('/users/view', methods=['GET'])
@require_permission('user:manage')
def users_view():
    """Read-only detail view for any user (active or deactivated)."""
    user_id = request.args.get('id')
    try:
        user_id = int(user_id)
    except (TypeError, ValueError):
        return redirect('/rbac/users')
    user = get_user_by_id(user_id)
    if not user:
        return redirect('/rbac/users')
    denied = _check_management_scope(user_id)
    if denied:
        return denied
    user_groups_map = _build_user_groups_map([user_id])
    return render_template(
        'redesign/user_form.html',
        user=user,
        view_mode=True,
        user_groups_map=user_groups_map,
        roles=[],
        groups=[],
        locked_group=None,
        job_title_choices=[],
        default_password='',
        user_group_ids=[],
    )



@rbac.route('/users/reset_password', methods=['POST'])
@require_permission('user:manage')
@csrf_protect
def users_reset_password():
    user_id = request.values.get('id')
    try:
        user_id = int(user_id)
    except (TypeError, ValueError):
        return _users_form_response(False, '参数错误', url='/rbac/users')
    denied = _check_management_scope(user_id)
    if denied:
        return denied
    result = trigger_password_reset(user_id, actor_user_id=session.get('user_id'))
    return _users_form_response(
        result['ok'],
        result['msg'],
        url='/rbac/users',
    )


@rbac.route('/users/reset_token', methods=['POST'])
@require_permission('user:manage')
@csrf_protect
def users_reset_token():
    """管理员触发重置用户 API Token（S6）。"""
    from .services import issue_user_api_token

    user_id = request.values.get('id')
    try:
        user_id = int(user_id)
    except (TypeError, ValueError):
        return _users_form_response(False, '参数错误', url='/rbac/users')
    denied = _check_management_scope(user_id)
    if denied:
        return denied
    result = issue_user_api_token(user_id)
    return _users_form_response(
        result['ok'],
        result['msg'],
        url='/rbac/users',
    )


@rbac.route('/users/set_active', methods=['GET', 'POST'])
@require_permission('user:manage')
@csrf_protect
def users_set_active():
    user_id = request.values.get('id')
    try:
        user_id = int(user_id)
        is_active = int(request.values.get('is_active'))
    except (TypeError, ValueError):
        return _users_form_response(False, '参数错误', url='/rbac/users')
    if is_active == 1:
        return _users_form_response(
            False, '停用后不可恢复启用，如需使用请重新注册或由管理员创建', url='/rbac/users')
    user = get_user_by_id(user_id)
    if not user:
        return _users_form_response(False, '用户不存在', url='/rbac/users')
    denied = _check_management_scope(user_id)
    if denied:
        return denied
    tpl = 'redesign/users_set_active.html'
    if request.method == 'GET':
        return render_template(
            tpl,
            user=user,
            target_active=is_active,
        )
    result = set_user_active(
        user_id,
        is_active,
        reason=request.values.get('reason', ''),
        actor_user_id=session.get('user_id'),
    )
    return _users_form_response(
        result['ok'],
        result['msg'],
        url='/rbac/users',
        template=tpl,
        user=user,
        target_active=is_active,
    )


@rbac.route('/groups', methods=['GET'])
@require_permission('user:manage')
def groups_list():
    bypass = _actor_bypasses_scope()
    if bypass:
        groups = list_resource_groups()
    else:
        actor_gids = set(session.get('group_ids') or [])
        groups = [g for g in list_resource_groups() if g.id in actor_gids]
    group_ids = [g.id for g in groups]
    group_user_counts = {}
    group_task_counts = {}
    group_top_users = {}  # {group_id: ['张', '李', '王']}
    if group_ids:
        from sqlalchemy import func
        from sqlalchemy import select as sa_select

        from datas.model.rbac_user import RbacUser
        from datas.model.task_group import TaskGroup
        from datas.model.user_group import UserGroup
        # 用户数
        rows = db.session.execute(
            sa_select(UserGroup.group_id, func.count(UserGroup.user_id))
            .where(UserGroup.group_id.in_(group_ids))
            .group_by(UserGroup.group_id)
        ).all()
        group_user_counts = {gid: cnt for gid, cnt in rows}
        # 任务数（走 task_groups 索引）
        task_rows = db.session.execute(
            sa_select(TaskGroup.group_id, func.count(TaskGroup.task_id))
            .where(TaskGroup.group_id.in_(group_ids))
            .group_by(TaskGroup.group_id)
        ).all()
        group_task_counts = {gid: cnt for gid, cnt in task_rows}
        # 每组前 3 个用户展示名（花名优先，否则用户名）
        user_rows = db.session.execute(
            sa_select(UserGroup.group_id, RbacUser.username, RbacUser.nickname)
            .join(RbacUser, RbacUser.id == UserGroup.user_id)
            .where(UserGroup.group_id.in_(group_ids))
            .order_by(UserGroup.group_id, UserGroup.id)
        ).all()
        tmp = {}
        for gid, uname, nick in user_rows:
            tmp.setdefault(gid, [])
            if len(tmp[gid]) < 3:
                display = (nick or uname or '?')[0].upper()
                tmp[gid].append(display)
        group_top_users = tmp

    return render_template(
        'redesign/groups.html',
        active_nav='groups',
        groups=groups,
        group_user_counts=group_user_counts,
        group_task_counts=group_task_counts,
        group_top_users=group_top_users,
        can_create_group=bypass,
    )


@rbac.route('/groups/add', methods=['GET', 'POST'])
@require_permission('user:manage')
@csrf_protect
def groups_add():
    if not _actor_bypasses_scope():
        return _users_form_response(False, '按组管理员不可创建新业务组', url='/rbac/groups')
    if request.method == 'GET':
        return render_template('redesign/group_form.html')
    result = create_resource_group(
        request.values.get('name', ''),
        request.values.get('description', ''),
    )
    return _users_form_response(
        result['ok'],
        result['msg'],
        url='/rbac/groups',
        template='redesign/group_form.html',
    )


@rbac.route('/groups/edit', methods=['GET', 'POST'])
@require_permission('user:manage')
@csrf_protect
def groups_edit():
    group_id = request.values.get('id')
    try:
        group_id = int(group_id)
    except (TypeError, ValueError):
        return _users_form_response(False, '参数错误', url='/rbac/groups')
    if not _actor_bypasses_scope():
        actor_gids = set(session.get('group_ids') or [])
        if group_id not in actor_gids:
            return _users_form_response(False, '该业务组不在您的管理范围内', url='/rbac/groups')
    group = get_resource_group(group_id)
    if not group:
        return _users_form_response(False, '业务组不存在', url='/rbac/groups')
    if request.method == 'GET':
        return render_template('redesign/group_form.html', group=group)
    result = update_resource_group(
        group_id,
        name=request.values.get('name', group.name),
        description=request.values.get('description', group.description),
    )
    if not result['ok']:
        group.name = request.values.get('name', group.name)
        group.description = request.values.get('description', group.description)
    return _users_form_response(
        result['ok'],
        result['msg'],
        url='/rbac/groups',
        template='redesign/group_form.html',
        group=group,
    )


@rbac.route('/audit-logs', methods=['GET'])
@require_permission('audit:read')
def audit_logs():
    page_query = PageQuery.from_args(request.args)
    chip = (request.args.get('chip') or '').strip()

    # Resolve chip presets into action/status filter values.
    action = (request.args.get('action') or '').strip() or None
    status = (request.args.get('status') or '').strip() or None
    if chip == 'login_ok':
        action, status = 'user:login', 'allow'
    elif chip == 'login_fail':
        action, status = 'user:login', 'deny'
    elif chip == 'perm_deny':
        action, status = 'permission:deny', None
    elif chip == 'user_manage':
        action, status = 'user:manage', None

    search = {
        'username': (request.args.get('username') or '').strip() or None,
        'action': action,
        'status': status,
        'time_from': (request.args.get('time_from') or '').strip() or None,
        'time_to': (request.args.get('time_to') or '').strip() or None,
    }
    repo = RbacAuditLogRepository(db.session)
    if _actor_bypasses_scope():
        page_data = repo.paginate_all(page_query, **search)
    else:
        viewer_group_ids = session.get('group_ids') or []
        page_data = repo.paginate_by_scope(page_query, viewer_group_ids, **search)
    # OPT-P1-19: AJAX partial refresh for audit logs filters
    if request.args.get('partial') == '1':
        partial_ctx = dict(
            page_data=page_data,
            audit_action_label=audit_action_label,
            audit_resource_label=audit_resource_label,
            audit_status_label=audit_status_label,
            search=search,
            chip=chip,
        )
        rows_html = render_template('redesign/_audit_logs_rows.html', **partial_ctx)
        pagination_html = render_template('redesign/_audit_logs_pagination.html', **partial_ctx)
        return jsonify({
            'rows': rows_html,
            'pagination': pagination_html,
            'total': page_data.total,
        })
    return render_template(
        'redesign/audit_logs.html',
        active_nav='audit',
        page_data=page_data,
        audit_action_label=audit_action_label,
        audit_resource_label=audit_resource_label,
        audit_status_label=audit_status_label,
        search=search,
        chip=chip,
        AUDIT_ACTION_LABELS=AUDIT_ACTION_LABELS,
    )


@rbac.route('/registration_review', methods=['GET'])
@require_permission('user:manage')
def registration_review():
    """注册审批管理页面（OPT-P1-10 Batch 3）。"""
    from app.repositories.registration_request_repository import RegistrationRequestRepository

    page_query = PageQuery.from_args(request.args)
    status_filter = (request.args.get('status') or '').strip() or None
    search_username = (request.args.get('username') or '').strip() or None
    repo = RegistrationRequestRepository(db.session)

    if _actor_bypasses_scope():
        page_data = repo.paginate_all(page_query, status=status_filter, search_username=search_username)
    else:
        actor_gids = session.get('group_ids') or []
        page_data = repo.paginate_by_groups(page_query, actor_gids, status=status_filter, search_username=search_username)
        # 按组管理员：隐藏其业务组未完全覆盖的 admin 角色申请
        # __ALL__ 申请仅种子/全局 admin 可见（上方已走 _actor_bypasses_scope 分支）
        actor_gids_set = set(actor_gids)
        def _can_see_admin_req(r):
            if r.role != 'admin':
                return True
            gids_raw = r.group_ids.strip()
            if gids_raw == '__ALL__':
                return False
            req_gids = set(int(g) for g in gids_raw.split(',') if g.strip())
            return req_gids.issubset(actor_gids_set)
        page_data.items = [r for r in page_data.items if _can_see_admin_req(r)]

    job_title_map = dict(JOB_TITLE_CHOICES)

    # 检查哪些申请用户名曾被停用（用于审批时提示）
    disabled_usernames = set()
    pending_usernames = [r.username for r in page_data.items if r.status == 'pending']
    if pending_usernames:
        from sqlalchemy import select as sa_select

        from datas.model.rbac_user import RbacUser
        disabled_users = db.session.scalars(
            sa_select(RbacUser.username).where(
                RbacUser.username.in_(pending_usernames),
                RbacUser.is_active == 0,
            )
        ).all()
        disabled_usernames = set(disabled_users)

    # group_name_map: {group_id: group_name} for resolving group_ids in detail rows
    from datas.model.resource_group import ResourceGroup
    all_groups = db.session.execute(
        select(ResourceGroup.id, ResourceGroup.name)
    ).all()
    group_name_map = {g.id: g.name for g in all_groups}

    # reviewer_map: {user_id: username} for resolving reviewer_id in detail rows
    reviewer_ids = set()
    for r in page_data.items:
        if r.reviewer_id:
            reviewer_ids.add(r.reviewer_id)
    reviewer_map = {}
    if reviewer_ids:
        from datas.model.rbac_user import RbacUser as RU
        reviewers = db.session.execute(
            select(RU.id, RU.username).where(RU.id.in_(reviewer_ids))
        ).all()
        reviewer_map = {rv.id: rv.username for rv in reviewers}

    if _actor_bypasses_scope():
        pending_count = repo.get_pending_count_all()
    else:
        pending_count = repo.get_pending_count_by_groups(session.get('group_ids') or [])

    return render_template(
        'redesign/registration_review.html',
        active_nav='reg-review',
        page_data=page_data,
        status_filter=status_filter or '',
        job_title_map=job_title_map,
        disabled_usernames=disabled_usernames,
        group_name_map=group_name_map,
        reviewer_map=reviewer_map,
        search_username=search_username or '',
        pending_count=pending_count,
    )


@rbac.route('/registration_review/approve', methods=['POST'])
@require_permission('user:manage')
@csrf_protect
def registration_approve():
    """批准注册申请。"""
    request_id = request.values.get('id')
    try:
        request_id = int(request_id)
    except (TypeError, ValueError):
        return _users_form_response(False, '参数错误', url='/rbac/registration_review')
    result = approve_registration(request_id)
    return _users_form_response(
        result['ok'], result['msg'], url='/rbac/registration_review',
    )


@rbac.route('/registration_review/reject', methods=['POST'])
@require_permission('user:manage')
@csrf_protect
def registration_reject():
    """拒绝注册申请。"""
    request_id = request.values.get('id')
    try:
        request_id = int(request_id)
    except (TypeError, ValueError):
        return _users_form_response(False, '参数错误', url='/rbac/registration_review')
    comment = request.values.get('comment', '').strip()
    if not comment:
        return _users_form_response(False, '请填写拒绝原因', url='/rbac/registration_review')
    result = reject_registration(request_id, comment=comment)
    return _users_form_response(
        result['ok'], result['msg'], url='/rbac/registration_review',
    )


@rbac.route('/registration_review/batch_approve', methods=['POST'])
@require_permission('user:manage')
@csrf_protect
def registration_batch_approve():
    """批量批准注册申请。"""
    ids_raw = request.values.get('ids', '')
    ids = []
    for s in ids_raw.split(','):
        s = s.strip()
        if s.isdigit():
            ids.append(int(s))
    if not ids:
        return web_api_return(code=1, msg='未选择任何申请')
    ok_count, fail_msgs = 0, []
    for rid in ids:
        result = approve_registration(rid)
        if result['ok']:
            ok_count += 1
        else:
            fail_msgs.append('#%d: %s' % (rid, result['msg']))
    msg = '成功 %d 条' % ok_count
    if fail_msgs:
        msg += '，失败 %d 条（%s）' % (len(fail_msgs), '；'.join(fail_msgs))
    return web_api_return(code=0, msg=msg, url='/rbac/registration_review')


@rbac.route('/registration_review/batch_reject', methods=['POST'])
@require_permission('user:manage')
@csrf_protect
def registration_batch_reject():
    """批量拒绝注册申请。"""
    ids_raw = request.values.get('ids', '')
    comment = request.values.get('comment', '').strip()
    if not comment:
        return web_api_return(code=1, msg='请填写拒绝原因')
    ids = []
    for s in ids_raw.split(','):
        s = s.strip()
        if s.isdigit():
            ids.append(int(s))
    if not ids:
        return web_api_return(code=1, msg='未选择任何申请')
    ok_count, fail_msgs = 0, []
    for rid in ids:
        result = reject_registration(rid, comment=comment)
        if result['ok']:
            ok_count += 1
        else:
            fail_msgs.append('#%d: %s' % (rid, result['msg']))
    msg = '成功 %d 条' % ok_count
    if fail_msgs:
        msg += '，失败 %d 条（%s）' % (len(fail_msgs), '；'.join(fail_msgs))
    return web_api_return(code=0, msg=msg, url='/rbac/registration_review')


# ─── OPT-P1-11：标签管理 ───────────────────────────────────────────
@rbac.route('/tags', methods=['GET'])
@require_permission('user:manage')
def tag_manage():
    from sqlalchemy import select as sa_select

    from app.services.tag_service import all_tags_with_count
    from datas.model.resource_group import ResourceGroup
    # scope 过滤：seed admin / __ALL__ admin 看全部，manager admin 只看自己组
    if _actor_bypasses_scope():
        tags = all_tags_with_count(group_id='__ALL__')
    else:
        gids = session.get('group_ids') or []
        tags = []
        for gid in gids:
            tags.extend(all_tags_with_count(group_id=gid))
        tags.extend(all_tags_with_count(group_id=None))
    groups = db.session.scalars(
        sa_select(ResourceGroup).order_by(ResourceGroup.name)
    ).all()
    group_name_map = {g.id: g.name for g in groups}
    # scope_groups：新建标签时可选的业务组
    if _actor_bypasses_scope():
        scope_groups = groups
    else:
        allowed = set(session.get('group_ids') or [])
        scope_groups = [g for g in groups if g.id in allowed]
    tag_tasks = {}
    if tags:
        from app.services.tag_service import get_tag_tasks
        for t in tags:
            _, tasks = get_tag_tasks(t['id'], limit=5)
            tag_tasks[t['id']] = [task['name'] for task in tasks]

    return render_template(
        'redesign/tags.html',
        active_nav='tags',
        tags=tags,
        tag_tasks=tag_tasks,
        group_name_map=group_name_map,
        scope_groups=scope_groups,
        is_bypass=_actor_bypasses_scope(),
    )


def _check_tag_group_id_scope(group_id):
    """Scope 校验：非全局管理员只能操作自己组的标签。返回 (ok, error_response)。"""
    if _actor_bypasses_scope():
        return True, None
    actor_gids = session.get('group_ids') or []
    if group_id is None:
        return False, web_api_return(code=1, msg='非全局管理员不能操作全局标签')
    if group_id not in actor_gids:
        return False, web_api_return(code=1, msg='无权操作该业务组的标签')
    return True, None


def _check_tag_scope(tag):
    """Scope 校验：已有标签的归属组是否在操作者范围内。"""
    return _check_tag_group_id_scope(tag.group_id)


@rbac.route('/tags/create', methods=['POST'])
@require_permission('user:manage')
@csrf_protect
def tag_create():
    from app.services.tag_service import create_tag as svc_create_tag
    name = request.values.get('name', '').strip()
    raw_gid = request.values.get('group_id', '').strip()
    group_id = int(raw_gid) if raw_gid and raw_gid.isdigit() else None
    description = request.values.get('description', '').strip()
    ok_scope, err = _check_tag_group_id_scope(group_id)
    if not ok_scope:
        return err
    ok, msg = svc_create_tag(
        name=name,
        group_id=group_id,
        description=description,
        created_by=session.get('username') or '',
    )
    return web_api_return(code=0 if ok else 1, msg=msg, url='/rbac/tags')


@rbac.route('/tags/update', methods=['POST'])
@require_permission('user:manage')
@csrf_protect
def tag_update():
    tag_id = request.values.get('tag_id')
    from datas.model.tag import Tag
    tag = db.session.get(Tag, int(tag_id)) if tag_id else None
    if not tag:
        return web_api_return(code=1, msg='标签不存在')
    ok_scope, err = _check_tag_scope(tag)
    if not ok_scope:
        return err
    new_name = request.values.get('new_name', '').strip() or None
    description = request.values.get('description')
    from app.services.tag_service import update_tag
    ok, msg = update_tag(tag_id, new_name=new_name, description=description)
    return web_api_return(code=0 if ok else 1, msg=msg, url='/rbac/tags')


@rbac.route('/tags/rename', methods=['POST'])
@require_permission('user:manage')
@csrf_protect
def tag_rename():
    """兼容旧路由，转发到 update。"""
    tag_id = request.values.get('tag_id')
    from datas.model.tag import Tag
    tag = db.session.get(Tag, int(tag_id)) if tag_id else None
    if not tag:
        return web_api_return(code=1, msg='标签不存在')
    ok_scope, err = _check_tag_scope(tag)
    if not ok_scope:
        return err
    new_name = request.values.get('new_name', '').strip()
    from app.services.tag_service import update_tag
    ok, msg = update_tag(tag_id, new_name=new_name)
    return web_api_return(code=0 if ok else 1, msg=msg, url='/rbac/tags')


@rbac.route('/tags/tasks', methods=['GET'])
@require_permission('user:manage')
def tag_tasks():
    """AJAX 查询标签关联的任务列表。"""
    tag_id = request.args.get('tag_id')
    if not tag_id:
        return web_api_return(code=1, msg='缺少 tag_id')
    from datas.model.tag import Tag
    tag = db.session.get(Tag, int(tag_id))
    if not tag:
        return web_api_return(code=1, msg='标签不存在')
    ok_scope, err = _check_tag_scope(tag)
    if not ok_scope:
        return err
    from app.services.tag_service import get_tag_tasks
    tag_name, tasks = get_tag_tasks(tag_id)
    return web_api_return(code=0, data={'tag_name': tag_name, 'tasks': tasks})


@rbac.route('/tags/delete', methods=['POST'])
@require_permission('user:manage')
@csrf_protect
def tag_delete():
    tag_id = request.values.get('tag_id')
    from datas.model.tag import Tag
    tag = db.session.get(Tag, int(tag_id)) if tag_id else None
    if not tag:
        return web_api_return(code=1, msg='标签不存在')
    ok_scope, err = _check_tag_scope(tag)
    if not ok_scope:
        return err
    force = request.values.get('force', '') == '1'
    from app.services.tag_service import delete_tag
    ok, msg, extra = delete_tag(tag_id, force=force)
    if extra and extra.get('need_confirm'):
        return web_api_return(code=2, msg=msg, data=extra)
    return web_api_return(code=0 if ok else 1, msg=msg, url='/rbac/tags')
