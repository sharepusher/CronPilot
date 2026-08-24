# CronPilot UI Redesign — 视觉设计规格书 (Design Spec)

> HTML 版：[UI重设计-视觉设计规格书.html](UI重设计-视觉设计规格书.html) · [文档索引](../index.html) · [索引 Markdown](../index.md)

# CronPilot UI Redesign — 视觉设计规格书

**📌 定位**：本文档为 [统一执行手册](UI重设计-统一执行手册.html) 的详细附录（Part 2 全局设计规格的完整版）。执行入口以统一手册为准。

**文档编号**：OPT-P1-16-SPEC · **源**：`doc/design/CronPilot-2026-redesign-mockup.html` CSS 全量提取

## 1. Design Tokens（全局变量）GLOBAL

### 1.1 色彩系统

#### Light Mode（默认）

| Token | 值 | 示意 | 用途 |
| --- | --- | --- | --- |
| --canvas | #F7F8F9 |  | 页面背景、sidebar 背景 |
| --surface | #FFFFFF |  | 卡片/表格/表单背景 |
| --surface-2 | #F1F2F4 |  | hover 背景、次级面板、code 背景 |
| --border | #E4E6E9 |  | 默认边框、分割线 |
| --border-strong | #D3D6DA |  | 输入框边框、按钮边框 |
| --ink | #14171A |  | 主文本 |
| --muted | #5B6169 |  | 次级文本、描述、meta 信息 |
| --faint | #9CA3AF |  | 占位符、section 标题、极弱文本 |
| --signal | #3D6FE0 |  | 主操作色、active 状态、链接 |
| --signal-ink | #2F5FCB |  | 按钮 hover、active 文本 |
| --signal-bg | rgba(61,111,224,0.09) |  | active chip 背景、avatar 背景 |
| --success | #0F9D66 |  | 成功/健康状态 |
| --success-bg | rgba(15,157,102,0.09) |  | 成功 badge 背景 |
| --warning | #B7791F |  | 警告/暂停状态 |
| --warning-bg | rgba(183,121,31,0.10) |  | 警告 badge 背景 |
| --danger | #D64545 |  | 错误/失败/危险操作 |
| --danger-bg | rgba(214,69,69,0.09) |  | 错误 badge 背景、exception panel |
| --shadow | 0 1px 2px rgba(20,23,26,0.04) | — | 按钮/卡片微投影 |

#### Dark Mode

| Token | Light | Dark | 调整策略 |
| --- | --- | --- | --- |
| --canvas | #F7F8F9 | #0D0F12 | 近黑，非纯黑 |
| --surface | #FFFFFF | #16191D | 深灰面板 |
| --surface-2 | #F1F2F4 | #1C2025 | 深一层 |
| --border | #E4E6E9 | #262B31 | 低对比度边框 |
| --border-strong | #D3D6DA | #34393F | 输入框边框 |
| --ink | #14171A | #ECEEF0 | 亮色主文本 |
| --muted | #5B6169 | #8B9198 | 中灰次文本 |
| --faint | #9CA3AF | #565C64 | 暗灰极弱文本 |
| --signal | #3D6FE0 | #4C8DFF | 更亮蓝（深色背景需更高饱和度） |
| --signal-ink | #2F5FCB | #7DAAFF | 更亮蓝 ink |
| --signal-bg | rgba(61,111,224,0.09) | rgba(76,141,255,0.12) | 提高透明度 |
| --success | #0F9D66 | #34D399 | 更亮绿 |
| --warning | #B7791F | #F5A623 | 更亮橙 |
| --danger | #D64545 | #F16565 | 更亮红 |
| --shadow | 0 1px 2px rgba(…) | none | 深色下投影不可见 |

### 1.2 字体系统

| Token | 值 | 用途 |
| --- | --- | --- |
| --sans | `'Inter','Helvetica Neue',Arial,sans-serif` | 主字体（所有 UI 文本） |
| --mono | `'JetBrains Mono','SFMono-Regular',Consolas,monospace` | 代码/ID/数字/时间/cron 表达式 |

#### 字号体系（从 Mockup CSS 提取的完整尺度）

