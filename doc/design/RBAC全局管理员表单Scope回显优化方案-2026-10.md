# RBAC 全局管理员表单 Scope 回显优化方案

> HTML 版：[RBAC全局管理员表单Scope回显优化方案-2026-10.html](RBAC全局管理员表单Scope回显优化方案-2026-10.html) · [文档索引](../index.html) · [索引 Markdown](../index.md)

# RBAC 全局管理员表单 Scope 回显优化方案

日期：2026-10-27 · 状态：**已确认、已实施、已验证**

## 1. 问题与根因

编辑非种子 global admin 时，数据库以“无 UserGroup 绑定行”表达全局 Scope；`get_user_group_ids_for_user()` 因此返回空列表。`user_form.html` 却只在该列表含字符串 `__ALL__` 时选中“全部（全局权限）”，导致表单没有任何选中项，视觉上误导为未配置 Scope，并可能让后续提交意外降为具体组。

根因是存储语义（无关联行）与表单语义（`__ALL__` marker）未在 ViewModel 边界转换，不是数据迁移、权限判定或服务写入的问题。

## 2. 推荐方案

1. 在 `users_edit()` 构建 `edit_ctx` 时新增仅供表单回显的规范化字段：先读取真实 group\_ids；再调用已验证的 `user_bypasses_scope(user.role, username=user.username, group_ids=...)`。若为全局 Scope，则返回 `['__ALL__']`，否则保留真实具体组 ID。
2. 模板继续只消费 `user_group_ids`，无需修改提交字段、JS 互斥行为、数据库或授权服务。
3. 详情只读页继续展示名称映射；本批不把 `__ALL__` 持久化为 UserGroup 行，避免改变“无绑定行 = global”的现有授权契约。

## 3. 范围与分批

| 包含 | 不包含 |
| --- | --- |
| 编辑表单的全局 Scope 选中状态；seed/global admin、具体组 admin、非 admin/异常数据的回归。 | 角色权限、数据库结构、UserGroup 存储语义、提交 API 或新增页面布局。 |

1. B0：先加全局 admin GET 编辑页红线断言。
2. B1：在 ViewModel 边界做无绑定行→`__ALL__` 映射。
3. B2：专项回归、浏览器表单截图、文档和复盘。

## 4. 验收标准

- 非种子 global admin 编辑页中 `<option value="__ALL__" selected>` 唯一存在，具体组均不选中。
- 有具体组的 admin 仍只选中其组，且不出现 `__ALL__` selected。
- 作用域受限管理员不能看到 global option；POST 现有 Scope 授权、CSRF 与 auth\_version 契约不变。
- 通过专项测试、Ruff、路由冒烟和实际浏览器表单检查。

## 5. 风险与控制

| 风险 | 控制 |
| --- | --- |
| 把无组的异常 non-admin 错当 global | 仅以既有 `user_bypasses_scope` 判定；它要求 admin（或种子）且无组。 |
| 前端 marker 与持久化混淆 | marker 仅在 edit ViewModel 存在；服务仍将 `__ALL__` 规范化为零关联行。 |
| 修复回显却放大授权 | 不触碰 `validate_user_scope_assignment()`、路由 guard 或提交逻辑，并保留反向用例。 |

## 6. Before / After 页面行为对比

### BEFORE

global admin 无 UserGroup 行；编辑页“业务组”下拉中的“全部（全局权限）”未被选中，用户看到空选择。

### AFTER

同一数据不变；编辑页仅选中“全部（全局权限）”，具体组不选中。保存后仍写回零关联行。

## 7. 专业评估摘要

**A，建议实施。**该方案将存储表示转换限制在展示边界，复用已有的全局 Scope 权威判定，变更面小且不改变安全策略。相较于在数据库插入伪 `__ALL__` 关联行或仅在 Jinja 中用“空列表”猜测，全局判定可避免把异常无组用户误展示为全局权限。

## 8. 实施与验证

已新增 `_form_group_ids_for_user()`，它先读取真实组关联，再复用 `user_bypasses_scope()` 将全局用户映射为表单 marker `__ALL__`；普通用户保持真实具体组。编辑成功或失败后的回渲染同样使用该函数。专项页面回归 7 项、Ruff、路由完整性检查和本地 Playwright 浏览器矩阵均通过；浏览器证据位于 `doc/qa/evidence/rbac-user-management-r02-2026-10-27/`。

[文档索引](../index.html) · [Markdown](RBAC全局管理员表单Scope回显优化方案-2026-10.md)

---

[← 文档索引（HTML）](../index.html) · [← 文档索引（Markdown）](../index.md)
