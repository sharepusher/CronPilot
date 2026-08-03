# 管理员 admin Scope 差异化设计

> HTML 版：[管理员admin-Scope差异化设计.html](管理员admin-Scope差异化设计.html) · [文档索引](../index.html) · [索引 Markdown](../index.md)

设计稿待确认

# 管理员 admin Scope 差异化设计

编号：OPT-P2-15/ADMIN-SCOPE · 日期：2026-07-31 · 状态：**已交付**  
注：原误标为 OPT-P2-12（已占用 = Resource Scope 资源隔离 v1.1.0），2026-08-03 更正为 OPT-P2-15

## 一、问题

当前系统中 `admin` 角色统一绕过 Scope（`role_bypasses_scope('admin') → True`），导致：

- **管理员 admin 用户**（非种子 `admin`）即使绑定了具体业务组，仍然能看到全量任务、日志、操作记录，业务组绑定形同虚设。
- 种子 `admin` 天然应全局可见（它是系统管理账号），但与管理员 admin 混用同一 bypass 逻辑，两者无法区分。
- 审计日志页（`/rbac/audit-logs`）对所有 admin 全量展示，无任何 Scope 过滤。

## 二、根因

| 位置 | 现状 | 问题 |
| --- | --- | --- |
| `app/rbac/policy.py` `SCOPE_BYPASS_ROLES` | `frozenset({'admin'})` | 按角色名 bypass，不区分种子/管理员；管理员 admin 绑定了业务组也被忽略 |
| `role_bypasses_scope(role)` | 仅看 `role in SCOPE_BYPASS_ROLES` | 不看 `username`，导致两类 admin 行为相同 |
| `validate_groups_for_role()` | `role != 'admin'` 时才要求绑组 | 管理员 admin 创建/编辑时允许不绑任何业务组，与你要求的"必选"不一致 |
| `build_scope_filter_clause()` | admin → 返回 `None`（不追加过滤） | 管理员 admin 绑了组也不过滤 |
| `audit_logs()` 路由 | 全量分页，无 Scope 过滤 | 审计日志不受 Scope 控制（注：审计日志与任务 Scope 的关联需单独讨论，见风险节） |

## 三、方案

### 3.1 两类 admin 的 Scope 模型

| 账号类型 | 判定条件 | 业务组选择规则 | Scope 行为 |
| --- | --- | --- | --- |
| **种子 admin** | `role='admin'` 且 `username='admin'` | 不可编辑业务组（永远全局） | 绕过 Scope，全局可见 |
| **管理员 admin** | `role='admin'` 且 `username != 'admin'` | 必须选择「全部」**或**至少 1 个具体业务组（互斥） | 选「全部」→ 全局可见；选具体组 → 仅 GLOBAL + 所属组资源 |

### 3.2 「全部」选项实现方式

- 在创建/编辑用户的业务组多选中增加一个虚拟选项 **「全部（全局权限）」**，其 value 为特殊标记（建议 `__ALL__`）。
- 选择「全部」时，`user_groups` 表中**不写入任何行**（`group_ids = []`），含义为"不受组限制"。
- 与「具体组」互斥：前端用 JS 实现——选 `__ALL__` 后取消其它选中，选具体组后取消 `__ALL__`。
- 提交时后端校验：如果 `group_ids` 同时包含 `__ALL__` 和具体 id，返回错误。

### 3.3 Scope 判定逻辑改动

核心改动：**`role_bypasses_scope` 从「按角色」改为「按角色 + 用户名/组」**。

```
# 改动前
def role_bypasses_scope(role):
    return (role or '') in SCOPE_BYPASS_ROLES

# 改动后：新增 username 和 group_ids 参数
def user_bypasses_scope(role, username=None, group_ids=None):
    """种子 admin 永远全局；管理员 admin 需看 group_ids。"""
    if (role or '') not in SCOPE_BYPASS_ROLES:
        return False                # viewer / operator 不绕过
    if is_seed_admin_username(username):
        return True                 # 种子 admin 永远全局
    # 管理员 admin：group_ids 为空 → 选了「全部」→ 全局；否则按组
    return not group_ids
```

注：旧函数 `role_bypasses_scope(role)` 改为 `user_bypasses_scope(role, username, group_ids)`，所有调用点需一并适配。

