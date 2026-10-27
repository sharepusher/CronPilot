# RBAC 全局管理员表单 Scope 回显缺失复盘

> HTML 版：[2026-10-RBAC全局管理员表单Scope回显缺失.html](2026-10-RBAC全局管理员表单Scope回显缺失.html) · [文档索引](../index.html) · [索引 Markdown](../index.md)

# RBAC 全局管理员表单 Scope 回显缺失复盘

日期：2026-10-27 · 状态：已修复并验证

## 1. Bug 定位

`/rbac/users/edit` 编辑 non-seed global admin 时，业务组多选框没有选中“全部（全局权限）”。

## 2. 根因

数据库以零条 `UserGroup` 关联表示 global Scope，而模板只把显式 `__ALL__` 当作 selected 值；持久化表示直接穿透到 UI，丢失了表单所需语义。

## 3. 测试漏洞

原页面测试只验证 global option 是否存在，未验证其 selected 状态，也没有构造“admin + 零关联行”的目标用户。

## 4. 修复

新增 `_form_group_ids_for_user()`。它读取真实组 ID 后调用 `user_bypasses_scope()`；仅权威 policy 判定为 global 时返回 `['__ALL__']`。该转换仅用于编辑表单 Context，未修改数据库、写服务或授权校验。

## 5. 防护测试

新增红线断言：零关联行 global admin 的组选择框必须仅选中 `__ALL__`，具体组不得 selected。页面 Scope 契约 7 项全部通过；Playwright fixture 实际打开编辑页并验证 option selected，同时复跑陈旧 Session 场景。

## 6. 同类排查

新增用户页不需要回显目标用户 Scope；详情页使用名称展示；服务层继续把 `__ALL__` 规范化为零关联行。本批未发现需要迁移的数据或其他表单存储语义泄漏。

## 7. 预防方案

- 在 `tests/test_rbac_global_scope_assignment.py::TestGlobalScopeAssignmentPageExposure` 固化 selected 而非仅 option 存在的断言；运行 `python -m unittest tests.test_rbac_global_scope_assignment.TestGlobalScopeAssignmentPageExposure -v` 可复验。
- 所有“特殊持久化表示→表单 marker”转换必须放在 ViewModel helper，并调用既有 policy；禁止在 Jinja 中以空集合猜测权限。
- 浏览器脚本 `scripts/verify_user_management_stale_session_browser.py` 将 global 表单选中状态纳入自清理 E2E 证据。

[复盘索引](index.html) · [Markdown](2026-10-RBAC全局管理员表单Scope回显缺失.md) · [正式设计](../design/RBAC全局管理员表单Scope回显优化方案-2026-10.html)

---

[← 文档索引（HTML）](../index.html) · [← 文档索引（Markdown）](../index.md)
