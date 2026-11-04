# 任务启停提交后读取异常修复设计

> HTML 版：[status-postcommit-snapshot-repair-2026-11-03.html](status-postcommit-snapshot-repair-2026-11-03.html) · [文档索引](../index.html) · [索引 Markdown](../index.md)

# 任务启停提交后读取异常修复设计

rev.2 · 2026-11-03 · 状态：用户确认后已实施，专项验证通过。

本稿仅处理提交后重试摘要读取问题；授权时点遵循用户确认的[决策](../qa/sqlite-revocation-next-assessment-2026-11-03.html)，不引入新的 SQLite 撤权锁或调整在途操作规则。

## 版本记录

rev.2：按用户确认实施；实际 Web 故障注入发现路由也会读取过期 actor，保存 actor ID 以保持既有令牌契约。

rev.1：基于当前代码、真实故障注入和既有 D2 契约提出最小修复及验收。

## 交付契约矩阵

| 对象与调用方 | 认证和唯一性 | 异常及响应 | 验收 |
| --- | --- | --- | --- |
| Web POST /update\_status、/cron\_status\_apply | 现有 Session、cron:write 与对象 scope；重试令牌绑定 actor、task、revision、target、config | 不新增响应字段；保存已确定后调度失败仍用现有可重试错误与签名令牌，未知提交不得生成可安全重试令牌 | 测试客户端真实路由与目标角色浏览器确认、重试、数据库和 Job |
| API POST /api/cron/status | 现有 API 权限和 scope；重试头绑定调用凭据摘要和原任务版本 | 沿用 JSON 与 X-Cron-Status-Retry，不更改字段；非法/陈旧令牌继续拒绝 | 真实 API 请求、签名重试、版本和 JobStore |
| 内部 save\_status / toggle\_status | 沿用 actor\_id 可选契约；无 context 调用不强制签发令牌 | 提交未知与确定失败继续区别；不输出异常原文 | 服务故障注入和无 context 回归 |

## 1. 问题与根因

已确认 commit 返回后，SQLAlchemy 默认过期 ORM 属性；save\_status 对原 task 再调用 status\_config 生成 context 摘要，可能在隐式 SELECT 时异常，而该语句位于 try 边界之外。[隔离复现](../qa/evidence/commit-review-2026-11-03/status-postcommit-read.json)显示 DB 已是运行、异常逃逸、调度调用 0 且 context 为空。该证据是服务级故障注入，不证明全部生产异常路径。

## 2. 已读实现与决策

- `cron_status_apply.py`：提交前已有六个调度字段快照、目标、revision 与 task name；提交后 context 构造再次访问 task。status\_config 使用这六字段、排序 JSON 与当前 secret 的 HMAC；正常同目标无重试在写前返回。
- `app/main/views.py::update_status`：失败且 context 非空时签发 actor 绑定令牌；GET 重试基线使用 status\_config。`app/api/views.py::cron_status` 将同一 context 与调用凭据摘要签名到响应头。
- `cron_edit_apply.py::check_version`：通过独立连接核对 DB 当前 revision/status，读取故障转换为 EditWriteError；不得把这个必要的提交后并发核验一并删除或笼统禁止所有 SELECT。

## 3. 推荐方案

1. 提取共享的配置摘要计算，使既有 status\_config(task) 和保存路径从同一六字段规范计算摘要；保证字段顺序、空值处理、JSON 默认编码、密钥和 HMAC 结果与现有 token 完全一致。调用者、签名 salt、schema 和现有令牌继续兼容。
2. 保存或明确目标重试前，从已取得的同一调度快照计算摘要，保存为请求内普通字符串；保证此步发生在业务 commit 前且在受控错误边界内。快照、revision 和目标须属于同次决定，禁止 commit 后通过 ORM task 再读取来构造 context。
3. commit 确定返回后才用上述不可变原始值填充 context，随后沿用 apply\_status 的独立版本核验、同步应用及有限观察。commit 抛异常时不填 context、不调用调度或成功日志；无 context 的内部调用保持兼容。若摘要计算或读取在 commit 前失败，回滚并返回既有安全失败，不向调用方暴露异常文本。
4. 保留 D2 的 no-op、签名令牌、缺失 Job、陈旧版本拒绝及调度不确定处理。业务已提交后不回滚旧状态，不用新值冒充旧快照，也不声称数据库和调度器跨库原子。

