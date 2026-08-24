# CronPilot 顶栏精化方案 — Demo 对比

> HTML 版：[UI重设计-顶栏精化方案.html](UI重设计-顶栏精化方案.html) · [文档索引](../index.html) · [索引 Markdown](../index.md)

切换主题

CronPilot 顶栏精化方案 — Demo 对比

基于 CronPilot-2026-full-mockup.html 对齐审计 · 2026-08

**背景说明：**顶栏用户菜单**已实现**（avatar + 用户名 + 下拉），但与 full-mockup 存在两处精化空间：① 主题切换使用文字 emoji 而非 SVG 图标；② 用户 Chip 缺少角色副标题 + chevron 箭头，下拉菜单无头像/邮件展示区。

Gap A — 主题切换样式：Emoji 文字 → SVG 图标分组按钮

当前实现

搜索任务或操作…
⌘K

☀
☾

A

admin

页面内容区域…

文字 emoji ☀/☾
无 SVG 图标视觉
已有 border 分组容器

方案 A — SVG 图标（推荐）

搜索任务或操作…
⌘K

A

admin

页面内容区域…

SVG 日/月图标
26×24px 精准尺寸
对齐 Mockup 规范

**实施方案 A（极小改动）**：仅需修改 `_topbar.html` 中两个 `<button>` 的内容，同时调整 `redesign-layout.css` 中 `.cp-theme-btn` 的尺寸规格。

```
{# 修改前 #}
<button class="cp-theme-btn{{ ' on' if theme == 'light' }}">☀</button>
<button class="cp-theme-btn{{ ' on' if theme == 'dark' }}">☾</button>

{# 修改后 #}
<button class="cp-theme-btn{{ ' on' if theme == 'light' }}" title="浅色模式">
  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
    <circle cx="12" cy="12" r="4"/>
    <path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>
  </svg>
</button>
<button class="cp-theme-btn{{ ' on' if theme == 'dark' }}" title="深色模式">
  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
    <path d="M20 14.5A8.5 8.5 0 119.5 4a7 7 0 0010.5 10.5z"/>
  </svg>
</button>
```

**CSS 调整**（`redesign-layout.css`，`.cp-theme-btn`）：将 `padding: 4px 8px` 改为 `width: 26px; height: 24px; display: flex; align-items: center; justify-content: center;`

Gap B — 用户 Chip 精化：添加角色副标题 + Chevron + 下拉框展开头

当前实现

Chip（收起状态）

A

admin

Dropdown（展开）

修改密码

API Token

切换到经典界面

退出登录

无角色副标题
无 chevron 箭头
下拉无头像/邮件区
条目完整

方案 B — 对齐 Mockup（推荐）

Chip（收起状态）

A

admin
种子管理员

Dropdown（展开）

A

admin

admin@cronpilot.local

修改密码

API Token

切换到经典界面

退出登录

角色副标题（Seed/Biz/Operator/Viewer）
Chevron 箭头
下拉头像+邮件区
pill 圆角 chip 样式

**实施方案 B — 需改动文件：**

- `app/templates/redesign/_topbar.html`：添加角色显示、chevron SVG；下拉头增加 avatar + email 区块
- `app/static/css/redesign-layout.css`：`.cp-topbar-user` 改为 pill 样式（`border-radius: 20px; border: 1px solid transparent;`），添加 `.cp-topbar-urole` 样式
- `app/rbac/context.py` 或视图层：传递用户角色 label（如"种子管理员"）和邮件到模板

**角色 label 映射**：

```
ROLE_LABELS = {
  'seed': '种子管理员',
  'biz_admin': '业务管理员',
  'operator': '运维人员',
  'viewer': '观察员',
}
```

完整顶栏：改动前 vs 改动后 对比

当前顶栏

搜索任务或操作…⌘K

☀
☾

A

admin

精化后顶栏（A + B 方案合并）

搜索任务或操作…⌘K

A

admin
种子管理员

实施评估

| 方案 | 改动范围 | 风险 | Mockup 对齐度 | 建议 |
| --- | --- | --- | --- | --- |
| **A — SVG 主题切换** | `_topbar.html`（2行） `redesign-layout.css`（1个选择器） | 极低 | 100% 对齐 | ✅ 立即执行 |
| **B — 用户 Chip 精化** | `_topbar.html`（结构调整） `redesign-layout.css`（新增样式） 视图层（传递角色 label + 邮件） | 低 | 95% 对齐 | ✅ 建议执行 |
| 通知铃（可选） | `_topbar.html` + 产品功能 | 中（需后端功能） | 超出 MVP 范围 | ⏸ P2，暂缓 |

**验收标准：**  
方案 A：`curl http://127.0.0.1:5001/ | grep 'M12 2v2'`（太阳 SVG path 存在）；浏览器重启确认主题切换按钮显示图标而非 emoji。  
方案 B：`curl http://127.0.0.1:5001/ | grep 'cp-topbar-urole'`；浏览器确认 chip 显示角色 + chevron；点击展开后出现头像 + 邮件头。

分批执行计划

| 批次 | 内容 | 文件 | 可独立验收 |
| --- | --- | --- | --- |
| Batch 1 | SVG 主题切换（方案 A） | `_topbar.html` + `redesign-layout.css` | ✅ 重启后截图确认 |
| Batch 2 | 用户 Chip 角色 + Chevron + 下拉框头 | `_topbar.html` + `redesign-layout.css` + 视图层角色 label | ✅ 重启后多角色账号截图确认 |

[文档索引](index.html) · [Markdown](UI重设计-顶栏精化方案.md) · [索引](index.html)

---

[← 文档索引（HTML）](../index.html) · [← 文档索引（Markdown）](../index.md)
