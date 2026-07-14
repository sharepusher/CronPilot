# CronPilot · RBAC 详细设计方案 v4

> HTML 版：[RBAC架构设计方案.html](RBAC架构设计方案.html) · [文档索引](index.html) · [索引 Markdown](index.md)

[← 文档索引](index.html)
OPT-P2-10RBACv4

# RBAC 详细设计方案

前后端联动 · 三角色 · Flask 装饰器 + Jinja2 `has_perm` · v4 性能与体验修正

状态：**已交付 · v1.0.0 待打 tag** · 落地路线见 [RBAC落地路线 v4](RBAC落地路线.html)

**废弃方案：**v1.0/v1.1（Node/Express、`init_rbac`、`route_registry`、JWT、四角色 `superadmin`）不适用本仓库。

**来源：**合并 `CronPilot_RBAC_设计方案_v2_真实代码版`、`前后端详细设计_v3`、`前后端详细设计_v4` 为仓库权威单文档。实施顺序见 [RBAC落地路线](RBAC落地路线.html)。

## 变更记录

| 版本 | 说明 |
| --- | --- |
| v2 | 真实 Flask 源码；三角色；`rbac_users` 单表；`@require_permission`；API `access_token` 不变 |
| v3 | 登录身份子阶段：`/rbac/login`、`app_context_processor`、`_nav.html`、按钮级权限、Ajax/页面 403 分流 |
| **v4** | `make_has_perm` 防 N+1；分权始终启用；`next`+`full_path`；307 运维清单；format-guard 规则 |
| v1.0.0 | 阶段 1～7 + OPT-P1-09：三角色、`operation:read`（operator 看操作记录）/ `audit:read`（仅 admin 看 RBAC 审计）、无 `legacy_admin`、种子 `admin`；待打 tag |

## 一、现状与前端约束

### 1.1 技术栈（代码出处）

| 维度 | 真实值 |
| --- | --- |
| Web | Flask 1.1.2；Blueprint `main`/`api`/`docs` |
| ORM | SQLAlchemy 1.4.52 + FSA 2.5.1（Tier 1 已交付） |
| 前端 | Jinja2 SSR + jQuery；`common.js` 约定 `js-ajax-form`、`js-ajax-delete` |
| 配置 | `conf.ini`；`configs()` 每次读盘、无缓存 |
| Web 鉴权 | **已交付**：`/rbac/login` 用户名+密码；`@require_permission`；空表种子 `admin`（密码=`login_pwd`）；无 `legacy_admin` |
| API 鉴权 | 各路由内 `api_access_token` 比对（三处重复） |

### 1.2 导航与前端事实（对齐 v0.2.0 已交付项）

| 项 | 现状（真实代码） |
| --- | --- |
| 主 Tab 导航 | **已交付** `rbac/_nav.html` + `has_perm`；「操作记录」(`operation:read`)、「用户管理」「审计」按角色裁剪 |
| 子页导航 | `job_log_list`、`job_log_item_list` 为单 Tab「运行记录」子视图，非主 Tab |
| 登录页 | `rbac/login.html`：用户名+密码**必填**；`/check_pass` 仅转发；无空用户名 / `legacy_admin` |

**纠正 v3 初稿：**主站导航并非 7 文件硬编码 `<ul class="nav nav-tabs">`；RBAC 阶段 3 是 **`_admin_nav` → `rbac/_nav`** 迁移 + 权限菜单，而非从零抽取。

### 1.3 项目纪律

- RBAC 新代码禁止 `Model.query` / 裸 SQL；用 `session.scalars(select(...))`
- 最小 diff：`main/views.py` 函数体不动（`check_pass` 转发除外）；仅换装饰器与 import
- JSON：`{errcode: int, errmsg, result, data, url}`
- 无新 pip 依赖；密码复用 `app/auth/password.py`

## 二、端到端链路

```
用户 → @require_permission(perm)
  ├─ 无 is_login → redirect /rbac/login?next={full_path}     ← v4
  └─ has_permission(role, perm) → 视图 | 403（Ajax JSON / 页面 forbidden.html）

/rbac/login POST
  ├─ username 必填 → rbac_users 校验；空表时种子 admin（密码=login_pwd）
  └─ 失败 → 请填写用户名 / 用户名或密码有误
  → redirect(next)

每请求：app_context_processor → current_user, has_perm()
模板：{% if has_perm('cron:write') %} ... {% endif %}
```

