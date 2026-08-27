# CronPilot — 全站图标迁移至 Heroicons 设计

> HTML 版：[全站图标迁移至Heroicons设计.html](全站图标迁移至Heroicons设计.html) · [文档索引](../index.html) · [索引 Markdown](../index.md)

# 全站图标迁移至 Heroicons 设计

**状态**：已完成  |  **日期**：2026-08-27  |  **关联**：OPT-P1-16 Redesign

**前置**：[图标规范化与替换设计](图标规范化与替换设计.html) B1-B3 已完成（密码 Eye/Eye-Slash、查看详情、API Token 入口）

## 1. 问题

B1-B3 完成后，全站 Redesign 模板中仍有 **36 个 Feather 图标**（`stroke-width="2"`）分布在 8 个文件中，与已迁移的 Heroicons（`stroke-width="1.5"`）图标混合使用。两种粗细在同一页面（如用户管理：操作列已 1.5，但侧边栏仍 2.0）中视觉不一致。

## 2. 根因

B1-B3 仅按最小 diff 原则替换了有语义问题的图标（密码 Eye、查看详情、API Token），未一次性迁移全站。导致 Feather (stroke:2) 与 Heroicons (stroke:1.5) 共存。

## 3. 方案

将剩余 36 个 Feather 图标全部替换为对应的 Heroicons Outline 版本（stroke-width: 1.5）。每个图标仅替换 SVG path data 和 stroke-width 属性，不改变 class name、事件绑定、布局结构。

## 4. 全站图标映射表

| # | 位置 | 语义 | 当前 Feather | → Heroicons | 状态 |
| --- | --- | --- | --- | --- | --- |
| \_sidebar.html（13 处） | | | | | |
| 1 | 任务中心 | 四宫格 | 4 个 rect | `squares-2x2` | B4 已完成 |
| 2 | 执行记录 | 文档 | file-text | `document-text` | B4 已完成 |
| 3 | 业务组 | 多人 | users | `user-group` | B4 已完成 |
| 4 | 标签 | 标签 | tag | `tag` | B4 已完成 |
| 5 | 用户管理 | 用户 | user | `user` | B4 已完成 |
| 6 | 注册审批 | 用户+加号 | user-plus | `user-plus` | B4 已完成 |
| 7 | 访问审计 | 盾牌 | shield | `shield-check` | B4 已完成 |
| 8 | 变更记录 | 时钟 | clock | `clock` | B4 已完成 |
| 9 | 个人资料 | 用户 | user | `user` | B4 已完成 |
| 10 | 修改密码 | 锁 | lock | `lock-closed` | B4 已完成 |
| 11 | API Token | 终端 | — | `command-line` | B3 已完成 |
| 12 | API 文档 | 代码 | code | `code-bracket` | B4 已完成 |
| 13-14 | 收起/展开按钮 | 箭头 | chevron-right/left | `chevron-right` / `chevron-left` | B4 已完成 |
| \_topbar.html（9 处） | | | | | |
| 15 | 移动端菜单 | 汉堡 | menu (3 lines) | `bars-3` | B5 已完成 |
| 16 | 搜索按钮 | 放大镜 | search | `magnifying-glass` | B5 已完成 |
| 17 | 浅色模式 | 太阳 | sun | `sun` | B5 已完成 |
| 18 | 深色模式 | 月亮 | moon | `moon` | B5 已完成 |
| 19 | 通知按钮 | 铃铛 | bell | `bell` | B5 已完成 |
| 20 | 用户下拉箭头 | 箭头 | chevron-down | `chevron-down` | B5 已完成 |
| 21 | 修改密码(下拉) | 锁 | lock | `lock-closed` | B5 已完成 |
| 22 | API Token(下拉) | 终端 | — | `command-line` | B3 已完成 |
| 23 | 切换经典界面 | 刷新 | refresh-ccw | `arrow-path` | B5 已完成 |
| 24 | 退出登录 | 退出 | log-out | `arrow-right-start-on-rectangle` | B5 已完成 |
| \_users\_rows.html（3 处） | | | | | |
| 25 | 修改密码(操作) | 锁 | lock | `lock-closed` | B6 已完成 |
| 26 | 重置密码(操作) | 钥匙 | key | `key` | B6 已完成 |
| 27 | 停用用户 | 禁止 | slash | `no-symbol` | B6 已完成 |
| dashboard.html（2 处） | | | | | |
| 28 | 异常任务面板 | 日历+时钟 | calendar-clock (自定义) | `calendar-days` | B7 已完成 |
| 29 | 空状态 | 日历(48px) | calendar (自定义 48x48) | 保留（stroke:1.5 调整） | B7 已完成 |
| \_dashboard\_rows.html（1 处） | | | | | |
| 30 | 执行记录按钮 | 文档 | file | `document-text` | B7 已完成 |
| run\_inspector.html（3 处） | | | | | |
| 31-32 | 面包屑箭头 | 箭头 | chevron-right | `chevron-right` | B8 已完成 |
| 33 | 复制按钮 | 剪贴板 | clipboard-copy | `clipboard-document` | B8 已完成 |
| task\_detail.html（4 处） | | | | | |
| 34 | 面包屑箭头 | 箭头 | chevron-right | `chevron-right` | B8 已完成 |
| 35 | 复制按钮 | 剪贴板 | clipboard-copy | `clipboard-document` | B8 已完成 |
| 36 | 暂停按钮 | 暂停 | pause | `pause` | B8 已完成 |
| 37 | 编辑按钮 | 编辑 | edit | `pencil-square` | B8 已完成 |
| groups.html（1 处） | | | | | |
| 38 | 成员计数 | 多人 | users | `users` | B9 已完成 |

