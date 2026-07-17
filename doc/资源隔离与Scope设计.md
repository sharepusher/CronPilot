# CronPilot · 资源隔离与 Scope 设计（OPT-P2-12）

> HTML 版：[资源隔离与Scope设计.html](资源隔离与Scope设计.html) · [文档索引](index.html) · [索引 Markdown](index.md)

[← 文档索引](index.html)
OPT-P2-12Resource Scope

# 资源隔离与 Scope 设计

Permission（能力）+ Resource Scope（可见范围）+ Policy stub · 防 IDOR · 不破坏 RBAC v4

状态：已交付 · v1.1.0 · 落地见 [资源隔离落地路线](资源隔离落地路线.html)

**与 RBAC v4：**[RBAC架构设计方案](RBAC架构设计方案.html) 只负责 Capability（三角色 / `has_permission`）。
本设计在其上叠加 Visibility，**不**引入角色爆炸、**不**把 Group 绑到 Role。

## 一、问题与目标

RBAC v4 交付后任意持 `cron:read/write` 的用户可按 ID 读写**全库**任务（IDOR）。本特性目标：

- 业务线级资源隔离（Group 作为 Scope 的首期实现）
- 列表过滤 + 单资源鉴权同时具备
- 历史数据默认 `GLOBAL`，行为兼容
- `/api/*` 首期仍为部署级 `api_access_token`（不按组隔离，见 §七）

## 二、三层模型

```
Authentication
        │
        ▼
RBAC Permission（能做什么）
        │
        ▼
Resource Scope（能访问哪些资源；admin 绕过）
        │
        ▼
Resource Policy（预留 stub，恒 True）
        │
        ▼
Allow / Deny（403）
```

| 层 | 职责 | 实现 |
| --- | --- | --- |
| Permission | Capability | `app/rbac/policy.py` · `@require_permission` |
| Scope | Visibility | `app/rbac/scope.py` · `authorize()` |
| Policy | 业务规则 | `check_policy` stub |

## 三、数据模型

### 3.1 `resource_groups` / `user_groups`

用户多对多业务组。禁止 `rbac_users.group_id` 单列。组 CRUD 复用权限 `user:manage`（不增 `group:manage`）。**禁止删除**业务组，防悬挂 `group_id`。

- **编码：**由名称自动生成；含中日韩等字符时先译为英文再 slug（如「研发」→ `research-development`）；冲突追加 `-2`…；创建后不可改。翻译依赖外网 API，失败时回退 `g-********`。
- **用户绑组：**viewer / operator **必须**至少绑定一个业务组；仅 admin 可不绑（仍可全局可见，因 Scope bypass）。

### 3.2 `cron_infos`

| 列 | 语义 |
| --- | --- |
| `scope_type` | `GLOBAL`（默认）| `GROUP` |
| `group_id` | `GLOBAL`⇒NULL；`GROUP`⇒必填 |

勿用 `group_id IS NULL` 同时表示「未设置」与「全局」。

### 3.3 派生资源

| 资源 | 隔离 |
| --- | --- |
| 执行日志 | 经 `cron_info_id` → Cron Scope |
| 操作记录 | `target_id` 对应可见 Cron；无 target / 无关联 → 仅 admin |

## 四、核心 API

- `build_scope_filter_clause(role, group_ids)` — 列表 WHERE；admin 返回 None
- `has_scope(role, group_ids, resource)`
- `authorize(role, permission, resource, group_ids)` — 失败抛 `AuthorizationError`
- `authorize_resource(permission, resource)`（装饰器辅助）— 写 `scope:deny` 审计；403

登录成功写入 `session['group_ids']`。**用户组变更后需重新登录**生效。管理端顶栏 `current_user_groups` 亦只解析 Session 中的组 ID（与列表 Scope 同源）；admin 顶栏不展示 Scope 标签。

`admin` ∈ `SCOPE_BYPASS_ROLES`，不增第四角色。

## 五、UI 契约

