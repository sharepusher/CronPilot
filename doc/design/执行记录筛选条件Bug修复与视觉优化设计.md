# 执行记录筛选条件 Bug 修复与视觉优化设计

> HTML 版：[执行记录筛选条件Bug修复与视觉优化设计.html](执行记录筛选条件Bug修复与视觉优化设计.html) · [文档索引](../index.html) · [索引 Markdown](../index.md)

# 执行记录筛选条件 Bug 修复与视觉优化设计

**编号**：OPT-P1-16 子项（执行记录页筛选条件）  
**状态**：已交付  
**创建**：2026-08-26  
**涉及页面**：`app/templates/redesign/execution_logs.html`

---

## 1. 问题

### 1.1 Bug 「仅异常」按钮完全失效

执行记录页筛选栏有五个按钮：非成功 / 全部 / 仅失败 / 仅异常 / 仅成功。其中「仅异常」按钮发送 `outcome=timeout`，但后端解析函数不识别该值，导致按钮完全失效（等同于「非成功」的行为，且无法显示选中态）。

### 1.2 Bug 「仅异常」语义设计缺陷

即使后端识别了 `timeout`，该按钮仅筛选超时记录（`status='timeout'`），遗漏了同属「系统异常」的 `error` 状态（URL 安全拦截、任务不存在等）。用户无法区分「仅异常」和「非成功」的实际差异，且「仅超时」作为独立按钮价值不高。

### 1.3 UX 筛选按钮选中指示点为黑色

选中筛选按钮前面有一个 5px 小圆点（`.el-f-btn.active::before`），使用 `background: currentColor` 继承文字色 `var(--cp-ink)`，在浅色主题下呈现为黑色，偏重且与系统交互主题色不统一。

## 2. 根因

### 2.1 Bug 根因（后端白名单遗漏）

`timeout` 状态是 OPT-P1-01b 引入的，但模板添加「仅异常」按钮时，**未同步更新三处后端白名单/分支**：

1. `_parse_log_outcome_param()`（`views.py:42`）白名单：`('success', 'fail', 'error', 'not_success', 'unknown')` — 缺 `'timeout'`
2. `job_log_list` 视图（`views.py:659`）内联白名单 — 同上
3. `job_log_outcome_clause()`（`job_log_filter.py`）— 缺 `timeout` 分支

结果：`'timeout'` 被 fallback 处理为 `'not_success'`，按钮行为等同于「非成功」；且 `outcome='not_success'` 回传模板后，`outcome == 'timeout'` 永不成立，高亮也失效。

### 2.2 语义设计根因

按钮 `value="timeout"` 仅映射单一状态值，但系统中「非应用层错误」实际包含两种状态：

| status 值 | display 名称 | 产生场景 | 性质 |
| --- | --- | --- | --- |
| `fail` | 失败 | HTTP 4xx/5xx、响应体关键词命中 | **应用层** — 目标服务返回了错误 |
| `error` | 异常 | URL 被 SSRF 拦截、任务不存在、内部错误 | **系统层** — 请求未发出 |
| `timeout` | 超时 | 连接超时、读取超时 | **系统层** — 请求已发出但无响应 |

`error` 和 `timeout` 同属「系统/基础设施层问题」，与 `fail`（应用层问题）形成自然的语义分界。原设计让「仅异常」仅筛选 `timeout`，既遗漏了 `error`，也无法为用户提供与「非成功」不同的排障视角。

### 2.3 颜色根因

筛选栏开发时使用 `currentColor` 做快速实现，未对齐系统主题色 `var(--cp-signal)`。

## 3. 方案

### 3.1 重新定义「仅异常」语义 + 修复后端

将「仅异常」的过滤逻辑从 `status = 'timeout'` 改为 `status IN ('error', 'timeout')`，形成与「仅失败」的清晰互补关系：