## 三、角色与权限

### 3.1 三内置角色

| role | 说明 |
| --- | --- |
| `viewer` | 只读任务与执行日志；**不可**见操作记录、用户管理、RBAC 审计 |
| `operator` | 可写任务 + **可看操作记录**（配置变更历史）；不可下线、不可管用户、**不可**看 RBAC 审计 |
| `admin` | 全部 Web 权限 + 下线 + 用户管理 + 操作记录 + RBAC 审计 |

### 3.2 权限点与路由

| permission | 路由 | 角色 |
| --- | --- | --- |
| `cron:read` | `cron_list`、`api_doc` | viewer+ |
| `cron:write` | `cron_add`、`cron_edit`、`update_status` | operator+ |
| `cron:retire` | `cron_retire`（下线，不可逆） | admin |
| `log:read` | `job_log_*` 执行记录 | viewer+ |
| `operation:read` | `/operation_log_list`（任务配置变更） | operator+admin |
| `user:manage` | `/rbac/users*` | admin |
| `audit:read` | `/rbac/audit-logs`（登录/权限拒绝） | admin |

**废弃：**`cron:delete`、`log:delete`。生命周期见 [任务生命周期与无删除](任务生命周期与无删除设计.html)。

`check_pass`、`logout` 不挂权限装饰器。

### 3.2.1 审计可见性（权威对照）

| 页面 | 数据 | viewer | operator | admin | 备注 |
| --- | --- | --- | --- | --- | --- |
| 操作记录 | `operation_log` | ✗ | ✓ | ✓ | 权限 `operation:read` |
| 审计 | `rbac_audit_logs` | ✗ | ✗ | ✓ | 权限 `audit:read` |
| 用户管理 | `rbac_users` | ✗ | ✗ | ✓ | 权限 `user:manage` |

### 3.3 `app/rbac/policy.py`

```
ROLE_PERMISSIONS = {
    'viewer':   {'cron:read', 'log:read'},
    'operator': {'cron:read', 'cron:write', 'log:read', 'operation:read'},
    'admin':    {'cron:read', 'cron:write', 'cron:retire',
                 'log:read', 'operation:read', 'user:manage', 'audit:read'},
}

def has_permission(role: str, permission: str) -> bool:
    return permission in ROLE_PERMISSIONS.get(role, set())
```

## 四、数据模型

### 4.1 `rbac_users`

```
class RbacUser(db.Model):
    __tablename__ = 'rbac_users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), nullable=False, unique=True, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='viewer')
    is_active = db.Column(db.SMALLINT, nullable=False, default=1)
    create_time = db.Column(db.String(25), nullable=False, default='')

    def set_password(self, plain):
        self.password_hash = hash_password(plain)
    def check_password(self, plain):
        return verify_login_password(plain, self.password_hash)
```

### 4.2 `rbac_audit_logs`

```
class RbacAuditLog(db.Model):
    __tablename__ = 'rbac_audit_logs'
    id, user_id, username, action, resource, ip, status(allow|deny), create_time
```

### 4.3 与 P1 `operation_log` 分工

| 表 | 职责 |
| --- | --- |
| `operation_log` | 业务变更（增删改任务） |
| `rbac_audit_logs` | 登录/登出、用户管理、`permission:deny` |

RBAC 启用后 Session 写 `user_id`、`username`、`role`，供 P1 `operator_*` 快照。

### 4.4 迁移

```
flask --app manage:app db migrate -m "add rbac_users and rbac_audit_logs"
flask --app manage:app db upgrade
```

CLI 不可用时：`ensure_rbac_tables(app)` 限定 `create_all` 至两模型。

### 4.5 首次启用与种子管理员

**已取消**空用户名 → `legacy_admin` 登录。`rbac_users` 为空且 `login_pwd` 已配置时，启动/登录时自动种子用户名 `admin`（密码=login\_pwd）。此后 Web 登录**必须**填写用户名 + 密码。

**分权始终启用**：三角色权限矩阵始终生效，无配置旁路。`conf.ini` 中遗留的 `rbac_enable` 键已废弃，存在亦忽略。

## 五、目录结构

