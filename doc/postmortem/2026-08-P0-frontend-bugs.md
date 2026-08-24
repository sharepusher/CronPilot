# 复盘：P0 前端+后端关键问题修复（P0-1/P0-2/P0-3/P0-4）

> HTML 版：[2026-08-P0-frontend-bugs.html](2026-08-P0-frontend-bugs.html) · [文档索引](../index.html) · [索引 Markdown](../index.md)

# 复盘：P0-1 / P0-2 / P0-3 / P0-4 前端+后端关键问题修复

|  |  |
| --- | --- |
| 日期 | 2026-08-24 |
| 发现方式 | Code Review（全面前后端代码审计） |
| 严重级别 | P0（影响核心交互功能 / 安全漏洞 / 安全信息泄露） |
| 涉及文件 | `task_detail.html`、`task_form.html`、`app/main/views.py`、`app/rbac/views.py`、`app/rbac/safe_redirect.py` |

## P0-1：CpConfirm.show() 参数名错误

### 1. Bug 定位

`app/templates/redesign/task_detail.html` 第 153 行和第 186 行，`CpConfirm.show()` 调用传入 `message:` 属性，但 `redesign-confirm.js:31` 的 API 仅识别 `body:` 属性。结果：确认对话框的正文区域渲染为空白。

### 2. 根因

`task_detail.html` 与 `dashboard.html` 独立开发，实现相同功能（任务操作确认对话框）。`dashboard.html` 正确参考了 `redesign-confirm.js` API 签名（使用 `body:`），而 `task_detail.html` 依赖了常见 UI 库惯例（SweetAlert、Element UI 等使用 `message`），未交叉验证项目自有 API。JavaScript 对未知属性完全静默（`opts.message` 被赋值但从不被读取），无任何开发时警告。

### 3. 测试漏洞

项目无前端 JS API 调用的自动化检查。现有单测覆盖后端逻辑（Python），但不覆盖前端模板中 JS API 调用的参数正确性。手动验收时可能因任务详情页功能不完整（seed admin 无 `cron:write` 权限看不到操作按钮）而跳过该路径。

### 4. 修复

2 处 `message:` → `body:` 纯字符串替换。

### 5. 防护测试

CDP 验证：`Runtime.evaluate` 检查页面 script 标签中 `CpConfirm.show` 调用仅包含 `body:`，不包含 `message:`。结果：`{"hasMessage":false,"hasBody":true}`。

### 6. 同类排查

| 文件 | CpConfirm 调用数 | 使用的参数 | 状态 |
| --- | --- | --- | --- |
| `dashboard.html` | 3 | `body:` | 正确 |
| `users.html` | 1 | `body:` | 正确 |
| `tags.html` | 1 | `body:` | 正确 |
| `api_token.html` | 1 | `body:` | 正确 |
| `task_detail.html` | 2 | `message:` → `body:` | 已修复 |

仅 `task_detail.html` 存在此问题。

### 7. 预防方案

| 措施 | 落地位置 | 验证命令 |
| --- | --- | --- |
| 在 `AGENTS.md` 新增规范：调用 `CpConfirm.show()` 时必须使用 `body:` 而非 `message:` | `AGENTS.md` | `grep "CpConfirm" AGENTS.md` |
| 新增 CI grep 检查：`grep -rn "CpConfirm.show" app/templates/ | grep "message:" && exit 1 || echo OK` | `scripts/` 或 CI workflow | `grep -rn "CpConfirm.show" app/templates/ | grep "message:" && echo FAIL || echo OK` |

---

## P0-4：Escape 键守卫选择器错误

### 1. Bug 定位

`app/templates/redesign/task_detail.html:237` 和 `task_form.html:339`，Escape 键处理器使用 `document.querySelector('.cp-confirm-overlay[style*="flex"]')` 检查对话框是否打开。`.cp-confirm-overlay` 这个 class 在整个项目中从未定义或创建，实际 class 为 `.cp-modal-overlay`。

### 2. 根因