| 按钮 | outcome 值 | 过滤逻辑 | 含义 |
| --- | --- | --- | --- |
| **非成功** | `not_success` | `status IN ('fail', 'error', 'timeout')` | 排障总览 — 所有出问题的记录 |
| **全部** | `all` | 无过滤 | 不限 |
| **仅失败** | `fail` | `status = 'fail'` | 应用层 — HTTP 错误、关键词命中 |
| **仅异常** | `exception` | `status IN ('error', 'timeout')` | 系统层 — 超时、连接失败、URL 被拦截 |
| **仅成功** | `success` | `status = 'success'` | 仅看成功 |

关键等式：**非成功 = 仅失败 ∪ 仅异常**，三者形成完美的集合分割。

具体代码变更：

| 文件 | 位置 | 变更 |
| --- | --- | --- |
| `app/main/views.py` | `_parse_log_outcome_param()` | 白名单追加 `'exception'` |
| `app/main/views.py` | `job_log_list` 视图内联白名单 | 同上追加 `'exception'` |
| `app/services/job_log_filter.py` | `job_log_outcome_clause()` | 新增分支：`if o == 'exception': return JobLog.status.in_((STATUS_ERROR, STATUS_TIMEOUT))` |
| `app/templates/redesign/execution_logs.html` | 「仅异常」按钮 | `value="timeout"` → `value="exception"`；active 判断 `outcome == 'timeout'` → `outcome == 'exception'` |

### 3.2 筛选指示点改为主题色 UX

| 文件 | 变更 |
| --- | --- |
| `app/static/css/redesign-pages.css` | `.el-f-btn.active::before` 的 `background: currentColor` → `background: var(--cp-signal)` |

`var(--cp-signal)` 是系统的交互主题色（蓝色系），在亮/暗色主题中均有定义，与 `:focus-visible` 等交互反馈色一致。

## 4. 范围

### 改动范围

| 文件 | 改动类型 |
| --- | --- |
| `app/main/views.py` | 两处白名单追加 `'exception'` |
| `app/services/job_log_filter.py` | 新增 `exception` 分支 |
| `app/templates/redesign/execution_logs.html` | 按钮 value 和 active 判断修改 |
| `app/static/css/redesign-pages.css` | `.el-f-btn.active::before` 颜色变量替换 |

### 明确不做

- 不修改按钮文案（「仅异常」保持不变，与 `job_log_display.py` 中 `STATUS_ERROR` 的显示名「异常」一致）
- 不新增/删除筛选按钮
- 不修改结果列的状态指示点颜色（已有语义化着色）
- 不修改 v1 旧版模板
- 不修改底部 footer 中的 total 描述文案（保持英文）

## 5. 分批

本次改动涉及 4 个文件共约 8 行变更，**一批交付**。

| 步骤 | 内容 | 可独立验收 |
| --- | --- | --- |
| 1 | 修复后端白名单/分支 + 模板 value/active 修改 + CSS 颜色 | ✅ restart 后浏览器验收 |

## 6. 验收

### 6.1 自动化验收

```
bash scripts/cronpilot.sh test
python scripts/check_ui_contract.py --check
python scripts/audit_hardcoded_colors.py --check
```

### 6.2 手动/浏览器验收（restart 后）

| # | 步骤 | 期望结果 |
| --- | --- | --- |
| 1 | 访问 `/job_log_all_list`，默认为「非成功」选中 | 「非成功」按钮 active，前面有**蓝色**小圆点（非黑色） |
| 2 | 点击「仅异常」按钮 | URL 出现 `?outcome=exception`；「仅异常」按钮显示为 active（蓝色圆点）；结果列中仅显示「异常」和「超时」状态的记录 |
| 3 | 点击「仅失败」按钮 | URL 出现 `?outcome=fail`；仅显示「失败」状态的记录；与「仅异常」的结果集**无交集** |
| 4 | 验证集合关系：「非成功」记录数 = 「仅失败」记录数 + 「仅异常」记录数 | footer 中 total 数字验证等式成立 |
| 5 | 五个按钮逐一点击，检查高亮状态切换 | 每个按钮点击后自身 active（蓝色圆点），其他按钮不显示圆点 |
| 6 | 从任务详情页进入单任务执行记录，点击「仅异常」 | 同样正常筛选 |

