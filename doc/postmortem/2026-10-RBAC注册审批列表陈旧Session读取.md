# RBAC 注册审批列表陈旧 Session 读取复盘

> HTML 版：[2026-10-RBAC注册审批列表陈旧Session读取.html](2026-10-RBAC注册审批列表陈旧Session读取.html) · [文档索引](../index.html) · [索引 Markdown](../index.md)

# RBAC 注册审批列表陈旧 Session 读取复盘

日期：2026-10-19 · 批次：R2-1 · 状态：已修复并验证

## 1. Bug 定位

`/rbac/registration_review` 及导航待审批数量使用 Session 中的角色、global 标志与组集合决定读取范围；用户在数据库中被降权或收窄业务组后，旧 Cookie 仍可能扩大审批数据可见范围。

## 2. 根因

会话有效性检查没有把当前角色与当前组关系作为读取授权事实；列表与 badge 又分别读取 Session，形成授权事实陈旧和同一响应可能撕裂的双重缺口。

## 3. 测试漏洞

原测试未覆盖“Cookie 保持 admin/global，但数据库当前角色/组已经变化”。新增红线初版还把范围外组设为 10，与既有 `LIKE '%1%'` 缺陷耦合，无法独立判断 R2-1。

## 4. 修复

新增无写入、无 Session 依赖的数据库当前 actor 解析器；Session 只提供 user\_id。列表、标题与导航 badge 在单请求内共享解析结果。用户不存在/停用清理会话并 302，当前角色无权限返回 403，数据库读取异常记录 traceback 并返回通用 500。

## 5. 防护测试

覆盖 global→scoped、组收窄、角色降级、请求内只解析一次、失效会话 302、异常 500 与 global 正向基线。R2 矩阵 13 项中 9 项通过，4 项保留给 R2-2。

## 6. 同类排查

审批列表主查询、页面 pending\_count、侧边栏 badge 已统一。写入侧此前已使用数据库当前 actor。CSV 精确匹配、admin 子集查询、分页/count 同源尚未修复，禁止将 F-02 宣告关闭。

## 7. 预防方案

- 在 `tests/test_rbac_global_scope_assignment.py` 固化陈旧 Session 的角色与组变化矩阵，并断言请求级解析次数。
- 正式设计将 actor 授权与资源谓词拆为 R2-1/R2-2 单变量批次，每批列明允许保留的预期失败。
- 第三方可执行 `python -m unittest tests.test_rbac_global_scope_assignment -v` 复现；R2-1 验收以 9 pass、4 个明确 R2-2 expected failure、0 error 为准。

[复盘索引](index.html) · [Markdown](2026-10-RBAC注册审批列表陈旧Session读取.md) · [正式设计](../design/RBAC注册审批列表Scope精确化优化方案-2026-10.html)

---

[← 文档索引（HTML）](../index.html) · [← 文档索引（Markdown）](../index.md)