### 3.4 受影响的调用点（逐一列出）

| # | 文件 | 现状 | 改动 |
| --- | --- | --- | --- |
| 1 | `app/rbac/policy.py` | `role_bypasses_scope(role)` | 新增 `user_bypasses_scope(role, username, group_ids)`；保留旧函数作兼容别名（deprecated） |
| 2 | `app/rbac/scope.py` — `build_scope_filter_clause` | 调用 `role_bypasses_scope(role)` | 改为接收 `username, group_ids` 或直接接收 bypass 布尔值 |
| 3 | `app/rbac/scope.py` — `has_scope` | 同上 | 同上 |
| 4 | `app/rbac/scope.py` — `user_can_assign_group` | 同上 | 同上 |
| 5 | `app/main/views.py` — `cron_list` | 多处 `role_bypasses_scope(role)` | 传入 `session username + group_ids` |
| 6 | `app/main/views.py` — `job_log_all_list` | `build_scope_filter_clause(role, group_ids)` | 传入 username |
| 7 | `app/main/views.py` — `operation_log_list` | `role_bypasses_scope(role)` | 传入 username + group\_ids |
| 8 | `app/rbac/context.py` — `get_current_user_groups` | `role_bypasses_scope(role)` 返回 [] | 种子 admin 返回 []；管理员 admin 选「全部」返回 []、选具体组返回组列表 |
| 9 | `app/rbac/authorize.py` — `authorize` | 内部调 `has_scope(role, ...)` | 传入 username |
| 10 | `app/api/__init__.py` — `check_api_scope` | `scope.get('role') == 'admin'` → 放行 | 对用户 token 改为看 `group_ids` 是否为空决定是否全局 |
| 11 | `app/api/views.py` — `_query_scope_context` | `scope.get('role') == 'admin'` → 放行 | 同上 |

### 3.5 管理员 admin 与「用户管理」的 Scope 规则

除了任务/日志/操作记录按组过滤外，「用户管理」功能本身也需要按 Scope 限制：

| 管理操作 | 种子 admin | 管理员 admin（全部） | 管理员 admin（按组） |
| --- | --- | --- | --- |
| 用户列表可见范围 | 全部用户 | 全部用户 | **仅能看到与自己存在组交集的用户**（不含种子 admin） |
| 创建用户 | 可创建任意角色（不含种子 admin）、任意组 | 可创建任意角色、任意组 | **只能将新用户绑定到自己所属的组**；角色不限（可创建 admin / operator / viewer） |
| 编辑用户（角色/组/启停） | 全部（不可编辑自己） | 全部（不可编辑自己） | **仅能编辑与自己有组交集的用户**；且只能在自己所属的组范围内调整用户的组绑定；不可编辑种子 admin |
| 重置密码 | 全部（不可重置自己） | 全部（不可重置自己） | **仅能重置与自己有组交集的用户**（不可重置自己、不可重置种子 admin） |
| 重置 API Token | 全部 | 全部 | **仅能重置与自己有组交集的用户** |
| 停用 / 启用用户 | 全部（不可停用自己） | 全部（不可停用自己） | **仅能操作与自己有组交集的用户**（不可操作种子 admin、不可停用自己） |
| 业务组管理（创建/编辑组） | 可操作全部 | 可操作全部 | **仅能查看和编辑自己所属的业务组**；不能创建新组（创建新组 = 扩展自身权限，应由种子或全局 admin 操作） |

#### 「组交集」判定规则

- 管理员 admin A 所属组为 `[1, 2]`，用户 B 所属组为 `[2, 3]` → 有交集（组 2） → A 可管理 B
- 管理员 admin A 所属组为 `[1, 2]`，用户 C 所属组为 `[3, 4]` → 无交集 → A **不可见/不可管理** C
- 管理员 admin A 所属组为 `[1, 2]`，用户 D（admin、全部）所属组为 `[]` → 无交集 → A **不可见/不可管理** D
- 种子 admin **不展示**在按组管理员的用户列表中（既不可操作也不可见）

#### 实现要点

