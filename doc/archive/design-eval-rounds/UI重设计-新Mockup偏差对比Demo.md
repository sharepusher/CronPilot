# CronPilot — 新 Mockup 偏差对比 Demo（2026-08-18）

> HTML 版：[UI重设计-新Mockup偏差对比Demo.html](UI重设计-新Mockup偏差对比Demo.html) · [文档索引](../../index.html) · [索引 Markdown](../../index.md)

# CronPilot — 新 Mockup 偏差对比 Demo

对比基准：/Users/summer/Downloads/CronPilot-2026-full-mockup.html · 生成于 2026-08-18

☀
☾

偏差总览

基于页面截图与 Mockup 源码逐项比对，共发现 9 处可量化偏差

| 编号 | 位置 | 偏差描述 | 优先级 | 状态 |
| --- | --- | --- | --- | --- |
| N1 | 全局 · 品牌 dot | Mockup: `border-radius:2px`（方形角）；当前: `border-radius:50%`（圆形） | 低 | 未修复 |
| N2 | 顶栏 · 通知铃 | Mockup 有通知铃 icon-btn（含 has-dot 红点变体）；当前顶栏缺少此按钮 | 中 | 未修复 |
| N3 | 任务中心 · 页面副标题 | Mockup: "管理与监控所有定时任务"；当前缺少副标题 | 高 | 未修复 |
| N4 | 任务中心 · Stats 指标名 | Mockup: 任务总数/运行中/今日失败/24h成功率；当前: 异常任务/连续失败次/运行中/今日失败次 | 信息 | 刻意差异 |
| N5 | 执行记录 · 页面副标题 | Mockup: "全部任务的调度执行历史"；当前缺少副标题 | 高 | 未修复 |
| N6 | 操作记录 · 页面副标题 | Mockup: "用户在控制台中的变更历史"；当前缺少副标题 | 高 | 未修复 |
| N7 | 操作记录 · 操作徽章 | Mockup 使用彩色 badge（badge-signal/danger/success）；当前使用纯文本 | 中 | 未修复 |
| N8 | 审计日志 · 页面副标题 | Mockup: "安全相关事件的完整留痕"；当前缺少副标题 | 高 | 未修复 |
| N9 | API 文档 · 页面副标题 | Mockup: "使用 API Token 通过接口管理任务"；当前缺少副标题 | 高 | 未修复 |

N1 品牌 Dot 形状 低优先级

Mockup 使用 border-radius:2px（略带圆角的方形），当前使用 border-radius:50%（圆形）

✦ Mockup — border-radius:2px

CronPilot

任务中心

执行记录

```
+ .brand .dot { border-radius: 2px; }
```

⚠ 当前 — border-radius:50%

CronPilot

任务中心

执行记录

```
- .cp-sidebar-brand .dot { border-radius: 50%; }
```

📐 建议：将 `redesign-layout.css` 中 `.cp-sidebar-brand .dot` 的 `border-radius` 从 `50%` 改为 `2px`，与 Mockup 视觉语言保持一致（dot 在品牌位置为方形，在状态指示中为圆形）。

N2 顶栏通知铃按钮 中优先级

Mockup 顶栏在主题切换和用户菜单之间有一个通知铃 icon-btn；当前顶栏无此按钮

✦ Mockup — 含通知铃

搜索任务、用户、日志…

☀
☾

张

张伟

系统管理员

```
+ <button class="icon-btn" title="通知">
+   <svg>…bell icon…</svg>
+ </button>
```

⚠ 当前 — 无通知铃

搜索任务或操作… ⌘K

☀
☾

A

admin

系统管理员

```
  <!-- 缺少：bell icon-btn -->
```

💡 说明：通知铃当前无后端业务功能。可作纯装饰性按钮（disabled 状态）添加，以保持与 Mockup 视觉结构一致，待后续通知功能上线时激活。

N3N5N6N8N9 5 处页面副标题缺失 高优先级 · 批量修复

所有主要页面 Mockup 均有副标题 `.sub`；当前有 5 个页面尚未添加

✦ Mockup — 有副标题

## 任务中心

管理与监控所有定时任务

＋ 新建任务

---

## 执行记录

全部任务的调度执行历史

---

## 操作记录

用户在控制台中的变更历史

---

## 审计日志

安全相关事件的完整留痕

---

## API 文档

使用 API Token 通过接口管理任务

⚠ 当前 — 缺少副标题

## 任务中心

-

＋ 新建任务

---

## 执行记录

（缺少副标题）

---

## 操作记录

（缺少副标题）

---

## 审计日志

（缺少副标题）

---

## API 文档

（缺少副标题）

🔴 5 处高优先级缺失。模板文件及修改内容：
  
• `dashboard.html` — `<div class="sub">管理与监控所有定时任务</div>`
  
• `execution_logs.html` — `<div class="sub">全部任务的调度执行历史</div>`
  
• `operation_log.html` — `<div class="sub">用户在控制台中的变更历史</div>`
  
• `audit_logs.html` — `<div class="sub">安全相关事件的完整留痕</div>`
  
• `api_doc.html` — `<div class="sub">使用 API Token 通过接口管理任务</div>`

N4 任务中心 Stats 指标 信息（刻意差异）

Mockup 为简化演示数据；当前实现基于实际健康监控，指标更贴近运维场景，属于合理增强

✦ Mockup — 简化 4 指标

任务总数

128

运行中

6

今日失败

2

24h 成功率

