# 复盘：Z3 标签管理页 Bootstrap Modal 迁移 — CronPilot

> HTML 版：[2026-08-Z3-标签页Bootstrap模态框迁移.html](2026-08-Z3-标签页Bootstrap模态框迁移.html) · [文档索引](../index.html) · [索引 Markdown](../index.md)

# 复盘：Z3 — 标签管理页 Bootstrap Modal 系统迁移

日期：2026-08-20 · 触发：用户报告「功能都不测试吗」 · 类型：Bug 修复复盘

## 1. Bug 定位

|  |  |
| --- | --- |
| 位置 | app/templates/redesign/tags.html，4 个 Bootstrap modal：#create-modal、#edit-modal、#tasks-modal、#delete-modal |
| 现象 | 点击删除/新建/重命名按钮后出现半透明遮罩，对话框不可见（内容区域空白）；用户强烈反馈"页面透明的，功能都不测试吗" |
| 失败代码 | ``` $('#delete-modal').modal('show');  // Bootstrap modal，在 redesign shell 中不渲染 $('#create-modal').modal('show');  // 同上 $('#edit-modal').modal('show');    // 同上 $('#tasks-modal').modal('show');   // 同上 ``` |

## 2. 根因

行为层根因（非"粗心"）：

- **CSS 命名空间污染**：redesign shell（redesign-components.css）重新定义了 .modal、.modal-backdrop 等类的样式，导致 Bootstrap 的定位和层叠规则失效。Bootstrap modal 依赖 display:block + position:fixed + 特定 z-index 协作，被 redesign CSS override 后对话框 display:none 条件不满足但 visibility 为 0。
- **迁移不完整**：同一时期，api\_token.html 和 users.html 上的对话框已被迁移到 CpConfirm.show()，但 tags.html 被遗漏——原因是 tags 页的表单型 modal（新建/重命名）需要额外的输入框支持，实现复杂度更高，导致偷懒推迟而未在同一轮完成迁移。
- **验证层级不足**：Z3 第一次实现（添加 pill 内联 × 按钮）时，验证只覆盖了"× 按钮是否渲染"和"stopPropagation 是否生效"，未验证点击后对话框是否正常显示——这是 E2E 交互验证的盲区。

## 3. 测试漏洞

| 现有测试 | 为何未能拦截 |
| --- | --- |
| tests/test\_redesign\_sidebar.py — 权限/导航测试 | 不覆盖 JS 模态框渲染行为 |
| tests/test\_ajax\_form\_guard.py — 防重复提交测试 | 只检查 form 类名，不验证模态框可见性 |
| 单元测试全部绿 | Python 单元测试无法验证浏览器内 CSS/JS 渲染结果 |
| CDP 自动化（pill 渲染检查） | 只检查 DOM 中 .tg-pill-del-btn 是否存在，未触发点击并检查 modal 可见性 |

根本漏洞：缺少"点击操作按钮 → 验证模态框 display 和 opacity"这一层 E2E 验证。CSS 冲突类 Bug 必须在浏览器渲染层才能发现。

## 4. 修复

最小 diff 方案：彻底替换 tags.html 中所有 Bootstrap modal 为 redesign 原生 modal 系统。

| 操作 | 内容 |
| --- | --- |
| 删除 | 4 个 Bootstrap modal HTML 块（#create-modal / #edit-modal / #tasks-modal / #delete-modal） |
| 删除 | <link rel="stylesheet" href="bootstrap.min.css"> 和 <script src="bootstrap.min.js"> |
| 新增 | CpModal(opts) 工厂函数（使用 .cp-modal-overlay / .cp-modal / .cp-modal-body 标准 CSS 结构，innerHTML 注入表单） |
| 新增 | 模态框内表单 CSS（.tg-fg / .tg-input / .tg-select / .tg-err） |
| 保留 | 删除确认使用 CpConfirm.show()（简单确认）；强制删除使用 CpModal()（需渲染任务列表 HTML） |

## 5. 防护测试

CDP 验证通过（2026-08-20）

| 验证项 | 方法 | 断言 |
| --- | --- | --- |
| 删除确认 modal | CDP click .btn-tag-delete，检查 snapshot | snapshot 中出现 role:button name:确认删除 和 role:heading name:删除标签「JP」 |
| 新建标签 modal | CDP click #btn-new-tag，检查 snapshot | snapshot 中出现 role:textbox placeholder:如：JP、支付核心 和 role:combobox（业务组选择） |
| ESC 关闭 | CDP press Escape，检查 modal 消失 | snapshot 不包含 role:heading name:新建标签 |
| 截图留证 | browser\_take\_screenshot | 对话框可见、背景半透明、按钮样式正确 |

E2E 验证截图保存在：doc/design/screenshots/round4/tags\_delete\_modal.png 和 tags\_create\_modal.png。

## 6. 同类排查

| 页面 | 是否存在 Bootstrap modal | 状态 |
| --- | --- | --- |
| api\_token.html | 原有，已在上一轮迁移到 CpConfirm | ✅ 已修复 |
| users.html | 原有，已在上一轮迁移到 CpConfirm | ✅ 已修复 |
| tags.html | 4个，本轮全部迁移 | ✅ 本轮修复 |
| 其他 redesign 模板 | 全量 grep 检查 | 见下方命令输出 |

```
grep -r "modal('show')\|\.modal('hide')\|bootstrap.min" \
  app/templates/redesign/ \
  --include="*.html"
# 结果：无匹配（clean）
```

## 7. 预防方案（可落地 + 可验证）

### 方案 A：规范文档落地（已执行）

在 .cursor/rules/cronpilot-project.mdc 和 AGENTS.md 新增"Redesign 确认对话框规范"：

- 禁止在 app/templates/redesign/ 中使用 $().modal('show')
- 强制使用：CpConfirm.show()（简单确认）或 CpModal()（表单/HTML体）

### 方案 B：CI 静态检查（新增门禁）

新增检查命令（可加入 scripts/check\_ui\_contract.py 或单独脚本）：

```
grep -r "modal('show')\|bootstrap.min.js" app/templates/redesign/ --include="*.html"
# 有匹配 → CI 失败
```

验证方法：grep -r "\.modal('show')" app/templates/redesign/ 返回空行则通过。

### 方案 C：E2E 模态框可见性验证规范（新增）

凡涉及"点击按钮 → 弹出对话框"的交互变更，验证必须包含：

- CDP click 后检查 snapshot 中是否出现对话框 heading 或按钮
- 或 Runtime.evaluate 检查 document.querySelector('.cp-modal-overlay') 不为 null
- 禁止仅凭"单测通过"或"DOM 中存在按钮"宣称对话框功能可用

落地位置：.cursor/rules/cronpilot-project.mdc §"浏览器端 DOM / CSS / JS 修改"和 §"Redesign 确认对话框规范"。

[文档索引](index.html) · [Markdown](2026-08-Z3-标签页Bootstrap模态框迁移.md) · [索引](index.html)

---

[← 文档索引（HTML）](../index.html) · [← 文档索引（Markdown）](../index.md)
