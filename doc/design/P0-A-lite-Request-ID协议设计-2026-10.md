# P0-A-lite Request ID 协议设计（2026-10）

> HTML 版：[P0-A-lite-Request-ID协议设计-2026-10.html](P0-A-lite-Request-ID协议设计-2026-10.html) · [文档索引](../index.html) · [索引 Markdown](../index.md)

# P0-A-lite Request ID 协议设计

版本：rev.3 · 日期：2026-10-10 · 状态：**待确认，未授权实施** · 父文档：[统一错误处理治理路线图](统一错误处理P0实施计划-2026-09.html)

## 版本变更记录

| 版本 | 日期 | 内容 |
| --- | --- | --- |
| rev.3 | 2026-10-10 | 处理 R1—R9：整合现行条款，补齐前置契约、精确边界与用例断言；仅修订设计。 |
| rev.2 | 2026-10-09 | 落实专业评审：补充当前源码基线、机器登记的强制字段和冻结门槛；明确响应覆盖边界、ContextVar 生命周期与 P0 关闭条件。 |
| rev.1 | 2026-10-08 | 从总览拆出 request\_id 协议、登记、OpenAPI、双 ID、缓存、发布与验收，成为本功能唯一实施规格。 |

## 交付契约矩阵

| 维度 | 本方案契约 |
| --- | --- |
| 对象/传输类型 | API / 管理 JSON |
| 调用方 | 内部脚本、Swagger、管理浏览器 |
| 认证边界 | Token/scope 或 Session/CSRF/RBAC |
| 唯一性责任 | 调用方每次尝试生成 UUID v4，不历史去重 |
| 缺失/非法行为 | required 缺失/非法为精确 400；SSR/双模式豁免 |
| 响应/日志关联 | 合法 request\_id 同值 Header/日志；执行 ID 独立 |
| 浏览器验收 | 逐 endpoint+method+mode 测试，浏览器三类调用与代理 |
| 交付物 | 本文件 HTML 与同名 Markdown、双索引、顶部版本记录；交付提供完整 URL。实施验收报告按本方案标识落入 doc/qa/，附用例结果和证据。 |

## 1. 问题与根因

当前全局 `before_request` 对所有请求自动生成或接受 `X-Request-Id`，写入 `g.trace_id` 与共享 `_ctx_trace_id`；无分类、格式校验、响应回传或 ContextVar 恢复。scheduler 同样复用该字段，导致 HTTP 与执行 trace 混用。

## 2. 目标、范围与非范围

目标：为登记 JSON 请求建立必填 UUID v4、同值响应 Header、零副作用协议拒绝和独立 HTTP/scheduler 日志关联。非范围：完整 JSON 错误信封、幂等、业务库 request\_id 字段、HTML/原生 form 改造、scheduler 状态机。

## 3. 契约与分类

**格式：**长度 36，完整匹配 `^[0-9A-Fa-f]{8}-[0-9A-Fa-f]{4}-4[0-9A-Fa-f]{3}-[89AaBb][0-9A-Fa-f]{3}-[0-9A-Fa-f]{12}$`；空白、逗号、多值非法；合法值原样回传但不查历史重复。

| 分类 | 规则 | 代表入口 |
| --- | --- | --- |
| `API_REQUIRED` | 内部 API operation 必填 | `GET /api/cron/query`、`POST /api/cron` |
| `MANAGEMENT_JSON_REQUIRED` | 纯 JSON POST 与 `partial=1` GET 必填 | `POST /cron_retire`、`GET /cron_list?partial=1` |
| `DUAL_POST_EXEMPT` | 同一业务 POST 同时支持原生 form/JSON，暂不要求 | 三个 reset POST |
| `SSR_EXEMPT` | 导航、form、文档、static、HEAD/OPTIONS、未匹配 404/405 不新增 Header | `GET /cron_retire` |

分类键固定为 endpoint + method + 显式模式。实施前由路由与调用扫描生成机器登记并签核；不得以 Accept、`X-Requested-With`、Session、状态码或 Header 是否存在猜测。登录 302 不改变已匹配 required 请求的分类。

