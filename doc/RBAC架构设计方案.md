# CronPilot · RBAC 架构设计方案 v4

> HTML 版：[RBAC架构设计方案.html](RBAC架构设计方案.html) · [文档索引](index.html) · [索引 Markdown](index.md)

[← 文档索引](index.html)
安全RBACOPT-P2-10v4

# RBAC 架构设计方案

v4 · v2 后端骨架 + v3 前后端联动 + v4 性能/体验修正 · Flask 装饰器 + Blueprint + Jinja2 条件渲染

状态：**设计稿 · 待确认实施** · 2026-06

**纠错：**v1.0/v1.1（Node 中间件、`route_registry`、JWT、四角色）**已废弃**。现行方案以 v2 真实 Flask 源码为基，v3 补全登录/模板联动，v4 修正权限闭包 N+1、`next` 透传与运维清单。

**交付状态：**OPT-P2-10 尚未编码；查「已交付 vs 未完成」见 [交付状态与路线图](交付状态与路线图.html)。Tier 0 已交付（`flask db`），技术前置已满足。

## 变更记录

| 版本 | 日期 | 说明 |
| --- | --- | --- |
| v1.0–v1.1 | — | **废弃**：误判技术栈 |
| v2 | 2026-06 | 三角色、`@require_permission`、`rbac_users` 单表、`rbac_enable` |
| v3 | 2026-06 | 登录身份子阶段：`/rbac/login`、`context_processor`、导航栏抽取、按钮级 `has_perm` |
| **v4** | 2026-06 | 修正 `make_has_perm` N+1、`get_rbac_enabled` 进程缓存、`next` + `full_path`、307 运维清单、格式保留规则 |

## 〇、版本关系

| 层级 | 内容 | 落地时以谁为准 |
| --- | --- | --- |
| v2 | 角色矩阵、`policy.py`、数据表、装饰器替换表、API 独立轨道 | §三–§四 |
| v3 | 登录页、`authenticate_user`、`_nav.html`、模板 `has_perm`、Web/Ajax 403 分流 | §五–§七 |
| v4 | 性能边界、`check_pass` 转发契约、运维监控、`cronpilot-format-guard` | §八（覆盖 v3 同节实现） |

## 一、现状与约束（v2，不变）

技术栈：Flask 1.1 + Jinja2 SSR + jQuery（`common.js` 的 `js-ajax-*`）；配置 `configs()` 每次读盘无缓存；Web 单密码 `login_pwd`；API 独立 `access_token`。详见 v2 §1.1–1.3。

- 导航栏在 **7 个模板**硬编码（`cron_list`、`cron_add`、`cron_edit`、三个 `job_log_*`、`api_doc`）——须先抽 `rbac/_nav.html`。
- 现有 `check_pass.html` 仅密码字段；登录成功后硬编码 `redirect('/cron_list')`，**从未支持 `next`**（v3 新引入，v4 对齐）。
- RBAC 新查询：**禁止**新增 `Model.query`；用 `session.scalars(select(...))`（Tier 1 纪律）。

## 二、端到端链路（v3）

```
受保护页面 → @require_permission
  ├─ 未登录 → /rbac/login?next={full_path}
  ├─ rbac_enable=0 → 与现网一致（仅 is_login）
  └─ 已登录 → has_permission(role, perm) → 视图 / 403

/rbac/login POST
  ├─ username 空 → legacy 单密码 → role=admin, username=legacy_admin
  └─ username 非空 → rbac_users 校验 → role/username 写入 session
  → redirect(next) 回原页

模板渲染：app_context_processor 注入 current_user + has_perm()
  → {% if has_perm('cron:delete') %} 控制按钮与导航
```

**渐进迁移：**用户名字段**可选**，留空走旧单密码，避免 RBAC 账号未建全时锁死管理员。

## 三、角色与权限（v2，不变）

| role | 权限摘要 |
| --- | --- |
| `viewer` | `cron:read`、`log:read` |
| `operator` | + `cron:write`、`log:delete`；不可 `cron:delete`、`user:manage` |
| `admin` | 全部含 `cron:delete`、`user:manage`、`audit:read` |

路由 → 装饰器替换表见 v2 §3.4；`check_pass` 改为转发壳（§八.2）；`api/views.py` **不改**。

## 四、数据模型（v2，不变）

`rbac_users`、`rbac_audit_logs`；与 P1 `operation_log` 分工见 v2 §4.3。迁移：`flask --app manage:app db migrate/upgrade`（Tier 0 已交付）。

## 五、目录结构（v3 扩展）

```
app/rbac/
  ├── __init__.py      Blueprint + app_context_processor
  ├── policy.py        ROLE_PERMISSIONS（v2）
  ├── decorators.py    require_permission（v4 修正 next）
  ├── context.py       get_current_user + make_has_perm（v4 性能）
  ├── services.py      authenticate_user, get_rbac_enabled, CRUD, audit
  └── views.py         /login /logout /users /audit-logs

app/templates/rbac/
  ├── login.html       用户名(可选)+密码
  ├── _nav.html        公共导航（has_perm 控制项）
  ├── users.html       用户管理
  └── forbidden.html   403 友好页

datas/model/rbac_user.py, rbac_audit_log.py
```

## 六、后端关键实现（v3 + v4 修正）

### 6.1 `app/rbac/__init__.py` — 全局模板注入

```
@rbac.app_context_processor
def inject_rbac_context():
    from .context import get_current_user, make_has_perm
    return {'current_user': get_current_user(), 'has_perm': make_has_perm()}
```