| 场景 | font-size | font-weight | line-height | 其他 |
| --- | --- | --- | --- | --- |
| 页面标题 H1 | 18px | 600 | — | letter-spacing: -0.01em |
| 卡片标题 (.detail-title) | 20px | 600 | — | — |
| 模态框标题 H2 | 15px | 600 | — | — |
| 健康度大标签 (.health-big .label) | 15px | 600 | — | — |
| 空状态标题 | 15px | 600 | — | — |
| Sidebar 品牌 | 14px | 600 | — | letter-spacing: -0.01em |
| CMD Palette 输入 | 14px | — | — | var(--sans) |
| Schedule 大 cron | 14px | — | — | var(--mono) |
| Run ID | 14px | 600 | — | var(--mono) |
| **正文/默认 (body)** | **13px** | 400 | **1.5** | -webkit-font-smoothing: antialiased |
| 按钮 (.btn) | 13px | 500 | — | — |
| Nav item / CMD item | 13px | — | — | — |
| Task name (.task-name) | 13px | 500 | — | — |
| 表单输入 | 13px | — | — | var(--sans) |
| Toast / Modal body | 13px | — | — | — |
| Schedule 人类描述 | 13px | — | — | color: muted |
| Page subtitle | 12.5px | — | — | color: muted |
| Topbar search / exception item | 12.5px | — | — | — |
| 表单 label | 12.5px | 500 | — | — |
| Empty state desc / config grid | 12.5px | — | — | — |
| User chip name | 12.5px | 500 | — | — |
| 表格正文 / Filters | 12px | — | — | — |
| Chip / Pagination / 面包屑 | 12px | — | — | — |
| Run badge / Health / Next run | 12px | 500-600 | — | — |
| 按钮 small (.btn-sm) | 12px | — | — | — |
| Section title (.form-section-title) | 12px | 600 | — | uppercase + letter-spacing: 0.05em |
| Breadcrumb | 12px | — | — | — |
| Run section body (mono) | 12px | — | 1.7 | var(--mono) |
| Run cell time / Config value | 11.5px | — | — | var(--mono) |
| Cron expr badge | 11.5px | — | — | var(--mono) |
| Exception detail / Timezone | 11.5px | — | — | — |
| Stat label / 表头 (thead th) | 10.5-11px | 500-600 | — | uppercase + letter-spacing: 0.04-0.06em |
| Task ID (.task-id) | 11px | — | — | var(--mono), color: faint |
| Schedule human / Help text | 11px | — | — | — |
| Nav section | 10px | 600 | — | uppercase + letter-spacing: 0.08em |
| Tag / Lifecycle badge | 10px | 500 | — | — |
| Nav badge / Count badge / kbd | 10px | 600 | — | — |
| CMD group header | 10px | 600 | — | uppercase + letter-spacing: 0.06em |
| Password strength text | 10px | 500 | — | — |

### 1.3 间距系统

#### 页面级间距

| 区域 | padding/margin | gap |
| --- | --- | --- |
| .main (内容区域) | padding: 24px 32px 60px | — |
| .main max-width | 1200px | — |
| .main--narrow | max-width: 640px | — |
| .main--form | max-width: 720px | — |
| Page head margin-bottom | 20px | gap: 12px (flex-wrap) |
| Stats margin-bottom | 20px | gap: 1px (grid) |
| Exception panel margin-bottom | 20px | — |
| Filters margin-bottom | 14px | gap: 8px |
| Detail grid | margin-bottom: 20px | gap: 16px |
| Form section margin-bottom | 16px | — |
| Form group margin-bottom | 14px | — |
| Run section margin-bottom | 12px | — |

#### 组件内间距

| 组件 | padding | gap | 其他 |
| --- | --- | --- | --- |
| Sidebar | 16px 12px | 2px (items) | width: 220px |
| Nav item | 7px 10px | 10px (icon→text) | border-radius: 6px; border-left: 2px |
| Topbar | 0 24px | 10px | height: 52px |
| Stats (.stat) | 14px 18px | — | .label margin-bottom: 6px |
| Exception item | 10px 16px | 12px | — |
| Table head (th) | 10px 14px | — | — |
| Table body (td) | 11px 14px | — | — |
| Detail card | 16px 18px | — | border-radius: 8px |
| Form section | 20px 22px | — | border-radius: 10px |
| Form row (2-col) | — | 14px | grid-template-columns: 1fr 1fr |
| Modal header | 18px 22px | — | — |
| Modal body | 22px | — | — |
| Modal footer | 14px 22px | 8px | background: surface-2 |
| Toast | 12px 16px | 10px | min-width: 280px |
| CMD palette input | 14px 16px | 10px | — |
| CMD item | 8px 10px | 10px | border-radius: 6px |
| Pagination | 12px 0 | — | — |
| Danger zone | 18px 22px | — | border-radius: 10px |

