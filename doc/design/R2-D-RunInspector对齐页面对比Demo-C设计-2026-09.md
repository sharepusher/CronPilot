# R2-D Run Inspector 对齐页面对比 Demo §C 设计（2026-09）

> HTML 版：[R2-D-RunInspector对齐页面对比Demo-C设计-2026-09.html](R2-D-RunInspector对齐页面对比Demo-C设计-2026-09.html) · [文档索引](../index.html) · [索引 Markdown](../index.md)

# R2-D · Run Inspector 对齐页面对比 Demo §C

待确认
UX · Run Inspector
纠偏 R2 与原方案 Demo  
日期：2026-09-17 · UI 权威：
[页面对比 Demo §C](任务执行链路可观测性-页面对比Demo.html)
· 场景补充：[Run Inspector 目标态 Demo](任务执行链路可观测性-RunInspector-Demo.html)
· 前序：[R2](R2-RunInspector-Presenter详情契约收口设计-2026-09.html)（已实施但偏离 §C）

**入口：**
[问题](#problem)
[根因](#root)
[方案](#solution)
[页面对比](#page-compare)
[范围](#scope)
[分批](#batches)
[验收](#accept)
[风险](#risk)

**一句话：**把 `/job_log_detail`（Run Inspector）的**改造后画面**拉回与
[页面对比 Demo §C](任务执行链路可观测性-页面对比Demo.html)
「改造后：先链路、后下钻」一致。本批不是 R3-C（任务详情最近执行 / Demo §B）。

**说明：**此前误把「与原方案 UI 不一致」理解成 Demo §B，并改写了 R3-C。用户所指是 **§C Run Inspector 执行详情**。R3-C 暂停，本设计专治 Run Inspector。

## 1. 问题

原方案 Demo §C / 目标态 Demo 约定的详情页形态，与现网 R2 实现不一致，用户打开详情时看不到「原方案里的 UI」。

| Demo §C TO-BE | 现网 R2 |
| --- | --- |
| Header 含相对时间（如「5 分钟前」） | 无 |
| Meta 含**计划延迟** + HTTP + 耗时 + 触发方式 | Meta 无计划延迟；延迟藏在元数据「启动开销」 |
| 主诊断区标题「**执行链路**」+ 竖线链（标题行 + 副文案） | 「执行时间线」+ `ri-timeline` 栅格（时刻/点/标签/偏移） |
| 链路下一步为「**响应 / 诊断**」 | 拆成请求 / 响应 / 业务日志 / 元数据 |

## 2. 根因

R2 设计稿写明「以实页为准、可再回写 Demo §C」，主动偏离了父 Demo。父 Demo 仍是产品确认过的 UI 权威；现网未回写对齐。

## 3. 方案

可见效果以 Demo §C TO-BE 为准（下节原文照录）。实施要点：

1. **Header**：badge 旁恢复相对时间（已有时间工具则复用）。
2. **Meta**：展示「计划延迟」（数据即现有 `trigger_delay_ms`）；保留 HTTP / 耗时 / 触发方式；失败原因可保留（目标态 Demo 亦有）。
3. **主区块**：标题改为「执行链路」；列表形态对齐 Demo 链（主标题 + 副行 `T+…`），仍只消费 Presenter 时间线 DTO（不回 raw detail）。
4. **其后**：保留可折叠的请求；响应区标题对齐「响应 / 诊断」（超时等无 body 时展示诊断文案）。业务日志 / 元数据仍可保留在更下方（目标态 Demo 有请求；§C 示意省略不影响保留）。
5. **不动**：路由、Presenter 三角色裁剪、禁 raw JSON、未完成提示条（可保留在 Meta 下）。

## 4. 页面对比（Before / After）

下列画面与
<任务执行链路可观测性-页面对比Demo.html>
**§C Run Inspector 执行详情**相同（AS-IS / TO-BE 原文照录）。

现状：终态详情平铺
AS-IS

执行 #10481
⏱ 超时
5 分钟前

HTTP **—**
耗时 **5.0s**
失败原因 **请求超时**

请求

POST https://api.example.com/v1/orders/trigger

响应

无响应内容

问题：不知道请求前经过哪些步骤、请求何时发出，也难以查看未终态记录。

改造后：先链路、后下钻
TO-BE

执行 #10481
⏱ 超时
5 分钟前

计划延迟 **18ms**
HTTP **—**
耗时 **5.0s**
触发方式 **定时调度**

执行链路 新增 · 系统事件 + 业务日志

- **任务入队**T+0ms · 计划时间 → 实际进入 18ms
- **安全校验**T+20ms · DNS Pinning 校验通过
- **发起 HTTP 请求**T+24ms · POST /v1/orders/trigger
- **请求超时**T+5.00s · 等待超过任务配置阈值

响应 / 诊断

请求在 5s 超时阈值内未返回响应。

变化：请求、响应、业务日志、元数据均保留；时间线成为首要诊断区，详情只消费 Presenter 的角色化 DTO。

## 5. 范围

| 做 | 不做 |
| --- | --- |
| - `run_inspector.html` / `redesign-pages.css`：对齐 Demo §C 信息架构与链路样式 - Presenter：Meta 暴露计划延迟；链路项主/副文案足够支撑 Demo 形态（仍无 raw detail） - 测试：HTML 含「执行链路」「计划延迟」；无 raw detail JSON | - R3-C 任务详情最近执行（Demo §B）— 另议 - 新路由 / events API / 双栏 - 改 R1 列表 |

## 6. 分批

| 子批 | 内容 | 可独立验收 |
| --- | --- | --- |
| R2-D1 | Header 相对时间 + Meta 计划延迟 + 标题「执行链路」 | 浏览器对照 Demo §C Meta/标题 |
| R2-D2 | 链路列表样式（主标题+副行）+「响应 / 诊断」 | 对照 Demo §C 链路区 |
| R2-D3 | 测试 + 设计已实施 + RELEASE | 门禁绿 |

## 7. 验收

1. 打开超时类执行详情：画面关键区与 Demo §C TO-BE 同构（相对时间、计划延迟、执行链路、响应/诊断）。
2. 与 [页面对比 Demo §C](任务执行链路可观测性-页面对比Demo.html) 并排对照。
3. `restart` 后 curl/浏览器断言；Presenter 测试仍禁 raw detail。

## 8. 风险

链路展示文案若改回 Demo 用词（「任务入队」等），须与 Presenter 标签表同步，并回归既有事件类型测试。相对时间依赖现有时间格式化工具，避免新时钟漂移。

**请确认后开干：**回复「按此方案执行」。确认前不改 `app/`。

UI 权威：[页面对比 Demo §C](任务执行链路可观测性-页面对比Demo.html) ·
[目标态 Demo](任务执行链路可观测性-RunInspector-Demo.html) ·
<#page-compare> ·
[Markdown](R2-D-RunInspector对齐页面对比Demo-C设计-2026-09.md)

---

[← 文档索引（HTML）](../index.html) · [← 文档索引（Markdown）](../index.md)