## 4. 流程与响应

顺序固定：HTTP/代理解析 → Flask 路由匹配 → 分类 → request\_id 校验 → 鉴权 → CSRF → schema/view → 副作用 → `after_request`。

- required + valid：进入 Flask `after_request` 的 2xx、302、业务 400、401、403、404、422、500 回传同值 Header。
- required + missing/invalid/multiple：鉴权和副作用前返回 400、无 Header；body 含稳定 `code=REQUEST_ID_INVALID`。
- exempt：不新增 Header。代理提前拒绝或进程级失败由对应基础设施负责，不能冒充 Flask 契约。

## 5. 实施方案（已确认契约迁入）

1. **协议模式登记与校验顺序：**实现前冻结“endpoint + method + URL + Blueprint + 显式模式 + 调用位置 + 分类 + 生成点 + 缓存/OpenAPI 要求 + 测试 ID”机器登记表。分类键固定为 endpoint + method + 显式模式。API Blueprint 业务 GET/POST 为 `API_REQUIRED`；纯 JSON 管理端点和已定义 `partial=1` 的 GET 模式为 `MANAGEMENT_JSON_REQUIRED`；普通 SSR 为 `SSR_EXEMPT`；只有业务响应本身同时支持原生 form 与 JSON 的 POST 才是 `DUAL_POST_EXEMPT`。应用内顺序固定为：代理/服务器 HTTP 解析 → Flask 路由匹配 → endpoint/method/mode 分类 → request\_id 校验 → 应用鉴权 → CSRF → schema/view → 副作用。自动 HEAD/OPTIONS、Swagger/OpenAPI、static、metrics、文档、未匹配 URL 的 404 与方法不匹配 405 均豁免；已匹配 required endpoint 内部产生的 302/401/403/404/422/500 仍遵循 required 契约。不能因端点可能触发登录重定向就把它改为豁免。
2. **响应传播与精确 400：**`after_request` 只依据“本请求分类为 required 且已经验证成功”的状态回传同值 Header，不依据 status、Content-Type 或是否重定向。真值表固定为：required + valid → 进入 Flask `after_request` 的应用 2xx、302、业务 400、401、403、404、422、500 均回传；required + missing/invalid/multiple → request-id 协议 400 且不回传；exempt → 不新增 Header；代理/网关提前拒绝或进程级失败 → 由该层定义响应，不能冒充 Flask 契约。API Blueprint 的协议 400 body 固定为 `{"errcode":1,"code":"REQUEST_ID_INVALID","errmsg":"X-Request-Id 缺失或格式不符合 UUID v4 要求","data":null,"result":null}`；管理端 JSON 固定为 `{"errcode":1,"code":"REQUEST_ID_INVALID","errmsg":"X-Request-Id 缺失或格式不符合 UUID v4 要求","result":null,"url":null}`。稳定 `code` 用于区分已有业务 400（例如 `POST /api/cron` 的 scope 错误）；对外只公开这一协议码，内部日志可记录 `missing/invalid_format/multiple_values`，但不记录原始非法值。使用独立入口响应函数，避免扩大公共 helper；该加法字段须在实施时按 API 返回结构变更规范在 Release Notes 标注 `⚠️ API Breaking Change`。
3. **管理页面受控请求：**公共 jQuery 工具仅在调用点或表单显式设置 `requestIdRequired: true` 时注入 Header；`js-ajax-form` 通过表单标记启用，`fetch()` 走 required-JSON wrapper，直接 `XMLHttpRequest` 使用同一生成工具。直接 `$.post()`（包括 dashboard 的 `POST /cron_retire`）改为共享 JSON POST 封装或显式 `$.ajax`，不得依赖无法携带选项的快捷调用。真正双模式 POST 不设置标记。优先使用安全上下文中的 `crypto.randomUUID()`；不支持时仅可用 `crypto.getRandomValues()` 构造 UUID v4，禁止 `Math.random()`。每次重试生成新值；禁止 hidden input，也不得仅凭存在全局 `ajaxSetup()` 宣称覆盖完成。
4. **调度执行与双 ID 日志：**scheduler 每次 `cron_do` 生成独立 UUID v4 execution trace，并通过既有 `cronpilot_trace_id` 关联 JobLog。结构化日志新增规范字段 `request_id` 与 `execution_trace_id`：定时执行前者为空；HTTP 手动执行期间两者同时存在；响应只回传 request\_id。兼容字段 `trace_id` 暂按 `execution_trace_id or request_id` 输出，新实现不得依赖其识别语义。P0-A-lite 不新增 JobLog request\_id 列，也不把 HTTP request\_id 传播为被触发下游请求的 Header。
5. **内部 API 文档：**使用 APIFlask 2.4 的全局 `spec_processor` 为每个业务 operation 注入同一 OpenAPI 参数组件：`name: X-Request-Id`、`in: header`、`required: true`、`schema: string`、`format: uuid` 及 UUID v4 pattern。响应文档明确区分：来自已验证请求的所有已声明响应均包含同值 response Header；request-id 协议 400 响应不含该 Header且 body 含 `code=REQUEST_ID_INVALID`；既有业务 400 仍属于已验证请求并回传 Header。不得以 body 字段或 APIFlask `input(..., location='headers')` 取代该文档注入。
6. **ContextVar 生命周期：**HTTP 使用 `_ctx_http_request_id`；scheduler 使用 execution trace、cron\_id、task\_name、duration\_ms、status；`single_task()` 另有 enqueue\_time。HTTP 状态机为：required + valid → set 并把 ContextVar 恢复令牌和“未消费”标志存入请求局部 `g` → after\_request 回传 → teardown 只 reset 一次并标记已消费；invalid/exempt 不创建令牌，重复 teardown 不得重复 reset。`cron_do` 最外层 try/finally 必须包住 execution trace 分配、JobLog、配置读取、执行、指标和最终日志，并反向 reset 首次 set 的全部令牌。`single_task()` 的 enqueue\_time 也由覆盖所有 early return/异常的 try/finally 恢复。ContextVar 的 `Token` 是标准 API 返回的恢复句柄，不是认证 token；仅在创建它的同一上下文使用一次，不得以 `set(None)` 代替 reset。
7. **execution trace 分配：**先生成 UUID v4 候选并初始化 scheduler 上下文，再创建 pending JobLog；只有捕获到并确认是 execution trace 唯一约束冲突的 `IntegrityError` 才允许生成新候选重试，其他完整性错误必须 rollback 后原样抛出。JobLog 创建成功后才记录正式 `cron.start`；分配失败记录 `cron.allocate_failed`，不得制造“已经开始”的假事件。最终 JobLog、上下文和结束日志必须使用同一个 execution\_trace\_id。
8. **日志与缓存/代理边界：**logging filter 同时输出 request\_id 与 execution\_trace\_id，不能用“优先级”丢弃其中之一。所有 required 动态 JSON GET 的响应设置 `Cache-Control: no-store`；fetch 使用 `cache:'no-store'`，jQuery GET 使用 `cache:false`，直接 XHR GET 必须走 wrapper；发布时清理代理相关动态路径的历史缓存。不得以 `Vary: X-Request-Id` 或 query 参数 ID 替代。调用方只发送一个长度 36 的 UUID v4；代理不得静默选择重复值，可保留多值供 Flask 拒绝或在代理层直接拒绝。只有请求到达 Flask 时才承诺上述 JSON 400；代理前置拒绝使用代理自己的响应体。上线前同时验证直连应用和真实代理路径不覆盖/剥离合法响应 Header。