### 1.4 圆角系统

| 值 | 使用场景 |
| --- | --- |
| 3px | tag, lifecycle badge |
| 4px | skeleton, scrollbar-thumb, tooltip, kbd, mono-code inline |
| 5px | action-btn, btn-sm, pagination btn, run-badge, cron-expr |
| 6px | nav-item, btn, search, chip, topbar input, form input/select, CMD item |
| 8px | stats panel, exception panel, table-wrap, detail-card, run-section, toast |
| 10px | form-section, danger-zone, nav-badge(10px=pill) |
| 12px | modal, cmd-box |
| 20px | user-chip(pill) |
| 50% | avatar, health dot, status pin |

### 1.5 阴影

| 层级 | 值 | 场景 |
| --- | --- | --- |
| 微阴影 (Light only) | `0 1px 2px rgba(20,23,26,0.04)` | 按钮 |
| 中阴影 | `0 4px 16px rgba(0,0,0,0.12)` | Toast |
| 大阴影 | `0 16px 48px rgba(0,0,0,0.2~0.3)` | Modal, CMD palette |

## 2. 组件规格GLOBAL

### 2.1 按钮

| 变体 | height | padding | font | border-radius | 背景 | 边框 | 文字色 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| .btn (default) | 32px | 0 14px | 13px/500 | 6px | surface | border-strong | ink |
| .btn-primary | 32px | 0 14px | 13px/500 | 6px | signal | signal | #fff |
| .btn-ghost | 32px | 0 14px | 13px/500 | 6px | transparent | transparent | muted |
| .btn-danger | 32px | 0 14px | 13px/500 | 6px | transparent | danger | danger |
| .btn-sm | 26px | 0 10px | 12px | 5px | (同上) | (同上) | (同上) |

**Hover**：default/ghost → background: surface-2; primary → background: signal-ink; danger → (同)

**图标按钮 (.icon-btn)**：30×30px, border-radius: 6px, icon 15×15px, 无文字

### 2.2 Action Buttons (表格行操作)

| 属性 | 值 |
| --- | --- |
| 尺寸 | 26×26px |
| 圆角 | 5px |
| 图标尺寸 | 13×13px (SVG) |
| 颜色 | muted (默认) / signal (.run 变体) |
| Hover | background: surface-2; border: 1px solid border; color: ink |
| 间距 | gap: 3px (between buttons) |
| 容器 | display: flex; 列宽约 90px |

### 2.3 表格

| 属性 | 值 |
| --- | --- |
| 外容器 (.table-wrap) | border: 1px solid border; border-radius: 8px; overflow: hidden |
| 表头 (th) | font: 10.5px/500 uppercase; letter-spacing: 0.05em; color: faint; padding: 10px 14px; bg: surface |
| 表格行 (td) | padding: 11px 14px; border-bottom: 1px solid border; vertical-align: middle |
| 最后行 | 无 border-bottom |
| 行 Hover | background: surface-2 |
| 失败行高亮 | background: danger-bg（直接在 <tr> 上） |

### 2.4 Chip / Filter

| 属性 | 值 |
| --- | --- |
| 高度 | 28px |
| padding | 0 10px |
| border | 1px solid border |
| border-radius | 6px |
| font | 12px; color: muted |
| Active 状态 | border-color: signal; color: ink; background: signal-bg |
| Search 输入 | height: 32px; padding: 0 10px; min-width: 180px; max-width: 260px; icon: 14×14px |

### 2.5 Stats Panel (Health-First)

| 属性 | 值 |
| --- | --- |
| 布局 | grid-template-columns: repeat(4, 1fr); gap: 1px; background: border (gap 充当分割线) |
| 外框 | border: 1px solid border; border-radius: 8px; overflow: hidden |
| 单项 (.stat) | background: surface; padding: 14px 18px |
| Label | 11px/500; uppercase; letter-spacing: 0.04em; color: muted; margin-bottom: 6px |
| Value | 22px/600; var(--mono); letter-spacing: -0.02em |
| Total (subtext) | 11px; color: faint; margin-top: 4px |
| 色彩修饰 | .signal / .success / .danger / .warning 应用于 .value |

