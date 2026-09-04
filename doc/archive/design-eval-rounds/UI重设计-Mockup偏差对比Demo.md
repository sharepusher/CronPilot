# CronPilot — Mockup 偏差对比 Demo（D1–D9）

> HTML 版：[UI重设计-Mockup偏差对比Demo.html](UI重设计-Mockup偏差对比Demo.html) · [文档索引](../../index.html) · [索引 Markdown](../../index.md)

Mockup 偏差对比 Demo — D1–D9

CronPilot 2026 重设计 · 现状 vs Mockup 逐项可视化对比

☀ 浅色
☾ 深色

📊 偏差总览

| # | 区域 | Mockup 规格 | 当前实现 | 修复成本 | 性质 |
| --- | --- | --- | --- | --- | --- |
| D1 | 侧边栏背景色 | `--canvas` = #F7F8F9（与页面融合） | `--surface` = #FFFFFF（白色，视觉分离） | 1行CSS | 视觉偏差 |
| D2 | 导航选中态背景 | `--signal-bg`（蓝调底 rgba） | `--surface-2`（灰色 #f1f5f9） | 1行CSS | 视觉偏差 |
| D3 | 品牌 dot 颜色 | `--signal` 蓝 #3D6FE0 | `--success` 绿 #059669 | 1行CSS | 视觉偏差 |
| D4 | 页面 H1 字号 | 18px | 16px | 1行CSS | 视觉偏差 |
| D5 | 导航分区数 | 3 组（无标签/管理/个人） | 5 组（含运维/配置/管理/个人/开发者） | 可保留 | 功能扩展 |
| D6 | Topbar 通知铃 | 有通知铃 icon-btn | 缺失 | 1行HTML | 无后端支撑 |
| D7 | 用户下拉头部 | email（mono字体） | 角色名 | HTML小改 | 各有合理性 |
| D8 | 业务组页面副标题 | "按团队划分任务归属与权限范围" | 无 | 1行HTML | 视觉偏差 |
| D9 | 标签管理页面副标题 | "用于任务分类与筛选" | 无 | 1行HTML | 视觉偏差 |

D1 · 侧边栏背景 视觉偏差   D2 · 选中态背景 视觉偏差   D3 · 品牌 dot 视觉偏差

✗ 当前实现

CronPilot

任务中心

执行记录

用户管理

任务中心

管理与监控所有定时任务

侧边栏: `background: #FFFFFF` (白色，与 canvas 分离)

选中项: `background: #f1f5f9` (灰色调)

品牌dot: `background: #059669` (绿色)

✓ 对齐 Mockup

CronPilot

任务中心

执行记录

用户管理

任务中心

管理与监控所有定时任务

侧边栏: `background: var(--canvas)` (= #F7F8F9，与页面融合)

选中项: `background: var(--signal-bg)` (蓝调底)

品牌dot: `background: var(--signal)` (蓝 #3D6FE0)

修复代码 — redesign-layout.css（3行）

/\* D1 \*/ .cp-sidebar { background: **var(--cp-surface)**; ... }

/\* D1 \*/ .cp-sidebar { background: **var(--cp-canvas)**; ... }

/\* D2 \*/ .cp-nav-item.active { background: **var(--cp-surface-2)**; ... }

/\* D2 \*/ .cp-nav-item.active { background: **var(--cp-signal-bg)**; ... }

/\* D3 \*/ .cp-sidebar-brand .dot { background: **var(--cp-success)**; ... }

/\* D3 \*/ .cp-sidebar-brand .dot { background: **var(--cp-signal)**; ... }

D4 · 页面标题 H1 字号 视觉偏差

✗ 当前 16px

任务中心

管理与监控所有定时任务

用户管理

4 名成员

✓ Mockup 18px

任务中心

管理与监控所有定时任务

用户管理

4 名成员

修复代码 — redesign-mockup-shared.css（1行）

/\* D4 \*/ .page-head h1 { font-size: **16px**; font-weight: 600; margin: 0; }

/\* D4 \*/ .page-head h1 { font-size: **18px**; font-weight: 600; margin: 0; }

D7 · 用户下拉菜单头部 设计差异

✗ 当前：显示角色名

A

admin

系统管理员

修改密码

API Token

退出登录

✓ Mockup：显示 email（mono）

张

张伟

zhangwei@cronpilot.dev

修改密码

API Token

退出登录

⚠️ 注意：当前实现显示的是**角色名**（如「系统管理员」），Mockup 显示的是 **email 地址**（mono 字体）。两种方式各有价值：email 更易识别身份，角色名更快了解权限。此项需要确认取舍方向再修复，因为显示 email 需要 backend 提供 email 字段到模板上下文。

D8 · 业务组页面副标题   D9 · 标签管理页面副标题 视觉偏差

✗ 当前：仅标题

业务组

标签管理

✓ Mockup：标题 + 副标题

业务组

按团队划分任务归属与权限范围

标签管理

用于任务分类与筛选

修复代码 — 模板 HTML（各 1行）

<div class="page-head"><h1>业务组</h1></div>

<div class="page-head"><div><h1>业务组</h1><div class="sub">按团队划分任务归属与权限范围</div></div></div>

<div class="page-head"><h1>标签管理</h1></div>

<div class="page-head"><div><h1>标签管理</h1><div class="sub">用于任务分类与筛选</div></div></div>

I5 · 业务组卡片：成员显示 已按用户要求完成 ✓

Mockup 原始：Avatar Stack

交易平台组

负责订单、支付、履约相关的定时任务

张

李

+3

18 个任务

数据平台组

报表生成、数仓同步、离线计算任务

王

+2

9 个任务

✓ 当前：数字成员数（用户明确选择）

交易平台组

负责订单、支付、履约相关的定时任务

5 名成员

18 个任务

数据平台组

报表生成、数仓同步、离线计算任务

3 名成员

9 个任务

✅ 有意优化（优于 Mockup，建议保留）

| # | 区域 | Mockup | 当前（优化版） | 建议 |
| --- | --- | --- | --- | --- |
| I1 | Dashboard 统计卡 | 总数/运行/今日失败/成功率 | 异常/连续失败/运行/今日失败（Health-First） | 保留 — 运维视角更优 |
| I2 | 任务表格 | 4列 | 7列（+健康度/最近执行/下次执行/业务组） | 保留 — 信息更完整 |
| I3 | Exception Panel | 无 | 有（连续失败任务聚合） | 保留 — 主动告警可见性 |
| I4 | 标签页 | 仅 tag cloud + × 删除 | T2：标签云 + 管理表格 | 保留 — 操作链路更完整 |

**修复汇总：** D1-D4（4行CSS） + D8/D9（2行HTML） = **6处修改，每处1行**。
D7（下拉显示 email 还是角色）需要决策方向：email 需要 backend 提供字段；角色名已有。
建议先确认 D7 取舍，D1-D4+D8+D9 可立即批量执行。

[文档索引](../../index.html) · [Markdown](UI重设计-Mockup偏差对比Demo.md) · [索引](../../index.html)

---

[← 文档索引（HTML）](../../index.html) · [← 文档索引（Markdown）](../../index.md)
