# CronPilot Run Inspector — 目标态场景 Demo

> HTML 版：[任务执行链路可观测性-RunInspector-Demo.html](任务执行链路可观测性-RunInspector-Demo.html) · [文档索引](../index.html) · [索引 Markdown](../index.md)

[CronPilot](#)

运维操作

[▦任务中心](#)[▤执行记录](#)

⌕搜索任务或操作…`⌘K`

[任务中心](#)›[订单触发检查](#)›执行 #10481

# Run Inspector：目标态场景

同一既有详情路由 `/job_log_detail` 的状态呈现、时间线与角色化字段边界。以下元素复用生产的 `ri-*`、`cp-*` 组件和令牌。

● 成功**success**HTTP 与业务判定成功。

⏱ 超时**timeout**请求超过任务阈值。

◎ 执行中**pending / running**可读已写事件；最终结果未知。

执行 #10481⏱ 超时5 分钟前

HTTP **—**耗时 **5.0s**触发方式 **定时调度**调度延迟 **18ms**失败原因 **请求超时**

执行链路 新增 · 系统事件 + 业务日志

- **任务入队**T+0ms · 计划时间 10:27:00.000 → 实际进入 10:27:00.018
- **安全校验**T+20ms · DNS Pinning 校验通过
- **发起 HTTP 请求**T+24ms · POST /v1/orders/trigger
- **请求超时**T+5.00s · 等待超过任务配置的 5 秒阈值

请求

POST https://api.example.com/v1/orders/trigger?token=••••

响应 / 诊断

请求在 5s 超时阈值内未返回响应。

角色化详情边界

| 字段 | Viewer | Operator | Biz Admin / Seed Admin |
| --- | --- | --- | --- |
| 阶段、状态、耗时 | 可见 | 可见 | 可见 |
| URL | 协议、主机、路径 | 有限摘要 | 入库脱敏版本 |
| 请求体、响应、异常详情 | 不展示 / 通用原因 | 截断诊断摘要 | 脱敏且截断的详情 |

静态评审稿，不读取生产数据。[查看涉及页面的 Before / After 对比](任务执行链路可观测性-页面对比Demo.html) · [返回设计方案](任务执行链路可观测性设计方案-收敛版.html) · [文档索引](../index.html)

[文档索引](../index.html) · [Markdown](任务执行链路可观测性-RunInspector-Demo.md)

---

[← 文档索引（HTML）](../index.html) · [← 文档索引（Markdown）](../index.md)
