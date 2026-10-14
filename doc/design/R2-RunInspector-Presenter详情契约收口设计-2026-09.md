# R2 Run Inspector Presenter/详情契约收口设计（2026-09）

> HTML 版：[R2-RunInspector-Presenter详情契约收口设计-2026-09.html](R2-RunInspector-Presenter详情契约收口设计-2026-09.html) · [文档索引](../index.html) · [索引 Markdown](../index.md)

# R2 · Run Inspector Presenter / 详情契约收口设计

已实施
UX · 执行详情
收敛版 B4 · 短设计  
日期：2026-09-16 · 父设计：[收敛版 §5.4–5.5 / B4](任务执行链路可观测性设计方案-收敛版.html) · 对照 Demo：[页面对比](任务执行链路可观测性-页面对比Demo.html) · 前序：[R1](R1-执行记录列表pending-running显示收口设计-2026-09.html)

**入口：**
[问题](#problem)
[根因](#root)
[方案](#solution)
[页面对比](#page-compare)
[范围](#scope)
[分批](#batches)
[验收](#accept)
[风险](#risk)

**一句话：**详情页已能打开且有时间线，但诊断顺序反了（时间线垫底），且 admin 仍可能看到事件 `detail` 的 JSON 串。本轮把时间线上移为摘要下第一诊断区，并按 Viewer / Operator / Admin 裁剪 DTO——**任何角色都不得再看到原始 detail JSON**。

## 1. 问题

用户打开 `/job_log_detail`（Run Inspector）时：

1. **诊断路径反了**：先看到请求/响应/业务日志/元数据，时间线在最下方，与「先看走到哪一步、再下钻」不符。
2. **敏感边界不达标**：`include_detail=True`（当前 `session.role=='admin'`）时，时间线把整段 `event.detail` `json.dumps` 进页面；设计要求**任何角色都不可见原始 detail JSON**。
3. **角色粒度不够**：仅 admin / 非 admin；Viewer 与 Operator 同权（都看不到正文），Admin 看到全文。设计矩阵要求 Operator 有「有限诊断摘要」。

**已有、本轮不重复造的：**Presenter DTO 接线已完成；pending/running 徽章文案已含「最终结果未知」；URL 查询值已统一脱敏为 `***`（执行详情 URL 脱敏修复）。

## 2. 根因

| 层 | 事实 |
| --- | --- |
| 模板 DOM | `run_inspector.html` 顺序：Header → Meta → 请求 → 响应 → 业务 → 元数据 → **时间线**。热修接线时保留了旧区块顺序。 |
| Presenter | `_detail_value(..., include_detail=True)` 直接 `json.dumps` 全量 detail；无白名单摘要字段。 |
| 视图鉴权 | `can_view_sensitive = (role == 'admin')` 二元门，未区分 viewer / operator；亦未覆盖「禁止 raw JSON」硬约束。 |

## 3. 方案（推荐）

### 3.1 信息架构（可见顺序）

固定为：

1. Header（ID + 状态徽章）
2. Meta（HTTP / 耗时 / 开始结束 / 触发方式 / 失败原因）
3. **未完成提示条**（仅 `pending`/`running`）：「执行未完成，最终结果未知」——徽章已有文案时仍保留一条独立提示，避免只扫 meta 漏读
4. **执行时间线**（首要诊断区）
5. 请求 / 响应 / 业务日志 / 元数据（保留；默认折叠行为见下）

折叠约定（沿用既有 `ri-section-head` 点击若已有；无则最小增量）：

- `success`：请求/响应/业务默认折叠
- `fail`/`error`/`timeout`：优先展开「响应」一节
- `pending`/`running`：时间线展开；请求/响应可折叠

### 3.2 时间线行契约（禁止 raw JSON）

| 字段 | 含义 |
| --- | --- |
| `label` | 阶段中文名（已有映射） |
| `time` / `offset_ms` | 时刻与相对耗时 |
| `outcome` | 结果语义 class |
| `summary` | **唯一**可展示的附加文案：由 Presenter 从 detail 白名单键生成（如 `method`、`block_type`、`http_status`）；缺键则空 |
| `detail` | **删除或恒为空**；模板不得再渲染 `event.detail` |

白名单摘要示例（实现时落在 Presenter，可测）：

- `http.start` → `GET`（仅 method；URL 不进时间线行，避免重复与泄露）
- `http.complete` → `HTTP 200`
- `ssrf.check` blocked → `拦截：private_ip`（类型枚举，非原文）
- `http.error` → Viewer：`请求异常`；Operator/Admin：`连接失败` 等有限类型文案，**不**输出 `exc_detail` 原文

### 3.3 角色矩阵（本轮落地版）

| 能力 | Viewer | Operator | Admin（含 Biz / Seed） |
| --- | --- | --- | --- |
| 状态 / 阶段 / 耗时 / 触发 | ✓ | ✓ | ✓ |
| 时间线 `summary` | 通用短句 | 有限诊断短句 | 同 Operator + 允许的类型枚举 |
| 请求 URL | scheme + host + path（**无 query**） | 脱敏 URL（键名 + `***`） | 同 Operator |
| 响应正文 | 占位：「响应正文仅管理员可见」→ 改为「无权限查看正文」 | 截断摘要 ≤200 字（去 HTML 噪声） | 截断正文 ≤2KB（仍非无限） |
| 业务日志全文 | 不展示区块 | 不展示全文（时间线若未来合并另议） | 可见（已有） |
| 原始 detail JSON / 模型字段 | 禁止 | 禁止 | 禁止 |

视图入参：由 `session['role']` 映射为 `viewer` / `operator` / `admin` 传给 Presenter（替换裸 `is_admin` 布尔，或保留布尔并新增 `viewer_role` 枚举——实现择一，测试锁三角色）。

**待确认点（默认按上表）：**Viewer 的 URL 是否隐藏整个 query（推荐：隐藏）。若你希望 Viewer 也看到 `token=***` 键名，回复时说明即可。

### 3.4 交互契约

| 项 | 约定 |
| --- | --- |
| 路由 | 仍 `GET /job_log_detail?id=`；无新 API、无新导航 |
| 模板 | 只读 `run.*` DTO；禁止 `jl`/`cif`/`event.detail` |
| 折叠 | **已有**：`.ri-section-head` 点击切换 `.collapsed`（见模板底部 JS）。本轮**不重做**折叠交互；仅重排 DOM。可选：失败态响应 section 默认不加 `collapsed`，成功态请求/业务可默认 `collapsed`（若做须写进验收） |
| 时间线文案 | 标签必须与 Presenter `_EVENT_LABELS` 一致（如「已入队」「发送 HTTP 请求」「HTTP 请求超时」），禁止另造「任务入队 / 发起 HTTP」等旧 Demo 用词 |

## 4. 页面对比（Before / After）

对照源：当前模板 `app/templates/redesign/run_inspector.html` + `redesign-pages.css` 中 `.ri-*`。示意 DOM class / 区块标题 / 时间线标签与实页同构；数据为同构样例（非生产 ID）。

打开本页时若样式异常，请用本地文档服务或 `file:` 路径加载 `../../app/static/css/`。结构仍可对照下方 HTML。

本对比**修正**了早期线框版与实页的偏差：不再用灰色卡片堆砌；使用真实 `ri-header / ri-meta / ri-section / ri-timeline`；区块标题为「执行时间线」而非「执行链路」；Admin BEFORE 展示真实 `<code class="ri-timeline-detail">` JSON dump。

### 场景 A · 超时终态（Admin）

问题：顺序反了 + 时间线泄 raw detail

BEFORE · 与当前模板一致
AS-IS · Admin

[任务中心](#)›
[订单触发检查](#)›
执行 #10481
`Esc` 返回

执行 #10481
⏱ 超时

HTTP **—**
耗时 **5.0s (超时)**
开始 **2026-09-16 16:20:01**
结束 **2026-09-16 16:20:06**
触发方式 **定时调度**
失败原因 **请求超时**

请求

POST https://api.example.com/v1/orders/trigger?token=\*\*\*&sign=\*\*\*

响应

无响应内容

元数据

任务订单触发检查
业务组订单中心
触发方式定时调度
Trace IDcp\_9f2a…e1
超时阈值5s
启动开销18ms

执行时间线 (5 项)

1. 16:20:01.012

   已入队
   +0ms
2. 16:20:01.030

   开始执行
   +18ms
3. 16:20:01.032

   安全校验
   +20ms
4. 16:20:01.036

   发送 HTTP 请求
   +24ms
   `{"method": "POST", "url": "https://api.example.com/v1/orders/trigger?token=secret"}`
5. 16:20:06.036

   HTTP 请求超时
   +5024ms
   `{"exc_detail": "HTTPSConnectionPool(...): Read timed out.", "timeout_sec": 5}`

问题：① 时间线在请求/响应/元数据**之后**（与模板 DOM 顺序一致）；② Admin 下 `include_detail=True` 把整段 detail `json.dumps` 进 `.ri-timeline-detail`，含明文 token / 异常栈。

AFTER · 本轮目标
TO-BE · Admin

[任务中心](#)›
[订单触发检查](#)›
执行 #10481
`Esc` 返回

执行 #10481
⏱ 超时

HTTP **—**
耗时 **5.0s (超时)**
开始 **2026-09-16 16:20:01**
结束 **2026-09-16 16:20:06**
触发方式 **定时调度**
失败原因 **请求超时**

执行时间线 (5 项)

1. 16:20:01.012

   已入队
   +0ms
2. 16:20:01.030

   开始执行
   +18ms
3. 16:20:01.032

   安全校验
   +20ms
4. 16:20:01.036

   发送 HTTP 请求
   +24ms
   POST
5. 16:20:06.036

   HTTP 请求超时
   +5024ms
   等待超过阈值

请求

POST https://api.example.com/v1/orders/trigger?token=\*\*\*&sign=\*\*\*

响应

无响应内容

元数据

任务订单触发检查
业务组订单中心
触发方式定时调度
Trace IDcp\_9f2a…e1
超时阈值5s
启动开销18ms

变化：时间线紧接 Meta；去掉 `.ri-timeline-detail`，改用白名单 `.ri-timeline-summary`；请求/响应/元数据区块保留、仅下移。面包屑与徽章文案不变。

### 场景 B · 执行中 pending（任意角色）

问题：仅靠徽章「最终结果未知」，摘要区无独立提示

BEFORE · 当前
AS-IS · pending

执行 #10502
○ 已入队 · 最终结果未知

HTTP **—**
耗时 **—**
开始 **2026-09-16 16:28:10**
触发方式 **定时调度**

请求

GET https://api.example.com/health

响应

无响应内容

元数据

任务健康检查
超时阈值5s

执行时间线 (2 项)

1. 16:28:10.100

   已入队
   +0ms
2. 16:28:10.118

   开始执行
   +18ms

问题：未完成语义只在徽章；时间线仍垫底，扫摘要区易当成「已发出请求但无响应」的终态页。

AFTER · 本轮目标
TO-BE · pending

执行 #10502
○ 已入队 · 最终结果未知

HTTP **—**
耗时 **—**
开始 **2026-09-16 16:28:10**
触发方式 **定时调度**

执行未完成，最终结果未知。以下为已记录阶段；请求/响应可能尚不完整。

执行时间线 (2 项)

1. 16:28:10.100

   已入队
   +0ms
2. 16:28:10.118

   开始执行
   +18ms

请求

GET https://api.example.com/health

响应

无响应内容

元数据

…

变化：Meta 下增加 `.ri-incomplete-banner`；时间线上移为首要区；请求/响应仍可点击折叠（复用现有 JS）。徽章文案保持 R1 Presenter 既有「最终结果未知」。

**与旧「页面对比 Demo §C」的差异说明：**既有 Demo TO-BE 使用了「执行链路」标题与 `demo-chain` 自定义列表，且 Meta 出现「计划延迟」——**均非当前实现**。本 R2 对比以实页为准；实现后可再回写 Demo §C。

## 5. 范围

| 做 | 不做 |
| --- | --- |
| - `run_inspector.html` 区块重排 + 未完成提示条 - `run_inspector_presenter.py`：去掉 raw detail 输出；三角色 DTO；时间线 `summary` - `views.py` `job_log_detail`：按 role 传 Presenter - CSS：提示条 / 时间线主位微调（`redesign-pages.css` · `.cp-page-run-inspector`） - 测试：Presenter 三角色 + HTML 否定断言（无 `{` 形态 detail / 无 `exc_detail`） | - 业务日志合并进时间线排序（收敛版完整态；留待 R2+ 或 B5 后） - 列表 / 默认筛选（R1 已做） - Tracer 写路径白名单扩字段（属 R3/B2 尾巴） - events API、新导航、双栏 - 标「可观测性已交付」/ B6 |

**可见变更清单：**

| 元素 | 旧 | 新 |
| --- | --- | --- |
| 区块顺序 | 请求→…→时间线 | 时间线紧接 Meta（+ 未完成提示） |
| 时间线附加信息 | 可能整段 JSON | 仅 `summary` 短句 |
| 未完成提示条 | 无独立条（仅徽章） | pending/running 显示提示条 |
| 面包屑 / 路由 / 列结构 | — | 不变 |

## 6. 分批

| 子批 | 内容 | 可独立验收 |
| --- | --- | --- |
| R2-A | DOM 重排 + 未完成提示条 + 最小 CSS | 浏览器：时间线在请求区之上；pending 有提示条 |
| R2-B | Presenter 去 raw JSON + 三角色 + views 传 role + 测试 | admin HTML 无 detail JSON；viewer/operator 断言矩阵 |
| R2-C | 设计状态→已实施；RELEASE 一行；复盘（若有回归缺陷） | 文档门禁 |

禁止与 R3 合同测试大文件、B5 保留策略同 commit。

## 7. 验收

1. `python -m unittest tests.test_run_inspector_presenter tests.test_job_log_detail_integration -v`（含新增三角色 / 否定 raw JSON 用例）
2. `bash scripts/cronpilot.sh restart --daemon` 后：
   - admin 打开含 events 的详情：时间线位于请求上方；源码无 `exc_detail` / 整段 `{"` 事件 dump
   - viewer（或等价受限账号）：无响应正文、无业务日志区、时间线无 JSON
   - pending/running 样本：可见未完成提示
3. Agent 自证：登录会话 curl + 断言 DOM 顺序（时间线 section 下标 < 请求 section）

## 8. 风险

- **Admin 诊断变「短」**：去掉 JSON 后依赖白名单摘要；须覆盖常见 event\_type，缺映射时显示空 summary 而非回退 JSON。
- **默认折叠**：现网已有点击折叠；若本轮给成功态加默认 `collapsed`，须在验收中点开确认内容仍在 DOM（非删除区块）。
- **角色会话**：验证须真实 viewer/operator 账号，不能只用 seed admin。

**状态：**已按本方案实施（R2-A/B/C，2026-09-16）。验收见 §7；复盘见 [raw detail 与时间线顺序](../postmortem/2026-09-RunInspector-raw-detail与时间线顺序.html)。

父设计：[收敛版 B4](任务执行链路可观测性设计方案-收敛版.html) ·
页面对比：<#page-compare> ·
全页 Demo：[既有 Demo §C](任务执行链路可观测性-页面对比Demo.html)
· [Markdown](R2-RunInspector-Presenter详情契约收口设计-2026-09.md) · [索引](index.html)

---

[← 文档索引（HTML）](../index.html) · [← 文档索引（Markdown）](../index.md)
