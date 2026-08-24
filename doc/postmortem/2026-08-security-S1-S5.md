# 复盘：安全问题 S1–S5 修复

> HTML 版：[2026-08-security-S1-S5.html](2026-08-security-S1-S5.html) · [文档索引](../index.html) · [索引 Markdown](../index.md)

# 复盘：安全问题 S1–S5 修复

|  |  |
| --- | --- |
| 日期 | 2026-08-24 |
| 发现方式 | 全面前后端代码审计（Code Review） |
| 严重级别 | P1 安全（5 个问题） |
| 修复状态 | S1–S5 全部已修复 |

## S5：API 装饰器 catch-all 异常文本泄露

### 1. Bug 定位

`app/decorated.py:32-34`，`api_deal_return` 装饰器的 `except Exception` 分支中 `return api_return(errcode=1, errmsg=str(e))` 将 Python 异常原始文本返回给 API 调用方。当前仅 `app/api/views.py:585` 的 `crons_legacy`（`/api/cron/add` 旧路径兼容层）使用此装饰器。

### 2. 根因

与 P0-3 完全同源。`decorated.py` 是上游 `xiaoniu_cron` 的遗留代码，在开发阶段将异常信息直接返回便于调试。P0-3 修复时执行 `grep "msg=str(e)" app/main/views.py app/rbac/views.py`，搜索范围限于管理端视图层，未扩展到 API 装饰器层。**根因行为层**：修复搜索时按"已知受影响文件"而非"全仓库相同模式"搜索，导致同源问题遗漏。

### 3. 测试漏洞

P0-3 的修复验证命令 `grep -rn "msg=str(e)" app/main/views.py app/rbac/views.py` 路径限定为两个文件，未覆盖 `decorated.py`。P0-3 复盘中提出的 CI grep 检查也仅覆盖了 `web_api_return`（管理端），未覆盖 `api_return`（API 层）。

### 4. 修复

将 `str(e)` 替换为通用错误信息 `'服务器内部错误'`。新增 `logging.getLogger(__name__).error()` 并设置 `exc_info=True` 确保完整堆栈写入日志。

### 5. 防护测试

```
# 全仓库搜索：确认无 str(e) 返回客户端
grep -rn "errmsg=.*str(e)\|msg=str(e)" app/ | grep -v "logger\|logging\|wechat"
# → 无匹配

# decorated.py 专项
grep -n "str(e)" app/decorated.py
# → 无匹配
```

### 6. 同类排查

P0-3（`main/views.py`）已修复。全仓库搜索 `str(e)` 出现在客户端响应构造中的情况：

```
grep -rn "str(e)" app/ | grep -v "logger\|logging\|wechat\|#\|'''" → 无匹配（所有 str(e) 仅用于日志/告警）
```

### 7. 预防方案

| 措施 | 落地位置 | 验证命令 |
| --- | --- | --- |
| **扩大 CI grep 搜索范围**：异常脱敏检查覆盖整个 `app/` 目录，包括 `api_return` 和 `web_api_return` 两套返回函数 | `AGENTS.md` "异常信息脱敏" 规范 | `grep -rn "errmsg=.*str(e)\|msg=str(e)" app/ | grep -v "logger\|logging" && echo FAIL || echo OK` |
| 更新 AGENTS.md 异常脱敏规范的自检命令，将搜索路径从 `app/main/views.py app/rbac/views.py` 扩展为 `app/` | `AGENTS.md` | `grep "app/" AGENTS.md | grep "str(e)"` |

---

## S3：标签 CRUD 缺 scope 校验

### 1. Bug 定位

`app/rbac/views.py` 的 `tag_create`（L1176）、`tag_update`（L1194）、`tag_rename`（L1206）、`tag_tasks`（L1217）、`tag_delete`（L1232）— 仅有 `@require_permission('user:manage')` 权限检查，无 scope 层面校验。按组管理员可越权操作其他组或全局标签。

### 2. 根因

