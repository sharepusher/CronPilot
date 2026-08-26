# Redesign 功能页全量审查 — 问题复盘与修复计划

> HTML 版：[Redesign功能页全量审查与修复计划.html](Redesign功能页全量审查与修复计划.html) · [文档索引](../index.html) · [索引 Markdown](../index.md)

# Redesign 功能页全量审查 — 问题复盘与修复计划

**审查范围**：`app/templates/redesign/` 全部 23 个功能页  
**审查维度**：HTML 结构 · JavaScript · 安全性 · UX · 功能 bug · 可访问性  
**发现统计**：Critical 2 · Medium ~35 · Low ~40  
**关联文档**：`doc/design/Redesign前端代码质量评估与优化计划.html`

## 一、系统性根因分析

### 1.1 为什么出现 77 个问题

这些问题来源于三个阶段的不同决策：

| 阶段 | 焦点 | 产出 | 遗留 |
| --- | --- | --- | --- |
| Phase 1：功能实现 | Mockup 还原 + 功能完整性 | 23 个完整页面 + 4 个 JS 模块 | 安全/可访问性/边界场景未系统覆盖 |
| Phase 2：安全加固 | CSRF、XSS、POST-only | S1-S5 安全修复 | 部分页面安全模式不一致（如 onclick 注入遗漏） |
| Phase 3：CSS 架构（R1） | 消除技术债 + 建立防护 | 零内联 CSS + CI 门禁 | 功能 bug / UX / 可访问性不在范围内 |

### 1.2 五层 Why（结构性根因）

| Why | 问题 |
| --- | --- |
| 1 | 存在 2 个 Critical bug + 35 个 Medium 级别问题 |
| 2 | 功能验收只测"正向路径"，未覆盖边界场景（如 cpRetire 不传 reason） |
| 3 | 开发时 DoD = "功能在正常场景下工作" + "视觉与 Mockup 一致" |
| 4 | 无系统性的安全/可访问性/边界场景检查清单 |
| 5 | Redesign 是 UI 迁移（v1→v2），优先级是视觉一致性而非功能完善 |

**核心认知**：这些不是"低质量代码"，而是**有意的范围取舍**——先交付 UI 一致性，再逐步补齐边界防护。现在是"补齐"的正确时机。

## 二、问题分类与必要性评估

### 2.1 Critical — 必须修复（影响核心业务流程）

#### C1: dashboard.html — cpRetire 不传 reason 导致下线永远失败

**问题**：Dashboard 快捷下线按钮调用 `cpRetire()`，只传 `{id, csrf_token}`，不传 `reason` 字段。后端 `validate_retire_reason(reason)` 检查 1-500 字符，reason=None 必定失败。

**影响**：用户点击下线 → 确认 → Toast 显示错误信息。功能完全不可用。

**修复方案**：在 CpConfirm 对话框中增加 reason textarea（参考 users.html 的 deactivation modal 模式），或改为跳转到 `/cron_retire?id=xx` 专用页面。

**必要性**：必须修复 — 功能不可用

#### C2: user\_form.html — 停用用户仍展示"启用"选项

**问题**：编辑已停用用户时，`is_active` 下拉框仍包含 `value="1"`（启用）选项。虽然后端 `update_user()` 会拦截，但 UI 误导管理员认为可以恢复。

**影响**：管理员操作后收到错误提示，体验割裂。违反"停用不可恢复"策略的 UI 一致性。

**修复方案**：当 `user.is_active == 0` 时，隐藏 `is_active` 下拉或改为只读展示"已停用"。

**必要性**：必须修复 — UI 与业务策略矛盾

### 2.2 Medium — 建议修复（按优先级排序）

#### M1: 功能性 Bug（必须修复）

| # | 页面 | 问题 | 修复方案 | 必要性 |
| --- | --- | --- | --- | --- |
| M1 | tags.html | 状态映射错误：`status === 2` 标为"已暂停"，实际 cron 状态码 `0=暂停, -1=下线` | 改为 `=== 0` | 必须 |
| M2 | execution\_logs.html | Esc 快捷键选择器 `a[href$="job_log_all_list"]` 在单任务视图下匹配失败 | 改为通用选择器（如表单 reset 或 base\_url 链接） | 建议 |

#### M2: 安全性问题（建议修复）

| # | 页面 | 问题 | 修复方案 | 必要性 |
| --- | --- | --- | --- | --- |
| M3 | task\_detail / run\_inspector | `onclick="cpCopy('{{ keyword }}'...)"` — keyword 含引号时 JS 断裂 | 改用 `data-keyword` + 事件委托 | 建议 — 低概率但可被触发 |

