# RBAC 四项 Review 问题闭环优化方案（2026-10）

> HTML 版：[RBAC四项Review问题闭环优化方案-2026-10.html](RBAC四项Review问题闭环优化方案-2026-10.html) · [文档索引](../index.html) · [索引 Markdown](../index.md)

# RBAC 四项 Review 问题闭环优化方案

版本：rev.1 · 日期：2026-10-26 · 状态：**待用户 Review 与明确确认** · 来源：[当前未提交代码与方案 Bugbot 专业评估](../qa/当前未提交代码与方案Bugbot专业评估-2026-10-26.html) · 页面/响应对比：[§8](#page-compare)

**推荐结论：**4 条发现均准确。问题 1、2 为 P1，必须在提交前关闭；问题 3、4 为 P2，但与同一 RBAC 交付的正确性和真值契约直接相关，建议同轮闭环。方案采用四个稳定原则：**授权落在服务边界、授权事实来自数据库当前状态、持久化 Scope 与表单 sentinel 双向映射、响应显式描述最终状态效果**。

## 1. 问题与准确性校准

| 编号 | 原发现 | 准确性 | 专业定性 | 是否阻断 |
| --- | --- | --- | --- | --- |
| R-01 | 单条/批量拒绝绕过申请 Scope | 成立，高置信 | P1 对象级授权缺失。CSRF 只能证明请求来自已登录页面，不能替代目标对象授权；顺序 ID 可被直接提交。 | 是 |
| R-02 | 用户管理读取面信任陈旧 Session | 成立，高置信 | P1 授权事实分裂。全局 before-request 只校验账号、启用状态和 `auth_version`；角色/组变更当前不 bump 版本，因此旧 role/group\_ids 仍有效。 | 是 |
| R-03 | 全局 admin 编辑页不回显 `__ALL__` | 成立，高置信 | P2 双向映射缺陷。不是权限提升，但会令合法全局管理员的原样保存失败，破坏 no-op 与可用性。 | 建议同轮 |
| R-04 | “失败项保持原状态”与自动拒绝冲突 | 成立，高置信 | P2 结果真值缺陷。数据库行为是设计过的自动拒绝，不是数据损坏；错误在于 `ok=False` 无法表达“请求动作失败但状态已改变”。 | 建议同轮 |

## 2. 根因

1. **动作授权不对称：**批准服务读取 reviewer 并校验当前数据库 Scope；拒绝服务仍是“拿到 ID 即更新”，路由只做粗粒度 `user:manage`。
2. **同域存在两套授权事实：**注册审批列表和用户写入已使用数据库当前 actor；用户列表、详情、编辑上下文及管理范围仍使用 Session role/group\_ids。`web_session_user_is_valid()` 又不会发现角色/组变化。
3. **领域值缺少反向转换：**POST 使用 `__ALL__` 表示全局，数据库使用“admin + 0 条 UserGroup”表示全局，但 GET 直接把数据库组 ID 列表交给模板，未恢复 sentinel。
4. **结果模型只有成功/失败：**批准服务的自动拒绝分支返回 `ok=False`，批量层把它归为 failure；页面由 failure 推导“未变化”，把“请求动作结果”和“状态副作用”错误合并。
5. **完成门禁按局部场景收口：**现有测试覆盖批准、注册审批列表和常规批量失败，但没有从“所有写动作”“所有用户管理读入口”“GET→原样保存”“失败后的最终状态”四个集合做完整性检查。

## 3. 设计原则与方案总览

| 原则 | 约束 | 落点 |
| --- | --- | --- |
| 服务边界授权 | 任何按 ID 改变注册申请状态的服务都必须接收明确 actor，并在写入前完成对象级授权；路由检查只作纵深防御。 | `app/rbac/services.py` |
| 数据库当前事实 | 用户管理路由不得再用 Session role/group\_ids 决定可见集合或目标管理权；数据库读取失败 fail-closed。 | `app/rbac/registration_scope.py` 可抽象为通用 actor context；`app/rbac/views.py` |
| 授权变更撤销会话 | 角色或组集合发生有效变化时，目标用户 `auth_version` 在同一业务事务中只 bump 一次。 | 用户编辑原子服务；不得在两个独立 commit 中重复 bump |
| 显式领域映射 | `admin + []` 只在合法全局语义下映射为表单 `['__ALL__']`；非 admin 空组不得误映射。 | 纯映射 helper + 模板上下文 |
| 结果与状态分离 | `ok` 表达请求动作是否成功；`state_changed/final_status/disposition` 表达数据库最终效果。 | 审批服务、批量摘要、页面结果条 |

## 4. R-01：拒绝入口对象级授权

### 4.1 推荐方案

1. 将 `reject_registration()` 改为必须显式接收 `reviewer_id`；禁止服务内部隐式从 Session 取 actor。
2. 申请加锁并确认仍为 pending 后，读取数据库当前 actor；actor 不存在、停用、无 `user:manage` 或授权读取异常时 fail-closed，且不得改变申请。
3. 冻结拒绝授权语义：
   - seed/global admin：可拒绝所有合法申请，也可处理异常/漂移申请，作为唯一治理出口；
   - scoped admin + viewer/operator 申请：目标申请组与 actor 组有精确交集才可拒绝，与列表可见性一致；
   - scoped admin + admin 申请：申请的全部具体组必须是 actor 当前组的非空子集；
   - `__ALL__`、缺关联、关联漂移、非法历史 Scope：scoped admin 一律不可拒绝。
4. 单条与批量路由都传 `session.user_id` 给服务；服务返回稳定原因码，路由只做受控文案映射和审计。
5. 拒绝成功写入 `reviewer_id`，失败审计只记录 actor ID、request ID、reason code，不记录申请敏感字段。

**为何不用批准校验直接代替：**批准是“授予用户 Scope”，必须按目标角色执行授予边界；拒绝是“终止申请”，其合法范围应与申请列表的审阅责任一致。对 viewer/operator 采用精确交集，对 admin 采用完整子集，可避免页面可见但无法拒绝，也不会让按组管理员处置全局或异常申请。

### 4.2 不推荐方案

- 只在路由里检查当前页是否出现该 ID：可被其他调用方绕过，且分页/筛选不是授权依据。
- 只复用 `@require_permission('user:manage')`：它是功能权限，不是对象 Scope。
- 对异常申请默认允许 scoped admin 拒绝：会把存储漂移变成越权治理入口。

## 5. R-02：用户管理数据库当前授权与 Session 撤销

### 5.1 推荐方案：双层闭环

**第一层：请求内即时授权。**将现有 `resolve_user_management_actor()` 提升为通用、请求级缓存的 user-management actor context。以下入口全部从同一 context 获取 `role/username/group_ids/bypass`：

- 用户列表及其 count、分页；
- 用户新增页面可选组与全局能力；
- 用户查看、编辑、重置密码、重置 Token、停用的目标 Scope；
- 用户编辑成功/失败回渲时的可选组。

actor 缺失/停用时清 Session 并要求重新登录；数据库当前角色无 `user:manage` 时返回 403；授权查询失败返回通用 500。不得回退到 Session。

**第二层：授权变更后的会话撤销。**当目标用户的角色或有效组集合发生变化时，在用户编辑的同一数据库事务中把 `auth_version` 增加一次；无变化不得 bump。这样旧 Cookie 在下一请求进入全局 before-request 时被撤销，顶栏、导航和其他仍使用 Session 的页面也不会长期展示旧权限。

**事务约束：**当前 `users_edit()` 依次调用 `update_user()`、`set_user_groups()` 和个人资料 commit，存在多个提交点。不得简单地在两个现有函数中各自 bump；应接入已设计的用户编辑差异写入/单事务服务，使 role、groups、auth\_version、Token/cache 失效与审计形成一个原子结果。

### 5.2 取舍

| 方案 | 优点 | 缺点 | 结论 |
| --- | --- | --- | --- |
| 只在每个用户管理路由读数据库 | 即时阻断越权；不依赖会话撤销 | 导航和其他 Session 消费点仍陈旧；每个入口都要保持同源 | 必要但不充分 |
| 只在角色/组变化时 bump auth\_version | 全站旧会话统一失效 | 遗漏某个写入口就重新出现漏洞；并发窗口依赖写路径完整性 | 必要但不单独依赖 |
| 数据库当前授权 + 原子 bump | 即时正确 + 全站收敛，纵深防御 | 需并入用户编辑单事务改造 | **推荐** |

## 6. R-03：全局 Scope 的表单双向映射

### 6.1 推荐方案

1. 新增纯函数，把目标用户的持久化角色与组集合转换为表单值：
   - 非种子 `admin + []` → `['__ALL__']`；
   - 具体组用户 → 对应字符串组 ID；
   - 非 admin + [] → 无效数据状态，绝不映射为全局；
   - seed admin → 固定全局语义，页面只读/锁定，不允许降级为具体组。
2. 模板只消费 `selected_group_values`，不再自行猜测数据库空关系的含义。
3. POST 仍以现有 `validate_user_scope_assignment()` 为唯一授权入口；GET 映射只负责回显，不能放宽后端。
4. 错误回渲优先使用本次已校验的表单值；数据库 reload 只用于成功后的事实展示，避免用户输入无故消失。

**稳定性关键：**不要让模板出现“如果空组且 admin 就 selected”这类领域判断；映射应有纯函数单测，保证持久化值、表单值、change-set 值三者一致。

## 7. R-04：批量反馈最终状态真值契约

### 7.1 推荐方案

保留现有 `ok` 含义——“用户请求的 approve/reject 动作是否成功”，同时为每项服务结果增加状态效果：

| 字段 | 语义 | 示例 |
| --- | --- | --- |
| `state_changed` | `true/false/null`；null 表示内部异常后无法在当前响应中安全断言最终状态。 | 自动拒绝为 true；Scope 拒绝为 false。 |
| `final_status` | 已知时为 `pending/approved/rejected`；未知时为 null。 | 用户名冲突自动拒绝为 rejected。 |
| `disposition` | 稳定原因类别，不让页面解析中文文案。 | `requested_succeeded`、`auto_rejected`、`unchanged`、`unknown`。 |

批量 summary 保持 `success_count/failure_count/outcome` 兼容，同时增加 `changed_failure_count`、`unchanged_failure_count`、`unknown_failure_count`。页面不再写“失败项保持原状态”，而是按计数与每项 disposition 展示最终事实。

**兼容性：**这是管理端 JSON 返回结构新增字段。按仓库规则，即使是加字段也须在 Release Notes 标注 `⚠️ API Breaking Change` 并同步前端契约测试；旧字段语义不得悄然改变。

### 7.2 最小补丁为何不够

只把文案改成“失败项请查看详情”可以消除当前误导，但后续调用方仍必须解析中文消息才能知道是否自动拒绝。它可作为紧急止血，不是稳定终局；本方案选择结构化状态效果。

## 8. Before / After 页面与响应对比

### 8.1 用户编辑页：全局管理员原样保存

#### BEFORE · 全局管理员编辑

角色：业务管理员

业务组：“全部（全局权限）”存在但未选中

修改花名后点击保存

结果：请至少选择一个业务组

持久化全局语义没有恢复为表单 sentinel。

#### AFTER · 全局管理员编辑

角色：业务管理员

业务组：“全部（全局权限）”已选中

修改花名后点击保存

结果：资料保存；Scope 保持全局

GET/POST/持久化三态映射一致。

### 8.2 注册审批页：部分失败最终状态

#### BEFORE · 批量通过部分失败

成功 1 条，失败 2 条

成功项已经生效，失败项保持原状态

#18 用户名冲突，申请已自动拒绝

摘要与逐项详情互相矛盾。

#### AFTER · 批量通过部分完成

按请求通过 1 条；未按请求完成 2 条

其中：自动拒绝 1 条；保持待审批 1 条；状态未知 0 条

#18 · 自动拒绝 · 用户名已被占用

#19 · 未变化 · 超出当前管理范围

摘要与数据库最终状态同源。

### 8.3 越权请求的可见响应

#### BEFORE · 直接提交范围外 ID

组 1 管理员 POST 拒绝组 10 申请 → “已拒绝”

#### AFTER · 服务边界拒绝

组 1 管理员 POST 拒绝组 10 申请 → 权限不足；申请仍 pending

#### BEFORE · 旧 Cookie

数据库 global→组 1，用户列表仍显示全量

#### AFTER · 数据库当前事实

同一 Cookie 立即按组 1 限制；授权变更后下一请求注销旧会话

## 9. 范围

### 9.1 包含

- 注册申请单条/批量拒绝的 actor 传递、对象级授权、审计和测试。
- 所有 `/rbac/users*` 管理入口的数据库当前 actor 同源。
- 角色/组变化时的单次 `auth_version` bump，并入用户编辑原子事务。
- 全局 admin/seed/concrete/invalid 四类表单映射。
- 批量结果状态效果字段、页面摘要和契约测试。
- 相关 QA、复盘、Release Notes、路线图状态校准。

### 9.2 不包含

- 不改变注册审批列表 R2-2 的 SQL 可见集合和分页性能方案。
- 不新增角色或权限字符串。
- 不改变 seed admin 不可停用、不可自编辑等既有策略。
- 不借本轮重做全部 RBAC context/sidebar；仅通过会话撤销保证其最终收敛。
- 不修改公开 `app/api/` 端点；管理端 JSON 契约变化单独标注。

## 10. 分批实施

| 批次 | 内容 | 独立停止条件 |
| --- | --- | --- |
| B0 | 先写 4 组红线测试：拒绝越权、用户管理旧 Cookie、global 原样保存、auto-reject 最终状态。 | 必须在未修复代码上按预期失败；不得用 mock 绕过 HTTP/模板链路。 |
| B1 | R-01 服务边界授权，单条/批量同源。 | 组外、global、异常申请均无写入；合法交集/子集与 global 正向通过。 |
| B2 | R-02 user-management actor context；随后接入单事务 auth\_version bump。 | 列表/详情/编辑/重置/停用全部使用 DB-current；旧会话立即受限并最终注销。 |
| B3 | R-03 纯映射 helper 与模板上下文。 | global GET 已选中；不改 Scope 保存成功；非 admin 空组不被误判全局。 |
| B4 | R-04 状态效果契约、批量摘要和页面文案。 | 自动拒绝、未变化、未知三类可机器判定；页面不含绝对错误表述。 |
| B5 | 同类排查、浏览器角色矩阵、文档/复盘/Release 收口。 | 全部门禁和本地可验证环境通过后才恢复“已关闭”状态。 |

## 11. 验收标准

### 11.1 自动化

- 单条拒绝：scoped admin 拒绝组外、global、异常申请均失败且状态保持；合法 viewer/operator 交集与 admin 子集成功。
- 批量拒绝：合法 + 越权混合时精确部分成功，越权项保持 pending；每项审计 actor 正确。
- 用户管理：global Session 在数据库降为组 1 后，列表 total、详情、编辑、密码/Token 重置、停用全部不能越界；角色降为 viewer 后固定 403/注销。
- Session：角色或组实际变化只 bump 一次；no-op 不 bump；缺键、版本不匹配、一次性 bump 既有矩阵继续通过。
- 表单：非种子 global admin GET 中 `__ALL__` selected；原样保存/只改资料成功且 0 条组关系不变；seed 固定全局；非法非 admin 空组 fail-closed。
- 反馈：自动拒绝返回 `state_changed=true`、`final_status=rejected`；Scope 拒绝返回 false/pending；内部异常为 null/null/unknown。

### 11.2 浏览器

- 以组 1 Biz Admin、组 10 Biz Admin、全局 Admin、seed Admin、Viewer 五类账号验证正向与反向路径并截图。
- 全局 Admin 打开编辑页，不触碰业务组，仅修改花名并保存；断言成功、仍为全局。
- 真实批量通过触发“自动拒绝 + Scope 拒绝 + 成功”混合结果；检查摘要、逐项 badge 和刷新后数据库状态一致。
- 同一 Cookie 完成 global→scoped/role downgrade，验证用户列表即时收敛或被注销。

### 11.3 命令门禁

```
.venv-py311/bin/python -m unittest tests.test_rbac_global_scope_assignment tests.test_registration tests.test_user_reactivation -v
.venv-py311/bin/python -m unittest tests.test_redesign_sidebar -v
.venv-py311/bin/ruff check app/ tests/
.venv-py311/bin/python scripts/check_route_completeness.py --check app/rbac/views.py
.venv-py311/bin/python scripts/smoke_routes.py --check
.venv-py311/bin/python scripts/check_ui_contract.py --check
.venv-py311/bin/python scripts/audit_hardcoded_colors.py --check
.venv-py311/bin/python scripts/check_doc_completeness.py --check
.venv-py311/bin/python scripts/check_doc_links.py --check
.venv-py311/bin/python scripts/html_docs_to_markdown.py --check
git diff --check
```

## 12. 风险与控制

| 风险 | 影响 | 控制 |
| --- | --- | --- |
| 拒绝规则与列表 SQL 再次漂移 | 可见但不可操作，或越权操作 | 用同一纯策略真值样本同时断言 Repository SQL 和 service 授权；1/10、多组、global、异常数据全覆盖。 |
| auth\_version 在多提交中重复或漏 bump | 误登出或旧会话不撤销 | 只在用户编辑原子服务的 change-set 中生成一次；提交后统一 cache 失效。 |
| 数据库当前 actor 查询增加开销 | 用户管理页额外查询 | 请求级 `g` 缓存；列表/详情/导航同请求复用，禁止跨请求缓存权限事实。 |
| 批量 JSON 增字段影响前端 | 契约测试或第三方脚本变化 | 保留旧字段及语义；新增字段显式发版标注；前端先容忍缺字段再切换展示。 |
| global 空关系映射掩盖非法数据 | 非 admin 被误显示为全局 | 映射必须同时检查 target role/seed 语义；非 admin 空关系输出 invalid，不得自动修复。 |

## 13. 用户确认点

推荐按 B0→B5 全部实施。请确认以下关键语义：**scoped admin 对 viewer/operator 申请按“精确交集”拥有拒绝权，对 admin 申请必须“完整子集”；异常/漂移申请只允许 seed/global admin 拒绝；角色或组变化会使目标用户旧 Web Session 在下一请求失效。**

[文档索引](../index.html) · [Markdown](RBAC四项Review问题闭环优化方案-2026-10.md)

---

[← 文档索引（HTML）](../index.html) · [← 文档索引（Markdown）](../index.md)
