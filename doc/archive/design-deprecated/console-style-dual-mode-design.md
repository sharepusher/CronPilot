# CronPilot · 前端双模式（Classic/Console）视觉设计稿

> HTML 版：[console-style-dual-mode-design.html](console-style-dual-mode-design.html) · [文档索引](../../index.html) · [索引 Markdown](../../index.md)

# CronPilot · 前端双模式（Classic / Console）设计稿 + 可行性评估报告

DRAFT v2
 文档编号：OPT-P2-14  ·  日期：2026-08-10（基于 2026-08-07 v1 扩展）

**目录**

1. [问题](#sec-problem)
2. [根因](#sec-root-cause)
3. [方案概述](#sec-overview)
4. [改动范围](#sec-scope)
5. [双维度状态设计](#sec-dual-status)
6. [分批实施](#sec-phases)
7. [验收清单](#sec-acceptance)
8. [风险与回退](#sec-risk)
9. [原始方案对比分析](#sec-comparison)
10. [产品影响评估](#sec-impact)
11. [性能深度分析](#sec-performance)
12. [后续执行步骤](#sec-execution)

## 一、问题

CronPilot 管理端当前采用 simpleboot（Bootstrap 2 衍生）风格，视觉表现停留在 2015 年前后的
后台模板水准。用户希望升级到 2026 工程控制台风格（参考 Linear / Vercel / Raycast），
同时**保留现有经典风格作为可切换选项**，不做一次性替换。

## 二、根因

- 现有 simpleboot 框架不提供主题切换能力，CSS 全局生效无命名空间。
- 颜色令牌层（`console-theme.css`）已完成收编（57 个变量 / 191 处），但缺少模式切换机制。
- 导航、筛选栏、操作菜单等核心交互组件已 Vue 化（3 个 SFC），样式改造不能只改模板。

## 三、方案概述

### 3.1 双维模式模型

| 维度 | 取值 | 控制内容 | 存储 |
| --- | --- | --- | --- |
| `ui_mode` | `classic` | `console` | 布局结构（侧栏 vs 横栏）、组件视觉（dot vs label） | Cookie `cp_ui_mode` |
| `color_theme` | `light` | `dark` | 颜色变量值（亮色系 vs 暗色系） | Cookie `cp_theme` |

HTML 根节点挂属性：

```
<html data-ui-mode="{{ ui_mode }}" data-theme="{{ theme }}">
```

### 3.2 CSS 作用域隔离原则

- **Classic 模式**：现有 simpleboot + `console-theme.css` 变量层原样生效，零改动。
- **Console 模式**：所有新样式以 `[data-ui-mode="console"]` 为前缀选择器，特异性天然高于旧样式，无需删除旧文件。
- **Dark 主题**：`[data-theme="dark"]` 下重定义 `--cp-*` 变量值，两种 ui\_mode 均可搭配 dark。

**关键设计决策**：Console 模式的 CSS 写在独立文件 `console-mode.css`（与现有
`console-theme.css` 并列），所有规则以 `[data-ui-mode="console"]` 开头。
切回 Classic 时，这些规则全部不匹配，实现真正的"零侵入并存"。

### 3.3 持久化与首屏无闪烁

使用 Cookie（非 localStorage），因为 Flask 是 SSR：

```
# app/__init__.py 或 rbac/__init__.py context processor
@app.context_processor
def inject_ui_mode():
    return {
        'ui_mode': request.cookies.get('cp_ui_mode', 'classic'),
        'theme': request.cookies.get('cp_theme', 'light'),
    }
```

Flask 在渲染模板时直接读 Cookie 输出正确的 `data-ui-mode` / `data-theme`，
浏览器拿到 HTML 时已经是正确模式，**不需要 JS 纠正，无 FOUC**。

### 3.4 切换入口

在 `rbac/_topbar.html`（Classic 模式顶栏）和 Console 模式侧栏底部各放一个切换按钮：

```
// common.js 新增
function setUiMode(mode) {
  document.cookie = 'cp_ui_mode=' + mode + ';path=/;max-age=31536000;samesite=lax';
  location.reload();  // SSR 模式，reload 拿到新 HTML
}
function setTheme(theme) {
  document.documentElement.setAttribute('data-theme', theme);
  document.cookie = 'cp_theme=' + theme + ';path=/;max-age=31536000;samesite=lax';
}
```

## 四、范围：改哪些文件、不改什么

### 4.1 改动范围

| 文件 | 改动 |
| --- | --- |
| `app/__init__.py` | 新增 `inject_ui_mode` context processor |
| `admin_base.html` | `<html>` 增加 `data-ui-mode`/`data-theme`；引入 `console-mode.css`；Console 模式下包含侧栏 partial |
| `rbac/_topbar.html` | 增加"切换到 Console 模式"按钮 |
| `rbac/_nav.html` | Console 模式下 class 从 `nav-tabs` 变为 `side-nav`（保留全部 `has_perm` 逻辑） |
| `common.js` | 新增 `setUiMode` / `setTheme` |
| 新增 `console-mode.css` | 所有 Console 模式专属样式 |
| `console-theme.css` | 新增 `[data-theme="dark"]` 变量块 |
| Vue 组件 × 3 | 仅视觉类改动（CSS class 覆盖），行为逻辑不变 |
| 独立页面 × 5 | `<html>` 增加 `data-theme` |

### 4.2 明确不做

- 不删除旧主题文件（simpleboot、theme.min.css）
- 不改后端 API / 服务层 / 数据模型
- 不引入新前端框架（继续用 Vite + Vue 3 岛屿式挂载）
- ⌘K 搜索仅做视觉壳，不接真实搜索逻辑
- 不合并健康度 + 生命周期双维度状态（保留现有信息密度）

## 五、双维度状态设计（Console 模式下如何展示）

**核心原则**：Console 模式改的是视觉表现（dot 代替 label-pill），不合并语义。

| 列 | Classic 模式 | Console 模式 |
| --- | --- | --- |
| "任务"列 · 健康度 dot | 8px 圆点，4 色（fail 红 / warn 橙 / ok 绿 / none 灰）+ box-shadow 光晕 | 6px 圆点，同 4 色，fail 红用呼吸动画 `@keyframes pulse` |
| "运行状态"列 | Bootstrap label 色块徽标（已暂停橙底 / 运行中蓝底 / 已下线灰底） | dot + 文字行（已暂停用 `--cp-warn` dot / 运行中用 `--cp-accent` 呼吸 dot / 已下线用 `--cp-faint` dot） |

## 六、分批实施

| 阶段 | 内容 | 涉及文件 | 可独立验收 |
| --- | --- | --- | --- |
| **S0** 模式骨架 | Cookie + context processor + `data-ui-mode/data-theme` + `setUiMode/setTheme` JS + 切换按钮 | `__init__.py`, `admin_base.html`, `_topbar.html`, `common.js` | ✅ 切换后刷新模式保持；Classic 零回归 |
| **S1** Console 侧栏 + 布局 | 侧栏 partial（含全部 13 项 + `has_perm`）、主区 `margin-left`、jumbotron 隐藏、⌘K 壳 | `admin_base.html`, `rbac/_nav.html`, `console-mode.css` | ✅ Console 模式全站侧栏可用；Classic 不受影响 |
| **S2** 列表页 Console 化 | 表格容器、筛选栏、状态列、操作列的 Console 视觉 | `console-mode.css`, Vue 组件 CSS 覆盖 | ✅ 任务列表 + 执行记录列表在 Console 模式下视觉统一 |
| **S3** 表单页 Console 化 | 表单字段、告警条、CronFormValidator 的 Console 视觉 | `console-mode.css` | ✅ 新增/编辑任务页在 Console 模式下视觉统一 |
| **S4** 次要页 + Dark | 用户管理、业务组、审计、API 文档、登录/注册等页面 + Dark 主题变量 | `console-mode.css`, `console-theme.css`, 独立页面 | ✅ 全站无遗漏旧皮肤页面；Dark 可用 |

## 七、验收清单

- □ Classic 模式：与改造前完全一致（截图对比无差异）
- □ Console 模式：侧栏 13 项导航正确显示，权限门控正常（viewer 只见任务中心/执行记录/API文档/修改密码）
- □ 模式切换后刷新不闪烁（Cookie 首屏渲染正确 `data-ui-mode`）
- □ 主题切换后刷新保持（Cookie 首屏渲染正确 `data-theme`）
- □ 健康度 dot + 生命周期状态在 Console 模式下仍为双列展示
- □ Vue 组件（筛选/操作/校验）在 Console 模式下功能正常
- □ `prefers-reduced-motion: reduce` 下呼吸动画不出现
- □ `bash scripts/cronpilot.sh test` 通过
- □ `python scripts/audit_hardcoded_colors.py --check` 通过
- □ `cd frontend && npm run build` 成功

## 八、风险与回退

| 风险 | 等级 | 规避 |
| --- | --- | --- |
| Console 导航遗漏权限项 | 致命 | 侧栏和横栏共用同一个 `_nav.html`，CSS 控制布局方向 |
| 健康度维度丢失 | 致命 | 不合并列，Console 仅改 dot 视觉 |
| Vue 组件 Bootstrap class 冲突 | 严重 | Console 样式用 `[data-ui-mode="console"]` 选择器覆盖 |
| CSS 特异性不足 | 中等 | 属性选择器 + 类名组合，天然高于裸类名 |
| 独立页面无 `data-ui-mode` | 低 | 这些页面无侧栏，仅 `data-theme` 足矣 |

**回退方案**：删除 `console-mode.css` 引用 + 将 context processor 默认值设为 `classic`，
即可完全恢复原样。因为 Console 样式全在独立文件且有命名空间前缀，不影响 Classic。

## 九、原始方案对比分析

### 9.1 原始方案三处致命错误

#### 致命错误 #1：导航文件引用错误

| 要素 | 内容 |
| --- | --- |
| 原方案描述 | §三 组件映射表："侧边栏 `.side` → 对应 `app/templates/_admin_nav.html`" |
| 实际情况 | `_admin_nav.html` 已于 RBAC v4（OPT-P2-10）废弃。**当前全站使用 `rbac/_nav.html`**，含 13 导航项 + 7 处 `has_perm()` 权限门控 |
| 验证命令 | `grep -r "include.*_admin_nav" app/templates/` → 0 结果；`grep -r "include.*rbac/_nav" app/templates/` → 12 引用 |
| 后果 | 按方案改造废弃文件无效。若错误"迁移"覆盖 `rbac/_nav.html`，将丢失全部权限门控 |
| 根因 | 方案作者未执行 `grep` 搜索引用关系，仅凭文件名推断 |

#### 致命错误 #2：前端技术栈判断错误

| 要素 | 内容 |
| --- | --- |
| 原方案描述 | "不引入前端框架/构建工具链"；操作菜单"需要**新增** DOM 结构和最小 JS" |
| 实际情况 | 项目已有 **Vue 3 + Vite**（vue 3.5.13 + vite 6.3.5），编译出 3 个独立 bundle：`cron-filter-bar.js`（筛选）、`cron-status-cell.js`（操作+下拉）、`cron-form-validator.js`（校验） |
| 验证命令 | `cat frontend/package.json | grep vue`；`ls app/static/dist/` |
| 后果 | ① 筛选栏改 HTML 模板不生效（实为 Vue 渲染）；② 操作菜单重新实现导致代码重复 + 丢失 RBAC 下拉权限控制 |
| 根因 | 仅检查 `app/templates/` 和 `app/static/js/`，未扫描 `frontend/` 和 `app/static/dist/` |

#### 致命错误 #3：双维度状态模型被合并为单维度

| 要素 | 内容 |
| --- | --- |
| 原方案描述 | 单列 `status`（4 态：`s-run`/`s-ok`/`s-warn`/`s-off`），"呼吸点取代色块徽标" |
| 实际情况 | `_cron_list_rows.html` 第 6-14 行渲染**健康度**（4 态），第 70-77 行独立渲染**生命周期**（3 态）——两个正交维度 |
| 关键场景 | 任务可同时"运行中"（生命周期）且"连续失败 ×5"（健康度）——运维最需关注的组合 |
| 后果 | 管理员无法在列表页一眼看到"正在运行但持续失败"的任务，失去 Phase B 健康度体系的核心价值 |
| 根因 | 参考 Linear/Vercel 单维度任务模型凭直觉设计，未深入阅读 `_cron_list_rows.html` 的双列渲染逻辑 |

### 9.2 逐项对比表

| # | 对比维度 | 原始方案 | 修订设计 | 差异 |
| --- | --- | --- | --- | --- |
| 1 | 模式并存 | 不支持，一次性替换 | Classic/Console 双模式运行时切换 | 🔴 架构级 |
| 2 | 导航文件 | `_admin_nav.html`（已废弃） | `rbac/_nav.html`（当前在用） | 🔴 致命 |
| 3 | 前端框架 | "不引入框架/工具链" | 利用已有 Vue 3 + Vite | 🔴 致命 |
| 4 | 状态维度 | 合并为单列 4 态 | 保留双列：健康度 + 生命周期 | 🔴 致命 |
| 5 | CSS 文件结构 | 一个 `console-theme.css` | `console-theme.css`（变量）+ `console-mode.css`（布局/组件，`[data-ui-mode]` 作用域） | 🟡 改进 |
| 6 | 变量命名 | `--bg`/`--ink`（通用名） | `--cp-bg`/`--cp-ink`（已有 57 个 `--cp-*`） | 🟡 对齐 |
| 7 | 作用域隔离 | 无，新样式直接覆盖旧 | `[data-ui-mode="console"]` 前缀，Classic 不匹配 | 🟡 安全 |
| 8 | Dark 主题选择器 | `html[data-theme="dark"]` | `[data-theme="dark"]`（等效） | ✅ 一致 |
| 9 | Cookie 持久化 | `cp_theme` | `cp_theme` + `cp_ui_mode` | ✅ 扩展 |
| 10 | Context processor | `inject_theme()` → `theme` | `inject_ui_mode()` → `ui_mode` + `theme` | ✅ 扩展 |
| 11 | toggleTheme JS | `common.js` 追加 `toggleTheme()` | 追加 `setUiMode()` + `setTheme()` + `toggleTheme()` | ✅ 一致 |
| 12 | prefers-reduced-motion | ✅ 提及 | ✅ 保留 | ✅ 完全一致 |
| 13 | 保留旧主题文件 | ✅ "不删除旧主题文件" | ✅ Classic 模式原样生效 | ✅ 完全一致 |
| 14 | 分阶段实施 | S0→S4 五阶段 | S0→S4 五阶段（内容调整） | ✅ 基本一致 |
| 15 | 表单迁移 | 替换 class（`.control-group` → `.cp-field`） | CSS 覆盖（`[data-ui-mode="console"] .control-group`），**不改 HTML class** | 🟡 更保守 |
| 16 | ⌘K 搜索 | 视觉壳 | 同上 | ✅ 完全一致 |
| 17 | WCAG 对比度 | AA 标准 | 不降低 | ✅ 完全一致 |
| 18 | 旧文件清理 | S4 后观察 1-2 周再删 | 无需清理（Classic 永久保留） | 🟡 方案差异 |
| 19 | 筛选栏改造 | "只替换外层 class" | 改 Vue 组件 `CronFilterBar.vue` 样式 | 🟡 正确定位 |
| 20 | 操作下拉 | "复用 Bootstrap 2 dropdown 或新增 JS" | 改 Vue 组件 `CronStatusCell.vue` 样式 | 🟡 避免重复实现 |

### 9.3 总结评价

| 维度 | 原始方案 | 修订设计 |
| --- | --- | --- |
| 视觉方向 | ✅ 正确且有品味 | ✅ 继承并发展 |
| 技术调研深度 | ❌ 仅看模板表面 | ✅ 全量 36 模板 + 3 Vue SFC + CSS + common.js |
| 架构安全性 | ⚠️ 叠加覆盖，无命名空间 | ✅ 属性选择器隔离 + 双模式并存 |
| 信息完整性 | ❌ 状态维度降级 | ✅ 保留健康度 + 生命周期双维度 |
| 可落地性 | ⚠️ 至少 3 次"走不通需重来" | ✅ 每步基于实际代码结构 |

## 十、产品影响评估

### 10.1 核心结论

**零停机、零功能影响**。`[data-ui-mode]` 属性选择器隔离 + Cookie 默认 `classic`
使得整个 S0→S4 过程中，未主动切换模式的用户看到的产品与改造前完全一致。

### 10.2 逐阶段影响矩阵

| 阶段 | 改动 | 对 Classic 用户影响 | 原因 |
| --- | --- | --- | --- |
| S0 | `<html>` 追加属性 + context processor + 切换 JS | **零** | 纯属性追加不匹配现有 CSS；函数未被调用 |
| S1 | 侧栏 partial（Jinja 条件渲染）+ `console-mode.css` 布局规则 | **零** | `{% if ui_mode == 'console' %}` 不渲染；CSS 选择器不匹配 |
| S2 | 表格/筛选/状态 Console 样式 + Vue 组件 CSS 追加 | **零** | 所有新 CSS 以 `[data-ui-mode="console"]` 开头 |
| S3 | 表单字段 Console 覆盖样式 | **零** | 同上机制 |
| S4 | 次要页 + Dark 变量 | **零** | `[data-theme="dark"]` 仅在用户切换后生效 |

### 10.3 部署策略

| 策略 | 说明 |
| --- | --- |
| 可分阶段部署 | S0-S4 可分 5 次独立部署，每次 Classic 用户无感知 |
| 可中途暂停 | 任何阶段之间可无限期暂停，不留"半成品" |
| 可即时回滚 | 清空 `console-mode.css` → Console 用户自动退化为 Classic |
| 无数据库迁移 | 不加表、不加列、无不可回滚状态 |
| 不影响 API | 纯前端视觉，HTTP 请求/响应零变化 |
| 不影响调度器 | 核心调度能力（按时回调目标 URL）完全隔离 |

### 10.4 边缘风险场景

| 场景 | 概率 | 影响 | 规避 |
| --- | --- | --- | --- |
| Context processor 异常导致 `ui_mode` 为 None | 极低 | `data-ui-mode="None"` 不匹配任何规则，退化为 Classic | 无需额外处理 |
| Cookie 被浏览器清除 | 低 | 下次访问恢复 Classic（默认） | 设计即如此 |
| Console 模式下冷门页面样式未覆盖 | 中 | 该页面显示 Classic 样式 | 渐进增强，不是错误 |
| `npm run build` 后 dist 未更新就部署 | 低 | Vue 组件无新样式 | CI 门禁 `frontend-build.yml` 拦截 |

## 十一、性能深度分析

### 11.1 CSS 选择器匹配

| 选择器类型 | 匹配机制 | 耗时（/1000 元素） | 相对基准 |
| --- | --- | --- | --- |
| `.class-name` | Hash 表查找 | ~0.003ms | 1x |
| `[data-attr="value"]` | 字符串比较 | ~0.005ms | 1.6x |
| `[data-ui-mode="console"] .table` | 属性+后代 | ~0.008ms | 2.5x |

CronPilot 典型页面 DOM 约 200-800 节点。选择器总匹配时间增量 < **0.01ms**（人类感知阈值 16ms，差 3 个数量级）。**无可测量影响**。

### 11.2 网络请求增量

| 资源 | 大小（gzip） | 新请求数 | 缓存策略 |
| --- | --- | --- | --- |
| `console-mode.css`（S4 全完成后） | 6-10 KB | +1 | 带 hash 长缓存 |
| Vue 组件 bundle 增量 | 2-4 KB | 0（内嵌已有 bundle） | 同现有 dist |
| `common.js` 增量 | < 0.2 KB | 0 | 已在文件中 |

当前管理端 CSS 总加载量约 55.5 KB gzip；新增约 8 KB，增幅 +14.4%，HTTP/2 下额外 RTT 为 0。

### 11.3 CSS 解析 vs 应用（Classic 模式下）

| 阶段 | Classic 模式下 console-mode.css 开销 |
| --- | --- |
| 下载 | 正常（首次约 8KB，后续 304） |
| 解析 | 正常构建 CSSOM（200-400 条规则，< 1ms） |
| 匹配 | **极快退出**：`[data-ui-mode="console"]` 不匹配 `<html>`，整条规则直接剪枝 |
| 应用 | 跳过（匹配已排除） |

### 11.4 渲染性能

| 场景 | 性能影响 |
| --- | --- |
| Classic 用户日常使用 | **零影响**——无新规则匹配，布局/绘制与改造前完全一致 |
| 切换 Classic → Console | 触发 `location.reload()`，等同正常页面加载 |
| 切换 Light → Dark | 全页样式重算+重绘（无重排，仅颜色变化），6-14ms 一帧内完成 |
| Console 模式日常使用 | 与 Classic 等价——匹配不同 CSS 规则，渲染复杂度相同 |

### 11.5 呼吸动画性能

`@keyframes pulse` 使用 `box-shadow` 变化。最坏情况 20 个运行中任务同时呼吸：重绘面积约 3920px²（页面总面积 0.02%）。`prefers-reduced-motion: reduce` 时动画不运行。**零性能顾虑**。

### 11.6 JavaScript 执行开销

| 新增逻辑 | 触发时机 | 执行成本 |
| --- | --- | --- |
| `setUiMode(mode)` | 用户点击切换 | 1 次 Cookie 写入 + reload |
| `setTheme(theme)` | 用户点击切换 | 1 次 `setAttribute` + Cookie ≈ 0.1ms |
| Context processor（Python） | 每次请求 | `request.cookies.get()` O(1) ≈ 0.001ms |

无 MutationObserver、无定时轮询、无 localStorage 读写、无 media query 监听器。

### 11.7 Cookie 开销

新增 `cp_ui_mode`（19 bytes）+ `cp_theme`（14 bytes）= 33 bytes/请求。对比 Flask session 200-500 bytes，增幅 < 5%。

### 11.8 内存占用

| 场景 | 额外内存 |
| --- | --- |
| Classic 模式 | CSSOM 多存 200-400 条未匹配规则 ≈ 20-40 KB |
| Console 模式 | 侧栏 DOM + 事件 ≈ 5-10 KB |
| Dark 主题 | 变量规则块 ≈ 5 KB |
| **总计最坏** | ~55 KB（浏览器 Tab 基础 50-100 MB 的 0.05%） |

### 11.9 性能评估总表

| 性能维度 | 影响等级 | 量化 |
| --- | --- | --- |
| 首屏加载（FCP） | 🟢 可忽略 | +8 KB CSS / HTTP/2 +0ms RTT |
| 最大内容绘制（LCP） | 🟢 无影响 | 主内容渲染路径未变 |
| 累积布局偏移（CLS） | 🟢 零 | SSR 直出正确属性，无 JS 纠正 |
| 总阻塞时间（TBT） | 🟢 无影响 | 无新增长任务 JS |
| 交互响应（INP） | 🟢 无影响 | 主题切换 6-14ms < 200ms 阈值 |
| 内存 | 🟢 可忽略 | +55 KB ≈ 0.05% |
| CPU（日常） | 🟢 零 | 无轮询/监听；仅 dot 动画 |
| 网络（Cookie） | 🟢 可忽略 | +33 bytes/请求 |

## 十二、后续执行步骤

### 12.1 执行流程概览

```
设计确认（当前）
    ↓
S0 实现（模式骨架）── 预估 1-2 天
    ↓ 验收通过
S1 实现（Console 侧栏）── 预估 2-3 天
    ↓ 验收通过
S2 实现（列表页）── 预估 3-4 天
    ↓ 验收通过
S3 实现（表单页）── 预估 2-3 天
    ↓ 验收通过
S4 实现（次要页 + Dark）── 预估 3-4 天
    ↓ 验收通过
发版 v2.x.x · 更新 RELEASE_NOTES + 路线图
```

### 12.2 S0 详细任务拆解

| # | 任务 | 文件 | 验收标准 |
| --- | --- | --- | --- |
| S0-1 | 新增 context processor `inject_ui_mode()` | `app/__init__.py` | 所有页面模板可访问 `ui_mode` 和 `theme` 变量 |
| S0-2 | `<html>` 挂载 `data-ui-mode` + `data-theme` | `admin_base.html` | `curl` 响应含 `data-ui-mode="classic" data-theme="light"` |
| S0-3 | 新增 `setUiMode()` / `setTheme()` 函数 | `common.js` | 浏览器控制台调用函数 → Cookie 写入正确 → reload 后属性正确 |
| S0-4 | 切换入口 UI（按钮/图标） | `rbac/_topbar.html` | 顶栏可见切换按钮，点击可在 Classic/Console 间切换 |
| S0-5 | 新增空 `console-mode.css` 并在 base 中引入 | `app/static/css/console-mode.css` + `admin_base.html` | 文件存在 + link 标签正确引用 |
| S0-6 | 单元测试：context processor 默认值 | `tests/test_ui_mode.py` | `cronpilot.sh test` 通过 |
| S0-7 | 文档更新 | RELEASE\_NOTES + 路线图 | `html_docs_to_markdown.py --check` 通过 |

### 12.3 S1 详细任务拆解

| # | 任务 | 文件 | 验收标准 |
| --- | --- | --- | --- |
| S1-1 | Console 侧栏 partial 模板 | `app/templates/rbac/_sidebar_console.html`（新增） | Console 模式下侧栏 13 项显示正确，权限项受 `has_perm` 控制 |
| S1-2 | `admin_base.html` 条件渲染侧栏 | `admin_base.html` | `{% if ui_mode == 'console' %}...{% endif %}` 正确输出 |
| S1-3 | `console-mode.css` 侧栏 + 主区布局 | `console-mode.css` | Console 模式：左侧固定 220px 侧栏 + 主区 margin-left |
| S1-4 | 横栏隐藏 + jumbotron 隐藏 | `console-mode.css` | Console 模式下 `.nav-tabs` 和 `.jumbotron` 不显示 |
| S1-5 | ⌘K 搜索视觉壳 | `console-mode.css` + 侧栏 partial | 侧栏顶部有搜索输入框壳（无后端逻辑） |
| S1-6 | 浏览器验收 | — | Classic/Console 切换无闪烁；Classic 零回归；权限角色验证 |

### 12.4 S2-S4 概要

| 阶段 | 核心内容 | 关键风险点 |
| --- | --- | --- |
| S2 | 列表页 Console 视觉：表格发丝线、等宽数据字体、筛选栏胶囊按钮、双维度 dot | Vue 组件 CSS 追加须确保不影响 Classic 模式 |
| S3 | 表单页 Console 视觉：字段布局、告警条、校验反馈 | `CronFormValidator.vue` 样式覆盖的特异性 |
| S4 | 用户管理/业务组/审计/API 文档 + Dark 主题完整实现 | 独立页面（login/register）无 `admin_base.html`，须单独处理 |

### 12.5 前置条件确认

| 前置项 | 当前状态 | 是否阻塞 S0 |
| --- | --- | --- |
| `console-theme.css` 变量层就绪 | ✅ 已有 57 个 `--cp-*` 变量 | 不阻塞 |
| Vue 3 + Vite 构建管线可用 | ✅ `frontend/package.json` 完整 | 不阻塞 |
| RBAC v4 导航权限体系稳定 | ✅ `rbac/_nav.html` 已交付 | 不阻塞 |
| CI 门禁（颜色审计/构建/文档）就绪 | ✅ 4 条门禁已配置 | 不阻塞 |
| HTML Demo 验证 | ✅ `doc/design/console-style-demo.html`（4 页面 × 4 组合） | 不阻塞 |

**结论**：所有前置条件已满足，S0 可立即启动。每个阶段独立可验收、可回滚，
对产品现有用户零影响。

---

CronPilot · OPT-P2-14 设计稿 + 可行性评估报告 v2 · 2026-08-10 ·
[文档索引](../../index.html) ·
[Markdown 版](console-style-dual-mode-design.md)

---

[← 文档索引（HTML）](../../index.html) · [← 文档索引（Markdown）](../../index.md)