备选为仅在提交后增加异常捕获：可避免未处理异常，但已保存状态缺少可靠的重试摘要，仍可能留下状态与调度不一致；因此不作为首选。单纯关闭 expire\_on\_commit 会改变应用全局会话语义，亦不采用。

## 4. 范围与边界

实现修改 app/services/cron\_status\_apply.py、app/main/views.py 的启停路由及对应测试；必要的可复验隔离测试工具、文档和复盘按批次补齐。Web/API 返回结构、模板、静态资源、数据库结构、用户授权规则、成功审计既有 best-effort 语义不变。本设计无前端可见改动，不需页面 Before/After；实际浏览器交互仍须验证。启停读前异常、全量六失败、图片资产、版本归档与 Docker 发布包不由本项自动关闭；如发现须扩大接口或 UI 行为，应先修订本稿并重新确认。

## 5. 实施分批

1. S0：冻结当前受影响源码与工作区状态，重跑旧负例，明确注入点在真实提交后；旧输出原样保留。
2. S1：先补失败测试，再实现共享摘要与提交前快照，不修改全局 Session 行为；逐字段核对既有令牌格式。
3. S2：服务与 HTTP 测试确认失败分类、令牌、调度和版本事实；隔离 SQLite、MySQL、浏览器及关键路由回归。
4. S3：七项复盘、HTML/MD 与发布说明、索引和最新证据；实际重启本地服务并验证登录及相关路径后交付；不把专项通过说成版本发布通过。

## 6. 验收矩阵与命令

- 真提交后拒绝对同一 ORM 对象触发读取，同时允许 check\_version 的独立连接读取：摘要不再触发隐式 SELECT；正常应用仍成功且目标和 Job 一致。另单独令独立版本查询失败，断言受控失败、数据库已保存、不冒称调度成功，签名重试上下文绑定正确。
- 在提交前摘要计算失败：明确无业务提交、无调度及成功日志，安全错误；在 commit 前/后分别注入 commit 异常，断言均不生成重试上下文、不调度，独立连接核对实际状态，不能断言两者必然相同。
- 实际 Web 与 API 成功/调度异常场景：校验令牌包含正确 actor、task、revision、target、config；旧实现产生的同配置令牌仍有效，改配置/版本、改 actor/target、伪造均拒绝；同目标重试不重复 resume。context=None 也需覆盖。
- SQLite/MySQL 独立库、真实 JobStore 与 Operator 浏览器确认→失败→重试；明确角色反向、CSRF、令牌泄露与敏感日志检查，覆盖启动与暂停。对防护作负向变异：恢复提交后读取须使测试失败；令牌摘要改变须被兼容性测试发现。

```
.venv-py311/bin/python doc/qa/evidence/commit-review-2026-11-03/status_postcommit_read.py
.venv-py311/bin/python -m unittest tests.test_cron_status_apply_d2 tests.test_cron_status_logging_d2 tests.test_cron_edit_concurrency -q
.venv-py311/bin/python scripts/smoke_routes.py --check
.venv-py311/bin/ruff check app/
.venv-py311/bin/python scripts/check_terminology.py --check
.venv-py311/bin/python scripts/html_docs_to_markdown.py --check
```

第一条是旧负例，修复前用于复现；修复后应以新测试观察实际状态，不可因旧探针退出 0 就认定修复成功。新增测试与双后端浏览器命令在确认后的实施批确定并保存验收记录。

## 7. 风险与回滚

摘要算法变动可能让旧令牌失效；以逐字段空值、Unicode、定时模式及现有令牌兼容测试阻断。快照与后续变化之间仍存在跨库窗口，现有版本核验只能有限检测，不承诺分布式串行。回滚应一起回退摘要实现和新增调用，保留已有业务数据；不得以恢复旧 DB 状态补偿未知调度。

## 8. 设计阶段核验

