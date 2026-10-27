# RBAC 用户管理数据库当前授权与 Session 撤销方案（2026-10）

> HTML 版：[RBAC用户管理数据库当前授权与Session撤销方案-2026-10.html](RBAC用户管理数据库当前授权与Session撤销方案-2026-10.html) · [文档索引](../index.html) · [索引 Markdown](../index.md)

# RBAC 用户管理数据库当前授权与 Session 撤销方案

版本：rev.2 · 日期：2026-10-27 · 状态：**已确认、已实施、验证中** · 来源：[R-02](RBAC四项Review问题闭环优化方案-2026-10.html#5-r-02用户管理数据库当前授权与-session-撤销) · 前置审查：[Bugbot P1](../qa/当前未提交代码与方案Bugbot专业评估-2026-10-26.html)

## 1. 问题

当前用户管理读取面把 Cookie 中的 `role`、`group_ids` 当作授权事实。数据库把一个 global admin 降为组 A admin，或把多组 admin 收窄到组 A 后，旧 Session 仍可在 `/rbac/users` 的列表、计数、分页、可选业务组、详情和目标操作范围中使用变更前的权限。`web_session_user_is_valid()` 仅校验账号启用和 `auth_version`；而角色/组变更没有可靠地在同一事务 bump 该版本。

**等级：P1。**这是对象读取与管理能力的授权事实分裂：受限后的旧 Cookie 可能继续发现范围外用户，或向范围外对象发起查看、编辑、重置密码、重置 Token、停用等请求。

## 2. 根因

1. `app/rbac/views.py` 的 `_actor_bypasses_scope()`、`_check_management_scope()`、用户列表和表单组筛选直接读 Session。
2. `@require_permission('user:manage')` 也只按 Session 角色判断，数据库已降为 viewer 的 Cookie 仍可进入用户管理处理器。
3. 现有 `resolve_user_management_actor()` 已能读取数据库当前 role、username、group\_ids、bypass，但只被注册审批读面和部分写入校验消费。
4. `users_edit()` 目前分开提交 role、组和资料；在各处简单加 `auth_version` bump 会造成重复 bump 或半提交。

## 3. 推荐方案

### 3.1 第一层：请求内数据库当前 actor（立即收口）

1. 新增请求级 `current_user_management_actor_scope()`：通过 Flask `g` 仅调用一次现有 `resolve_user_management_actor(session.user_id)`；不读取 Session 的 role/group\_ids。
2. 新增专用守卫 `@require_user_management_actor`，覆盖 7 个用户管理入口：`/users`、`/users/add`、`/users/edit`、`/users/view`、`/users/reset_password`、`/users/reset_token`、`/users/set_active`。actor 缺失/停用：清 Session 后跳登录；当前无 `user:manage`：受控 403；授权读取失败：通用 500；均不得回退 Session。
3. 上述入口把列表/计数/分页、表单可选组、bypass、目标范围检查全部改从同一 context 取值。目标读取须在守卫之后，避免通过范围外 ID 枚举用户存在性。
4. 保留 `validate_user_scope_assignment()` 作为写服务的最终边界；路由 context 是读取面防线，服务校验是纵深防御。

### 3.2 第二层：授权变更原子撤销（全站收敛）

1. 将用户编辑归并为单一事务服务：在同一 commit 中写入 role、UserGroup 集合、资料与会话版本。
2. 仅当 role 或规范化后的组集合实际变化时，对目标用户 `auth_version` 增加一次；资料-only/no-op 不 bump。
3. commit 成功后写审计并失效 API Scope 缓存；失败 rollback，不能出现“已撤销 Session 但授权数据未落库”或相反状态。
4. 下一请求由现有 `web_session_user_is_valid()` 发现版本不匹配，清理旧 Cookie；这同时收敛尚未迁移到数据库 context 的导航与其他页面。

## 4. 范围

| 包含 | 不包含 |
| --- | --- |
| 用户列表、详情、编辑、新增、重置密码、重置 Token、停用；数据库当前 actor；用户编辑授权变更的单事务版本撤销；专项 HTTP/浏览器测试。 | 注册审批拒绝（已闭环）；组管理、标签管理、审计日志的陈旧 Session 读取（另立 Scope）；RBAC 角色模型与权限字符串变更。 |

## 5. 分批实施

| 批次 | 工作 | 停止条件 |
| --- | --- | --- |
| B0 | 红线测试：global→scoped、组收窄、admin→viewer 后的列表、详情、编辑、密码/Token 重置、停用。 | 旧实现能复现越界或陈旧 200，且断言无业务写入。 |
| B1 | 请求级 context + 专用守卫；迁移 7 个用户入口。 | 所有读取与目标检查只使用 context；DB 查询失败 fail-closed。 |
| B2 | 用户编辑单事务 + 一次性 auth\_version bump + 缓存失效。 | 角色/组变化一次 bump；资料-only/no-op 不 bump；失败完全 rollback。 |
| B3 | 浏览器正反路径、路由/文档/复盘收口。 | 目标角色验证与全部门禁通过。 |

## 6. 验收标准

- 数据库 global→组 A：持有旧 global Cookie 的用户列表 total、详情与编辑均不能看见/操作组 B；AJAX 同样受限。
- 数据库 admin→viewer：7 个入口均返回受控 403 或登录失效，不暴露范围外用户存在性。
- 角色或组真实变更使旧 Cookie 下一请求失效；资料-only 与 no-op 不改变 auth\_version。
- 用户编辑任一落库失败时 role、组、资料、auth\_version、缓存和审计保持原状态。
- 目标角色浏览器覆盖 global、scoped、被降权 Cookie 的正反路径；测试临时数据清理为零。
- 通过 `tests.test_rbac_global_scope_assignment`、用户再激活/Session 矩阵、86 路由冒烟、Ruff、文档同步与链接门禁。

## 7. 风险与控制

| 风险 | 控制 |
| --- | --- |
| 仅改列表仍让敏感操作越权 | 以 7 个入口清单和 route-level guard 做完整性门禁。 |
| 只 bump 版本导致窗口或遗漏写入口 | 请求内 DB-current 授权与版本撤销双层防御。 |
| 多次 commit 导致部分更新/重复 bump | B2 先建立单事务服务，禁止在旧函数分别追加 bump。 |
| 数据库故障退回 Cookie | 统一返回 500/403，不以 Session 兜底。 |

## 8. Before / After 页面行为对比

### BEFORE · 旧 global Cookie

数据库已将管理员收窄为组 A。

**用户管理页：**仍显示组 A + 组 B 用户和总数；可提交组 B 用户详情/重置请求。

### AFTER · 数据库当前 actor

同一 Cookie 请求用户管理入口。

**用户管理页：**仅显示组 A；组 B ID 的详情、编辑、重置、停用一律受控拒绝；若角色已降为 viewer，入口统一 403/失效。

## 9. 专业评估

**结论：A-，可实施，但 B1 与 B2 必须一起交付。**数据库当前 context 直接修复当前读取越权，且复用已验证的 `resolve_user_management_actor()`，准确、最小且可测试；一次性 `auth_version` bump 解决其他 Session 消费面的滞后。只做其中任一层均不完整：前者不能收敛全站陈旧 UI，后者依赖所有变更入口永不遗漏。最大实现风险是既有 `users_edit()` 的多提交结构，故方案明确先原子化再 bump，避免安全修复制造一致性回归。

## 10. 实施记录

**B0–B3 已完成。**新增 `user_management_scope.py` 请求级数据库当前 actor context 和 `@require_user_management_actor`，7 个入口均在目标对象读取前完成当前权限判定。用户编辑改用 `update_user_management()`，一次事务更新角色、组、资料与 auth\_version；角色/组真实变化只 bump 一次，资料-only 不 bump。

已通过：用户管理陈旧 Session 专项 7 项、既有 auth\_version Session 矩阵 4 项、`ruff check app/`、86 路由冒烟、文档同步/完整性/链接门禁。Playwright 本地浏览器矩阵以自清理 fixture 验证：global 初始可见组 A/B，数据库收窄后仅组 A 可见且组 B 详情重定向，随后角色降为 viewer 后用户管理 403；证据位于 `doc/qa/evidence/rbac-user-management-r02-2026-10-27/`。

[文档索引](../index.html) · [Markdown](RBAC用户管理数据库当前授权与Session撤销方案-2026-10.md)

---

[← 文档索引（HTML）](../index.html) · [← 文档索引（Markdown）](../index.md)
