# 复盘：Dashboard AJAX 路径错误（F1+F2+F3）

> HTML 版：[2026-08-dashboard-ajax-path.html](2026-08-dashboard-ajax-path.html) · [文档索引](../index.html) · [索引 Markdown](../index.md)

# 复盘：Dashboard AJAX 路径错误（F1+F2+F3）

|  |  |
| --- | --- |
| 日期 | 2026-08-24 |
| 发现方式 | 全面前后端代码审计（Code Review） |
| 严重级别 | 功能性 Bug — Dashboard 操作按钮全部失效 |
| 修复状态 | 已修复 |

## 1. Bug 定位

`app/templates/redesign/dashboard.html` 行 465, 485, 513：

| 函数 | 原路径 | 实际 Flask 路由 | 后果 |
| --- | --- | --- | --- |
| `cpToggleStatus()` | `/update_status/{cronId}` | `/update_status`（id via form data） | 404 |
| `cpRunNow()` | `/cron_run_now/{cronId}` | `/cron_run_now`（id via form data） | 404 |
| `cpRetire()` | `/update_status/{cronId}` + `{status:-1}` | `/cron_retire`（id via form data） | 404 + 逻辑错误 |

验证：`curl -s -o /dev/null -w "%{http_code}" -X POST http://127.0.0.1:5001/update_status/123` → **404**

## 2. 根因

Redesign Dashboard 在开发时，开发者习惯使用 RESTful 风格 URL（`/resource/{id}`），而未检查 Flask 实际注册的路由格式。CronPilot 后端统一使用 query param / form data 传递 `id`（`request.values.get('id')`），不使用 path param。

同项目的 v1 模板 `_cron_list_rows.html` 使用 `url_for('main.update_status', id=item.id)` 生成正确 URL；redesign `task_detail.html` 使用 `/update_status?id=taskId`。唯独 `dashboard.html` 使用了不同格式。

**根因行为层**：新模板开发时未检查已有模板中的同一 API 调用方式，也未 `curl` 验证 AJAX 请求的实际响应。

## 3. 测试漏洞

无集成测试或 E2E 测试覆盖 Dashboard 的 AJAX 操作。单元测试覆盖 `update_status` 和 `cron_run_now` 的后端逻辑，但不覆盖前端发送的 URL 是否正确。Redesign 验收只验证了 Dashboard 的静态渲染（列表显示），未验证交互操作。

## 4. 修复

- **F1**：`'/update_status/' + cronId` → `'/update_status'`，`id` 通过 POST data 传递
- **F1**：`'/cron_run_now/' + cronId` → `'/cron_run_now'`，同上
- **F2**：`cpRetire()` 改 POST 到 `/cron_retire`（正确路由 + 正确权限 `cron:retire`）
- **F3**：去除 `{status: newStatus}` 无用参数（后端 toggle 模式不读取此参数）

## 5. 防护测试

```
# 登录后验证渲染结果
python3 -c "..." → 确认三处 $.post 路径为 /update_status、/cron_run_now、/cron_retire
# 验证路径匹配
curl -s -o /dev/null -w "%{http_code}" -X POST "http://127.0.0.1:5001/update_status?id=1" → 302（需登录）而非 404
```

## 6. 同类排查

全仓库搜索所有模板中对后端路由的直接硬编码引用：

```
rg "\.post\('/[a-z_]+/" app/templates/ → 无其他 path-param 风格调用
rg "\.post\('/update_status" app/templates/ → 仅 dashboard.html（已修复）
```

`task_detail.html` 使用 `/update_status?id=`（正确）。`_cron_list_rows.html` 使用 `url_for()`（正确）。

## 7. 预防方案

| 措施 | 落地位置 | 验证命令 |
| --- | --- | --- |
| 新增规范：模板中 AJAX 请求 URL 必须使用 `url_for()` 或与已有调用点对齐，禁止凭记忆/惯例构造 URL | `AGENTS.md` | `grep "url_for\|AJAX.*URL" AGENTS.md` |
| 新增自检命令：搜索模板中使用 path-param 风格的 AJAX URL | `AGENTS.md` | `rg "\.post\('/[a-z_]+/'" app/templates/ && echo "WARN: path-param URL found" || echo "OK"` |

---

## 附录：D5+D6 标签页代码质量修复

### D5: alert() → CpToast

**Bug 定位**：`tags.html` 行 322, 344, 445, 448 — 使用 `alert()` 显示错误，而 redesign 其余页面统一使用 `CpToast.error()`。

**根因**：标签页开发较早，当时 `CpToast` 模块尚未就绪或开发者未意识到应使用统一组件。

**修复**：4 处 `alert()` 替换为 `CpToast.error()`。

**同类排查**：`grep -r "alert(" app/templates/redesign/` → 无其他 alert() 残留。

### D6: CSRF meta null check

**Bug 定位**：`tags.html` 行 249 — `document.querySelector('meta[name="csrf-token"]').content` 在 meta 标签不存在时抛出 `TypeError: Cannot read properties of null`。

**根因**：`_base.html` 中 meta 标签有条件渲染 `{% if csrf_token %}`，理论上 CSRF token 应始终存在，但防御性编码应处理边界情况。

**修复**：`var csrfMeta = document.querySelector(...); var csrfToken = csrfMeta ? csrfMeta.content : '';`

**同类排查**：`registration_review.html` 行 113 已正确使用 null check 模式。

[文档索引](../index.html) · [Markdown](2026-08-dashboard-ajax-path.md)

---

[← 文档索引（HTML）](../index.html) · [← 文档索引（Markdown）](../index.md)