## 5. 对比 Demo

### Demo 1：侧边栏导航完整对比

左：当前 Feather (stroke:2) / 右：Heroicons (stroke:1.5)

当前 Feather (stroke:2)

任务中心
执行记录
业务组
标签
用户管理
访问审计
变更记录
修改密码
API 文档

Heroicons (stroke:1.5) ★

任务中心
执行记录
业务组
标签
用户管理
访问审计
变更记录
修改密码
API 文档

### Demo 2：顶栏工具按钮

对比 Feather vs Heroicons 在小尺寸（13-15px）下的表现

Feather

Heroicons

### Demo 3：用户管理操作列（完整替换后）

当前混合粗细不一致

全 Heroicons粗细统一 ★

### Demo 4：用户菜单下拉

下拉菜单中的 4 个操作图标全部迁移

当前 Feather

修改密码

API Token

切换经典界面

退出登录

Heroicons ★

修改密码

API Token

切换经典界面

退出登录

## 6. 范围

**改动范围**：8 个模板文件中的 36 个 SVG（仅替换 path data + stroke-width 属性）

- `_sidebar.html` — 12 个导航图标 + 2 个收起/展开箭头
- `_topbar.html` — 7 个工具/菜单图标
- `_users_rows.html` — 3 个操作图标
- `dashboard.html` — 1 个面板图标 + 1 个空状态（特殊处理）
- `_dashboard_rows.html` — 1 个操作图标
- `run_inspector.html` — 2 个面包屑 + 1 个复制
- `task_detail.html` — 1 个面包屑 + 1 个复制 + 1 个暂停 + 1 个编辑
- `groups.html` — 1 个成员计数图标

**明确不做**：

- 不改变 CSS 类名、事件绑定、布局结构
- 不涉及 v1 模板
- `dashboard.html` 中 48x48 的空状态 SVG 为自定义组合图标，需单独评估

## 7. 分批

| 批次 | 内容 | 文件 | SVG 数 |
| --- | --- | --- | --- |
| B4 | 侧边栏导航图标（12 个 + 2 个箭头） | `_sidebar.html` | 14 |
| B5 | 顶栏工具与用户菜单（7 个） | `_topbar.html` | 7 |
| B6 | 用户管理操作列剩余（3 个） | `_users_rows.html` | 3 |
| B7 | Dashboard（面板 + 操作列 + 空状态） | `dashboard.html` + `_dashboard_rows.html` | 3 |
| B8 | 详情页与面包屑（6 个） | `run_inspector.html` + `task_detail.html` | 6 |
| B9 | 业务组成员图标（1 个） | `groups.html` | 1 |

## 8. 验收

| 门禁 | 命令 |
| --- | --- |
| 无旧 Feather stroke-width:2 残留 | `rg 'stroke-width="2"' app/templates/redesign/ --count` → 应为 0 |
| 86 条路由冒烟通过 | `python scripts/smoke_routes.py --check` |
| 颜色审计 | `python scripts/audit_hardcoded_colors.py --check` |
| UI 契约门禁 | `python scripts/check_ui_contract.py --check` |
| restart 后浏览器验收 | 4 个关键页面截图：侧边栏 / 顶栏 / 用户管理 / Dashboard |

## 9. 风险

- **低风险**：仅替换 SVG path 和 stroke-width，不改 class/事件/布局
- **视觉变化**：全站统一后所有图标线条变细 25%，整体更精致。Heroicons 部分图标造型与 Feather 略有差异（如 shield-check 带勾号，clock 更简洁）
- **回退**：Git revert 单 commit 即可还原全部

[文档索引](index.html) · [Markdown](全站图标迁移至Heroicons设计.md) · [索引](index.html)

---

[← 文档索引（HTML）](../index.html) · [← 文档索引（Markdown）](../index.md)