### 6.3 防护测试

新增/扩展 `job_log_outcome_clause` 的单元测试，覆盖 `'exception'` 输入：

- `job_log_outcome_clause('exception')` 应生成 `status IN ('error', 'timeout')` 条件
- `job_log_outcome_clause('timeout')` 应返回 `None`（不再是合法输入，归入 fallback）
- 原有 `'fail'`、`'not_success'`、`'success'`、`'all'` 行为不变

## 7. 风险

| 风险 | 评估 | 缓解 |
| --- | --- | --- |
| 修改过滤逻辑影响已有筛选行为 | 低 — `fail`/`not_success`/`success`/`all` 的逻辑完全不变；仅新增 `exception` 分支 | 单测覆盖所有 outcome 值 |
| 旧 URL 中 `outcome=timeout` 的书签/收藏失效 | 极低 — `timeout` 此前本就是死值（fallback 到 not\_success），改后行为不变（仍 fallback） | 不需额外处理 |
| CSS 颜色改变影响暗色主题 | 低 — `var(--cp-signal)` 在暗色主题中已有定义 | 亮/暗主题各验证一次 |

---

## 复盘：「仅异常」筛选按钮失效 复盘

### 1. Bug 定位

`app/main/views.py` 的 `_parse_log_outcome_param()`（第 42 行）和 `job_log_list` 视图（第 659 行）白名单缺少 `'timeout'`；`app/services/job_log_filter.py` 的 `job_log_outcome_clause()` 缺少 `timeout` 分支。

### 2. 根因

`timeout` 状态在 OPT-P1-01b 引入，模板添加「仅异常」按钮时发送 `value="timeout"`，但后端三处白名单/分支未同步更新。根本原因是 **新增枚举值时未执行「新增枚举值扩展检查清单」**（`cronpilot-backend.mdc` 已有该清单），未对所有消费点做全局搜索。

### 3. 测试漏洞

现有测试 `test_b1_execution_status` 覆盖了 `timeout` 状态的写入和显示，但**未覆盖 outcome 筛选参数解析** — 没有测试用例验证「以 `outcome=timeout` 请求执行记录页时返回正确结果集」。筛选参数的端到端测试缺失。

### 4. 修复

见上方「方案 3.1」— 重新定义按钮值为 `exception`，覆盖 `error` + `timeout` 两种系统层异常状态。

### 5. 防护测试

新增 `job_log_outcome_clause` 单元测试（见「验收 6.3」），覆盖 `'exception'` 输入产生正确 SQL 条件。

### 6. 同类排查

检查 `_parse_log_outcome_param()` 白名单中已有的所有值是否均在 `job_log_outcome_clause()` 中有对应分支：

- `success` ✅ 有分支
- `fail` ✅ 有分支
- `error` ✅ 有分支
- `not_success` ✅ 有分支
- `unknown` ✅ 有分支

现有值均已覆盖，问题仅出在新增的 `timeout` 值。其他消费点（`should_alert`、`update_job_health`、`cron_repository`）均已包含 `STATUS_TIMEOUT`。

### 7. 预防方案

1. **outcome 参数测试覆盖**（落地位置：`tests/test_job_log_filter.py`）：新增 `test_outcome_clause_exception` 等用例，确保每个合法 outcome 值在 `job_log_outcome_clause` 中都有正确的 SQL 输出。后续新增按钮时，测试缺失将在 CI 中暴露。
2. **白名单与模板 value 交叉验证**（落地位置：`scripts/check_ui_contract.py` 或独立脚本）：建议后续迭代中新增门禁，提取模板中 `name="outcome" value="xxx"` 的所有值，验证每个值在后端解析函数中有对应处理。当前改动量小，先通过人工 code review + 单测覆盖保证。

[文档索引](index.html) · [Markdown](执行记录筛选条件Bug修复与视觉优化设计.md) · [索引](index.html)

---

[← 文档索引（HTML）](../index.html) · [← 文档索引（Markdown）](../index.md)