| # | 文件 | 改动 |
| --- | --- | --- |
| U1 | `app/rbac/services.py` | 新增 `user_in_management_scope(actor_group_ids, target_user_id)` — 查 `user_groups` 判交集 |
| U2 | `app/repositories/rbac_user_repository.py` | 新增 `paginate_by_groups(page_query, group_ids)` — JOIN `user_groups` 过滤；或追加 `scope_filter` 参数 |
| U3 | `app/rbac/views.py` — `users_list` | 按组管理员：调 `paginate_by_groups`（而非 `paginate_all`）+ 加上种子 admin |
| U4 | `app/rbac/views.py` — `users_edit` | 编辑前校验 `user_in_management_scope`；业务组多选框仅展示当前 admin 所属的组 |
| U5 | `app/rbac/views.py` — `users_reset_password` / `users_reset_token` / `users_set_active` | 操作前校验 `user_in_management_scope` |
| U6 | `app/rbac/views.py` — `groups_list` / `groups_edit` / `groups_add` | 按组管理员：列表/编辑仅展示所属组；隐藏创建入口 |
| U7 | `app/rbac/views.py` — `users_add` | 业务组多选框仅展示当前 admin 所属的组 |

### 3.6 创建/编辑用户页面交互

| 场景 | 当前行为 | 改后行为 |
| --- | --- | --- |
| 角色选 `admin` 时的业务组 | 允许不选（灰字提示"admin 可不选"） | 必须选择「全部」或至少 1 个具体组；灰字提示改为"选择「全部」即全局权限；否则请至少选择一个业务组" |
| 选了「全部」后再选具体组 | N/A | JS 自动取消「全部」；反之亦然（互斥） |
| admin 不选任何组就提交 | 允许保存 | 后端拦截并返回"管理员必须选择「全部」或至少一个业务组" |
| 编辑种子 `admin` 账号的业务组 | 种子不可在用户管理编辑自己 | 不变；种子永远全局，不显示业务组选择（如因故进入编辑页，业务组选择框显示为 disabled + "系统管理员始终为全局权限"） |
| 按组管理员创建用户时的业务组可选范围 | 展示全部组 | 仅展示当前管理员所属的组（不含「全部」选项）；不可将用户绑定到超出自身 Scope 的组 |
| 按组管理员编辑用户时的业务组可选范围 | 展示全部组 | 仅展示当前管理员所属的组；该用户在 admin Scope 外的组绑定**保留不变**（不可增删 Scope 外的绑定） |
| 按组管理员创建新 admin 用户 | 可创建 | 可创建，但新 admin 的业务组范围**不超出**创建者的组；不可选「全部」 |

### 3.7 `validate_groups_for_role` 服务层改动

```
# 改动前
def role_requires_groups(role):
    return (role or '') != 'admin'

# 改动后
def role_requires_groups(role, username=None):
    """所有角色都须选择业务组；种子 admin 豁免。"""
    if is_seed_admin_username(username):
        return False
    return True
```

`validate_groups_for_role` 改动：

```
def validate_groups_for_role(role, group_ids, username=None):
    if not role_requires_groups(role, username):
        return ''
    # 检查是否含 __ALL__
    has_all = '__ALL__' in [str(g) for g in (group_ids or [])]
    real_ids = [g for g in (group_ids or []) if str(g) != '__ALL__']
    if has_all and real_ids:
        return '「全部」与具体业务组不能同时选择'
    if has_all:
        return ''   # 选了「全部」→ 合法（group_ids 清空为 []）
    # 未选「全部」→ 至少选一个具体组
    cleaned = []
    for g in real_ids:
        try:
            cleaned.append(int(g))
        except (TypeError, ValueError):
            return '业务组参数无效'
    if not cleaned:
        return '管理员必须选择「全部」或至少一个业务组'
    return ''
```

### 3.8 `set_user_groups` 改动

- 若 `group_ids` 包含 `__ALL__`：删除该用户所有 `user_groups` 行（表示全局）。
- 若 `group_ids` 为具体 id 列表：按现有逻辑 diff 写入。

## 四、范围（改什么、不改什么）

### 改