在 redesign 组件开发过程中，确认对话框的 overlay class 名从概念名 `.cp-confirm-overlay` 演进为通用的 `.cp-modal-overlay`（因为 CpConfirm 和 CpModal 共用同一套 overlay 结构）。编写 `task_detail.html` 和 `task_form.html` 的 Escape 守卫时，使用了假设的旧名，未通过 `grep` 验证该 class 是否在 CSS 或 JS 中实际存在。此外 `[style*="flex"]` 属性选择器有双重问题：即使 class 名正确，CSS 定义的 `display: flex` 不会出现在 DOM 的 inline style 中。

### 3. 测试漏洞

无自动化检查：① 模板中 `querySelector` 引用的 CSS class 是否在项目中有定义；② Escape 键在对话框打开/关闭两种状态下的行为端到端测试。

### 4. 修复

两处选择器修正为 `.cp-modal-overlay`，去掉不可靠的 `[style*="flex"]`（因为 overlay 元素在创建时 `appendChild` 到 DOM，关闭时 `removeChild` 移除，只需检查元素是否存在即可）。

### 5. 防护测试

CDP 验证：`Runtime.evaluate` 检查页面 script 标签中 Escape handler 使用 `cp-modal-overlay`（正确）且不包含 `cp-confirm-overlay`（错误）。结果：`{"hasOldSelector":false,"hasNewSelector":true}`。

### 6. 同类排查

```
grep -rn "cp-confirm-overlay" app/templates/redesign/  → 无匹配（修复后）
grep -rn "cp-modal-overlay" app/templates/redesign/     → 仅 task_detail.html:237, task_form.html:339（正确引用）
```

全仓库已无 `.cp-confirm-overlay` 的任何引用。

### 7. 预防方案

| 措施 | 落地位置 | 验证命令 |
| --- | --- | --- |
| 新增 CI grep 检查：禁止引用 `.cp-confirm-overlay`（不存在的 class） | `scripts/` 或 CI workflow | `grep -rn "cp-confirm-overlay" app/templates/ && echo FAIL || echo OK` |
| 在 `AGENTS.md` 新增规范：模板中 `querySelector` 引用的 CSS class 必须先 `grep` 确认在 CSS/JS 中有定义 | `AGENTS.md` | `grep "querySelector" AGENTS.md` |

---

## P0-2：开放重定向修复 (Open Redirect)

### 1. Bug 定位

登录页 `next` 参数未做校验，3 处调用点直接将用户提供的 `next` 值用于重定向目标：

- `app/rbac/views.py:189` — GET 渲染登录页时 `request.args.get('next', '/cron_list')` 原样传入模板
- `app/rbac/views.py:194` — POST 登录成功后 `request.values.get('next', '/cron_list')` 用作 `redirect()` 目标
- `app/main/views.py:1203` — 未登录拦截重定向时 `request.args.get('next', '')` 拼入 `/rbac/login?next=`

攻击向量：`https://example.com/rbac/login?next=https://evil.com/steal` → 用户登录后被自动重定向到钓鱼站点。

### 2. 根因

Flask 原生 `redirect()` 不对目标 URL 做安全校验（仅生成 302 响应）。项目在引入 `next` 参数时直接信任用户输入，未引入白名单或同域校验。这是 Web 安全领域的经典漏洞（CWE-601），但因项目最初面向内网使用，开发阶段未将其纳入安全审计范围。

### 3. 测试漏洞

现有测试仅覆盖登录成功/失败的业务逻辑，未测试 `next` 参数的安全性。无集成测试验证"登录后重定向目标是否为安全的相对路径"。`verify_golden_path.sh` 的登录流程使用固定 `next=/cron_list`，不覆盖恶意输入。

### 4. 修复

新增 `app/rbac/safe_redirect.py` → `safe_next_url(next_url, default='/cron_list')` 函数：

- 拒绝有 `scheme` 的 URL（`http://`、`https://`、`javascript:`、`data:` 等）
- 拒绝有 `netloc` 的 URL（`//evil.com` 协议相对 URL）
- 拒绝以 `//` 开头的字符串（双重保险）
- 空值返回 `default`（`/cron_list`）

3 处调用点全部包裹 `safe_next_url()`。

### 5. 防护测试

`tests/test_safe_redirect.py` — 11 条单元测试：