来源：总稿历史 §2.1.1 的八项条款等价迁入本节；本节为现行规范。手动执行在同一执行上下文同步进入 cron\_do 时保留两个 ID；若后续改为跨线程/队列，必须显式传递已验证 request\_id 并在接收上下文创建/恢复自己的令牌，不能跨上下文复用 Token。新定时执行不得继承无关 HTTP ID。scheduled\_run\_time 的既有 executor 作用域也须纳入检查，保持原有来源语义。

## 6. 分批、验收与风险

| 批次 | 退出条件 |
| --- | --- |
| A-lite-1 | 机器登记冻结；调用方、分类、校验、Header、协议 400、OpenAPI 的 endpoint+method+mode 测试通过。 |
| A-lite-2 | 双 ID、ContextVar、异常/嵌套/重复 teardown、trace 唯一冲突测试通过。 |
| A-lite-3 | no-store、真实代理、资源版本化、原子发布与整版回滚演练完成。 |

同一动态 GET 的不同 ID 都必须抵达 Flask；302 禁止自动跟随检查；代理多值不得静默选择。当前无外部使用方，采用原子发布；旧标签页提示刷新。失败时整版回滚 hook、前端资源、OpenAPI、日志接入和缓存。

## 7. 确认点

确认后仅先执行 A-lite-1 的登记与基线测试；A-lite-2、A-lite-3 分别以独立验收报告关闭。