```
app/rbac/
  __init__.py       Blueprint + app_context_processor
  policy.py
  decorators.py     require_permission（v4 next）
  context.py        get_current_user, make_has_perm（v4）
  services.py       authenticate_user, CRUD, audit
  views.py          login, logout, users, audit-logs

app/templates/rbac/
  login.html, _nav.html, users.html, forbidden.html

datas/model/rbac_user.py, rbac_audit_log.py
```

## 六、后端实现

### 6.1 `app/rbac/__init__.py`

```
rbac = Blueprint('rbac', __name__, url_prefix='/rbac')

@rbac.app_context_processor
def inject_rbac_context():
    from .context import get_current_user, make_has_perm
    return {'current_user': get_current_user(), 'has_perm': make_has_perm()}

from . import views  # noqa
```

### 6.2 `app/rbac/decorators.py`（v4）

```
def require_permission(permission):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            if 'is_login' not in session:
                next_url = request.full_path.rstrip('?')  # v4：保留 query
                return redirect(f'/rbac/login?next={next_url}')
            role = session.get('role') or ''
            if not has_permission(role, permission):
                write_audit_log(..., status='deny')
                return _forbidden_response(permission)
            return func(*args, **kwargs)
        return wrapper
    return decorator

def _forbidden_response(permission):
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return json_response(errcode=1, errmsg=f'权限不足，需要 {permission}', status=403)
    return render_template('rbac/forbidden.html', permission=permission), 403
```

### 6.3 `app/rbac/views.py`（登录节选）

```
@rbac.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'GET':
        return render_template('rbac/login.html',
            next_url=request.args.get('next', '/cron_list'),
            msg=request.args.get('msg', ''))
    result = authenticate_user(
        request.values.get('username', '').strip(),
        request.values.get('password', ''))
    next_url = request.values.get('next', '/cron_list')
    if not result['ok']:
        return redirect(f"/rbac/login?msg={result['msg']}&next={next_url}")
    session['is_login'] = True
    session['username'] = result['username']
    session['role'] = result['role']
    session['user_id'] = result['user_id']
    write_audit_log(action='user:login', resource=result['username'])
    return redirect(next_url)
```

### 6.4 `authenticate_user`（服务层 · 交付后）

```
def authenticate_user(username, password):
    # 用户名必填；无 legacy_admin；空表由 ensure_seed_admin() 写入 admin
    if not username:
        return {'ok': False, 'msg': '请输入用户名'}
    user = session.scalars(select(RbacUser).where(
        RbacUser.username == username, RbacUser.is_active == 1)).first()
    if user and user.check_password(password):
        return {'ok': True, 'role': user.role, 'username': user.username,
                'user_id': user.id, 'msg': ''}
    return {'ok': False, 'msg': '用户名或密码有误'}
```

### 6.5 `check_pass` 兼容壳（v4 · 仅改函数体）

```
@main.route('/check_pass', methods=['GET', 'POST'])
def check_pass():
    next_url = request.args.get('next', '')
    target = f'/rbac/login?next={next_url}' if next_url else '/rbac/login'
    if request.method == 'GET':
        return redirect(target)
    return redirect(target, code=307)
```

保留 `check_pass.html` 文件，不删除。

## 七、v4 修正（最终落地版本）

### 7.1 权限闭包性能

**根因：**v3 若在每行按钮内重复查权限集，列表 100 行 × 2 按钮有 N+1 风险。  
**修正：**闭包**创建时**一次性取 `user_perms`；闭包内仅 `in` 判断。分权始终启用，无旁路分支。

```
def make_has_perm():
    role = session.get('role') or ''
    user_perms = get_role_permission_set(role)
    def _has_perm(permission):
        return permission in user_perms
    return _has_perm

def get_role_permission_set(role):
    return ROLE_PERMISSIONS.get(role, set())
```

*扩展：*权限矩阵若改 DB 可配置，须在 `get_role_permission_set` 上加 Flask `g` 请求级缓存。

### 7.2 `next` 与 `full_path`

装饰器与 `check_pass` 使用相同 query 参数名 `next`、相同拼接格式；写前核对装饰器实现，写后自查一致。

### 7.3 HTTP 307 运维清单

- 灰度监控 `/check_pass` 307 频次、`/rbac/login` 4xx/5xx
- 外部 POST 调用方迁移至 `/rbac/login`，勿长期依赖 307