使 `main` 蓝图下的 `cron_list.html` 等**无需**在每个 `render_template` 手动传参。

### 6.2 `app/rbac/decorators.py` — Web/Ajax 403 分流

- `X-Requested-With: XMLHttpRequest` → `json_response(errcode=1, ..., status=403)`（兼容 `common.js`）
- 普通 GET → `rbac/forbidden.html`
- 未登录 → `redirect('/rbac/login?next=' + request.full_path.rstrip('?'))`（**v4：保留 query string**）

### 6.3 `app/rbac/services.py` — `authenticate_user`

username 空 → `verify_login_password` 对比 `login_pwd`；非空 → `rbac_users` 查表（`select`，非 `Model.query`）。

## 八、v4 修正（相对 v3 的最终实现）

### 8.1 权限闭包性能（`context.py` + `services.py`）

**问题：**`configs()` 每次读盘；列表页每行按钮调用 `has_perm()` 会 N+1 触发 I/O。  
**修正：**`make_has_perm()` 在闭包**创建时**一次性取 `rbac_enabled` 与 `get_role_permission_set(role)`；闭包内仅 `permission in user_perms`（O(1)）。  
**`get_rbac_enabled()`：**`@lru_cache(maxsize=1)` 进程级缓存——与「改 conf.ini 须重启」一致，无额外滞后风险。

```
def make_has_perm():
    from .services import get_rbac_enabled, get_role_permission_set
    rbac_enabled = get_rbac_enabled()
    role = session.get('role', '')
    user_perms = get_role_permission_set(role) if rbac_enabled else None
    def _has_perm(permission):
        if not rbac_enabled:
            return True
        return permission in user_perms
    return _has_perm
```

*扩展提醒：*若未来权限矩阵改数据库可配置，须在 `get_role_permission_set` 上加请求级缓存（Flask `g`）。

### 8.2 `check_pass` 转发与 `next` 契约

```
@main.route('/check_pass', methods=['GET', 'POST'])
def check_pass():
    next_url = request.args.get('next', '')
    target = f'/rbac/login?next={next_url}' if next_url else '/rbac/login'
    if request.method == 'GET':
        return redirect(target)
    return redirect(target, code=307)  # 保留 POST body
```

不删除 `check_pass.html`；与装饰器拼接 `next` 的格式必须一致。

### 8.3 上线运维清单（非代码）

- 灰度监控：`/check_pass` 307 频次、`/rbac/login` 4xx/5xx
- 外部 POST 调用方应迁移到 `/rbac/login`，勿长期依赖 307 转发

### 8.4 格式保留规则

已写入 `.cursor/rules/cronpilot-format-guard.mdc`（`alwaysApply: true`）：模板改动禁止无关格式化（引号、缩进、import 顺序）。

## 七、前端改造（v3）

### 7.1 导航栏抽取（第一批 3 + 第二批 4 文件）

7 个模板将 `<ul class="nav nav-tabs">...` 替换为 `{% include 'rbac/_nav.html' with context %}`；视图仅补 `active_tab` 参数。

### 7.2 按钮级权限（示例 `cron_list.html`）

```
{% if has_perm('cron:write') %}...编辑...{% endif %}
{% if has_perm('cron:delete') %}...js-ajax-delete...{% endif %}
```

复用既有 `js-ajax-delete` / `js-ajax-form`，RBAC 只控制渲染与否。

### 7.3 登录页 `rbac/login.html`

隐藏域 `next`；placeholder 写明「用户名留空则使用旧版密码登录」。

## 九、配置与兼容

```
[default]
rbac_enable=0   ; 0=单密码全权限（默认） 1=启用三角色多账号
```

`rbac_enable=0`：装饰器与 `has_perm` 均旁路，行为与现网一致。首次 `rbac_enable=1` 且表空时，legacy 登录仍为 `admin`，不被锁门外。

## 十、实施阶段（建议顺序）

1. 格式规则 `cronpilot-format-guard.mdc`（已提交则跳过）
2. 模型 + `flask db migrate`
3. `app/rbac/` 核心（policy、services、decorators、context v4）
4. 登录 / 登出 / `check_pass` 转发
5. `_nav.html` + 7 模板分批替换（3+4，每批 `git diff`）
6. `main/views.py` 装饰器逐路由替换 + 模板按钮 `has_perm`
7. 用户管理页 + `tests/test_rbac_phase.py`
8. 文档 + [交付状态](交付状态与路线图.html) 标版本 + `RELEASE_NOTES [Unreleased]`

## 十一、验收标准

- `rbac_enable=0`：P0 单测全绿；UI/行为与现网一致
- `rbac_enable=1`：viewer 不可写/删任务；operator 不可删任务；admin 可管用户
- 登录 `next` 带回 query string（如 `/cron_list?task_name=x`）
- 列表 100 行 × 2 按钮：`get_rbac_enabled` 磁盘读取 ≤1 次/请求
- API `access_token` 不变；无新增 pip 依赖

## 十二、测试

`python -m unittest tests.test_p0_phase_a tests.test_rbac_phase -v` — 含 `has_permission`、legacy 旁路、`get_rbac_enabled.cache_clear()` 单测钩子。

CronPilot · RBAC v4 ·
[Markdown](RBAC架构设计方案.md) ·
[交付状态](交付状态与路线图.html) ·
[架构 §15](架构设计文档.html#rbac-arch) ·
[OPT-P2-10](产品优化需求-借鉴Plombery.html#opt-p2-10) ·
[索引](index.html)

---

[← 文档索引（HTML）](index.html) · [← 文档索引（Markdown）](index.md)