标签系统在用户管理/组管理之后开发。开发时 **UI 层面用前端 JS 控制了 `group_id` 下拉选项**（只展示用户所属组），误以为前端限制等于安全防护。同期的组管理路由（`groups_edit` L913）已有 `_actor_bypasses_scope()` 检查，但标签路由开发时未对齐该模式。**根因行为层**：新功能开发时未执行"策略变更影响分析"中的"全路径枚举"步骤，遗漏了与已有安全模式的对齐。

### 3. 测试漏洞

现有标签测试覆盖 CRUD 正常流程（管理员），不覆盖"按组管理员越权操作其他组标签"的负面场景。无集成测试以 Biz Admin 身份 POST 篡改 `group_id`。

### 4. 修复

新增 `_check_tag_group_id_scope(group_id)` 和 `_check_tag_scope(tag)` 辅助函数。5 个标签路由全部加入 scope 校验：

- `tag_create`：校验 `group_id` 在 `session['group_ids']` 中；拒绝全局标签（`group_id=None`）
- `tag_update` / `tag_rename` / `tag_delete`：先查标签归属组，校验在操作者 scope 内
- `tag_tasks`：读取也需 scope 限制，防止信息泄露

### 5. 防护测试

`tests/test_tag_scope.py` — 9 条单元测试：

| 类别 | 测试数 | 覆盖场景 |
| --- | --- | --- |
| 自组操作（应放行） | 3 | create/update/delete 自组标签 |
| 他组操作（应拦截） | 4 | create/update/delete/tasks 他组标签 |
| 全局操作（应拦截） | 2 | create/update 全局标签 |

### 6. 同类排查

搜索所有使用 `@require_permission` 但无 `_actor_bypasses_scope()` 的路由：

- 用户管理路由（`users/groups/audit`）— 已有 scope 检查
- 任务相关路由（`cron_add/edit/update_status`）— 通过 `build_scope_filter_clause` 过滤
- 标签路由 — **唯一缺失**，已修复

### 7. 预防方案

| 措施 | 落地位置 | 验证命令 |
| --- | --- | --- |
| 新增 scope 校验函数 + 9 条覆盖测试 | `app/rbac/views.py` + `tests/test_tag_scope.py` | `.venv-py311/bin/python -m unittest tests.test_tag_scope -v` |
| 在 `AGENTS.md` "策略变更影响分析" 中追加示例：新功能路由必须对齐已有 scope 校验模式 | `AGENTS.md` | `grep "scope" AGENTS.md | grep -i "标签\|tag"` |

---

## S4：存储型 XSS（data-\* → innerHTML 链路）

### 1. Bug 定位

多个模板中 `data-*` 属性取值后直接拼入 `innerHTML` / `bodyHtml`：

| 文件 | 行号 | 问题 |
| --- | --- | --- |
| `registration_review.html` | 139, 153 | `username` 拼入 `CpModal bodyHtml` |
| `tags.html` | 334, 339, 424, 432, 449 | `tagName` / `task.name` / `tag_name` 拼入 `CpModal title/bodyHtml` |
| `task_form.html` | 247 | `addTag()` 用 `innerHTML` 拼标签名 |

### 2. 根因

开发者信任 Jinja2 自动转义提供完整 XSS 防护。模板层确实安全——`{{ req.username }}` 在 `data-username` 属性中被转义为 `&lt;` 等。但 HTML entity 编解码存在链路不对称：

1. Jinja2 转义保护 **HTML 解析阶段**（防止属性值跳出引号）
2. 浏览器解析 HTML 时**解码** entities → DOM 属性值为原始字符串
3. jQuery `.data()` 返回解码后的值
4. 拼入 `bodyHtml` → `innerHTML` → **脚本执行**

**根因行为层**：将"Jinja2 自动转义"等同于"全链路 XSS 防护"，忽略了 JS 层的 innerHTML 二次注入风险。同一项目的 `register.html` 已正确使用 `escHtml()`，但未形成团队规范。

### 3. 测试漏洞

无前端 XSS 自动化测试。手动验收时使用正常字符的用户名/标签名，不覆盖特殊字符输入。现有后端测试不覆盖 JS 层行为。

### 4. 修复