#### M3: UX 问题（可选修复）

| # | 页面 | 问题 | 修复方案 | 必要性 |
| --- | --- | --- | --- | --- |
| M4 | dashboard/task\_detail/registration\_review | AJAX 操作无 loading 状态，用户可重复点击 | confirm 回调中禁用按钮 + 文案追加"中…" | 建议 |
| M5 | register/user\_form/user\_profile/complete\_profile | `job_title_other` 选中时 JS 不设 `required` | change 事件中 toggle `required` | 建议 |
| M6 | register | 无客户端密码匹配/组选择验证 | submit 前 JS 检查 | 可选 — 后端兜底 |
| M7 | change\_password | 无客户端新密码 === 确认密码检查 | 同上 | 可选 |
| M8 | api\_token | 使用已废弃 `document.execCommand('copy')` | 改用 `navigator.clipboard.writeText()` | 可选 — 当前仍可工作 |

#### M4: 可访问性问题（建议批量修复）

| # | 问题模式 | 影响页面 | 修复方案 | 必要性 |
| --- | --- | --- | --- | --- |
| M9 | Icon-only 按钮无 `aria-label` | dashboard, users, execution\_logs | 逐个添加 `aria-label` | 建议 |
| M10 | `<label>` 缺少 `for` 关联 | user\_form, group\_form, cron\_retire 等 8 页 | 逐个添加 `for/id` | 建议 |
| M11 | register 确认模态框无 `role="dialog"` / focus trap | register | 添加 ARIA + 键盘处理 | 建议 |
| M12 | `<a onclick="..." href="javascript:;">` 代替 button | dashboard, tags | 改为 `<button type="button">` | 可选 |

### 2.3 Low — 不建议单独修复（ROI 过低）

| 问题模式 | 数量 | 为什么不单独修复 |
| --- | --- | --- |
| Clipboard API 无 `.catch()` | 4 处 | 静默失败对内部工具用户无感知影响 |
| 残留 `style=""` 属性（var-only） | ~8 处 | 使用 CSS 变量的 inline style 已在 `check_ui_contract.py` 允许名单中 |
| Pagination 伪 `<a>…</a>` 椭圆号 | 3 处 | 视觉纯装饰，不影响功能 |
| `<table>` 缺 `<caption>` / scope | 全部 | 管理后台表格数据已有标题行上下文 |

## 三、修复计划 — 分批实施

**总体策略**：按"影响面 × 修复确定性"排序。功能 bug 优先于 UX 优先于可访问性。每批独立可验收。

### Batch 1：Critical Bug 修复（0.5 天）

| 项 | 文件 | 修复 | 验收 |
| --- | --- | --- | --- |
| C1 | `dashboard.html` | cpRetire 改为跳转到 `/cron_retire?id=xx`（复用已有带 reason 的专用页面），或在 CpConfirm 中加 textarea 收集 reason 后 POST | 浏览器下线操作 → 跳转到下线页 / 成功 toast |
| C2 | `user_form.html` | 当 `user.is_active == 0` 时，隐藏 is\_active 行或改为只读"已停用"文本 | 编辑停用用户 → 不展示"启用"选项 |

### Batch 2：功能性 Bug + 安全修复（0.5 天）

| 项 | 文件 | 修复 | 验收 |
| --- | --- | --- | --- |
| M1 | `tags.html` | `status === 2` → `=== 0` | 含已暂停任务的标签 → 正确显示"已暂停" |
| M2 | `execution_logs.html` | Esc handler 改为查找表单 action URL 或 `.el-filters` 内链接 | 单任务日志页按 Esc → 跳回全量日志 |
| M3 | `task_detail.html` + `run_inspector.html` | onclick 内联改为 `data-keyword` + 事件委托 | keyword 含 `'` 时复制不报错 |

### Batch 3：UX 改善（1 天）

| 项 | 文件 | 修复 | 验收 |
| --- | --- | --- | --- |
| M4 | dashboard/task\_detail/registration\_review | AJAX confirm 操作添加 loading 状态 | 连续快击 → 第二次被拦截 |
| M5 | register/user\_form/user\_profile/complete\_profile | job\_title\_other change 事件 toggle required | 选"其他" → 提交空值 → 浏览器原生提示 |
| M8 | api\_token | execCommand → navigator.clipboard + fallback | 复制按钮在 HTTPS/localhost 下工作 |