### 2.6 Exception Panel

| 属性 | 值 |
| --- | --- |
| 外框 | border: 1px solid danger; border-radius: 8px; background: danger-bg |
| Header | padding: 10px 16px; font: 12.5px/600; color: danger; icon: 14×14px |
| List 背景 | surface (白底); border-top: 1px solid border |
| Item | padding: 10px 16px; gap: 12px; font: 12.5px; border-bottom: 1px solid border |
| .ex-icon | color: danger; font-weight: 700; font-size: 14px |
| .ex-name | font-weight: 500; flex: 1 |
| .ex-detail | font: 11.5px; color: muted |
| .ex-action | color: signal; font: 12px/500; cursor: pointer |

### 2.7 表单

| 属性 | 值 |
| --- | --- |
| Section 容器 | background: surface; border: 1px solid border; border-radius: 10px; padding: 20px 22px; margin-bottom: 16px |
| Section title | 12px/600; faint; uppercase; letter-spacing: 0.05em; margin-bottom: 16px |
| Input/Select | width: 100%; height: 34px; padding: 0 11px; border: 1px solid border-strong; border-radius: 6px; font: 13px var(--sans) |
| Textarea | min-height: 70px; padding: 9px 11px; resize: vertical |
| Focus 状态 | border-color: signal; box-shadow: 0 0 0 3px signal-bg |
| Error 状态 | border-color: danger; background: danger-bg; help-text color: danger |
| Success 状态 | border-color: success |
| Help text | 11px; color: muted; margin-top: 5px |
| 2-col row | grid: 1fr 1fr; gap: 14px |

### 2.8 分页

| 属性 | 值 |
| --- | --- |
| 布局 | flex; justify-content: space-between; padding: 12px 0; font: 12px; color: muted |
| 按钮 (.pg-btn) | 28×28px; border-radius: 5px; border: 1px solid border; font: 12px/500 |
| Active 按钮 | background: signal-bg; border-color: signal; color: signal-ink; font-weight: 600 |
| Disabled | opacity: 0.4; cursor: not-allowed |
| Nav gap | 2px |

### 2.9 图标规格

| 场景 | 尺寸 | stroke-width | 颜色 |
| --- | --- | --- | --- |
| Sidebar nav | 15×15px | 2 | currentColor (opacity: 0.75; active: 1) |
| Topbar search/icon-btn | 13-15px | 2 | muted |
| Action button (table) | 13×13px | 2 | muted / signal |
| Exception header | 14×14px | 2 | danger |
| Search input | 14×14px | 2 | opacity: 0.7 |
| CMD palette | 16×16px (search) / 14×14px (items) | 2 | muted |
| Toast | 16×16px | 2 | inherit |
| Empty state | 48×48px | 2 | faint; opacity: 0.6 |
| Breadcrumb separator | 10×10px | 2 | faint |
| Error msg | 12×12px | 2 | danger |
| Password toggle | 14×14px | 2 | faint → hover: ink |

**图标库**：Heroicons / Feather 风格 SVG（stroke-based, viewBox="0 0 24 24"）。不使用 icon font。

### 2.10 状态指示

#### Lifecycle Badge

| 状态 | 背景 | 文字色 | 文案 |
| --- | --- | --- | --- |
| .active | success-bg | success | 运行中 |
| .paused | warning-bg | warning | 已暂停 |
| .retired | surface-2 | faint | 已下线 |

#### Health Indicator

| 状态 | Dot 颜色 | 文字色 | 文案 | Dot 尺寸 |
| --- | --- | --- | --- | --- |
| .healthy | success | success | 健康 | 7×7px (列表) / 10×10px (详情) |
| .warning | warning | warning | 警告 | 同上 |
| .failing | danger | danger | 异常 | 同上 |

#### Run Status Pin

| 属性 | 值 |
| --- | --- |
| 尺寸 | 5×5px |
| 形状 | border-radius: 50% |
| 颜色 | success (成功) / danger (失败) |

## 3. 布局规格

### 3.1 Shell Grid

```
#app-shell {
  display: grid;
  grid-template-columns: 220px 1fr;
  min-height: 100vh;
}
```