- `registration_review.html`：新增 `escHtml()` 函数，2 处 `username` 拼接加 `escHtml()`
- `tags.html`：新增 `escHtml()` 函数，5 处 `tagName` / `task.name` 拼接加 `escHtml()`
- `task_form.html`：`addTag()` 的 `innerHTML` 改为 `textContent` + DOM API 创建 `<button>`

### 5. 防护测试

```
# 全模板 innerHTML 扫描
rg -n "innerHTML\s*=" app/templates/redesign/
# → 仅 task_form.html:275（清空 innerHTML=''）和 register.html:478（已用 escHtml）

# data-* 取值后拼 HTML 扫描
rg -n "\.data\(|dataset\." app/templates/redesign/ | grep -v escHtml | grep -v textContent | grep -v "\.id\b"
# → 无高风险残留
```

### 6. 同类排查

全仓库搜索 `innerHTML` 赋值 + `data-*`/`dataset` 取值拼接：修复后仅剩安全用法（`innerHTML = ''` 清空 / `escHtml()` 包裹 / `textContent` 替代）。`register.html` 在项目初期已正确使用 `escHtml`，未推广到其他模板。

### 7. 预防方案

| 措施 | 落地位置 | 验证命令 |
| --- | --- | --- |
| 在 `AGENTS.md` 新增规范：模板 JS 中凡从 `data-*` / `dataset` 取值后拼入 `innerHTML` / `bodyHtml`，必须经 `escHtml()` 转义或改用 `textContent` | `AGENTS.md` | `grep "escHtml\|innerHTML" AGENTS.md` |
| CI 扫描：`rg "innerHTML\s*=(?!.*escHtml)" app/templates/redesign/` 检查是否有未转义的 innerHTML 赋值 | CI workflow | `rg -n "innerHTML\s*=" app/templates/redesign/ | grep -v "= ''" | grep -v escHtml && echo WARN || echo OK` |

---

## S1+S2：登出 CSRF + 遗留路由清理

### 1. Bug 定位

`app/rbac/views.py` L247：`@rbac.route('/logout', methods=['GET', 'POST'])` — 登出接受 GET 请求。攻击者可构造 `<img src="/rbac/logout">` 使已登录用户被强制登出。

遗留路由 `app/main/views.py`：`/logout`（L1209）直接 `session.clear()`；`/check_pass`（L1201）接受 `safe_next_url` 参数但实质是登录重定向。

前端引用：`app/templates/redesign/_topbar.html` L61 — `<a href="/rbac/logout">` 直接 GET 链接；`app/static/js/common.js` L854 — Command Palette 搜索结果中 "退出登录" 使用 GET 导航。

### 2. 根因

登出功能在 RBAC 系统初始开发时沿用上游 `xiaoniu_cron` 的 GET 登出模式。上游系统为内网工具，不考虑 CSRF 攻击面。RBAC 改造时添加了 CSRF 保护中间件和 `@csrf_protect` 装饰器，但 `@csrf_protect` 在 GET 请求时不校验 CSRF token（这是正确行为——GET 应该是幂等的），而登出不是幂等操作。**根因行为层**：`@csrf_protect` 的存在创造了"CSRF 已防护"的假象，但它只保护 POST，而登出同时接受 GET。

### 3. 测试漏洞

无测试覆盖 "GET /rbac/logout 应返回 405" 的负面场景。现有登出测试仅验证 POST 成功后 session 清除，不验证 GET 被拒绝。

### 4. 修复

- **后端**：`/rbac/logout` 改为 `methods=['POST']`（GET → 405）
- **Redesign 前端**：`_topbar.html` 登出链接改为 `<a id="cp-logout-btn">` + 隐藏 `<form method="POST">`（含 CSRF token）；`redesign-shell.js` 新增 click handler 提交表单
- **v1 前端**：`common.js` Command Palette 的 "退出登录" 标记为 `post: true`；新增 `postNavigate()` 函数动态创建 POST 表单（含 CSRF meta token）
- **遗留路由**：`/logout` 和 `/check_pass` 不再清除 session，仅重定向到 `/rbac/login`
- `decorated.py` 中死代码 `login_required` 的 `/check_pass` 引用改为 `/rbac/login`

### 5. 防护测试

`tests/test_logout_csrf.py` — 4 条单元测试：

