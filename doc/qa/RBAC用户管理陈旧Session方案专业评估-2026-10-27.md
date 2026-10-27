# RBAC 用户管理陈旧 Session 方案专业评估（2026-10-27）

> HTML 版：[RBAC用户管理陈旧Session方案专业评估-2026-10-27.html](RBAC用户管理陈旧Session方案专业评估-2026-10-27.html) · [文档索引](../index.html) · [索引 Markdown](../index.md)

# RBAC 用户管理陈旧 Session 方案专业评估

日期：2026-10-27 · 对象：[独立方案 rev.1](../design/RBAC用户管理数据库当前授权与Session撤销方案-2026-10.html)

## 结论

**A- / 条件通过。**方案对问题定性、授权边界和事务风险的判断准确；在 B1 请求内数据库当前授权与 B2 原子会话撤销均完成、并通过完整入口矩阵前，不应宣布 R-02 关闭。

## 维度评估

| 维度 | 结论 |
| --- | --- |
| 准确性 | 高。现有 `resolve_user_management_actor()` 的确从 DB 获取 role/group\_ids；用户管理路由和 `@require_permission` 的确仍读 Session。 |
| 专业性 | 高。区分功能权限、对象 Scope、请求内授权与会话撤销；明确 fail-closed 和信息枚举边界。 |
| 合理性 | 高。复用既有 actor resolver，限定 7 个入口，避免无界重构；以单事务防止重复 bump/半提交。 |
| 可验证性 | 高。验收包含 global 降权、组收窄、角色降权、失败 rollback、no-op 和真实浏览器 Cookie。 |

## 必须遵守的实施条件

1. 守卫必须在按 ID 读取目标用户之前执行，不能仅在页面模板隐藏数据。
2. 所有 7 个入口须迁移；遗漏 reset\_token 或 set\_active 仍构成 P1。
3. 禁止在 `update_user()`、`set_user_groups()` 等旧多提交函数各自 bump 版本。
4. 授权读取异常必须 500/拒绝，不能降级使用 Cookie。

## 不推荐替代方案

仅清 Session、只改用户列表、或只在 Session role 不符时隐藏导航都不能保证对象读取和敏感操作安全，不能作为本问题的修复结论。

[文档索引](../index.html) · [Markdown](RBAC用户管理陈旧Session方案专业评估-2026-10-27.md)

---

[← 文档索引（HTML）](../index.html) · [← 文档索引（Markdown）](../index.md)