| 类别 | 测试数 | 覆盖场景 |
| --- | --- | --- |
| 安全相对路径（应放行） | 3 | `/cron_list`、`/cron_list?page=2`、`/rbac/users` |
| 恶意目标（应拒绝） | 5 | `http://evil.com`、`https://evil.com`、`//evil.com`、`javascript:alert(1)`、`data:text/html,...` |
| 边界情况 | 3 | 空字符串、`None`、自定义 default |

端到端验证：`curl "http://127.0.0.1:5001/rbac/login" -X POST -d "username=admin&password=changeme&next=https://evil.com/steal"` → 302 重定向到 `/cron_list`（安全默认值），非 `https://evil.com`。

### 6. 同类排查

```
grep -rn "request\.\(args\|values\|form\)\.get('next" app/  → 仅 3 处，全部已包裹 safe_next_url()
grep -rn "redirect(" app/main/views.py app/rbac/views.py  → 其他 redirect 调用使用硬编码路径或 url_for()，无开放重定向风险
```

### 7. 预防方案

| 措施 | 落地位置 | 验证命令 |
| --- | --- | --- |
| 新增 `safe_next_url()` 工具函数，所有 `next` 参数必须经过此函数校验 | `app/rbac/safe_redirect.py` | `python3 -m unittest tests.test_safe_redirect -v` |
| 在 `AGENTS.md` 新增规范：所有 `request.args.get('next')` 必须经 `safe_next_url()` 包裹 | `AGENTS.md` | `grep "safe_next_url" AGENTS.md` |
| CI grep 检查：裸用 `request.*.get('next')` 而未包裹 `safe_next_url` 应告警 | `scripts/` 或 CI workflow | `grep -rn "request\.\(args\|values\)\.get('next" app/ | grep -v safe_next_url && echo FAIL || echo OK` |

---

## P0-3：异常文本泄露修复

### 1. Bug 定位

`app/main/views.py:901`，`cron_add` 的 `except Exception` 分支中 `web_api_return(code=1, msg=str(e))` 将 Python 异常原始文本（可含数据库引擎/表名/内网 IP/文件路径）直接返回给前端 Ajax 响应。

### 2. 根因

开发阶段为调试便利，将异常信息直接返回前端。转向生产时未清理。同一 catch 块中的 `wechat_info_err(str(e), trace_info)` 是合理的服务端告警行为，开发者在此基础上顺手复用 `str(e)` 作为前端错误信息 — 将"服务端日志内容"和"用户可见内容"混为一体。其他路由（`rbac/views.py`、`crons.py`）的异常处理均未将 `str(e)` 返回前端，说明这是孤立的遗留问题而非系统性模式。

### 3. 测试漏洞

现有测试关注正常流程（添加成功）和业务校验（字段缺失），未覆盖"构造异常触发 catch-all"的场景。无规范要求审查 `web_api_return` 的 `msg` 参数是否包含敏感信息。

### 4. 修复

将 `msg=str(e)` 替换为通用错误信息 `msg='服务器内部错误，请稍后重试'`。新增 `current_app.logger.error` 确保异常详情不丢失（写入服务端日志文件）。微信告警保持不变。

### 5. 防护测试

`grep -n "msg=str(e)" app/main/views.py app/rbac/views.py` → 无匹配，确认修复完成。restart 后 `curl` 确认 HTTP 200 正常。

### 6. 同类排查

全仓库搜索 `msg=str(e)`：仅此 1 处。`crons.py` 中的 `str(e)` 用于服务端日志和微信推送（不返回 HTTP 响应），不存在同类问题。`rbac/views.py` 无 `str(e)` 返回前端。

### 7. 预防方案

| 措施 | 落地位置 | 验证命令 |
| --- | --- | --- |
| 在 `AGENTS.md` 新增规范：禁止 `web_api_return(msg=str(e))`，catch-all 必须返回通用错误信息 | `AGENTS.md` | `grep "msg=str" AGENTS.md` |
| CI grep 检查：`grep -rn "web_api_return.*msg=str(e)" app/ && echo FAIL || echo OK` | `scripts/` 或 CI workflow | `grep -rn "msg=str(e)" app/main/views.py app/rbac/views.py && echo FAIL || echo OK` |

[文档索引](index.html) · [Markdown](2026-08-P0-frontend-bugs.md)

---

[← 文档索引（HTML）](../index.html) · [← 文档索引（Markdown）](../index.md)
