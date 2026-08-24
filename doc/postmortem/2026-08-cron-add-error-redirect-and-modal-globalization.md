# 复盘：cron_add 错误重定向 + CpModal 全局化 — 2026-08

> HTML 版：[2026-08-cron-add-error-redirect-and-modal-globalization.html](2026-08-cron-add-error-redirect-and-modal-globalization.html) · [文档索引](../index.html) · [索引 Markdown](../index.md)

# 复盘：cron\_add 错误重定向 & CpModal 全局化 — 2026-08

**触发来源**：用户报告 Bug + 自查发现同类问题

**涉及功能**：任务创建表单 (`cron_add`) + 注册审批弹窗 (`registration_review`)

---

## BUG-1：cron\_add 异常时立即跳转到任务列表

### 1 · Bug 定位

|  |  |
| --- | --- |
| 位置 | `app/main/views.py`，第 898–901 行，`cron_add` POST 处理器的 except 分支 |
| 现象 | 用户填写任务新建表单后提交，若服务端发生异常（如 DB 写入失败、tag 解析异常等），页面立即跳转到 `/cron_list`，用户失去所有填写内容，无法看到具体错误原因 |
| 复现 | 触发任意服务端异常（如构造非法 cron 表达式绕过前端校验）后观察页面跳转行为 |

### 2 · 根因

```
# app/main/views.py 原始代码（已修复）
except Exception as e:
    trace_info = traceback.format_exc()
    wechat_info_err(str(e), trace_info)
    return web_api_return(code=1, msg=str(e), url='/cron_list')  # ← 错误：含 url 字段

# app/static/js/common.js js-ajax-form 的 success 回调（第 187-189 行）：
if (data.url) {
    window.location.href = data.url;   # ← 无论 errcode 是否为 1，只要有 url 就跳转
}
```

**行为层根因**：

- `common.js` 的 `js-ajax-form` success 回调在有 `data.url` 时**无条件重定向**，不检查 `errcode`
- 正常验证错误（code=1，无 url）会在按钮旁显示短暂提示然后消失，行为符合预期
- 但异常分支（except）写了 `url='/cron_list'` ——这是从正常成功路径（code=0）复制时带入的参数，未意识到 url 会触发无条件跳转

### 3 · 测试漏洞

|  |  |
| --- | --- |
| 现有测试 | `tests.test_p0_phase_a`、`tests.test_ajax_form_guard` 均未测试"服务端抛出异常时响应不含 url" |
| 漏洞根因 | 异常路径属于 happy-path 测试的盲区；AJAX 错误响应字段内容未纳入契约测试 |

### 4 · 修复

```
# 修复后（app/main/views.py 第 901 行）
return web_api_return(code=1, msg=str(e))  # 移除 url='/cron_list'
```

### 5 · 防护测试

在 `tests/test_ajax_form_guard.py` 中添加测试：`test_cron_add_error_response_has_no_url`

```
# 验证 cron_add POST 错误响应不含 url 字段（防止重定向）
def test_cron_add_error_response_has_no_url(self):
    # 触发服务端验证错误
    resp = self.client.post('/cron_add', data={'task_name': '', ...})
    data = json.loads(resp.data)
    self.assertEqual(data['errcode'], 1)
    self.assertNotIn('url', data, "错误响应不应含 url 字段（会触发 js-ajax-form 无条件跳转）")
```

### 6 · 同类排查

| 排查范围 | 结论 |
| --- | --- |
| `cron_edit` POST handler | 无 except 块，异常会 500 并由 Flask 全局错误处理器接管，不含 url ✓ |
| `update_status` 的 code=1 错误 | 包含 `url='/cron_list'`（第 991 行），但这是 task-not-found 的 GET/POST 双路由守卫，触发时用户不在表单上，重定向行为可接受 |
| 其他 code=1 含 url 的地方（L932/937/1026/1055） | 均在函数最开头（资源查找失败），非提交中的异常，重定向符合预期 |

### 7 · 预防方案

