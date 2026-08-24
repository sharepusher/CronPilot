# 复盘：Tier 3-5 代码质量修复（CSS 规范 + 可访问性 + 后端日志 + JS 兼容性）

> HTML 版：[2026-08-tier345-code-quality.html](2026-08-tier345-code-quality.html) · [文档索引](../index.html) · [索引 Markdown](../index.md)

# 复盘：Tier 3-5 代码质量修复

**日期**：2026-08-24  
**范围**：CSS 硬编码颜色提取、重复 CSS 合并、HTML 可访问性、后端静默异常、JS 废弃 API

## 1. Bug 定位

| 编号 | 文件 | 行号 | 问题 |
| --- | --- | --- | --- |
| S3 | `redesign-pages.css` | 870, 972 | `rgba(8,145,178,0.12)` focus ring 硬编码，违反 `--cp-*` 变量规范 |
| S3 | `redesign-mockup-shared.css` | 47 | 同上 |
| S3 | `console-mode.css` | 274, 356 | 同上 |
| S2 | `redesign-mockup-shared.css` | 22, 181 | `.btn-c` 定义 2 次，transition 声明冲突 |
| A1 | `login.html` | 180 | 密码字段用 `<span>` 代替 `<label for>` |
| A2 | `change_password.html` | 27, 35, 44 | 3 个 `<label>` 缺 `for=` 属性 |
| A3 | `_topbar.html` | 16, 19 | 主题按钮缺 `aria-pressed` |
| A4 | `_sidebar.html` | 20 | `<nav>` 缺 `aria-label` |
| A5 | `execution_logs.html` | 367 | Escape 键无 modal overlay 检查 |
| A5 同类 | `run_inspector.html` | 148 | 同上 |
| B1 | `rbac/views.py` | 233 | `last_login_at` 更新失败 `except: rollback` 无日志 |
| B2 | `rbac/views.py` | 709 | Profile commit 失败无日志 |
| B3 | `cron_service.py` | 169, 222, 246 | 调度器 `pause_job`/`remove_job` 异常 `pass` 吞掉 |
| B4 | `common.js` | 500 | `escape()` 已废弃，应使用 `encodeURIComponent()` |

## 2. 根因

- **S2/S3（CSS 硬编码与重复）**：Mockup 直出的 CSS 被逐节复制到生产样式表中，未经统一颜色变量化审计。`rgba(8,145,178,…)` 是设计系统主色 `--cp-accent` 的半透明变体，但 `console-theme.css` 中未定义对应变量，导致各文件直接硬编码。
- **A1-A4（可访问性缺失）**：Redesign 开发以视觉还原为主，缺少 a11y checklist。`login.html` 使用 `<span>` + flex 布局实现密码行的 label-row，跳过了语义化 `<label>`。
- **A5（Escape 键误触）**：P0-4 修复时只检查了 `task_detail.html` 和 `task_form.html`，遗漏了 `execution_logs.html` 和 `run_inspector.html` 中的相同模式。
- **B1-B3（静默异常）**：防御性 try-except 编写时以"不影响主流程"为目标，直接 `pass`，未考虑运维可观测性。
- **B4（废弃 API）**：`setCookie()` 是早期 v1 遗留代码，从未经过现代化审查。

## 3. 测试漏洞

- 无 CSS lint 门禁检查 `rgba()` 硬编码（现有 `audit_hardcoded_colors.py` 只检查 hex 色值）。
- 无 a11y 自动化测试（如 axe-core / pa11y）。
- P0-4 同类排查时搜索了 `.cp-confirm-overlay`，但 `execution_logs.html` 和 `run_inspector.html` 使用的是直接 `e.key === 'Escape'` 不含 `.cp-confirm` 关键字，因此未被搜索到。
- 后端 `except: pass` 无 lint 规则禁止。

## 4. 修复

- **S3**：`console-theme.css` 新增 `--cp-accent-ring`（light/dark 双套），5 处硬编码替换为 `var(--cp-accent-ring)`。
- **S2**：`.btn-c` 的 transition 合并到首定义，删除重复块。
- **A1**：`login.html` `<span>密码</span>` → `<label for="login-pwd-input">密码</label>`。
- **A2**：`change_password.html` 3 个 `<label>` 补全 `for="pwd-old/pwd-new/pwd-confirm"`。
- **A3**：2 个主题按钮增加 `aria-pressed="{{ 'true' if theme == '...' else 'false' }}"`。
- **A4**：`<nav>` 增加 `aria-label="主导航"`。
- **A5**：`execution_logs.html` + `run_inspector.html` Escape handler 增加 `!document.querySelector('.cp-modal-overlay')` 守卫。
- **B1/B2**：`rbac/views.py` 两处 `except` 增加 `current_app.logger.warning(..., exc_info=True)`。
- **B3**：`cron_service.py` 3 处 `except: pass` 改为 `_log.warning(..., exc_info=True)`。
- **B4**：`escape(value)` → `encodeURIComponent(value)`。

## 5. 防护测试

- 现有 `audit_hardcoded_colors.py --check` 对 hex 色值的门禁覆盖，`rgba` 变体需人工确认（见预防方案）。
- `cronpilot.sh test` 全 438 用例通过，确认后端变更未引入回归。
- Escape 键守卫已由 P0-4 测试覆盖 `task_detail.html` 和 `task_form.html`；新增的 `execution_logs.html` 和 `run_inspector.html` 同类修复由结构一致性保证。

## 6. 同类排查

- `rgba(8,145,178` 全仓库搜索结果：仅剩 `console-theme.css` 中的变量定义（预期）。
- `escape(` 在 JS 中仅 `common.js` 一处（已修复），`redesign-*.js` 无此用法。
- `except.*:\n.*pass` 在 `app/` 中全局搜索：`cron_service.py` 3 处已修复；其余 `except: pass` 在 `register_cron_job`（JobLookupError 可容忍）、`__init__.py`（APScheduler 初始化）属合理场景。
- Escape 键 handler 全模板搜索：`task_detail.html`、`task_form.html`（已修）、`execution_logs.html`（本轮已修）、`run_inspector.html`（本轮已修）、`users.html`（仅关闭弹窗，合理）。

## 7. 预防方案

| 措施 | 落地位置 | 验证命令 |
| --- | --- | --- |
| 新增 `--cp-accent-ring` CSS 变量，未来 focus ring 样式统一引用 | `console-theme.css` :root + [data-theme="dark"] | `grep 'accent-ring' app/static/css/console-theme.css` |
| Escape 键 handler 同类排查已覆盖所有 redesign 模板 | 本复盘文档 §6 同类排查 | `grep -r "e.key === .Escape" app/templates/redesign/ | grep -v cp-modal-overlay | grep -v closeDm`（应为空） |
| `except: pass` 后端审查完成 | 本复盘文档 §6 同类排查 | `grep -rn "except.*:$" app/services/ app/rbac/ | grep -A1 "pass$"`（应无新增盲吞） |

[文档索引](index.html) · [Markdown](2026-08-tier345-code-quality.md) · [索引](index.html)

---

[← 文档索引（HTML）](../index.html) · [← 文档索引（Markdown）](../index.md)
