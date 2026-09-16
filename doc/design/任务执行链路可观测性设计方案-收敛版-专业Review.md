# 任务执行链路可观测性设计方案（收敛版）— 专业 Review

> HTML 版：[任务执行链路可观测性设计方案-收敛版-专业Review.html](任务执行链路可观测性设计方案-收敛版-专业Review.html) · [文档索引](../index.html) · [索引 Markdown](../index.md)

# 任务执行链路可观测性设计方案（收敛版）— 专业 Review

评审对象：<任务执行链路可观测性设计方案-收敛版.html>（rev.2）· 日期：2026-09-14 · 对照代码：当前 `main` 工作区

**总评：有条件通过（Conditional Approve）— 确认前须修订 3 项 Blocker**  
产品边界清晰、非目标克制、安全与分批意识强，页面矩阵与对比 Demo 已补齐可读性。但存在与生产调度器/清理路径/交互契约不一致的假设，以及状态扩展消费面未写全。建议修完 Blocker 后再进入实施确认。

## 一、结论摘要

| 维度 | 评分 | 说明 |
| --- | --- | --- |
| 问题定义与非目标 | 强 | 正确拒绝工作流/lease/heartbeat/自动 interrupted；对齐 CronPilot「同步 HTTP 触发」定位 |
| 与现状代码对齐 | 中 | 终态写入、pending/running 常量已存在、add\_log 依赖父记录等判断基本正确；调度延迟注入路径写窄了 |
| 数据与状态机 | 中+ | 复用 JobLog + events 合理；skipped 消费面与 MaxInstances 缺口未写清 |
| 安全 / RBAC | 强 | 写库前脱敏 + Presenter DTO + 无 events API 方向正确 |
| UI / 页面范围 | 中 | §〇 与对比 Demo 清楚；§5.5「桌面双栏」与现网列表→详情跳转冲突 |
| 分批与验收 | 强 | B0→B6 + 暂停点/回滚意识好；但与上文 Batch 1–4 编号并行易混淆 |
| 可实施性 | 中 | 独立 Tracer Engine 方向对；清理路径、返回值契约、枚举门禁清单需补强后才能开干 |

## 二、做得好的地方

- **定位克制**：明确「调度触发 → 同步 HTTP → 写结果」，避免把 CronPilot 做成分布式工作流。
- **复用 JobLog 作父记录**：列表、清理、add\_log、详情仍以 `trace_id` 关联，迁移成本低于新 `job_runs`。
- **提前创建父记录**：顺带解锁今日缺口——`/api/cron/add_log` 当前要求 JobLog 已存在（`app/api/views.py`），终态前无法回传进度；pending 早建是真实产品增益，建议在价值表中显式写出。
- **安全分层**：入库脱敏 + Presenter 裁剪 + 禁止模板读原始 detail，符合既有「凭据字段访问面」规范。
- **页面矩阵 + 对比 Demo**：rev.2 补齐了「改哪些页 / 不改哪些页」，评审可执行。
- **分批暂停点**：迁移幂等后再写、可靠数据后再产品化、四角色反向验证后再发版——顺序正确。
- **拒绝伪 interrupted**：与既有事故教训（凭印象写 `next_run_time`）同向，避免二次误判。

## 三、必须修订（Blocker）— 确认前

### B1 · §5.5「桌面双栏」与 §〇 / 对比 Demo 冲突 Blocker

§5.5 写「桌面端采用近期执行列表 + 当前 Inspector 双栏；窄屏才列表跳详情」。但 §〇、对比 Demo、§5.6 均以现网路径为准：`/job_log_list` → `/job_log_detail` 整页跳转，**不新增双栏壳**。

**要求**：删掉或改写 §5.5 双栏句，统一为「本期保持列表→详情跳转；双栏若需要另立 UI 设计」。否则 Batch 3 范围会在实现时膨胀。

### B2 · 调度延迟注入路径写得过窄 Blocker

§4.3 / B3 写「自定义 threadpool Executor + ContextVar」。现状：