| 路径 | 改动类型 |
| --- | --- |
| `app/rbac/policy.py` | 新增 `user_bypasses_scope()` |
| `app/rbac/scope.py` | 所有 bypass 判定改为接收 username/group\_ids |
| `app/rbac/services.py` | `validate_groups_for_role` + `set_user_groups` + `role_requires_groups` + 新增 `user_in_management_scope` |
| `app/rbac/views.py` | 创建/编辑用户路由传入 username；用户列表/编辑/重置/启停加 Scope 校验；业务组管理按组限制 |
| `app/repositories/rbac_user_repository.py` | 新增 `paginate_by_groups()` — 按组过滤用户列表 |
| `app/rbac/context.py` | `get_current_user_groups()` 改判定 |
| `app/rbac/authorize.py` | `authorize()` 传 username |
| `app/main/views.py` | 所有 `role_bypasses_scope` 调用点适配 |
| `app/api/__init__.py` | `check_api_scope` 按 group\_ids 判定 |
| `app/api/views.py` | `_query_scope_context` 适配 |
| `app/templates/rbac/users_add.html` | 增加「全部」选项 + JS 互斥 |
| `app/templates/rbac/users_edit.html` | 同上 |
| `tests/test_rbac_scope.py` | 覆盖两类 admin Scope 差异 |
| `tests/test_api_scope_s6.py` | 覆盖管理员 admin 用户 token 的 Scope |

### 不改

- 种子 admin 的 Permission 裁剪（`SEED_ADMIN_PERMISSIONS`）保持不变。
- viewer / operator 的 Scope 逻辑保持不变。
- 任务 `scope_type` / `group_id` 字段与模型不变。
- 审计日志（`rbac_audit_logs`）Scope 过滤已在 OPT-P2-16 独立交付（方案 A · 按操作者组过滤）。

## 五、分批

| 批次 | 内容 | 验收标准 |
| --- | --- | --- |
| **Batch 1** 后端鉴权 | - `policy.py`：`user_bypasses_scope()` - `scope.py`：所有 bypass 判定改签名 - `services.py`：`validate_groups_for_role` + `set_user_groups` - `authorize.py`：传 username - `context.py`：顶栏组展示适配 - 测试：`test_rbac_scope.py` 新增两类 admin 用例 | `bash scripts/cronpilot.sh test` 通过；  新测试断言：种子 admin bypass=True、管理员 admin 无组 bypass=True、管理员 admin 有组 bypass=False |
| **Batch 2** 任务/日志 Web 视图 | - `main/views.py`：所有 `role_bypasses_scope` 替换（任务列表、执行日志、操作记录） - `users_add.html` / `users_edit.html`：增加「全部」选项 + JS 互斥 - `rbac/views.py`：创建/编辑用户时传入 username + 校验 `__ALL__` | `bash scripts/cronpilot.sh test` 通过；  `restart` 后浏览器验收：管理员 admin 绑 1 组 → 只能看到该组 + GLOBAL 任务/日志/操作记录；选「全部」→ 全局可见 |
| **Batch 3** 用户管理 Scope | - `services.py`：新增 `user_in_management_scope()` - `rbac_user_repository.py`：新增 `paginate_by_groups()` - `rbac/views.py`：`users_list` 按组过滤；`users_edit`/`reset_password`/`reset_token`/`set_active` 加 Scope 校验 - `rbac/views.py`：`groups_list`/`groups_edit`/`groups_add` 按组管理员限制 - 测试：管理员 admin 只能看到/操作组交集内的用户 | `bash scripts/cronpilot.sh test` 通过；  管理员 admin（组 [1,2]）登录 → 用户列表仅展示组交集用户 + 种子 admin；无法编辑/重置无交集用户；业务组列表仅展示所属组 |
| **Batch 4** API 鉴权适配 | - `api/__init__.py`：`check_api_scope` 改判定 - `api/views.py`：`_query_scope_context` 适配 - `test_api_scope_s6.py`：新增管理员 admin token 的 Scope 用例 | `bash scripts/cronpilot.sh test` 通过；  管理员 admin 的 token 按组隔离；选「全部」的 admin token 全局可见 |

## 六、验收

### 6.1 角色 × 页面/API 权限矩阵（改后预期）