## 8. 证据、登记与边界

**当前基线（仅作事实依据，不是实现）：**`app/__init__.py` 的全局 `before_request` 当前接受或生成 ID，写入 `g.trace_id` 与共享 ContextVar，未按协议分类、未验证格式、也未保存恢复句柄；`app/logging_config.py` 定义该 ContextVar，scheduler 复用它；`app/crons.py` 当前使用 UUID1 且在创建 pending JobLog 前记录开始事件；`app/common/functions.py` 的 `single_task()` 设置 enqueue 上下文但未成对恢复。实施不得把这些现状误述为已满足本设计。

| 机器登记必填列 | 冻结要求 |
| --- | --- |
| endpoint、method、显式模式、blueprint、路由来源、调用方来源、当前响应类型、目标分类、ID 生成点、缓存策略、OpenAPI 状态、测试 ID、责任评审人 | 路由扫描与 JS/脚本调用扫描共同生成；每行人工核验。未登记、调用方未定位或分类有歧义的端点不得改代码；新增路由先更新登记与测试。 |

**Header 覆盖边界：**仅已通过协议校验且由 Flask 生成的响应对象，经 `after_request` 返回时回传同值 Header。网关拒绝、TLS/WSGI 失败、路由未匹配与进程崩溃不属于本承诺；不得以应用测试宣称其也必然带 Header。

**ContextVar 恢复：**`set()` 的返回值是恢复句柄，应命名为 `restore_token` 或 `context_restore_token`，不是鉴权 token。每个 HTTP、scheduler 与 enqueue ContextVar 各自保存自己的句柄，在同一执行上下文的 finally/teardown 中恰好 `reset(restore_token)` 一次；异常、嵌套与重复 teardown 都必须覆盖。

## 验收用例与迁移映射

旧 §2.1.1 分类/响应 → 本 §3—5 → A-01：缺失、空白、非 v4、多值精确 400 且无业务调用；有效值覆盖各应用状态同值 Header。生成/双 ID → §5 → A-02：两次尝试不同值、非安全上下文生成、定时/手动不混淆。上下文/分配 → §5 → A-03：六类执行字段、HTTP 字段及调度时点按归属恢复，异常、嵌套、重复 teardown、非唯一约束错误、分配失败均覆盖。OpenAPI/缓存/发布 → §5—6 → A-04：登记全覆盖、真实代理两次请求到达 Flask、旧标签页与整版回滚。

拟新增 tests/test\_request\_id\_contract.py、tests/fixtures/request\_id\_registry.json；实施阶段命令 python -m unittest tests.test\_request\_id\_contract -v。当前未创建/执行这些业务测试。登记产物包含调用点、分类、测试 ID；每条迁移条款由 A-01—04 明确承接，记录到 doc/qa/request-id-acceptance.html。

[文档索引](../index.html) · [Markdown](P0-A-lite-Request-ID协议设计-2026-10.md)

---

[← 文档索引（HTML）](../index.html) · [← 文档索引（Markdown）](../index.md)