- `app/__init__.py` 固定 `CuBackgroundScheduler`；开发态默认 executor 为 `ThreadPoolExecutor`（已实测）。
- 仓库仍保留 `CuGeventScheduler`；计划时间真实来源是 `submit_job(job, run_times)` 的 `run_times`（见 `CuBackgroundScheduler.py` / `CuGeventScheduler.py`），不是「换一个 ThreadPool 类」本身。
- 既有教训：禁止用 `next_run_time` 反推（复盘已记录）。

**要求**：改为「在 executor 提交边界（或 job wrapper）注入本次 `run_times[-1]` 到 ContextVar，Background/Gevent 两条 executor 路径均须覆盖；worker/greenlet 结束必须 reset」。验收写清：串扰测试 + 手动路径 NULL。

### B3 · 清理路径未纳入状态保护与 events 级联 Blocker

现状 `app/services/job_log_service.py` 的 `delete_job_logs_for_cron` / `trim_job_logs_for_cron` **只删 JobLog**，不删 items（历史已可能孤儿），更不会删 events。§5.3 / B5 要求级联与「不裁剪活跃 pending/running」，但未点名改造这两个函数与 `cron_del_job_log`。

**要求**：在范围与 B5 文件清单显式列入 `job_log_service.py`：① 删父时同批删 items+events；② trim 跳过 `pending/running`；③ 补回归测试防孤儿与误删执行中记录。

## 四、重要问题（Major）

| # | 问题 | 证据 / 影响 | 建议 |
| --- | --- | --- | --- |
| M1 | `pending`/`running` 常量与展示已存在，文案未对齐 | `job_log_outcome.py` 已有常量；`job_log_display.py` 将 pending 显示为「待执行」、running 为「执行中」；模型 docstring 已含两态。设计写「本批次只新增 skipped」正确，但 UI 文案与「待执行」易误解为「尚未调度」。 | B0 明确：pending=父记录已建未进业务；展示文案建议「排队中/已入队」或统一「执行中（未开始业务）」；更新 display 映射与列表徽章。 |
| M2 | Redis 锁跳过的返回值契约未定义 | 今日 `single_task` 抢锁失败直接 `return`（None）。`cron_run_now` 把 falsy 当成「正在执行中」。若改为写 `skipped` 父记录，应返回 log id，否则手动触发 UX 仍报错文案。 | 在装饰器契约写明：observe 路径锁失败 → finalize skipped → **返回 JobLog.id**；手动触发跳详情展示「已跳过」。 |
| M3 | APS `MaxInstancesReachedError` 未纳入观测 | `Cu*Scheduler` 在 max instances 时只打日志/事件，不进 `cron_do`，也不会走 Redis `skipped`。 | 本期若不做，须在非目标写明「不覆盖 APS max\_instances 抑制」。若要覆盖，另增事件类型或记入风险，避免用户以为「所有未执行都有 JobLog」。 |
| M4 | `trigger_delay_ms` 语义冲突风险 | 模型注释明确为「装饰器入口到 t0 的开销（通常 0–2ms）」；设计要用 `scheduled_delay_ms`（计划→实际）。若把新语义写进旧列，历史数据与文档全错。 | JobLog 保留 `trigger_delay_ms` 旧义或弃用；调度延迟只放在 `task.enqueued.detail.scheduled_delay_ms` + Presenter 摘要字段，禁止无说明地复用旧列。 |
| M5 | 状态扩展消费面清单不完整 | 后端规范要求新增 STATUS 时审计 filter/health/alert/API/CSS。设计 B0 点到 outcome/filter/display/health，但未列：API `status` 过滤（`app/api/views.py`）、OpenAPI 枚举、Prometheus label、列表 AJAX 筛选、种子数据。 | B0 附「枚举扩展检查清单」勾选表（对齐 `cronpilot-backend.mdc`），并标注 API Additive Change。 |
| M6 | 独立 Engine 与业务库同文件 SQLite | 设计已承认不保证零阻塞；但未规定默认 `TRACE_LEVEL`、超时毫秒、熔断阈值与开关配置键（且配置键须进 `configs()` 可达性门禁）。 | 补 conf 键草案 + `test_config_keys` 登记；默认偏保守（例如仅终态前后关键事件，或短 timeout）。 |
| M7 | 批次编号双轨 | §六 Batch 1–4 与 §6.2 B0–B6 并存，Review/实施易串。 | 删掉简表或改成「B0–B6 为权威」，简表仅作索引。 |