### 7.4 格式保留

`.cursor/rules/cronpilot-format-guard.mdc`：`url_for` 内单引号、Jinja 定界符双引号；禁止任务外格式化 diff。

## 八、前端设计

### 8.1 `rbac/_nav.html`（自 `_admin_nav.html` 演进）

5 个主页面 `{% include "rbac/_nav.html" %}`（保留 `{% with active='...' %}`）。**已实施** `has_perm` 菜单裁剪：

```
{% if has_perm('cron:read') %}...任务列表、API文档...{% endif %}
{% if has_perm('cron:write') %}...任务添加...{% endif %}
{% if has_perm('log:read') %}...任务执行记录...{% endif %}
```

| 批次 | 文件 | 状态 |
| --- | --- | --- |
| 3-A | `cron_list`、`cron_add`、`cron_edit` | include 已切至 `rbac/_nav`（行为不变） |
| 3-B | `job_log_all_list`、`api_doc` | include 已切至 `rbac/_nav` |

### 8.2 `rbac/login.html`

隐藏域 `next`；用户名、密码均必填（无「留空旧版密码」）。

### 8.3 按钮级权限（`cron_list.html`）

```
{% if has_perm('cron:write') %}<a href="...cron_edit...">编辑</a>
<a ...>运行/停止</a>{% endif %}
{% if has_perm('cron:retire') %}<a ...>下线</a>{% endif %}
```

装饰器权限字符串与模板 `has_perm('...')` 必须完全一致。**无**删除按钮（见 [生命周期设计](任务生命周期与无删除设计.html)）。

### 8.4 `rbac/users.html`（阶段 6a · 已交付）

复用 `admin_page.html` 分页、`js-ajax-form`；角色下拉 viewer/operator/admin。路由：`/rbac/users`、`/users/add`、`/users/edit`。无物理删除；禁停用当前登录账号与最后一名启用中 admin。导航与路由按 `user:manage` 裁剪。

### 8.4b `rbac/audit_logs.html`（阶段 6b · 已交付）

只读分页 `/rbac/audit-logs`，权限 `audit:read`（仅 admin）。列：时间 / 用户 / 动作 / 资源 / IP / 结果。与「操作记录」`operation_log`（权限 `operation:read`，operator+admin）分表分权。

### 8.5 `rbac/forbidden.html`

展示 `current_user`、`permission`；返回任务列表链接。

### 8.6 404 友好页（`errors/404*.html`）

无效 URL **不**全局跳登录（与受保护路由装饰器分流）：

- 已登录 → `errors/404.html`（含 `rbac/_nav.html`）+ HTTP 404
- 未登录 → `errors/404_guest.html` 极简页 +「前往登录」

`smoke_http_not_found` 纳入黄金路径；部署后须重启进程。

## 九、配置

三角色分权**始终启用**，无 `rbac_enable` 开关。空表种子用户角色为 `admin`（见 `conf.ini.example` 注释）。

## 十、验收标准

- 三角色矩阵：viewer 不可写任务、不可见操作记录与 RBAC 管理面；operator 可见操作记录、不可下线/管用户/看 RBAC 审计；admin 全覆盖
- `next` 保留 query（如 `/cron_list?task_name=x`）
- Ajax 403 → JSON 弹窗；页面 403 → forbidden 页；404 → 品牌化错误页（非纯文本）
- API `access_token` 不变；无新依赖

## 十一、测试

```
bash scripts/cronpilot.sh test   # 含 tests.test_rbac_phase
source scripts/smoke_http.sh && smoke_http_suite "http://127.0.0.1:5001" "changeme"
```

用例：`has_permission` 边界；三角色真实登录矩阵；404 登录态分流；`smoke_http_not_found` 检测未重启旧 handler。

## 十二、实施与发布

分阶段任务、PR 切分、Release 前文档梳理见 **[RBAC落地路线 v4](RBAC落地路线.html)**。建议目标版本 **v1.0.0**。

CronPilot · RBAC 详细设计 v4 ·
[Markdown](RBAC架构设计方案.md) ·
[落地路线](RBAC落地路线.html) ·
[交付状态](交付状态与路线图.html) ·
[索引](index.html)

---

[← 文档索引（HTML）](index.html) · [← 文档索引（Markdown）](index.md)
