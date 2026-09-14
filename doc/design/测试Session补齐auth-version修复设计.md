# 测试 Session 补齐 auth_version 修复设计

> HTML 版：[测试Session补齐auth-version修复设计.html](测试Session补齐auth-version修复设计.html) · [文档索引](../index.html) · [索引 Markdown](../index.md)

# 测试 Session 补齐 auth\_version 修复设计

**日期**：2026-09-09　**类型**：Bugbot P1 修复设计　**状态**：已交付（2026-09-11：定向回归 21 项通过）

## 1. 问题

Bugbot 发现，认证中间件对缺少 `auth_version` 的 Session 按设计 fail-closed，但多个测试登录夹具仍只写入 `is_login`、角色和用户名，导致本应登录成功的测试被重定向到登录页，阻塞 CI。

## 2. 根因

认证 Session 契约新增了版本键后，测试夹具没有集中复用真实登录流程，也没有同步升级所有手工构造 Session 的测试路径；测试数据状态与生产 Session schema 不一致。

## 3. 方案

推荐在测试夹具的登录辅助函数中，从当前测试数据库用户读取其 `auth_version` 并写入 Session；对没有数据库用户的纯权限单测，显式使用与测试用户一致的版本值。保留专门的缺键否定用例，不对生产认证逻辑降级，不使用 `or 0` 掩盖缺键。

同时全仓检查 `tests/` 中的 `session_transaction()` 手工登录路径，逐点补齐版本键或明确其“故意缺键”语义；不修改业务 Session 安全契约。

## 4. 范围

| 范围 | 内容 |
| --- | --- |
| `tests/` | 修复认证测试夹具及受影响的手工 Session；新增/保留缺键 fail-closed 回归断言 |
| 生产代码 | 不改 `app/rbac/views.py` 和 `web_session_user_is_valid()` |
| 文档 | 修复后补充复盘与 Release Notes（若用户可感知的 CI/交付影响需记录） |

## 5. 分批

1. 扫描并分类所有测试 Session：正常登录夹具、无用户权限夹具、故意缺键安全用例。
2. 补齐正常路径版本键，运行 Bugbot 指出的 RBAC/Dashboard/操作日志相关测试。
3. 运行全量测试与 Ruff，确认失败数下降且缺键否定用例仍失败关闭。
4. 同步复盘、HTML/Markdown 和必要的 Release Notes。

## 6. 验收

- 受影响的测试不再因“登录状态已失效”失败。
- `tests.test_user_reactivation.TestDisabledSessionRevocation.test_missing_auth_version_key_fails_closed` 继续通过。
- Session 版本不匹配仍会撤销；正常测试用户 Session 的版本值与 DB 用户一致。
- `ruff check app/` 与定向/全量测试结果可追溯。

## 7. 风险

若粗暴给所有 Session 写固定值，可能掩盖用户版本不匹配或破坏缺键否定用例。缓解措施是按测试类别逐点补齐，并保留独立的缺键、错配、一次性 bump 三类安全矩阵。回滚仅涉及测试夹具，不影响生产数据。

**实施记录（2026-09-11）：**列表页测试现在创建真实 `RbacUser` 并在 Session 写入匹配的 `user_id`/`auth_version`；运行详情集成测试在 `create_all()` 前注册 `RbacRegistrationRequest`。P1 定向回归 21 项通过；P2 URL/签名问题仍待单独确认。

[文档索引](index.html) · [Markdown](测试Session补齐auth-version修复设计.md) · [索引](index.html)

---

[← 文档索引（HTML）](../index.html) · [← 文档索引（Markdown）](../index.md)
