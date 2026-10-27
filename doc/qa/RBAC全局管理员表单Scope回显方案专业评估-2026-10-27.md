# RBAC 全局管理员表单 Scope 回显方案专业评估

> HTML 版：[RBAC全局管理员表单Scope回显方案专业评估-2026-10-27.html](RBAC全局管理员表单Scope回显方案专业评估-2026-10-27.html) · [文档索引](../index.html) · [索引 Markdown](../index.md)

# RBAC 全局管理员表单 Scope 回显方案专业评估

日期：2026-10-27 · 对象：[独立优化方案](../design/RBAC全局管理员表单Scope回显优化方案-2026-10.html)

## 结论

**A / 可实施。**问题判断准确：无 UserGroup 关联行是 global Scope 的既有持久化语义，而 UI 直接把该空集合用于 option selected 判定，造成表示层丢失。推荐方案只做 ViewModel 映射，不改变授权事实。

## 维度评估

| 维度 | 结论 |
| --- | --- |
| 专业性 | 将存储、授权和展示语义分层；复用 policy 中的权威判定而非复制 if 条件。 |
| 准确性 | 高。`_replace_user_groups_in_session()` 已明确 `__ALL__` 表示零关联行，`user_bypasses_scope()` 精确表示 global Scope。 |
| 合理性 | 高。局限在编辑页 Context；不迁移数据、不新增数据库哨兵值、不触碰写入安全边界。 |
| 风险 | 低。唯一关键是禁止以“空组”单独判断，必须调用 `user_bypasses_scope()`，并锁定 non-admin 无组反例。 |

## 实施条件

1. 先落地 global admin 回显红线和具体组 admin 反例。
2. 提交后验证“\_\_ALL\_\_ selected”而非仅验证 option 存在。
3. 浏览器覆盖读取、保存无修改后仍为 global，确保 ViewModel marker 未泄漏到存储层。
[文档索引](../index.html) · [Markdown](RBAC全局管理员表单Scope回显方案专业评估-2026-10-27.md)

---

[← 文档索引（HTML）](../index.html) · [← 文档索引（Markdown）](../index.md)