| 页面 / 接口 | 种子 admin `username='admin'` | 管理员 admin（全部） `group_ids=[]` | 管理员 admin（按组） `group_ids=[1,2]` | operator | viewer |
| --- | --- | --- | --- | --- | --- |
| 任务列表 | 全局（只读） | 全局 | GLOBAL + 组 1,2 | GLOBAL + 所属组 | GLOBAL + 所属组 |
| 任务写/下线 | ❌ 无权限 | ✅ 全局 | ✅ 仅组 1,2 + GLOBAL | ✅ 写（无下线）仅所属组 | ❌ 无权限 |
| 执行日志列表 | 全局（只读） | 全局 | GLOBAL + 组 1,2 | GLOBAL + 所属组 | GLOBAL + 所属组 |
| 操作记录 | 全局（只读） | 全局 | 仅组 1,2 + GLOBAL 的任务记录 | 仅所属组 + GLOBAL | ❌ 无权限 |
| 审计日志 | 全局 | 全局 | 全局（本批次不按组过滤，见风险） | ❌ 无权限 | ❌ 无权限 |
| 用户管理 — 可见范围 | 全部用户 | 全部用户 | 仅组交集用户（不含种子 admin） | ❌ 无权限 | ❌ 无权限 |
| 用户管理 — 可操作范围 | 全部（不可编辑自己） | 全部（不可编辑自己） | 仅组交集用户（不可操作种子 admin、不可操作无交集用户） | ❌ | ❌ |
| 业务组管理 | 全部 | 全部 | 仅查看/编辑所属组；不可创建新组 | ❌ | ❌ |
| API（用户 token） | N/A（种子不做 API 调用） | 全局 | 仅 GLOBAL + 组 1,2 | 仅所属组 | 仅所属组 |

### 6.2 最低验收命令

- `bash scripts/cronpilot.sh test`
- `bash scripts/verify_golden_path.sh`
- `python scripts/audit_hardcoded_colors.py --check`
- `python scripts/html_docs_to_markdown.py --check`
- `bash scripts/cronpilot.sh restart --daemon` → 浏览器走通上述矩阵关键路径

## 七、风险

| 风险 | 影响 | 缓解 |
| --- | --- | --- |
| `role_bypasses_scope` 改签名涉及 11+ 调用点 | 遗漏某处则该页面行为不一致 | Batch 1 先改底层 + 测试覆盖；Batch 2 逐个视图替换并 restart 验收 |
| 存量管理员 admin 无业务组记录 → 默认行为变化 | 升级后这些 admin 变为"全局可见"（与之前一致），因为 `group_ids = []` | **无破坏**：与现行行为一致（之前也是全局）。种子创建新 admin 时才强制选组 |
| 审计日志（`rbac_audit_logs`）无 `group_id` 字段 | 本批次不做审计日志的 Scope 过滤；管理员 admin 即使绑了组，审计日志仍全局可见 | 如需限制审计日志，需新增 `rbac_audit_logs.scope_group_id`（或关联操作人组），作为独立 RFC 排期 |
| Session 中 `group_ids` 在登录时写入 | 管理员 admin 的组变更后须重新登录才生效 | 与现有 viewer/operator 行为一致，无额外风险 |
| 按组管理员编辑用户时，被编辑用户可能同时属于 admin Scope 外的组 | 如不妥善处理，admin 可能误删用户在 Scope 外的组绑定 | 后端仅 diff admin 可见的组（`actor_group_ids ∩ target_group_ids`），**保留** Scope 外的绑定不变 |
| 按组管理员可创建新 admin，该 admin 可进一步管理用户 | 权限传递链：admin A → 创建 admin B → B 可管理 A 可见范围内的用户 | B 的组范围不超出 A 的范围（后端强制校验）；权限传递在 Scope 内闭合 |

## 八、与现有文档的一致性

- 改后需同步更新：`doc/资源隔离与Scope设计.html`、`doc/RBAC架构设计方案.html`、`AGENTS.md`、`.cursor/rules/rbac.mdc`
- 路线图 `doc/交付状态与路线图.html` 增加本项条目
- 如纳入版本发布，更新 `RELEASE_NOTES.md`

[文档索引](../index.html) · [Markdown](管理员admin-Scope差异化设计.md) · [索引](../index.html)

---

[← 文档索引（HTML）](../index.html) · [← 文档索引（Markdown）](../index.md)