本稿基于当前工作区读取上述源代码与既有 D2 验收；故障注入的已保存状态及异常见原记录。此前全量 1146 项、6 失败、12 跳过，发布图片资产 162 项错误和版本归档问题仍存在。以上为 rev.1 的设计阶段历史；确认后结果见第 9 节。

## 9. 实施复盘与最终验收

1. **定位：**提交后服务使用过期 task 生成摘要可能触发 SELECT；Web 错误响应中的 actor.id 也可能在提交后触发 SELECT。两处均可能绕过受控响应。[修复前实测](../qa/evidence/status-postcommit-snapshot-2026-11-03/before.json)。
2. **根因：**跨事务边界继续持有 ORM 实体，而提交使属性过期；错误路径缺少在提交前冻结恢复令牌所需普通值。
3. **测试漏洞：**旧用例覆盖调度异常但未禁止提交后 ORM 加载，故未覆盖成功提交、读取失败和重试令牌生成的组合。
4. **修复：**摘要从提交前六字段快照计算并复用；Web 在提交前保存 actor ID；提交阶段异常包括 StaleDataError 保守判为结果待核实。旧摘要格式、令牌字段、权限与响应结构不变。
5. **防护测试：**tests/test\_status\_postcommit\_snapshot.py 覆盖提交后 ORM 加载拒绝、真实 Job 启停、Web/API 错误令牌、旧摘要一致性、摘要失败、提交前及已提交后异常、提交期版本异常和独立版本读取故障。最终相关回归 40 项通过；关键路由 86/86、Ruff 通过。[旧探针修复后结果](../qa/evidence/status-postcommit-snapshot-2026-11-03/after.json)显示提交成功、无过期读取、调度调用一次；旧探针替换了调度调用，不单独证明实际 Job 状态。
6. **同类排查：**Web 路由确有同源 actor 隐式读取并一同处理；API 路由提交后使用已计算的凭据摘要而非 ORM 对象。独立连接版本检查保留；执行态调度与数据库仍非跨库原子。
7. **预防方案：**新增提交后禁止 ORM 列加载的服务、Web 与 API 测试，并覆盖旧摘要兼容和提交结果未知。落点 tests/test\_status\_postcommit\_snapshot.py，执行 `.venv-py311/bin/python -m unittest tests.test_status_postcommit_snapshot -v`；恢复任一旧的提交后对象读取会触发失败。

隔离 SQLite/MySQL 启停验证均输出 D2\_VERIFIED 和 D1\_API\_VERIFIED；包括真实 Operator 浏览器确认、失败重试、角色反向和 JobStore，D1 页面本轮跳过。[SQLite 输出](../qa/evidence/status-postcommit-snapshot-2026-11-03/sqlite.txt)；[MySQL 输出](../qa/evidence/status-postcommit-snapshot-2026-11-03/mysql.txt)。完整全量套件未在本轮重跑；上次 6 失败、12 跳过，发布图片资产和版本门禁等未因本修复消失。

**本地环境限制：**重启开发服务时日志报告 SQLite 索引损坏，实际 `PRAGMA integrity_check` 返回 `row 8 missing from index ix_apscheduler_jobs_next_run_time`；`quick_check` 为 ok 不能排除该问题。5001 当前未运行；未重建索引、未恢复或修改数据库以掩盖问题。该观察无法单凭现有证据判断何时或为何发生，须另行保护数据并诊断。生产 5860 状态显示运行，不因此断言其数据库安全。

已启动独立临时 SQLite 预览，调度器全局暂停。登录页 HTTP 200，浏览器以测试账号 POST 登录后显示任务中心。用户名 `d1_preview`，密码 `D1-preview-only-2026!`；打开任务“D1暂停示例”，可查看启停按钮并操作测试任务。此预览只能复验常规交互；提交后 ORM 读取故障由上述自动化测试验证。

```
http://127.0.0.1:50992/rbac/login
```

[Markdown 版](status-postcommit-snapshot-repair-2026-11-03.md) · [文档索引](../index.html)

---

[← 文档索引（HTML）](../index.html) · [← 文档索引（Markdown）](../index.md)