## 五、次要问题（Minor）与信息项

- Minor `job_log_events.cron_id INTEGER` 与 `JobLog.cron_info_id` 同为 Integer；若 OPT-P0-21 任务 ID 升 BIGINT，须同步类型（可在风险表预留）。
- Minor 事件表缺 `(cron_id, occurred_at_ms)` / `(trace_id)` 查询索引说明；详情按 trace\_id+seq 够用，清理按 cron 批量删时建议有索引。
- Minor §5.6 写「Demo 直接加载生产 CSS」——当前交互 Demo 仍是自包含样式；要么改 Demo 真链生产 CSS，要么改表述为「视觉 token 对齐，非强制同源 CSS」。
- Info `single_task()` 今日无参；改为 `single_task(observe_execution=False)` 时，所有 `@single_task()` 调用点需保持兼容（现状均为带括号调用，可行）。
- Info 提前建父记录后，业务方可在 running 期间 add\_log——时间线合并业务日志的价值应写进 1.2 对比表。
- Info 种子 Admin 无 `cron:write` 但有 `log:read`：矩阵已覆盖，B4 浏览器验收须含 Seed Admin 正向读详情。

## 六、与代码现状对照（抽样）

| 设计陈述 | 代码事实 | 判定 |
| --- | --- | --- |
| `_save_job_log` 仅终态创建 | `app/crons.py` 各分支调用时已带终态 status | 正确 |
| pending/running 产品化不足 | 常量与 display 已有，但 cron\_do 不写这两态 | 正确（差写入与列表语义） |
| Redis 锁可选，默认单机 | `single_task`：`is_single != '1'` 才抢锁 | 正确 |
| add\_log 依赖已有 JobLog | `cron_add_log` 查不到 trace 即错误 | 正确；早建父记录可解 |
| 清理级联 events | `job_log_service` 只删 JobLog | 设计缺口 → B3 |
| threadpool ContextVar 传计划时间 | 默认确为 ThreadPoolExecutor；注入点应在 submit 边界 | 部分正确 → B2 |
| `job_log_items.occurred_at_ms` 新增 | 模型仅有 id/trace\_id/content | 正确 |
| 不改 Dashboard 健康统计 | 健康度基于终态；须显式排除 pending/running/skipped | 依赖 B0 落地 |

## 七、建议的确认项修订（替换/追加第八章）

1. 确认本期 UI **保持列表→详情整页跳转**，不做桌面双栏（或另立 UI 设计）。
2. 确认调度延迟经 **executor 提交边界 ContextVar** 注入，覆盖当前 Background 路径，并写清与 Gevent 变体的关系；禁止 `next_run_time` 反推。
3. 确认清理/裁剪改造 `job_log_service`：级联 items+events，保护 pending/running。
4. 确认 APS max\_instances 抑制：本期不做观测 / 或纳入范围（二选一写死）。
5. 确认 `scheduled_delay_ms` 不复用扭曲 `trigger_delay_ms` 旧语义。
6. 保留原稿：仅观测 cron\_do；复用 JobLog；脱敏+Presenter；无 events 公开 API。

## 八、修订后的实施建议顺序

1. 改设计稿解决 B1–B3 + M1–M5（仍不写业务实现）。
2. 你明确「按修订稿执行」后，严格按 B0→B6，每批独立验收。
3. B0 必须跑通枚举扩展清单（含 API/健康度/筛选/CSS）。
4. B3 通过串扰与锁跳过返回值测试后，才开 B4 页面。

**一句话**：方案方向正确、值得做；先把「交互范围、调度延迟注入、清理级联」三处写死并对齐代码，再确认实施。

关联：[设计原文](任务执行链路可观测性设计方案-收敛版.html) ·
[页面对比 Demo](任务执行链路可观测性-页面对比Demo.html) ·
[目标态 Demo](任务执行链路可观测性-RunInspector-Demo.html) ·
[文档索引](../index.html)
· [Markdown](任务执行链路可观测性设计方案-收敛版-专业Review.md) · [索引](index.html)

---

[← 文档索引（HTML）](../index.html) · [← 文档索引（Markdown）](../index.md)
