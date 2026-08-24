# 复盘：用户管理页 UX 三 Bug（2026-08）

> HTML 版：[2026-08-users-ux-bugs.html](2026-08-users-ux-bugs.html) · [文档索引](../index.html) · [索引 Markdown](../index.md)

# 复盘：用户管理页 UX 三 Bug（2026-08）

**版本**：Unreleased（A2 后续） | **复盘时间**：2026-08-18 | **触发来源**：用户报告

## 一、问题概述

用户在 A2（用户管理页列结构重构 + Chip 筛选器）交付后反馈三个 UX 问题：

| 编号 | 问题描述 | 严重程度 |
| --- | --- | --- |
| UX-1 | 操作列图标按钮鼠标悬停提示（tooltip）显示极慢（浏览器原生延迟约 500ms–1s） | 体验差 |
| UX-2 | 停用用户的操作列使用眼睛图标（👁），与密码可见性图标含义冲突，产生歧义 | 认知混乱 |
| UX-3 | 停用用户点击操作（眼睛图标链接）跳转到用户编辑页，停用账号不应可编辑 | 功能错误 |

## 二、逐 Bug 复盘

### Bug UX-1：Tooltip 显示慢

| 要素 | 内容 |
| --- | --- |
| **Bug 定位** | `app/templates/redesign/users.html` — 图标按钮使用 HTML 原生 `title` 属性 |
| **根因** | 浏览器原生 `title` tooltip 有约 500ms–1000ms 的操作系统级内置延迟，无法通过 CSS/JS 覆盖。这是 OS 级行为，与 Web 代码无关 |
| **测试漏洞** | A2 实现期间未在浏览器中做悬停体验测试；图标按钮的 tooltip 延迟是感知性问题，不会在 Python unittest 或 curl 中暴露 |
| **修复** | 将 `title="xxx"` 替换为 `data-tooltip="xxx"`，通过 CSS `[data-tooltip]::after` + `transition: opacity 0.08s` 实现立即显示的自定义 tooltip |
| **防护测试** | ``` python -c " import urllib.request resp = urllib.request.urlopen('http://127.0.0.1:5001/rbac/users') html = resp.read().decode() assert 'data-tooltip=' in html, 'FAIL: data-tooltip missing' assert 'title=' not in html.split(' ')[0], 'FAIL: title attr still present in ops column' print('OK: data-tooltip found, no title attr in ops column') " | ``` |
| **同类排查** | 检查 `redesign/` 目录下其他模板中的 `title=` 用法：任务列表页、执行日志页的操作按钮均未使用 `title`；此问题仅出现在 users.html |
| **预防方案** | 在 `tests/test_check_ui_contract.py` 中新增断言：`redesign/users.html` 的 `.um-ops` 列不得含有 `title=` 属性；或在 `scripts/audit_button_classes.py` 中追加 "action column title attribute" 检查 |

### Bug UX-2：眼睛图标语义歧义

| 要素 | 内容 |
| --- | --- |
| **Bug 定位** | `app/templates/redesign/users.html` — 停用用户操作列使用眼睛（eye）SVG 图标表示"查看用户" |
| **根因** | 眼睛图标在 Web 惯例中几乎固定表示"显示/隐藏密码"。实现时选用 eye 图标表示"查看详情"，未检查 icon-to-meaning 惯例映射，导致与密码操作含义冲突 |
| **测试漏洞** | 无 UX/可用性测试；icon-semantic 正确性是主观感知问题，需要设计审查或 UX 测试，纯代码审查无法发现 |
| **修复** | 对停用用户操作列，完全移除图标按钮，改为静态文字标签 `<span class="um-inactive-label">已停用</span>`，彻底消除歧义 |
| **防护测试** | ``` python -c " import urllib.request resp = urllib.request.urlopen('http://127.0.0.1:5001/rbac/users') html = resp.read().decode() assert 'um-inactive-label' in html, 'FAIL: inactive label missing' print('OK: um-inactive-label present') " ``` |
| **同类排查** | 全仓库搜索眼睛图标使用：`grep -r "eye" app/templates/redesign/`。结论：仅 `change_password.html` 使用眼睛图标（密码可见性切换），语义正确 |
| **预防方案** | 在 `doc/design/CronPilot-2026-redesign-mockup.html` 的图标规范节中明确 eye 图标仅用于密码可见性；在 `.cursor/rules/cronpilot-project.mdc` 追加"图标语义约束"规范条目（见下方规范更新） |