| 措施 | 落地位置 | 验证命令 |
| --- | --- | --- |
| 在 `AGENTS.md` 和 `cronpilot-project.mdc` 补充规范：**AJAX POST handler 的 except 分支，禁止在 code=1 错误响应中携带 url 字段** | `AGENTS.md`「AJAX 响应字段名规范」节 | `grep -n "url.*code=1\|code=1.*url=" app/main/views.py app/rbac/views.py`（应只返回已知合法的资源守卫场景） |
| 新增测试：`test_cron_add_error_response_has_no_url` | `tests/test_ajax_form_guard.py` | `.venv-py311/bin/python -m unittest tests.test_ajax_form_guard -v` |

---

## BUG-2：registration\_review.html Bootstrap modal 在 redesign shell 中不可见

### 1 · Bug 定位

|  |  |
| --- | --- |
| 位置 | `app/templates/redesign/registration_review.html`，第 81-129 行，2 个 Bootstrap modal div + Bootstrap JS 导入 |
| 现象 | 点击"通过"/"拒绝"按钮，弹窗要么透明、要么完全不显示（与 Z3 tags.html 事故同根因） |

### 2 · 根因

Redesign shell 的 CSS（`console-theme.css`、`redesign-components.css`）与 Bootstrap 的 modal z-index / positioning 策略冲突。Bootstrap modal 依赖 `position:fixed` 和特定的 `z-index` 层级，而 redesign 的 shell 容器改变了 stacking context，导致 modal 背景遮罩透明或内容区域定位错误。此问题在 Z3（tags.html）中已被识别，但 registration\_review.html 的迁移被推迟。

### 3 · 测试漏洞

|  |  |
| --- | --- |
| 漏洞 | 同类排查（Z3 postmortem）已标记此文件为"待修复"，但未被纳入任何自动化测试；CI 中无 Bootstrap modal 使用的检测门禁 |
| 修复后 | `grep "\.modal('show')\|bootstrap.min" app/templates/redesign/` 返回 0 结果，可纳入 CI |

### 4 · 修复

- 移除 `registration_review.html` 中所有 Bootstrap modal HTML（`#approveModal`、`#rejectModal`）及 CSS/JS 导入
- 迁移"批准"弹窗至 `CpModal()`（支持 HTML body，显示 username 加粗 + 停用警告）
- 迁移"拒绝"弹窗至 `CpModal()`（含 textarea 输入）
- 弹窗确认后通过 `submitForm()` 动态创建原生 form 提交（绕过 jQuery 事件链，避免守卫干扰）

### 5 · 同类排查 + CpModal 全局化

**根本改进**：将 `CpModal` 从 `tags.html` 的内联定义提取到 `redesign-confirm.js` 作为 `window.CpModal`，使所有 redesign 页面无需重复定义即可使用。

```
# 验证 CpModal 全局可用
browser_cdp: typeof window.CpModal  → "function"
browser_cdp: typeof window.CpConfirm  → "object"
```

`tags.html` 已同步更新：移除本地 `CpModal` 定义，更新按钮选择器（`.tg-m-confirm` → `.cp-modal-confirm-btn`）。

### 6 · 防护测试

| 测试 | 内容 |
| --- | --- |
| `grep "\.modal('show')\|bootstrap.min" app/templates/redesign/` | CI 门禁：返回非零 = CI 失败（现在已是 0 结果） |
| 12 个 sidebar 单测 | 全部通过，模板变更未影响权限回归 |

### 7 · 预防方案

| 措施 | 落地位置 | 验证命令 |
| --- | --- | --- |
| 将 Bootstrap modal 检测加入 CI 门禁（`check_ui_contract.py` 或新增 shell 检测步骤） | `.github/workflows/ui-contract.yml` 或 `scripts/check_ui_contract.py` | `grep -r "\.modal('show')\|bootstrap.min" app/templates/redesign/ && exit 1 || echo OK` |
| 规范更新：所有新增弹窗必须使用 `CpConfirm.show()`（简单确认）或 `CpModal()`（表单/HTML），全局可用无需重复定义 | `AGENTS.md`「Redesign 确认对话框规范」节 | — |

[文档索引](index.html) · [Markdown](2026-08-cron-add-error-redirect-and-modal-globalization.md) · [索引](index.html)

---

[← 文档索引（HTML）](../index.html) · [← 文档索引（Markdown）](../index.md)