- 顶栏：登录后展示当前用户与可见范围（组名或「全局可见」/「未分配业务组」）；退出走 `/rbac/logout`
- 任务添加/编辑：**非 admin** 强制「所属业务组」可见（不可选 GLOBAL）；仅一组成员时只读展示；多组时仅可选本人所属组。admin 可创建 GLOBAL 或指定任意组
- 导航「业务组」：`/rbac/groups*`（`user:manage`）
- 用户编辑：多选绑定业务组（非 admin 必选）
- 任务列表按角色密度的 Scope 二次过滤（admin 侧栏 / 1～2 组水平 Segment 等）：权威规格见 [规模化信息架构设计 OPT-P2-13](规模化信息架构设计.html)；线框 Demo 见 [Scope UX 专章](规模化Scope过滤与角色差异化设计.html)（确认实现前未落地）

## 六、安全要求

- 列表 Scope Filter + GET/PUT/启动·暂停/下线 单资源 `authorize`
- 越权 → **403**（非 500）；审计 `scope:deny`
- 禁止 Handler/Service/DAO 散落 `if group_id`；统一走 `authorize` / `build_scope_filter_clause`
- `cron_service` 仅透传 `scope_type`/`group_id`，不判角色

## 七、API 除外（已知缺口）

`/api/*` 仍使用部署级 `api_access_token`，可操作全库任务。按组 token / 调用方身份挂 Scope 见 §八 远期。

## 八、远期（S6，本迭代不实现）

- 新任务默认 `GROUP`（配置项）
- API Scope / 每组凭证
- Policy：Owner、Environment
- 抽象 Tenant / Workspace（仍不绑 Role）

## 九、验收

- `tests/test_rbac_scope.py` 并入 `bash scripts/cronpilot.sh test`
- 他组任务列表不可见；直接编辑 URL → 403
- 历史 GLOBAL 任务对所有已登录有权限用户可见
- `tests.test_ajax_form_guard` 通过

## 十、schema 升级（部署自动 + 人工备用）

**推荐（SQLite / MySQL）：**部署时执行 `bash scripts/ensure_business_tables.sh`（`run_production.sh`、`cronpilot.sh start` 已调用；旧名 `ensure_sqlite_tables.sh` 仍转发）。行为：

- `db.create_all()` — 仅创建**缺失**表（含 `resource_groups` / `user_groups` / RBAC / `operation_log` 等），不删不改已有表
- 已有表缺列时 `ALTER TABLE … ADD COLUMN`（`scope_type` / `group_id` 等）
- 空表时种子 `admin`（密码=`login_pwd`）

前提：MySQL **数据库已建好**且 `cron_db_url` 账号有建表/改表权限。列已存在则跳过对应 ALTER。

**备用手写 DDL（MySQL）：**

```
CREATE TABLE IF NOT EXISTS resource_groups (
  id INT AUTO_INCREMENT PRIMARY KEY,
  name VARCHAR(64) NOT NULL,
  code VARCHAR(64) NOT NULL UNIQUE,
  description VARCHAR(255) NOT NULL DEFAULT '',
  create_time VARCHAR(25) NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS user_groups (
  id INT AUTO_INCREMENT PRIMARY KEY,
  user_id INT NOT NULL,
  group_id INT NOT NULL,
  UNIQUE KEY uq_user_groups_user_group (user_id, group_id)
);
ALTER TABLE cron_infos
  ADD COLUMN scope_type VARCHAR(16) NOT NULL DEFAULT 'GLOBAL',
  ADD COLUMN group_id INT NULL;
```

列已存在时 `ADD COLUMN` 会报错，可先 `SHOW COLUMNS FROM cron_infos LIKE 'scope_type'`。

CronPilot · OPT-P2-12 Resource Scope ·
[Markdown](资源隔离与Scope设计.md) ·
[落地路线](资源隔离落地路线.html) ·
[交付状态](交付状态与路线图.html) ·
[索引](index.html)

---

[← 文档索引（HTML）](index.html) · [← 文档索引（Markdown）](index.md)
