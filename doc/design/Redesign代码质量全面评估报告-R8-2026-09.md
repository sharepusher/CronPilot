# Redesign 代码质量全面评估报告 R8（2026-09）

> HTML 版：[Redesign代码质量全面评估报告-R8-2026-09.html](Redesign代码质量全面评估报告-R8-2026-09.html) · [文档索引](../index.html) · [索引 Markdown](../index.md)

# Redesign 代码质量全面评估报告 R8（2026-09-03）

状态：待讨论 · 基于 R7 修复后的代码基线

## 0. 自动化门禁结果

| 门禁 | 结果 | 说明 |
| --- | --- | --- |
| `ruff check app/` | PASS | 0 违规 |
| `audit_hardcoded_colors.py --check` | PASS | 模板/Vue 无硬编码颜色 |
| `check_ui_contract.py --check` | PASS | inline CSS ≤ 3 行 |
| `check_dead_css.py --check` | PASS | 0 死 CSS 类 |
| `check_css_token_reachability.py --check` | PASS | 所有 token/动画可达 |
| `html_docs_to_markdown.py --check` | PASS | 文档同步 |
| 单元测试 | PASS | 664 tests, 0 failures |
| Bootstrap modal 禁令 | PASS | Redesign 无 Bootstrap 引用 |
| jQuery 同步加载 | PASS | `_base.html:47` 无 defer/async |

## 1. 后端发现（Backend）

### 1.1 P0 — 安全 / 数据完整性

| ID | 文件:行 | 描述 | 建议修复 |
| --- | --- | --- | --- |
| BE-P0-1 | `cron_service.py:361-382` | **B-15 scope 持久化仍未修复。**`upsert_cron_by_task_name()` 调用 `validate_cron_form()` 后得到的 `normalized` 不含 `scope_type`/`group_id`。对比 `add_cron_web()`（行 389-391）有手动拷贝。API 创建的 GROUP 任务全部退化为 GLOBAL。 | 验证后合并 scope：`if 'scope_type' in datas: normalized['scope_type'] = datas['scope_type']; normalized['group_id'] = datas.get('group_id')` |
| BE-P0-2 | `api/views.py:670-706` | **旧路由 `/api/cron/add` 接受 GET 执行状态修改。**GET 可通过 `<img src=...>` 触发 CSRF 和缓存投毒。 | 限制为 `methods=['POST']`，或 GET 时返回 405。 |
| BE-P0-3 | `api/__init__.py:76-78,97-99` | **配置 `api_access_token` 为空时，API 默认赋予 admin 权限。**部署遗漏配置即开放全部 API。 | 空 token 配置时拒绝请求（401/500），或要求显式 `api_dev_mode=true` 才放行。 |

### 1.2 P1 — 功能缺陷 / 重要质量问题

| ID | 文件:行 | 描述 | 建议修复 |
| --- | --- | --- | --- |
| BE-P1-1 | `cron_service.py:231,275` | `create_cron()`/`update_cron()` commit 后 `register_cron_job()` 无 try/except 回滚。scheduler 失败 → DB 有 active 任务但无调度。 | 对齐 `toggle_status()` 的 commit→scheduler→rollback 模式。 |
| BE-P1-2 | `cron_service.py:328-332` | `retire_cron_by_id()` 先 `remove_job()` 再 commit。commit 失败时 scheduler 已删除。 | 调换顺序：先 commit retire 状态，再 remove\_job。 |
| BE-P1-3 | `cron_service.py:257-264` | `update_cron()` 切换到 GLOBAL 时不清理 `task_groups` 残留。 | 当 `scope_type == 'GLOBAL'` 时执行 DELETE。 |
| BE-P1-4 | `operation_log_service.py:41-56` | 操作日志快照仍引用已移除的 `cif.group_id`，快照不含组变更。 | 改为查 `get_task_group_id(cif.id)`。 |
| BE-P1-5 | `api/views.py:133-426` | 所有 GET 查询端点无 `check_api_permission('cron:read')`，仅做 scope 过滤。 | 每个 GET 端点顶部加 permission 检查（防御纵深）。 |
| BE-P1-6 | `registration_request_repository.py:56-58` | 组 ID 过滤用 `like('%%%s%%' % gid)` 无边界，ID=1 匹配 11/21 等。 | 改为逗号边界匹配 `like('%,1,%')` 或关系化存储。 |
| BE-P1-7 | `rbac/services.py:912-918` | `submit_registration()` 用 `str(exc)` 字符串匹配判断冲突，易误判。 | 改为 catch `IntegrityError`。 |
| BE-P1-8 | `cron_infos.py:14` | `task_name` 无数据库 UNIQUE 约束，仅应用层校验。并发创建可重名。 | 加 `unique=True` + 迁移脚本。 |
| BE-P1-9 | `task_group.py:20-22` | `UniqueConstraint('task_id','group_id')` 允许一任务多组，但业务假设单组。 | 改为 `UniqueConstraint('task_id')` 或业务校验+约束。 |
| BE-P1-10 | `api/__init__.py:149-151` | `_resolve_user_token()` catch-all 返回 None，基础设施异常与无效 token 不可区分。 | 区分基础设施错误（500+log）和无效 token（401）。 |
| BE-P1-11 | `cron_service.py:212-221` | `create_cron()` 可写入 `scope_type='GROUP'` 无 `group_id`，导致任务不可见。 | 服务入口校验：GROUP 必须有 group\_id。 |
| BE-P1-12 | `cron_validator.py:137-138` | run\_date 过期检查使用字符串比较，格式/时区变化时脆弱。 | 改为解析后的 datetime/BIGINT 比较。 |