99.4%

✓ 当前 — 健康优先 4 指标（合理增强）

异常任务

8

连续失败次

8

运行中

6

今日失败次数

53

✅ 此偏差属于合理功能增强，无需修改。当前实现采用「健康优先」信息架构，将连续失败/异常作为核心指标前置，比 Mockup 的「总数优先」更适合实际运维场景。

N7 操作记录 · 操作类型徽章 中优先级

Mockup 使用彩色 badge 区分操作类型（修改=signal/蓝，下线=danger/红，新建=success/绿）；当前使用纯文本

✦ Mockup — 彩色操作 Badge

| 操作人 | 操作 | 对象 | 时间 | IP |
| --- | --- | --- | --- | --- |
| 张伟 | 修改 | order-sync | 08-11 14:20 | 10.2.31.4 |
| 李娜 | 下线 | legacy-promo | 08-11 11:03 | 10.2.31.9 |
| 张伟 | 新建 | inventory-scan | 08-10 19:44 | 10.2.31.4 |

⚠ 当前 — 纯文本操作类型

| ID | 用户 | 类型 | 内容 | IP | 时间 |
| --- | --- | --- | --- | --- | --- |
| 17 | davytest | 创建任务 | b4-browser-test… | 127.0.0.1 | 08-13 19:43 |
| 15 | davytest | 下线任务 | tagged-task-test | 127.0.0.1 | 08-10 17:47 |

💡 建议：在 `operation_log.html` 中对「操作类型」列添加彩色 badge：创建=`badge-success`，修改=`badge-signal`，下线/停用=`badge-danger`，暂停=`badge-warning`。

审计日志 · 筛选栏结构对比 信息（功能增强）

Mockup 使用 3 个简单 chip；当前使用更完整的筛选表单（用户名+动作+结果+时间区间）

✦ Mockup — 简单 3 Chip

全部

登录失败

权限变更

| 事件 | 用户 | 时间 | IP | 结果 |
| --- | --- | --- | --- | --- |
| 登录 | 张伟 | 09:02:14 | 10.2.31.4 | 成功 |
| 登录 | unknown | 03:11:02 | 203.0.113.9 | 失败×5 |
| 角色变更 | 张伟→李娜 | 16:40:00 | 10.2.31.4 | 成功 |

✓ 当前 — 完整筛选表单（合理增强）

全部动作
全部结果

搜索

| ID | 操作人 | 操作 | 目标 | 详情 | IP | 时间 |
| --- | --- | --- | --- | --- | --- | --- |
| 256 | admin | 登录 | user | 账号 admin | 127.0.0.1 | 17:42:24 |
| 248 | admin | 权限拒绝 | permission | 缺少权限 cron:write | 127.0.0.1 | 15:04:07 |

✅ 此偏差属于合理功能增强。当前实现提供了比 Mockup 更完整的审计筛选能力，无需降级。N8（缺少副标题）仍需修复。

符合度良好的页面 无需修复

以下页面与 Mockup 整体符合度高（90%+）

| 页面 | 符合度 | 说明 |
| --- | --- | --- |
| **登录页** | 9.5/10 | 卡片布局、字段结构、CTA 样式均与 Mockup 高度一致；username vs email 为刻意差异（不用邮箱登录） |
| **业务组** | 9/10 | M1 纯 Mockup 样式卡片，卡片结构（gname/gdesc/gfoot）与 Mockup 一致；成员数用数字展示符合 M1 方案 |
| **标签管理** | 8.5/10 | 副标题已有 ✓，tag-cloud pill 样式与 Mockup 接近；表格视图为额外功能增强 |
| **侧边栏导航** | 9/10 | 背景色 canvas ✓，选中态 signal-bg + 左侧竖条 ✓，字号 13px ✓；仅 dot 形状偏差（N1） |
| **主题切换** | 10/10 | 浅/深色双按钮 toggle，已实现并完整验收 |
| **用户菜单** | 9/10 | avatar + 姓名 + 角色 + 下拉菜单（含退出）均已实现；缺少 email 行（展示上次登录时间替代） |
| **Run Inspector** | 9/10 | 面包屑导航 ✓，失败原因面板 ✓，请求/响应区块 ✓，元数据展示 ✓；整体超出 Mockup 演示范围 |
| **执行记录（单任务）** | 8.5/10 | 任务信息卡 + 表头 + 状态过滤 ✓；副标题缺少（N5 同类问题） |

综合评估结论

9.0

综合符合度 / 10

5

需修复偏差数

4

合理增强（保留）

**总体结论：**项目当前实现与新 Mockup 高度对齐（9.0/10），主要问题集中在 5 处页面副标题缺失（N3/N5/N6/N8/N9），属于统一模式的批量修复，改动极小。

**建议执行：**

- **立即修复**：N3+N5+N6+N8+N9 — 5 处副标题，共 ~5 行 HTML 改动
- **酌情修复**：N7 — 操作记录操作类型彩色 badge；N2 — 顶栏通知铃（可按需添加）
- **可选修复**：N1 — 品牌 dot border-radius（1 行 CSS）
- **保留现状**：N4（Stats 健康优先指标）、审计筛选表单、7 列任务表（均为合理增强）

[文档索引](../../index.html) · [Markdown](UI重设计-新Mockup偏差对比Demo.md) · [索引](../../index.html)

---

[← 文档索引（HTML）](../../index.html) · [← 文档索引（Markdown）](../../index.md)