| 测试 | 断言 |
| --- | --- |
| `test_get_logout_returns_405` | GET /rbac/logout → 405 |
| `test_post_logout_redirects` | POST /rbac/logout → 302 + session 清除 |
| `test_legacy_logout_redirects_to_login` | GET /logout → 302 → /rbac/login |
| `test_legacy_check_pass_redirects_to_login` | GET /check\_pass → 302 → /rbac/login |

### 6. 同类排查

搜索所有状态修改操作仍使用 GET 的路由：

```
grep -n "methods=\['GET'\]" app/rbac/views.py | grep -v "login\|password\|register\|complete_profile"
# → 无其他状态修改操作使用纯 GET
```

v1 topbar（`rbac/_topbar.html`）已使用 POST form，无需修改。`change_password.html`、`complete_profile.html` 的登出按钮已使用 POST form。

### 7. 预防方案

| 措施 | 落地位置 | 验证命令 |
| --- | --- | --- |
| 新增规范：状态修改操作（登出、删除、修改等）必须使用 POST + CSRF，禁止 GET | `AGENTS.md` | `grep "POST.*CSRF\|登出.*POST" AGENTS.md` |
| 4 条单元测试持续回归 | `tests/test_logout_csrf.py` | `.venv-py311/bin/python -m unittest tests.test_logout_csrf -v` |

---

## C1+X1+X2：Cookie SameSite 一致性 + XSS 防御深度

### 1. Bug 定位

- **C1**：`redesign-theme.js:17`、`redesign-shell.js:20`、`_topbar.html:56` — cookie 写入缺 `samesite=lax`
- **X1**：`tags.html:420` — `r.errmsg` 未经 `escHtml()` 直接拼入 modal bodyHtml
- **X2**：`redesign-confirm.js:115,118` — `CpModal` 的 `confirmText`/`cancelText` 通过 `innerHTML` 拼接

### 2. 根因

**C1**：Redesign JS 模块独立开发，未对齐 `common.js` 已有的 `samesite=lax` 写法。**X1/X2**：与 S4 同源，S4 修复时搜索范围覆盖 `data-*` → `innerHTML` 链路，但 `r.errmsg`（AJAX 响应 → innerHTML）和 `opts.confirmText`（函数参数 → innerHTML）属于不同输入路径，未被 S4 修复搜索覆盖。

### 3. 测试漏洞

无自动化检查 cookie 属性一致性。S4 的 innerHTML 扫描命令 `rg "innerHTML\s*=" app/templates/redesign/` 覆盖模板但不覆盖 JS 模块文件。

### 4. 修复

- **C1**：3 处 cookie 写入追加 `;samesite=lax`
- **X1**：`r.errmsg` 包裹 `escHtml()`
- **X2**：`CpModal` footer 改为 DOM API（`createElement` + `textContent`），不再使用 innerHTML 拼接

### 5. 防护测试

```
rg "samesite" app/static/js/redesign-theme.js app/static/js/redesign-shell.js app/templates/redesign/_topbar.html
# → 3 处均已包含 samesite=lax

rg "escHtml.*errmsg" app/templates/redesign/tags.html
# → 确认 escHtml 包裹

rg "textContent.*Text" app/static/js/redesign-confirm.js
# → 确认 cancelText/confirmText 使用 textContent
```

### 6. 同类排查

Cookie：`rg "document\.cookie" app/static/js/ app/templates/` — 所有写入点均已包含 `samesite=lax`。innerHTML：S4 已修复模板中 `data-*` → innerHTML 链路；X1/X2 覆盖了剩余的 AJAX 响应 → innerHTML 和函数参数 → innerHTML 路径。

### 7. 预防方案

| 措施 | 落地位置 | 验证命令 |
| --- | --- | --- |
| 新增规范：cookie 写入必须包含 `samesite=lax` | `AGENTS.md` | `rg "document\.cookie\s*=" app/static/js/ app/templates/ | grep -v "samesite" && echo WARN || echo OK` |

[文档索引](index.html) · [Markdown](2026-08-security-S1-S5.md)

---

[← 文档索引（HTML）](../index.html) · [← 文档索引（Markdown）](../index.md)