### 1.3 P2 — 代码质量改进

| ID | 文件 | 描述 |
| --- | --- | --- |
| BE-P2-1 | `cron_service.py:7,15` | 双 logger 定义 `logger` + `_log`（同模块） |
| BE-P2-2 | `cron_service.py:146` | `reschedule_orphan_task()` bare `except Exception: pass` |
| BE-P2-3 | `tag_service.py:107` | `suggest_tags()` LIKE 通配符未转义 |
| BE-P2-4 | `pagination.py:32-40` | `per_page` 无上限（可 OOM） |
| BE-P2-5 | `api/views.py:164` | cron\_query LIKE 通配符未转义 |
| BE-P2-6 | `api/views.py:56-116` | token 成功签发无审计日志 |
| BE-P2-7 | `rbac/decorators.py:17-18` | 未认证重定向 `next=` 未经 `safe_next_url()` |
| BE-P2-8 | `rbac/services.py:543` | 重置密码返回默认密码 `changeme` |
| BE-P2-9 | `errors.py:1-40` | 仅注册 404/500，缺 403/400/405 处理器 |
| BE-P2-10 | `cron_infos.py:35-37` | `status` 默认 `True`（布尔），应为 `1` |
| BE-P2-11 | `cron_infos.py:14` | `task_name` 无索引 |
| BE-P2-12 | `job_log.py:50-59` | `to_json()` 引用不存在字段（死代码） |
| BE-P2-13 | `job_log.py:21-36` | 缺 `(cron_info_id, create_time)` 复合索引 |
| BE-P2-14 | `operation_log_service.py:173-178` | API 审计 metadata 固定写 `cron:write` |
| BE-P2-15 | `api/__init__.py:193` | scope 拒绝用 HTTP 200 + errmsg |
| BE-P2-16 | `rbac/policy.py:41-43` | 废弃函数 `role_bypasses_scope` 仍导出 |
| BE-P2-17 | `rbac_audit_log.py:15-18` | `username`/`action` 列缺索引 |
| BE-P2-18 | `operation_log.py:37` | `target_id` 列缺索引 |

## 2. 前端发现（Frontend）

### 2.1 P0 — 无

所有自动化门禁通过。无 Bootstrap modal 违规、无硬编码颜色、无 XSS 直接利用路径。

### 2.2 P1 — 安全加固 / 可访问性 / 可维护性

| ID | 文件:行 | 描述 | 建议修复 |
| --- | --- | --- | --- |
| FE-P1-1 | `registration_review.html:155` `redesign-shell.js:111` | `escHtml` fallback 直接返回原始字符串（`return s`）。如 `common-redesign.js` 未加载，`bodyHtml` 拼接存在 XSS 风险。 | 移除 fallback；或 inline 最小转义函数。 |
| FE-P1-2 | `_users_rows.html:46,53,56-70,82` | 5 个 icon-only `um-icon-btn` 有 `data-tooltip` 但无 `aria-label`。 | 添加 `aria-label` 与 tooltip 文案一致。 |
| FE-P1-3 | `_topbar.html:35-41` | 用户菜单触发器是 `<div>`，不可键盘聚焦，无 ARIA。 | 改为 `<button type="button">` + `aria-haspopup` + `aria-expanded`。 |
| FE-P1-4 | `dashboard.html:189,209,260,287` | AJAX URL 硬编码（`/update_status` 等），不用 `url_for()`。 | 用 Jinja `url_for()` 注入。 |
| FE-P1-5 | `task_form.html:274` | 标签建议 `fetch('/api/tags/suggest')` 硬编码 + 无 `r.ok` 检查。 | 用 `url_for` + 加 status 检查。 |
| FE-P1-6 | `registration_review.html:211-213` | 批量审批 `$.post()` 无 `.fail()` 和 `errcode` 检查。 | 补充错误处理。 |
| FE-P1-7 | `dashboard.html:331-342` 等多处 | `fetch().then(r => r.json())` 未检查 `r.ok`，500 HTML 响应导致 JSON 解析失败。 | 加 `if (!r.ok) throw`。 |
| FE-P1-8 | `task_form.html:12-13` | POST 表单无显式 `csrf_token` hidden field（依赖 meta + JS 注入）。 | 添加隐藏字段增强鲁棒性。 |
| FE-P1-9 | `complete_profile.html:85-88` | 注销表单无防重复提交保护（auth 页不加载 `common-redesign.js`）。 | 添加 inline submit 守卫。 |

