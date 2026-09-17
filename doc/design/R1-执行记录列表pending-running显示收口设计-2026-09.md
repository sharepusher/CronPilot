# R1 执行记录列表 pending/running 显示收口设计（2026-09）

> HTML 版：[R1-执行记录列表pending-running显示收口设计-2026-09.html](R1-执行记录列表pending-running显示收口设计-2026-09.html) · [文档索引](../index.html) · [索引 Markdown](../index.md)

# R1 · 执行记录列表 pending / running 显示收口设计

已实施
UX · 执行记录
收敛版 B5 前半 · 短设计  
日期：2026-09-16 · 父设计：[收敛版 rev.6](任务执行链路可观测性设计方案-收敛版.html) · 收口评估：[2026-09-16 未提交评估](../qa/未提交变更与方案评估-2026-09-16.html)

**入口：**
[问题](#problem)
[根因](#root)
[方案](#solution)
[页面对比](#page-compare)
[范围](#scope)
[分批](#batches)
[验收](#accept)
[风险](#risk)

**一句话：**数据库里状态仍是 `pending`（已入队），列表「结果」列却显示成「未知」。本轮只修执行记录列表的**文案/样式**，并加一个「进行中」筛选；**不改**默认「非成功」筛选，不动详情 Presenter（那是 R2/B4）。

## 1. 问题

用户在「执行记录」页看结果列时：

- 一条其实是 `pending`（触发后已建父记录、尚未进入业务）的记录，显示成灰色 **「未知」**；
- `running`（执行中）虽文案对了，但套用了与「未知」相同的灰色样式 class（`el-log-unknown`），语义偏弱；
- 默认筛选是「非成功」（只含 fail/error/timeout），进行中记录本来就不在默认列表里；即使修好徽章，用户若不点「全部」仍看不到它们。需要一个明确入口发现进行中记录。

**不是：**把库里的 `pending` 字段改成别的值；也不是把「未知」这个词全局删掉（空 status 的历史脏数据仍可显示「未知」）。

## 2. 根因

| 层 | 事实 |
| --- | --- |
| 模板 | `_exec_logs_rows.html` 结果列只分支了 success/fail/error/timeout/running，其余进 `else → 「未知」`。`pending` 无分支。 |
| 已有正确文案未复用 | `job_log_display.job_log_badge()` 已定义 `pending→已入队`、`running→执行中`，列表未调用。 |
| 筛选 SQL | `job_log_outcome_clause('not_success')` 仅 `fail/error/timeout`，不含 pending/running；筛选项也无「进行中」。 |

## 3. 方案（推荐）

### 3.1 结果列徽章（必做）

- 模板改为调用 `job_log_badge(log.status)`（或与其对齐的同等映射），按返回的文案与 tone 渲染。
- 映射锁定：

| status | 文案 | CSS class（新建/复用） |
| --- | --- | --- |
| `success` | 成功 | `el-log-success`（已有） |
| `fail` | 失败 | `el-log-fail` |
| `error` | 异常 | `el-log-error` |
| `timeout` | 超时 | `el-log-timeout` |
| `running` | 执行中 | `el-log-running`（新建，信号色，不用 unknown） |
| `pending` | 已入队 | `el-log-pending`（新建，警告/中性进行中语义） |
| 空 / 非法 | 未知 | `el-log-unknown`（保留兜底） |

颜色一律 `var(--cp-*)`，写入 `redesign-pages.css` 的 `.cp-page-exec-logs` / 既有 `.el-log-*` 作用域。

### 3.2 筛选「进行中」（推荐同轮）

- 在 outcome chip 组增加 **「进行中」**，对应 `outcome=in_progress`（或 `active`，实现时统一一名称并写进测试）。
- `job_log_outcome_clause`：该值 → `status IN (pending, running)`。
- AJAX 局部刷新契约不变（沿用现有 `execution_logs.html` filter JS）。
- **默认筛选仍为「非成功」**：不把 pending/running 塞进默认失败视图，避免运维「非成功」列表语义突变。

**待你确认的产品点：**若希望打开执行记录页默认就能看见进行中记录，备选是把默认改为「全部」，或把 pending/running 并入「非成功」。本短设计**默认不采用**这两种（噪音大、改变「非成功」运维习惯）。若你点名要改默认，实现前再补一行确认即可。

### 3.3 交互契约

| 项 | 约定 |
| --- | --- |
| 页面 | 仍是 GET 列表 + AJAX 换行；不整页刷新降级 |
| chip 文案 | 现有：非成功 / 全部 / 仅失败 / 仅异常 / 仅成功；新增：进行中（建议放在「全部」旁） |
| 表头 | 不改列名、不改列数 |
| 详情 / 任务中心 | 本轮不改（任务详情近期点已有 pending/running class） |

## 4. 页面对比（Before / After）

覆盖本轮可见区域：筛选 chip + 结果列。示意数据与验收同构。

BEFORE · 现状

非成功
全部
仅失败
仅异常
仅成功

| 时间 | 任务 | 结果 |
| --- | --- | --- |
| 15:40:01 | testgoogle | 未知 |
| 15:39:50 | backup-job | 执行中（灰样式） |
| 15:38:12 | report | 失败 |

问题：pending 被标「未知」；running 文案对但样式像未知；无「进行中」入口。

AFTER · 本轮目标

非成功
全部
进行中
仅失败
仅异常
仅成功

| 时间 | 任务 | 结果 |
| --- | --- | --- |
| 15:40:01 | testgoogle | 已入队 |
| 15:39:50 | backup-job | 执行中 |

选「进行中」只看到 pending+running；徽章文案与 `job_log_badge` 一致。

## 5. 范围

| 做 | 不做 |
| --- | --- |
| - `app/templates/redesign/_exec_logs_rows.html` 结果列 - `app/templates/redesign/execution_logs.html` 增加「进行中」chip + AJAX state - `app/services/job_log_filter.py` 增加 in\_progress 子句 - `app/static/css/redesign-pages.css`：`.el-log-pending` / `.el-log-running` - 单测：badge 渲染 + filter SQL +（如有）列表 partial HTML 断言 | - 改默认 outcome（保持 not\_success） - Run Inspector DOM / Presenter / 角色矩阵（R2/B4） - 任务详情近期执行（已有 class，本轮不扩） - events API、新导航、改状态机枚举 - 保留策略 / 自动裁剪（B5 后半） |

**可见变更清单（实现时不得超此表）：**

| 元素 | 旧 | 新 |
| --- | --- | --- |
| 结果列 pending | 「未知」+ unknown 样式 | 「已入队」+ pending 样式 |
| 结果列 running | 「执行中」+ unknown 样式 | 「执行中」+ running 样式 |
| 筛选 chip | 5 个 | 6 个（+「进行中」） |
| 表头 / 列数 | — | 不变 |

## 6. 分批

| 子批 | 内容 | 可独立验收 |
| --- | --- | --- |
| R1-1 | filter 子句 + 单测 | `unittest` 断言 in\_progress 含 pending/running，且不影响 not\_success |
| R1-2 | 模板徽章 + CSS + chip + AJAX | 浏览器：造 pending 行 →「进行中」可见「已入队」；默认「非成功」仍无 pending |
| R1-3 | 文档：本设计状态→已实施；RELEASE 一行 | 索引/笔记同步 |

禁止与 R2 Presenter 重排同 commit。

## 7. 验收

1. `python -m unittest` 覆盖 `job_log_outcome_clause('in_progress')`（或最终命名）与 badge 映射；既有 not\_success/success 回归不过期。
2. `bash scripts/cronpilot.sh restart --daemon` 后登录：
   - 准备一条 `status=pending` 的 job\_log（或触发后未终态）；
   - 点「进行中」→ 结果列文案为「已入队」，class 非 `el-log-unknown`；
   - 点「非成功」→ 该 pending 行不出现；
   - 点「全部」→ pending/running 文案正确；
   - 筛选切换仍为 AJAX（无整页闪白）。
3. Agent 自证：curl/会话 HTML 含「已入队」且同页 pending 行无「未知」误标。

## 8. 风险

- **默认仍藏进行中：**刻意保留；靠「进行中」「全部」发现。若产品要默认可见，需另确认改默认。
- **历史空 status：**仍显示「未知」，避免把脏数据硬标「已入队」。
- **回归面：**执行记录 AJAX；勿破坏 OPT-P1-18 局部刷新。

**状态：**已按方案实施（2026-09-16）。复盘：[执行记录 pending 误标「未知」](../postmortem/2026-09-执行记录pending误标未知.html)。

父设计：[收敛版](任务执行链路可观测性设计方案-收敛版.html) ·
页面对比锚点：<#page-compare> ·
Markdown：同名 `.md` ·
索引：挂在收敛版子文档下
· [Markdown](R1-执行记录列表pending-running显示收口设计-2026-09.md) · [索引](index.html)

---

[← 文档索引（HTML）](../index.html) · [← 文档索引（Markdown）](../index.md)
