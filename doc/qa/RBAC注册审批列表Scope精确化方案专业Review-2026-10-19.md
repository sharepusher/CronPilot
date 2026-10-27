# RBAC 注册审批列表 Scope 精确化方案专业 Review（2026-10-19）

> HTML 版：[RBAC注册审批列表Scope精确化方案专业Review-2026-10-19.html](RBAC注册审批列表Scope精确化方案专业Review-2026-10-19.html) · [文档索引](../index.html) · [索引 Markdown](../index.md)

# RBAC 注册审批列表 Scope 精确化方案专业 Review

日期：2026-10-19 · 被审查文档：[rev.1](../design/RBAC注册审批列表Scope精确化优化方案-2026-10.html) · 审查范围：代码事实、授权语义、R2-0 可证伪性、双后端可实施性、风险与验收闭环

**结论：A-（8.8/10），专业、方向正确、可实施，但建议“修订后确认”。**方案准确识别了 CSV 子串匹配、Session 陈旧权限、分页后过滤和 count 口径分裂四个核心问题；分批和正反测试思路成熟。确认前需修正停用 Session 的现状描述，并把 fail-closed 的 HTTP 表现、R2-2 查询策略决策门槛与 R2-0 红/绿分类进一步锁死。上述问题不推翻方案主方向。

**采纳状态（2026-10-19）：**用户已确认上述修订，设计 rev.2 已完成全部校准：停用 Session 改为绿色基线，角色降权与组收窄拆分为真实红线，302/403/500 契约已冻结，R2-2 前置 DEC 与关联表升级条件已加入。该状态表示设计修订完成，不表示 R2-0 已实施。

## 1. 评分

| 维度 | 评分 | 评价 |
| --- | --- | --- |
| 专业性 | 9.2 / 10 | 安全边界、列表/count/page 同源、fail-closed、双后端、浏览器角色矩阵和分批停止条件完整。 |
| 准确性 | 8.4 / 10 | 主要代码事实准确；停用旧 Session 的风险描述未纳入现有 `web_session_user_is_valid()` 防线，需校准。 |
| 合理性 | 8.9 / 10 | 先红线、再 actor、再查询、最后集成的顺序合理；短期 CSV 闭环与中期关联表解耦得当。 |
| 可验证性 | 8.7 / 10 | 矩阵覆盖充分，但部分场景允许“拒绝或零数据”会导致测试契约含糊。 |
| **综合** | **8.8 / 10** | **A-，修订后可进入 R2-0。** |

## 2. 已核实且准确的核心判断

- 准确：`paginate_by_groups()` 与 `get_pending_count_by_groups()` 使用 `LIKE '%gid%'`，组 1 会命中 10/11/21。
- 准确：`registration_review()` 使用 Session 的 role/group\_ids 判断 bypass 和 scoped 查询，未读取数据库当前 actor Scope。
- 准确：admin 子集过滤发生在分页之后，只改 `items`，无法修正 total/pages/pending count。
- 准确：写入服务已经使用数据库当前事实，故 F-02 的主要风险是读取机密性和页面准确性，而不是现存的直接写入越权。
- 准确：短期安全闭环不应被关联表迁移绑架；但长期规范化方向仍应保留。

## 3. 必须在确认前修订的发现

### F-01 · 停用旧 Session 的现状描述不准确

**代码事实：**`rbac.before_app_request` 在所有已登录请求前调用 `web_session_user_is_valid()`；该函数读取数据库用户，检查存在、`is_active`、用户名和 `auth_version`。停用操作还会 bump `auth_version`。因此“数据库已停用但旧 Session 继续展示审批列表”在正常入口上已有防线。

**真正缺口：**`update_user()` 仅在启用→停用时 bump 版本，单纯角色降权不会 bump；`set_user_groups()` 组关系变化会更新 Token，但不 bump Web Session 的 `auth_version`。所以“global admin 降为 scoped admin”或“组集合被收窄”仍可能留下陈旧 role/group\_ids。

**修订要求：**RL-06 应从预期失败红线改为现有安全基线，并断言重定向登录/Session 清理的既有准确行为；新增或强化“角色降权”和“组收窄”两个真正红线，不能用停用场景代替。

### F-02 · fail-closed 的外部响应契约仍含糊

设计对停用/缺失 actor 写“拒绝或零数据”，对读取异常写“通用错误页/空集”。这允许实现者任选多个不等价行为，R2-0 无法形成唯一验收标准。

**推荐冻结：**已失效会话沿用现有登录失效重定向；数据库当前角色不具备 `user:manage` 返回 403；actor Scope 查询基础设施异常返回通用 500，并仅在服务端记录 traceback。禁止用空列表伪装授权系统故障，因为这会误导用户为“没有申请”。

