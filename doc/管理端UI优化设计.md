# CronPilot · 管理端 UI 优化设计（含原型）

> HTML 版：[管理端UI优化设计.html](管理端UI优化设计.html) · [文档索引](index.html) · [索引 Markdown](index.md)

[← 文档索引](index.html)
UI已交付

# 管理端 UI 优化设计

执行记录 · Cron 周期说明 · 含线框原型 · **v2 按反馈修订**

状态：已交付 · b105e47 · 2026-06-22

**在线访问（与管理端同端口 `/docs/`）：**  
· Docker / 本地生产：[http://127.0.0.1:5860/docs/管理端UI优化设计.html](http://127.0.0.1:5860/docs/%E7%AE%A1%E7%90%86%E7%AB%AFUI%E4%BC%98%E5%8C%96%E8%AE%BE%E8%AE%A1.html)  
· 本地开发（`start_local.sh` 默认 5001）：[http://127.0.0.1:5001/docs/管理端UI优化设计.html](http://127.0.0.1:5001/docs/%E7%AE%A1%E7%90%86%E7%AB%AFUI%E4%BC%98%E5%8C%96%E8%AE%BE%E8%AE%A1.html)  
· 仓库源稿：`doc/管理端UI优化设计.html` · Markdown：<管理端UI优化设计.md>

**交付说明：**A′+B1 已于 `b105e47` 交付；本文保留问题背景、原型与验收清单供查阅。

## 一、背景与问题

| # | 用户反馈 | 根因（已核实） |
| --- | --- | --- |
| 1 | 点击「更详细的执行记录」弹窗为空 | **已修复（b105e47）**：改为「查看详情」展示 `job_log` HTTP 全文；原 `job_log_items` 仅 add\_log 有数据时折叠显示 |
| 2 | 执行记录列表「没有有效内容」 | 列表把整页 HTML（约 80KB）塞进单元格，页面难读；与「空」的主观感受相关 |
| 3 | 「1 分钟一次」只跑一条 | Cron 语义：`minute=1` = 每小时第 1 分，非每 1 分钟；需 `minute=*/1`（见 §四） |
| 4 | 周期说明 UI 丑陋、风格不一致 | 试探性 `alert` / 独立说明块未对齐 simpleboot `control-group` + 行内灰字 |

## 二、数据模型与现状缺口

```
cron_do 触发 ──► job_log（每次必有）
                         ├─ content   ← 目前只存 HTTP 响应正文（或异常文案）
                         ├─ take_time、log_id、create_time
                         └─ http_status ← 已写入（cron_do 成功时落库，b105e47）

    job_log_items ← 另一套机制：业务在执行过程中 POST /api/cron/add_log 上报中间进度
                    与「看本次回调 HTTP 结果」不是一回事，不应作为「更详细执行记录」的主入口。
```

**用户诉求（2026-06-22 反馈）：**

- **列表不要加新列**——仍在「返回的内容」一格里，用**两行**展示：第一行 HTTP 状态，第二行响应摘要。
- 点击「更详细的执行记录」就是要看**本次调用的结果或异常**，不要叫「进度明细」，也不要打开空的 add\_log 表。

**已确认（2026-06-22）：**采用 `job_log.http_status` 单独字段存储状态码；列表 UI **不加列**，仍在「返回的内容」一格内两行展示。详情弹窗展示完整 HTTP 结果/异常（非 add\_log 空表）。

## 三、推荐方案总览（v2 · 按反馈修订）

| 模块 | 推荐 | 说明 |
| --- | --- | --- |
| 执行记录列表 | **方案 A′** | 仍一列「返回的内容」，单元格内**两行**：① HTTP 状态/异常 ② 正文截断 |
| 详情弹窗 | **方案 A′** | 原「更详细的执行记录」改为「**查看详情**」→ 同一逻辑：状态行 + 完整正文 `<pre>` |
| 后端 | **已确认** | `cron_do` 写入 `job_log.http_status`（INTEGER，可空）；异常时 status 空/0，`content` 为错误文案；**列表不加列** |
| add\_log / job\_log\_items | 从主 UI 隐藏 | 保留 API 给长任务上报进度；管理端仅在详情页底部可选展示「业务上报（N 条）」 |
| Cron 周期说明 | **方案 B1** | 分钟行尾一行灰字，不新增说明块 |

## 四、原型 · 任务添加（周期说明 B1）

对齐现有 `cron_add.html`：不增加蓝色 alert、不增加「周期说明」label 行；仅在**分钟**输入框后保留与「小时」字段同款的灰色说明。

现状（易误解）

分钟

0-59，不填表示默认

用户填 `1` 以为「每 1 分钟」→ 实际是「每小时第 1 分」。

方案 B1（推荐）已交付

小时

0-23；留空表示每个小时。每 2 小时填 `*/2`

分钟

0-59；**每分钟**填 `*/1`。只填 `1` 表示每小时第 1 分钟

**Cron 语义速查（APScheduler，与 Linux crontab 一致）：**未填字段 = `*`。

| 意图 | 填写 |
| --- | --- |
| 每分钟 | `minute=*/1`（小时留空） |
| 每小时第 2 分 | `minute=2` |
| 每天 02:00 | `hour=2` `minute=0` |

## 五、原型 · 任务执行记录（方案 A′ · 单列两行）

### 5.1 列表页 — 不增列，一格两行

线框 · 「返回的内容」列（仍为单列）

| 任务名称 | 返回的内容 | 执行时间 | 耗时 | 操作 |
| --- | --- | --- | --- | --- |
| teststp | **HTTP 200** · 0.85s  `<!doctype html><html…`（截断，不撑破表格） | 2026-06-22 09:02:00 | 0.85 | [查看详情](#detail) · 删除 |
| badurl | **请求异常** · 1.2s  发生严重错误: Connection timeout | 2026-06-22 10:00:00 | 1.2 | [查看详情](#detail) · 删除 |

第一行：HTTP 状态码（4xx/5xx 可标红）或「请求异常」；第二行：`content` 摘要。列数与现网一致。

### 5.2 详情弹窗 — 即「更详细的执行记录」应展示的内容

用户点击「查看详情」（替代现「更详细的执行记录」）时期望看到**本次 HTTP 调用的完整结果或异常**，不是 add\_log 进度表。

执行详情 · teststp · 2026-06-22 09:02:00

**HTTP 200** · 耗时 0.85s · log\_id `ab8148aa-…`

回调 URL：`http://example.com/callback`

```
（第二行起：完整响应正文，等宽、可滚动；JSON 可原样展示）
```

---

**可选折叠区**「业务上报进度」：仅当存在 `job_log_items` 时展开（`POST /api/cron/add_log`），默认收起，避免与 HTTP 结果混淆。

### 5.3 现网误导点（为何弹窗是空的）

| 现按钮文案 | 实际打开 | 用户期望 | v2 改法 |
| --- | --- | --- | --- |
| 更详细的执行记录 | `job_log_item_list`（add\_log 表） | HTTP 响应 / 异常全文 | 改为打开**执行详情**（`job_log` 一条），见 §5.2 |
| 返回的内容列 | 整页 HTML 塞进一格 | 先看状态，再看摘要 | 同列两行（§5.1） |

**「进度 / add\_log」是什么？** 给**长时间运行**的回调用的：被调方在处理过程中多次 POST 进度文本（如「步骤 1/3」）。普通「CronPilot 调一下 URL 拿响应」的任务**不会**产生这类记录，所以原弹窗常为空——不是没执行，而是入口绑错了数据表。

## 六、方案对比

### 执行记录

| 方案 | 说明 | 结论 |
| --- | --- | --- |
| 旧 A2 | 新增「HTTP 响应摘要」列 +「进度明细」弹窗 | 用户不需要加列；「进度明细」语义错误 |
| **A′ 推荐** | 单列两行 +「查看详情」= HTTP 结果/异常全文；`http_status` 落库但列表不加列 | 与反馈一致 |
| A3 远期 P1 | success/fail 枚举、失败规则、筛选 | OPT-P1-01，本次不做 |

### 周期说明

| 方案 | 说明 | 结论 |
| --- | --- | --- |
| B0 | 独立「周期说明」`control-group` 多行 | 用户反馈风格突兀，不推荐 |
| **B1 推荐** | 小时/分钟行尾灰字，与现有一致 | 推荐 |
| B2 | 旁路链到本文档 §四 | 可作补充链接「Cron 填写说明」 |

## 七、索引策略（`job_log.http_status`）

**结论（方案 A′ 本次）：**只加列 `http_status`，**不新增、不修改**任何索引。现有查询路径不变，`http_status` 仅用于展示。

### 7.1 现有 `job_log` 索引（保持不变）

| 索引 | 字段 | 典型查询 |
| --- | --- | --- |
| PRIMARY KEY | `id` | `ORDER BY id DESC` 分页 |
| `ix_job_log_log_id` | `log_id` | `POST /api/cron/add_log` 反查主记录 |
| `ix_job_log_cron_info_id` | `cron_info_id` | `/job_log_list?id=` 单任务记录 |

详见 [详细技术方案](详细技术方案.html) §6.1。注：`create_time` 目前**无索引**；全量记录按时间范围筛选时大数据量可能偏慢（既有问题，非本次引入）。

### 7.2 本次迁移（A′）

```
ALTER TABLE job_log ADD COLUMN http_status INTEGER NULL;
-- 不执行 CREATE INDEX … ON job_log(http_status)
```

- 旧数据 `http_status IS NULL` → UI 显示「—」或「无状态码」。
- `job_log_items` 表与索引**不变**。
- 迁移方式：`flask db migrate` + `flask db upgrade`（Tier 0 已交付）。

### 7.3 远期索引（OPT-P1-01，本次不做）

若产品增加「只查失败 / 4xx / 5xx」筛选或失败率统计，再单独评估索引，例如：

| 场景 | 候选索引 | 说明 |
| --- | --- | --- |
| 单任务失败列表 | `(cron_info_id, http_status)` | 与现有 `cron_info_id` 查询叠加 |
| 全局失败筛选 | `(http_status, id)` 或 `create_time` | 需结合数据量与 EXPLAIN；可能先加 `create_time` 索引 |

原则：**有 WHERE 再建索引**；A′ 仅展示不筛选，避免无效索引拖慢 `cron_do` 写入。

## 八、影响范围与验收

| 文件（确认后修改） | 变更 |
| --- | --- |
| `app/crons.py` | 写入 `job_log.http_status`（成功）；异常写 status 空或 0 + content 含错误 |
| `datas/model/job_log.py` + 迁移 | 新增 `http_status`（INTEGER，可空）；**不新增索引**（见 §七） |
| `app/main/views.py` | 新增或改造 `job_log_detail`（按 job\_log.id 展示详情） |
| `job_log_all_list.html`、`job_log_list.html` | 「返回的内容」单元格两行；链接改「查看详情」→ detail |
| `job_log_item_list.html` | 仅作详情页内可选「业务上报」区块，或废弃主入口 |
| `cron_add.html`、`cron_edit.html` | 方案 B1 行内 hint |

**验收步骤：**

1. 触发一次成功回调 → 列表同一格见「HTTP 200」+ 正文摘要
2. 触发一次失败（超时/4xx）→ 第一行见异常或状态码，第二行见错误信息
3. 点「查看详情」→ 弹窗见完整两行结构（状态 + 全文），**不应再是空白页**
4. 未调用 add\_log 的任务 → 详情页无「业务上报」或显示 0 条

## 九、确认项（请勾选后回复）

- ☑ 执行记录采用 **方案 A′**（列表不加列，一格两行）
- ☑ 「更详细的执行记录」改为「**查看详情**」，展示 HTTP 状态 + 完整响应/异常
- ☑ `job_log.http_status` 单独字段（已确认；列表不加列；**索引不变**，见 §七）
- ☑ `add_log` 从主按钮移除，改详情页可选折叠
- ☑ 周期说明采用 **方案 B1**

## 十、导航栏 partial（OPT-P1-07 · 已交付）

管理端主 Tab 抽为 `app/templates/_admin_nav.html`，参数 `active` 取值：`cron_list` | `cron_add` | `job_log` | `api_doc`。

| 文件 | 说明 |
| --- | --- |
| `_admin_nav.html` | 5 项：任务列表 / 任务添加 / 任务执行记录 / API文档 / 退出 |
| `cron_list`、`cron_add`、`cron_edit`、`job_log_all_list`、`api_doc` | `{% include "_admin_nav.html" %}` |
| `job_log_list.html` 等 iframe 页 | 仍用轻量 Tab，不在本次范围 |

修复：`cron_add` / `cron_edit` 曾仅 2 项导航，导致添加页无法跳转执行记录等 Tab。

[文档索引](index.html) ·
[Markdown 索引](index.md) ·
[产品 PRD](产品优化需求-借鉴Plombery.html) ·
[技术方案与前端设计](技术方案与前端设计.html) ·
Markdown 版：<管理端UI优化设计.md>
· [Markdown](管理端UI优化设计.md) · [索引](index.html)

---

[← 文档索引（HTML）](index.html) · [← 文档索引（Markdown）](index.md)