### 3.2 Sidebar (220px)

```
.sidebar {
  background: var(--canvas);
  border-right: 1px solid var(--border);
  padding: 16px 12px;
  display: flex;
  flex-direction: column;
  gap: 2px;
  position: sticky;
  top: 0;
  height: 100vh;
  overflow-y: auto;
}
```

### 3.3 Content Area

```
.col-main {
  display: flex;
  flex-direction: column;
  min-width: 0;  /* prevent grid blowout */
}

.topbar {
  height: 52px;
  position: sticky;
  top: 0;
  z-index: 20;
}

.main {
  padding: 24px 32px 60px;
  max-width: 1200px;
}
```

### 3.4 表格列宽参考

#### Dashboard (7 列)

| 列 | 建议宽度 | 内容 |
| --- | --- | --- |
| 任务 | flex/auto (最宽) | task-name + task-id + tags + lifecycle badge |
| 调度策略 | ~150px | cron-expr badge + human text |
| 健康度 | ~80px | dot + text |
| 最近执行 | ~130px | status pin + time + duration |
| 下次执行 | ~100px | relative time text |
| 业务组 | ~90px | group name |
| 操作 | 90px | 3 icon buttons (run/pause/more) |

#### 执行记录 (7 列)

| 列 | 建议宽度 | 内容 |
| --- | --- | --- |
| 任务 | flex/auto | task-name + task-id |
| 触发时间 | ~140px | datetime (mono) |
| 耗时 | ~70px | duration (mono) |
| 响应码 | ~60px | HTTP code (mono) |
| 状态 | ~70px | dot + text |
| 失败原因 | ~160px | truncated error text |
| 详情 | 60px | eye icon button |

#### 用户管理 (9 列)

| 列 | 建议宽度 | 内容 |
| --- | --- | --- |
| 用户 | flex/auto | avatar + username + email |
| 花名 | ~80px | text |
| 岗位 | ~80px | text |
| 角色 | ~80px | badge |
| 业务组 | ~90px | text |
| 状态 | ~60px | dot + text |
| 密码状态 | ~80px | text/badge |
| 创建时间 | ~100px | date |
| 操作 | 180px | text buttons + icon edit |

## 4. 动画与过渡

| 元素 | 属性 | 值 |
| --- | --- | --- |
| Nav item hover | transition | all 0.1s |
| Toast 入场 | animation | slideIn 0.2s ease-out (translateX 100%→0) |
| Skeleton | animation | shimmer 1.5s infinite (background-position 200%→-200%) |
| Tooltip | transition | opacity 0.15s |

## 5. 当前实现 vs Mockup 差异对照

### 5.1 Token 映射（Mockup → Production）

| Mockup Token | Production CSS Variable | 文件 |
| --- | --- | --- |
| --canvas | --cp-canvas | console-theme.css |
| --surface | --cp-bg (已有) 或需新增 --cp-surface | 待确认 |
| --surface-2 | 需新增 --cp-surface-2 | console-theme.css |
| --border | --cp-border (已有) | console-theme.css |
| --border-strong | 需新增 --cp-border-strong | console-theme.css |
| --ink | --cp-text (已有) | console-theme.css |
| --muted | --cp-muted (已有) | console-theme.css |
| --faint | 需新增 --cp-faint | console-theme.css |
| --signal | --cp-signal (已有) | console-theme.css |
| --signal-ink | --cp-signal-ink (已有) | console-theme.css |
| --signal-bg | --cp-signal-bg (已有) | console-theme.css |
| --success | --cp-success (已有) | console-theme.css |
| --warning | --cp-warn (已有) | console-theme.css |
| --danger | --cp-danger (已有) | console-theme.css |
| --mono | --cp-font-mono (已有) | console-theme.css |
| --sans | --cp-font-sans (已有) | console-theme.css |

**需要新增的 Production Token**：`--cp-surface`, `--cp-surface-2`, `--cp-border-strong`, `--cp-faint`, `--cp-shadow`

---

*文档版本：v1 · 创建日期：2026-08-11 · 源：Mockup CSS 全量提取（334 行 CSS → 本规格书）*

[文档索引](../index.html) · [Markdown](UI重设计-视觉设计规格书.md) · [索引](../index.html)

---

[← 文档索引（HTML）](../index.html) · [← 文档索引（Markdown）](../index.md)