### Batch 4：可访问性系统性补全（1 天）

| 项 | 文件 | 修复 | 验收 |
| --- | --- | --- | --- |
| M9 | dashboard/users/execution\_logs | icon 按钮添加 `aria-label` | axe-core 扫描无"button without label" |
| M10 | 8 个表单页 | `<label for>` + input `id` | 点击 label → 聚焦对应 input |
| M11 | register.html | 确认模态框添加 ARIA + focus trap + Escape | 键盘 Tab 不逃出模态框；Esc 关闭 |

## 四、不做的项目及理由

| 问题 | 为什么不做 |
| --- | --- |
| M6/M7 客户端密码匹配验证 | 后端已完整校验；客户端验证是 UX 增强而非 bug 修复；`js-ajax-form` 模式下后端错误通过 toast 反馈 |
| M12 `<a onclick>` 改 `<button>` | 语义改善但功能完全等价；改动需同步修改 CSS（`<a>` → `<button>` 会丢失样式）；ROI 过低 |
| 所有 Low 级问题 | 见 2.3 节分析——对用户无感知影响 |
| login.html 错误信息位置 | 设计遵循 Mockup；移动位置属于 UX 重设计而非 bug 修复 |

## 五、验收标准

### 5.1 Batch 1-2（Critical + 功能 bug）

```
# C1: Dashboard 下线操作
curl -s -b cookie.txt -X POST "http://127.0.0.1:5001/cron_retire" \
  -d "id=TEST_ID&reason=测试下线&csrf_token=TOKEN"
# → errcode=0 或跳转成功

# C2: 停用用户编辑页
curl -s -b cookie.txt "http://127.0.0.1:5001/rbac/users_edit?id=DEACTIVATED_USER_ID" \
  | grep -c 'value="1".*启用'
# → 0（不出现"启用"选项）

# M1: Tags 状态码
# 创建暂停状态任务 → 查看包含该任务的标签详情 → 状态显示"已暂停"

# M2: Esc 快捷键
# 打开 /job_log_list?id=1 → 按 Esc → 跳回全量日志页

# M3: onclick 注入
# 创建 keyword 含单引号的任务 → 任务详情页 → 复制按钮不报错
```

### 5.2 Batch 3-4（UX + A11y）

```
# M4: loading 状态
# Dashboard 操作按钮 → 点击 → 按钮 disabled + 文案变化

# M5: job_title_other required
# 注册页选"其他" → 空提交 → 浏览器原生"请填写此字段"

# M9: aria-label
grep -c 'aria-label' app/templates/redesign/dashboard.html  # ≥ 5

# M10: label for
grep -c 'for=' app/templates/redesign/user_form.html  # ≥ 6

# M11: 模态框 a11y
# register.html 确认模态框 → Tab 循环在模态内 → Esc 关闭
```

## 六、风险

| 风险 | 概率 | 影响 | 缓解 |
| --- | --- | --- | --- |
| C1 修复方案选择（跳转 vs 内嵌 textarea）影响 UX 一致性 | 中 | 低 | 跳转方案最安全（复用已有完整页面）；内嵌方案需参考 users.html deactivation modal |
| M3 事件委托改造影响已有 onclick 逻辑 | 低 | 中 | 改动范围仅 copy 按钮，不影响其他 onclick |
| M10 添加 id 属性可能与其他元素冲突 | 极低 | 低 | 使用唯一前缀如 `uf-field-xxx` |
| Batch 4 可访问性改造影响视觉 | 极低 | 低 | ARIA 属性不影响视觉渲染 |

## 七、时间线

| Batch | 内容 | 预估工时 | 依赖 |
| --- | --- | --- | --- |
| 1 | 2 个 Critical bug | 0.5 天 | 无 |
| 2 | 功能 bug + 安全 | 0.5 天 | 无（可与 B1 合并） |
| 3 | UX 改善 | 1 天 | B1/B2 先完成 |
| 4 | 可访问性补全 | 1 天 | B3 先完成 |
| 合计 | | 3 天 |  |

**推荐策略**：Batch 1+2 合并为一天交付（修复所有功能性问题），Batch 3+4 视用户优先级决定是否执行。

[文档索引](index.html) · [Markdown](Redesign功能页全量审查与修复计划.md) · [索引](index.html)

---

[← 文档索引（HTML）](../index.html) · [← 文档索引（Markdown）](../index.md)
