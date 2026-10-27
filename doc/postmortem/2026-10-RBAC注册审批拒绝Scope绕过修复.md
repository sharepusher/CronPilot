# RBAC 注册审批拒绝 Scope 绕过修复复盘（2026-10-27）

> HTML 版：[2026-10-RBAC注册审批拒绝Scope绕过修复.html](2026-10-RBAC注册审批拒绝Scope绕过修复.html) · [文档索引](../index.html) · [索引 Markdown](../index.md)

# RBAC 注册审批拒绝 Scope 绕过修复复盘

日期：2026-10-27 · 等级：P1 · 状态：已修复并验证

## 1. Bug 定位

`app/rbac/services.py::reject_registration` 仅按申请 ID 更新 pending 记录；`/rbac/registration_review/reject` 和 `/batch_reject` 因而均可让已登录、但 Scope 受限的管理员拒绝范围外或 `__ALL__` 申请。

## 2. 根因

拒绝被错误建模为普通状态更新。路由的 `user:manage` 功能权限被当作对象级授权，服务层没有读取数据库当前 actor、没有还原申请 Scope，也没有成为入口不可绕过的最终防线。

## 3. 测试漏洞

原有测试覆盖拒绝成功、已处理和提交异常，却未覆盖“知道范围外 ID”的单条/批量 POST、`__ALL__`、管理员部分子集、关联表漂移和数据库降权后的陈旧 Session。

## 4. 修复

- `reject_registration` 强制接收 `reviewer_id`，使用行锁读取申请，并将 reviewer 归因到显式 actor。
- 新增数据库当前 actor 与申请 Scope 授权 helper：viewer/operator 请求按组交集；admin 请求按完整非空子集；scoped actor 对全局、范围外或异常申请 fail-closed。
- 仅 seed/global admin 可关闭 CSV/关联表漂移等异常遗留申请；成功审计标注治理分支，拒绝审计仅记录 request ID 和稳定 reason code。
- 单条、批量入口均显式传递 Session actor，并复用同一服务边界。

## 5. 防护测试

| 场景 | 断言 |
| --- | --- |
| 组外、全局、admin 部分覆盖、关联漂移 | 响应受控失败，申请保持 pending。 |
| viewer 组交集 | scoped admin 可拒绝。 |
| 混合批量 | 仅允许项变更，返回 partial\_failure。 |
| 数据库降权 | 陈旧的全局 Session 不会保留拒绝权限。 |
| 全局异常治理 | global admin 可关闭关联漂移申请。 |

## 6. 同类排查

已确认批准入口已读取数据库当前 actor 并有 Scope 校验；本次继续使用其存储一致性检查，未发现其他注册审批拒绝入口。全仓调用搜索限定了 `reject_registration` 的服务签名调用点，避免遗漏显式 actor 传递。

## 7. 预防方案

**可验证防护：**在 `tests/test_rbac_global_scope_assignment.py::TestRegistrationApprovalScopeClosure` 固化单条、批量、异常和陈旧 Session 的拒绝矩阵；后续任何变更均执行 `.venv-py311/bin/python -m unittest tests.test_rbac_global_scope_assignment.TestRegistrationApprovalScopeClosure -v`。服务签名去除隐式 Session actor，使未更新的入口在调用时直接失败，而非静默绕过。

关联设计：[RBAC 注册审批拒绝 Scope 授权闭环方案](../design/RBAC注册审批拒绝Scope授权闭环方案-2026-10.html)。

[文档索引](index.html) · [Markdown](2026-10-RBAC注册审批拒绝Scope绕过修复.md) · [索引](index.html)

---

[← 文档索引（HTML）](../index.html) · [← 文档索引（Markdown）](../index.md)
