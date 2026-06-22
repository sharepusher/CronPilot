# CronPilot · 管理端 UI 优化设计（含原型）

> HTML 版：[管理端UI优化设计.html](管理端UI优化设计.html) · [文档索引](index.html) · [索引 Markdown](index.md)

[← 文档索引](index.html)
UI原型待确认

# 管理端 UI 优化设计

执行记录交互 · Cron 周期说明 · 含线框原型

状态：Draft · 待产品确认 · 2026-06-22 · 确认后再改 `app/templates/`

**在线访问（与管理端同端口 `/docs/`）：**  
· Docker / 本地生产：[http://127.0.0.1:5860/docs/管理端UI优化设计.html](http://127.0.0.1:5860/docs/%E7%AE%A1%E7%90%86%E7%AB%AFUI%E4%BC%98%E5%8C%96%E8%AE%BE%E8%AE%A1.html)  
· 本地开发（`start_local.sh` 默认 5001）：[http://127.0.0.1:5001/docs/管理端UI优化设计.html](http://127.0.0.1:5001/docs/%E7%AE%A1%E7%90%86%E7%AB%AFUI%E4%BC%98%E5%8C%96%E8%AE%BE%E8%AE%A1.html)  
· 仓库源稿：`doc/管理端UI优化设计.html` · Markdown：<管理端UI优化设计.md>

**交付纪律：**本文档为**设计稿**，非已实现功能。按 [项目总则](../.cursor/rules/cronpilot-project.mdc)「UI / 功能优化先设计」——**你确认方案后**再改模板并走 Docker 验收。

## 一、背景与问题

| # | 用户反馈 | 根因（已核实） |
| --- | --- | --- |
| 1 | 点击「更详细的执行记录」弹窗为空 | `job_log_items` 仅由 `POST /api/cron/add_log` 写入；普通 GET 回调只写 `job_log.content`，故弹窗无行是**现有设计**，但文案误导用户以为坏了 |
| 2 | 执行记录列表「没有有效内容」 | 列表把整页 HTML（约 80KB）塞进单元格，页面难读；与「空」的主观感受相关 |
| 3 | 「1 分钟一次」只跑一条 | Cron 语义：`minute=1` = 每小时第 1 分，非每 1 分钟；需 `minute=*/1`（见 §四） |
| 4 | 周期说明 UI 丑陋、风格不一致 | 试探性 `alert` / 独立说明块未对齐 simpleboot `control-group` + 行内灰字 |

## 二、数据模型（不变）

```
cron_do 触发
    │
    ├─► job_log（必有）     content = HTTP 响应正文；log_id = cronpilot_log_id
    │
    └─► job_log_items（可选） 仅当业务 POST /api/cron/add_log?cronpilot_log_id=&content=...
```

## 三、推荐方案总览

| 模块 | 推荐 | 改动量 |
| --- | --- | --- |
| 执行记录列表 | **方案 A2**：列表截断预览 +「查看响应」弹窗展示摘要 | 模板 + 少量 JS |
| 详细记录弹窗 | 改名为「进度明细」；无数据时固定说明 + 链到 API 文档 | 模板文案 |
| Cron 周期说明 | **方案 B1**：仅「分钟」行尾一行灰字，不新增分组 | 2 个模板 |
| 远期（P1） | OPT-P1-01：`status` / `http_status` 列，替代读 HTML 判断成败 | 需库表迁移，单独立项 |

## 四、原型 · 任务添加（周期说明 B1）

对齐现有 `cron_add.html`：不增加蓝色 alert、不增加「周期说明」label 行；仅在**分钟**输入框后保留与「小时」字段同款的灰色说明。

现状（易误解）

分钟

0-59，不填表示默认

用户填 `1` 以为「每 1 分钟」→ 实际是「每小时第 1 分」。

方案 B1（推荐）待确认

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

## 五、原型 · 任务执行记录（方案 A2）

### 5.1 列表页 `/job_log_all_list`

线框 · 任务执行记录

#### CronPilot 定时调度平台

方便、统一、自由

任务列表任务添加任务执行记录API文档

| 任务名称 | HTTP 响应摘要 | 执行时间 | 耗时 | 操作 |
| --- | --- | --- | --- | --- |
| teststp | `<!doctype html><html…`（前 120 字）[查看全文](#modal) | 2026-06-22 09:02:00 | 0.85s | [进度明细](#progress) · 删除 |

列名「返回的内容」→ 建议改为「**HTTP 响应摘要**」；悬停 `title` 可看更长片段。

### 5.2 弹窗 · 查看 HTTP 响应（新增）

HTTP 响应 · teststp · 2026-06-22 09:02:00

log\_id: `ab8148aa-6e24-11f1-a53a-d24c536d198f` · 耗时 0.85s

```
<!doctype html><html itemscope="" lang="id">…（全文，等宽字体，可滚动）
```

实现：`open_iframe_dialog` 或只读 `<pre>`，勿把 80KB HTML 直接渲染进表格。

### 5.3 弹窗 · 进度明细（原「更详细的执行记录」）

现文案 更详细的执行记录

| 内容 |
| --- |

（空白 — 用户认为坏了）

推荐 进度明细 待确认

暂无进度上报。  
  
仅当回调方在任务执行期间调用  
`POST /api/cron/add_log`  
（`cronpilot_log_id` + `content`）时才会有明细。  
  
HTTP 响应正文见列表「[查看全文](#modal)」或上栏响应弹窗。

[API 文档](详细技术方案.html) §add\_log

## 六、方案对比

### 执行记录

| 方案 | 说明 | 优点 | 缺点 |
| --- | --- | --- | --- |
| A1 仅改文案 | 改名 + 空状态说明 | 最小 diff | 列表仍难读大段 HTML |
| **A2 推荐** | A1 + 列表截断 + 响应弹窗 | 解决「无有效内容」观感；不误导 | 需统一 3 个模板 |
| A3 P1 | 增加 status / http\_status 列 | 运维体验最佳 | 库表 + cron\_do 改动，属 OPT-P1-01 |

### 周期说明

| 方案 | 说明 | 结论 |
| --- | --- | --- |
| B0 | 独立「周期说明」`control-group` 多行 | 用户反馈风格突兀，不推荐 |
| **B1 推荐** | 小时/分钟行尾灰字，与现有一致 | 推荐 |
| B2 | 旁路链到本文档 §四 | 可作补充链接「Cron 填写说明」 |

## 七、影响范围与验收

| 文件（确认后修改） | 变更 |
| --- | --- |
| `app/templates/cron_add.html`、`cron_edit.html` | 方案 B1 行内 hint |
| `app/templates/job_log_all_list.html`、`job_log_list.html` | 方案 A2 截断 + 查看全文 |
| `app/templates/job_log_item_list.html` | 空状态文案 + 标题「进度明细」 |
| `doc/详细技术方案.html` | 可选：Cron 示例表同步 B1 |

**验收步骤（实现后）：**

1. 登录 `http://127.0.0.1:5860/`（`changeme`）
2. 任务添加 → 选「定时模式」→ 确认分钟行 hint 无突兀色块
3. 任务执行记录 → 列表有摘要；「查看全文」可见响应；「进度明细」无 add\_log 时显示说明
4. `bash scripts/cronpilot.sh test`；Docker compose 冒烟

## 八、确认项（请勾选后回复）

- □ 执行记录采用 **方案 A2**（非仅 A1）
- □ 周期说明采用 **方案 B1**（非独立说明块 B0）
- □ 列名「返回的内容」改为「HTTP 响应摘要」
- □ 「更详细的执行记录」改为「进度明细」
- □ OPT-P1-01（status 列）另开迭代，不纳入本次

[文档索引](index.html) ·
[Markdown 索引](index.md) ·
[产品 PRD](产品优化需求-借鉴Plombery.html) ·
[技术方案与前端设计](技术方案与前端设计.html) ·
Markdown 版：<管理端UI优化设计.md>
· [Markdown](管理端UI优化设计.md) · [索引](index.html)

---

[← 文档索引（HTML）](index.html) · [← 文档索引（Markdown）](index.md)