### F-03 · R2-2 需要显式技术决策门槛

“完整 token + admin 子集 + SQLite/MySQL 等价”是正确目标，但 CSV 上实现 admin 子集并非普通交集查询：必须证明申请中不存在 actor 范围之外的 token。方案当前谨慎地没有虚构具体 SQL API，这是优点；但还需在 R2-2 前增加一个明确的 DEC：选择数据库表达式、规范化临时派生、或关联表迁移中的一种，并用双后端样例验证复杂度与性能。

**停止条件：**若短期 CSV 查询无法在两端以可审计、可索引或可接受性能实现，不应退回分页后 Python 过滤，应升级为关联表方案并重新走迁移设计确认。

## 4. R2-0 专业性评估

**整体判断：**R2-0 的方法正确。它同时断言用户名、items、total/pages、pending badge 和数据库 actor 事实，比只检查 HTML 是否出现用户名更可靠；正向交集和 global 基线也能防止过度收紧。

| 测试组 | 评价 | 调整 |
| --- | --- | --- |
| 1/10 数字边界 | 必要且可稳定复现。 | 保留双向、开头/中间/末尾 token，避免只测单值。 |
| viewer/operator 交集 | 语义正确。 | 正向与越界必须在同一 fixture 中，证明 Scope 而非数据缺失。 |
| admin 完整子集 | 关键且专业。 | 分别断言 items、total、pages、badge，捕获当前分页后二次过滤。 |
| global→scoped 旧 Session | 真实红线。 | 拆成角色降权与仅组收窄两项，数据库状态快照必须显式断言。 |
| 停用旧 Session | 当前已有防线。 | 改为绿色防回退基线，不应期待旧实现失败。 |
| 读取异常 | 必要。 | 冻结通用 500/日志契约，避免“空集也算通过”。 |
| 分页与筛选 | 覆盖完整。 | 优先在 Repository 层断言 PaginationResult，再用路由 HTML 验证用户可见结果。 |

## 5. 方案合理性与分批顺序

R2-0→R2-1→R2-2→R2-3→R2-4 的依赖顺序合理：

1. R2-0 先证明缺陷并锁住合法能力；
2. R2-1 先纠正“谁在看”的授权事实，避免精确 SQL 仍使用错误 actor；
3. R2-2 再纠正“能看哪些申请”的查询谓词，并统一分页与计数；
4. R2-3 做筛选/搜索和同类查询影响面；
5. R2-4 用真实角色浏览器矩阵完成交付证据。

不建议合并 R2-1 与 R2-2：两个批次分别改变 actor 授权来源与资源查询算法，拆分更利于定位回归和回滚。

## 6. 风险评估

| 风险 | 概率 | 影响 | 现有控制 | 评价 |
| --- | --- | --- | --- | --- |
| 范围外申请信息泄露 | 高 | 中高 | 写守卫不能补偿读取泄露 | P1 定级合理 |
| 过度收紧合法交集 | 中 | 中 | 正向交集/global 基线 | 控制充分 |
| total/count 再次漂移 | 中 | 中 | 同源谓词 + 多层断言 | 控制充分 |
| CSV 查询跨库分叉 | 中高 | 高 | 双后端验证与停止条件 | 需补 DEC 后充分 |
| 基础设施异常被伪装为空列表 | 中 | 中 | 当前契约含糊 | 需修订 |

## 7. 最终建议

**建议结论：**保留方案架构和分批顺序，先做一次 rev.2 文档校准：①停用 Session 改为绿色基线；②新增角色降权、组收窄两条红线；③冻结 302/403/500 外部行为；④在 R2-2 前增加双后端查询 DEC 门槛。完成后可专业地确认并实施 R2-0。

## 8. 本次代码依据

```
registration_request_repository.py：列表/count 均为无边界 LIKE
rbac/views.py：registration_review 使用 Session role/group_ids；admin 分页后过滤
rbac/services.py：web_session_user_is_valid 校验 DB active/auth_version
rbac/services.py：update_user 仅停用时 bump auth_version；角色降权不 bump
rbac/services.py：set_user_groups 变更组关系但不 bump Web Session auth_version
pagination.py：total 在 limit/offset 前由 SQL count 得出，后改 items 不会重算 total/pages
```

[文档索引](../index.html) · [Markdown](RBAC注册审批列表Scope精确化方案专业Review-2026-10-19.md) · [被审查设计](../design/RBAC注册审批列表Scope精确化优化方案-2026-10.html)

---

[← 文档索引（HTML）](../index.html) · [← 文档索引（Markdown）](../index.md)
