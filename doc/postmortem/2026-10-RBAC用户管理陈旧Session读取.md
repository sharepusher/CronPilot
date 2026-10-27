# RBAC 用户管理陈旧 Session 读取复盘

> HTML 版：[2026-10-RBAC用户管理陈旧Session读取.html](2026-10-RBAC用户管理陈旧Session读取.html) · [文档索引](../index.html) · [索引 Markdown](../index.md)

# RBAC 用户管理陈旧 Session 读取复盘

日期：2026-10-27 · 问题：R-02 · 状态：已修复、待完整交付验证

## 1. Bug 定位

`/rbac/users`、新增、编辑、详情、密码重置、Token 重置和停用共 7 个入口曾以 Cookie 的 `role`/`group_ids` 决定功能权限与对象范围。数据库已将 global admin 收窄到组 A 或降为 viewer 后，旧 Cookie 仍可能读取组 B 用户或进入管理入口。

## 2. 根因

授权事实分裂：路由层与通用 `require_permission` 信任登录时快照，虽然服务层已有数据库当前 actor 解析器，却没有成为用户管理读取面的强制前置条件。编辑页还将角色、组和资料分多次 commit，无法安全地把授权改变与会话撤销绑定为一个状态转换。

## 3. 测试漏洞

原测试只验证当前登录 Session 和常规 Scope，没有构造“Cookie 仍是 global/admin、数据库已收窄/降权”的时间差状态；也没有逐一枚举 7 个入口，因此列表修复仍可能遗漏详情或敏感 POST。

## 4. 修复

新增请求级 `current_user_management_actor_scope()`，只以 Session 的 user\_id 查询数据库当前角色、组和 bypass；新增专用 guard，在目标用户读取前 fail-closed 地处理停用/缺失（清 Session）、无权限（403）与授权查询失败（500）。7 个入口统一消费该 context。新增 `update_user_management()`，单次事务写入角色、业务组、资料和 auth\_version；角色/组变更或停用只 bump 一次，成功后才审计和失效 API scope 缓存。

## 5. 防护测试

`TestUserManagementCurrentActorRedLines` 覆盖 global→组 A 后范围外列表、详情与 Token 重置拒绝；admin→viewer 后 7 个入口全部 403；以及角色/组变更恰好一次 auth\_version bump、资料-only 不 bump。既有 Session 缺键、版本不匹配与一次性 bump 矩阵也已回归。Playwright 的自清理浏览器 fixture 还实际保留 Cookie 后执行 global→组 A→viewer 路径，断言范围外详情重定向与最终 403，并保存截图与 JSON 证据。

## 6. 同类排查

注册审批读取面已独立使用数据库当前 actor，拒绝写入口也已闭环。本次刻意未修改组管理、标签管理、审计日志等入口的 Session 语义，避免把用户管理专用 context 错用于其他策略；它们须在各自正式设计中单独评估。

## 7. 预防方案

- 在 `tests/test_rbac_global_scope_assignment.py` 固化“数据库降权 + 陈旧 Cookie”矩阵，并将 7 个用户管理入口列为同一测试的显式清单；第三方可运行 `python -m unittest tests.test_rbac_global_scope_assignment.TestUserManagementCurrentActorRedLines -v` 验证。
- 在 `app/rbac/decorators.py` 保持用户管理专用 guard，禁止新用户管理路由退回通用 Session-only guard；新增入口时以该 7 项清单审查。
- 在 `app/rbac/services.py::update_user_management()` 维持单提交与单次版本 bump 契约；第三方可运行 `python -m unittest tests.test_user_reactivation.TestAuthVersionOneTimeBump -v` 复验基础版本语义。

[复盘索引](index.html) · [Markdown](2026-10-RBAC用户管理陈旧Session读取.md) · [正式设计](../design/RBAC用户管理数据库当前授权与Session撤销方案-2026-10.html)

---

[← 文档索引（HTML）](../index.html) · [← 文档索引（Markdown）](../index.md)
