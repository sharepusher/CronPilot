# RBAC 注册审批拒绝 Scope 授权闭环方案（2026-10）

> HTML 版：[RBAC注册审批拒绝Scope授权闭环方案-2026-10.html](RBAC注册审批拒绝Scope授权闭环方案-2026-10.html) · [文档索引](../index.html) · [索引 Markdown](../index.md)

# RBAC 注册审批拒绝 Scope 授权闭环方案

版本：rev.3 · 日期：2026-10-27 · 状态：**已确认、已实施并验证** · 前置发现：[Bugbot P1](../qa/当前未提交代码与方案Bugbot专业评估-2026-10-26.html) · 父方案：[RBAC 四项 Review 问题闭环方案](RBAC四项Review问题闭环优化方案-2026-10.html) · 页面响应对比：[§7](#page-compare)

**决策：**拒绝注册申请必须像批准一样在服务边界校验数据库当前 actor 的对象 Scope；但拒绝不是授予新权限，因此 scoped admin 的允许集合与注册审批列表可见集合同源：viewer/operator 为精确交集，admin 为完整非空子集。全局/seed admin 保留拒绝异常或漂移申请的唯一治理出口。

## 1. 问题

当前 `reject_registration(request_id, comment)` 仅按 ID 读取 pending 申请并提交 rejected；它从 Session 写 reviewer，而不接收明确 actor，也未校验 actor 对目标申请的 Scope。路由层的 `user:manage` 和 CSRF 不构成对象级授权：一个拥有组 A 的 Biz Admin 可以提交组 B 或全局申请 ID，将原本不可见的申请拒绝。

**风险等级：P1。**攻击不要求伪造身份；已登录的受限管理员只需知道或猜测顺序 ID。影响是完整性：合法申请可被跨组终止；同时 reviewer 审计会错误归因到该 actor。

## 2. 根因

1. 批准服务已读取 reviewer 并使用数据库当前 Scope；拒绝服务仍是早期“状态更新”实现，授权模型没有同步演进。
2. 路由把功能权限误当成对象权限，服务层没有成为不可绕过的最终防线。
3. 注册申请有正常、全局和存储漂移三类 Scope 数据，而拒绝路径没有定义异常数据应由谁治理。
4. 单条和批量拒绝都调用同一个未授权服务，因此漏洞在两个入口同时存在。

## 3. 方案

### 3.1 服务边界与事务顺序

1. `reject_registration` 改为强制接收 `reviewer_id`，不再在服务内部从 Session 获取 actor。
2. 服务以与批准路径相同的行锁读取申请，先确认存在且仍为 pending。
3. 读取数据库当前 actor：不存在/停用、没有 `user:manage`、或授权读取异常时返回受控失败且不写申请。
4. 完成对象 Scope 授权后，才更新 status、pending\_username、reviewer\_id、review\_comment、update\_time，并一次 commit。
5. commit 失败 rollback，返回通用错误与 trace\_id；成功后写不含申请敏感内容的拒绝审计。

该顺序已按现有实现验证：`resolve_user_management_actor()` 可读取数据库当前 role、username、group\_ids；批准路径已用 `with_for_update()` 锁住申请与关联行。因此本方案不依赖尚不存在的调度器或 ORM API。

### 3.2 冻结的授权矩阵

| actor | 申请角色/Scope | 允许拒绝 | 理由 |
| --- | --- | --- | --- |
| seed/global admin | 所有正常申请 | 是 | 拥有全局审阅职责。 |
| seed/global admin | 非法 CSV、缺关联、关联漂移、悬空组 | 是 | 唯一治理出口；拒绝可结束不可批准的异常申请。 |
| scoped admin | viewer/operator，申请组与 actor 组有精确交集 | 是 | 与列表可见集合一致。 |
| scoped admin | admin，申请所有具体组是 actor 当前组的非空子集 | 是 | 避免按组管理员处置覆盖其权限外的管理员申请。 |
| scoped admin | `__ALL__` 全局申请 | 否 | 全局 Scope 不属于任何按组管理员。 |
| scoped admin | 无交集、部分超集、异常/漂移申请 | 否 | fail-closed；防止把异常数据变成越权治理入口。 |
| viewer/operator | 任何申请 | 否 | 数据库当前 actor 无 `user:manage`。 |

### 3.3 同源实现策略

新增一个只读授权 helper，由拒绝服务调用。它应先获得数据库当前 actor，再根据申请的规范化 Scope 返回固定 reason code；scoped actor 必须先通过存储一致性校验。为避免“列表可见、服务不可操作”或两处规则漂移，测试以同一组真值样本同时断言：

- Repository 的 SQL 可见集合；
- 拒绝服务的允许/拒绝结果；
- 最终申请状态和 reviewer\_id。

全局 actor 对异常数据不调用“必须一致”的 scoped 判定；其治理许可应记录 `registration_reject_anomaly` 审计原因。scoped actor 遇到同类数据只获得不泄露字段细节的“无权处理该申请”响应。

### 3.4 路由与批量行为

- 单条路由把 `session.user_id` 显式传给服务。
- 批量路由逐项调用同一服务；允许项成功、拒绝项保持 pending，并继续沿用现有 partial-failure 摘要，不产生假成功跳转。
- 所有 Scope 拒绝使用稳定 reason code；客户端不根据中文错误文案做安全判断。

## 4. 范围

### 包含

- `app/rbac/services.py` 的拒绝服务、审计和授权 helper。
- `app/rbac/views.py` 的单条/批量 reviewer 传递和受控反馈。
- 注册审批 Scope 专项测试、服务测试、HTTP 批量测试及目标角色浏览器验证。
- 本设计、复盘、Release Notes、QA 证据和索引同步。

### 不包含

- 不改变批准授权规则或列表 SQL 本身。
- 不改变用户管理陈旧 Session、全局 Scope 表单回显、批量最终状态契约；它们由父方案后续批次处理。
- 不新增 RBAC 角色、权限字符串或公开 API。

## 5. 分批实施

| 批次 | 工作 | 停止条件 |
| --- | --- | --- |
| B0 | 写失败红线：单条/批量组外拒绝、全局拒绝、异常申请拒绝；合法交集、完整子集及 global 正向。 | 每条红线必须在旧实现上失败，且断言 DB 未写或错误写入。 |
| B1 | 实现 actor 显式传递、数据库当前 actor 和 scoped 授权 helper。 | 拒绝服务不读取 Session actor；越权项不变，合法项有正确 reviewer。 |
| B2 | 接入单条/批量路由、审计与受控错误。 | 部分失败无跳转；不泄露范围外申请详情。 |
| B3 | 同类排查、目标角色浏览器、路由/文档/复盘收口。 | 全部验收通过前不得把 P1 标记关闭。 |

## 6. 验收标准

- 组 A scoped admin 直接 POST 拒绝组 B、全局、异常/漂移申请：响应受控失败，状态仍 pending，reviewer\_id/comment 均不变。
- 组 A scoped admin 可拒绝组 A viewer/operator 申请；可拒绝组 A（或 A 的完整子集）admin 申请；不能拒绝 A+B admin 申请。
- global/seed admin 可拒绝正常全局申请，也可拒绝异常申请，异常路径产生治理审计。
- 混合批量中，成功/失败计数精确，越权项不会被修改或重定向掩盖。
- HTTP 测试有真实 CSRF、session 与数据库断言；浏览器以 scoped/global 两类角色完成正反路径并保存截图。
- 回归通过：`tests.test_rbac_global_scope_assignment`、`tests.test_registration`、路由冒烟、Ruff、文档同步及链接门禁。

## 7. 风险与控制

| 风险 | 控制 |
| --- | --- |
| 拒绝规则与列表 SQL 语义漂移 | 同一真值样本对 Repository 与服务双断言；覆盖 1/10、交集、完整子集、global、非法关联。 |
| 拒绝异常申请时绕过所有安全检查 | 仅 bypass actor 可进入治理分支；仍要求 pending、行锁和单次事务。 |
| 授权查询错误被误作“无可见数据” | 返回通用失败并记录服务端异常；绝不退回 Session 或放行。 |
| 批量部分成功被 UI 误报 | 保持 errcode=1、url 为空的部分失败语义；逐项显示受控结果。 |

## 8. Before / After 响应对比

### BEFORE · 组 A 管理员直接提交

POST /registration\_review/reject id=组B申请

返回：已拒绝

数据库：组 B 申请变为 rejected

### AFTER · 服务边界授权

POST /registration\_review/reject id=组B申请

返回：无权处理该申请

数据库：申请保持 pending，reviewer/comment 不变

## 9. 设计自评

**结论：方案可实施，无设计阻断。**它没有复用错误的“批准即授予”语义，也没有仅在路由打补丁；以数据库当前 actor、服务边界、锁与事务建立完整性防线。唯一需要产品确认的规则已在 §3.2 冻结：scoped admin 对 viewer/operator 使用交集，对 admin 使用完整子集，异常申请仅由全局治理。

## 10. 实施与验收记录

- 实施：`reject_registration(request_id, reviewer_id, comment)` 使用行锁、数据库当前 actor 与 Scope 授权 helper；单条/批量入口均显式传递 actor。
- 专项矩阵：`TestRegistrationApprovalScopeClosure` 24 项通过，覆盖组外、全局、admin 部分子集、关联漂移、陈旧 Session、混合批量与全局异常治理。
- 相关回归：`tests.test_rbac_global_scope_assignment tests.test_registration tests.test_user_reactivation` 共 172 项通过。
- 质量门禁：Ruff、HTML↔Markdown 同步、文档完整性/链接、路由完整性及 86 条路由冒烟均通过。
- 运行验证：本地服务 `http://127.0.0.1:5001/rbac/login` 返回 200；Playwright 注册审批角色矩阵通过，临时用户与申请清理为零。
[文档索引](../index.html) · [Markdown](RBAC注册审批拒绝Scope授权闭环方案-2026-10.md)

---

[← 文档索引（HTML）](../index.html) · [← 文档索引（Markdown）](../index.md)