### Bug UX-3：停用用户跳转编辑页

| 要素 | 内容 |
| --- | --- |
| **Bug 定位** | `app/templates/redesign/users.html` — 停用用户的操作链接 `href="{{ url_for('rbac.users_edit', ...) }}"` 指向编辑路由 |
| **根因** | A2 实现时从启用用户行直接复制了操作列 HTML，只改了图标为 eye，未将链接目标改为只读视图（且项目当前无独立只读用户视图路由）。策略"停用用户不可编辑"未在模板层体现 |
| **测试漏洞** | 未针对停用用户编写"点击操作后跳转目标正确性"的集成测试；单元测试只验证用户数据查询，不验证模板 URL 生成语义 |
| **修复** | 停用用户操作列不渲染任何链接或按钮，仅显示 `<span class="um-inactive-label">已停用</span>`，从根本上阻止跳转 |
| **防护测试** | ``` python -c " import re, urllib.request resp = urllib.request.urlopen('http://127.0.0.1:5001/rbac/users') html = resp.read().decode() # Verify inactive users don't have edit links inactive_ops = re.findall(r'um-inactive-label.*?', html, re.DOTALL) assert len(inactive_ops) > 0, 'FAIL: no inactive user rows found' edit_in_inactive = 'users_edit' in str(inactive_ops) assert not edit_in_inactive, 'FAIL: edit link found in inactive user row' print(f'OK: {len(inactive_ops)} inactive users, no edit links') " ``` |
| **同类排查** | 检查其他页面的停用/受限状态行为：注册审批页的"已拒绝"申请仅展示状态标签，无操作链接 — 模式正确。仅 users.html 存在此问题 |
| **预防方案** | 在 `tests/test_rbac_scope.py` 或新建 `tests/test_users_template.py` 中添加测试：创建一个停用用户，GET `/rbac/users`，断言响应 HTML 中该用户行不含 `href.*users_edit`；将此用例加入 CI 必跑套件 |

## 三、综合预防方案

| 预防措施 | 落地位置 | 验证命令 |
| --- | --- | --- |
| 新建 `tests/test_users_template.py`，覆盖：① ops 列无 `title=`；② 停用行无编辑链接；③ 停用行含 `um-inactive-label` | `tests/test_users_template.py` | `python -m unittest tests.test_users_template -v` |
| 在图标规范中明确 eye 图标仅用于密码可见性，其他"查看"操作使用 person 或 info 图标 | `doc/design/CronPilot-2026-redesign-mockup.html` 图标规范节 | `grep -c "eye.*password" doc/design/CronPilot-2026-redesign-mockup.html` |
| 策略变更影响分析强制清单追加：UI 中停用/受限状态行必须做"无操作链接"验证 | `.cursor/rules/cronpilot-project.mdc` 策略变更影响分析节 | Review 时执行 `git diff -- app/templates/redesign/users.html | grep users_edit` |

## 四、修复验证证据

```
# 1. 重启后验证
PID: 7187 — 监听 127.0.0.1:5001

# 2. data-tooltip 验证
document.querySelectorAll('.um-icon-btn[data-tooltip]')[0..2]
→ ["编辑用户", "重置密码", "重置 API Token"]  ✅

# 3. 停用标签验证
document.querySelector('.um-inactive-label').outerHTML
→ <span class="um-inactive-label">已停用</span>  ✅

# 4. 用户页面正常加载
curl -s http://127.0.0.1:5001/rbac/users -w "%{http_code}" | tail -1
→ 200  ✅
```

## 五、关联文档

- [CronPilot-2026-redesign-mockup.html](../design/CronPilot-2026-redesign-mockup.html) — 权威设计规格
- [2026-08-错误Mockup文件评估复盘](2026-08-错误Mockup文件评估复盘.html) — 上轮使用错误Mockup文件的复盘

[文档索引](index.html) · [Markdown](2026-08-users-ux-bugs.md) · [索引](index.html)

---

[← 文档索引（HTML）](../index.html) · [← 文档索引（Markdown）](../index.md)