### 2.3 P2 — 代码质量改进（25 项）

| ID | 主题 | 涉及文件 |
| --- | --- | --- |
| FE-P2-1 | dashboard stat-line inline style → CSS class | `dashboard.html:18,401` |
| FE-P2-2 | run\_inspector inline 布局/颜色 → redesign-pages.css | `run_inspector.html:45-47` |
| FE-P2-3 | user\_form inline display/color → utility class | `user_form.html:43,45` |
| FE-P2-4 | task\_form conditional display:none → CSS class | `task_form.html:67,91` |
| FE-P2-5 | tags CpConfirm title 不需要 escHtml（textContent 已安全） | `tags.html:299` |
| FE-P2-6 | 全局函数 highlightTag 应命名空间化 | `tags.html:325` |
| FE-P2-7 | dashboard\_rows 下拉用 `<a onclick>` 无键盘可达 | `_dashboard_rows.html:98-104` |
| FE-P2-8 | register 自定义 modal 可共享 auth 组件 | `register.html:130-142` |
| FE-P2-9 | auth 页面验证逻辑重复 | `login/register/complete_profile` |
| FE-P2-10 | common-redesign.js 全局变量（getCookie/setCookie/escHtml） | `common-redesign.js:160-178` |
| FE-P2-11 | redesign-shell.js 命令面板 href 拼接未编码 | `redesign-shell.js:102` |
| FE-P2-12 | 主题切换无 `aria-pressed` | `redesign-theme.js:15-22` |
| FE-P2-13 | cpCopy 重复实现（task\_detail + run\_inspector） | `task_detail.html:238` |
| FE-P2-14 | api\_token 剪贴板无 `.catch()` | `api_token.html:65-69` |
| FE-P2-15 | dashboard 全局函数与 partial 耦合 | `dashboard.html:180-300` |

## 3. 汇总

| 维度 | P0 | P1 | P2 | 主要主题 |
| --- | --- | --- | --- | --- |
| 后端 | 3 | 12 | 18 | B-15 scope 丢失、API GET 修改、空 token admin 放行、scheduler/DB 事务序 |
| 前端 | 0 | 9 | 15+ | escHtml fallback、a11y 缺失、AJAX URL 硬编码、fetch 错误处理 |
| **合计** | **3** | **21** | **33+** |  |

### 3.1 与 R7 对比

| 指标 | R7（2026-08） | R8（2026-09） | 变化 |
| --- | --- | --- | --- |
| P0 | 1 | 3 | +2（更深入审计发现 API-01/API-02） |
| P1 | 6 BE + 9 FE = 15 | 12 BE + 9 FE = 21 | +6（更细粒度 service 层审计） |
| P2 | 6 BE + 11 FE = 17 | 18 BE + 15 FE = 33 | +16（model 索引 + 死代码） |
| 自动化门禁 | 全通过 | 全通过 | — |

R8 比 R7 发现更多问题是因为审计粒度提升（深入到 service 事务序列、model 约束、repository LIKE 通配符、API 空 token 降级等），并非代码质量退化。R7 修复的 S-1/S-2/S-3/S-4/S-5 等安全项均未回归。

## 4. 建议处理优先级

1. **BE-P0-1（B-15 scope 丢失）** — 恢复 API scope 隔离；解除 e2e 测试 expectedFailure（~15min）
2. **BE-P0-2 + BE-P0-3** — 关闭 API 层 CSRF + auth 降级风险（~30min）
3. **BE-P1-1 + BE-P1-2** — scheduler/DB 事务对齐（~20min）
4. **FE-P1 批次** — a11y + AJAX 加固（需设计文档 + 前后对比 demo）
5. **BE-P1-6 ~ P1-9** — 数据完整性约束加固
6. P2 按需处理

[文档索引](index.html) · [Markdown](Redesign代码质量全面评估报告-R8-2026-09.md)

---

[← 文档索引（HTML）](../index.html) · [← 文档索引（Markdown）](../index.md)
