# 复盘：change_password.html 嵌套 form 导致退出登录失效

> HTML 版：[2026-08-change-password-nested-form.html](2026-08-change-password-nested-form.html) · [文档索引](../index.html) · [索引 Markdown](../index.md)

# 复盘：change\_password.html 嵌套 form 导致退出登录失效

P1 发现于 2026-08 UI 重构全面 Review

## 1. Bug 定位

`app/templates/redesign/change_password.html` L56-59（修复前）。当 `force_reset=True`（管理员重置密码后用户首次登录）时，退出登录的 `<form method="post">` 嵌套在外层密码修改的 `<form class="js-ajax-form">` 内部。

```
<form method="post" class="js-ajax-form" action="/rbac/password">
  ...
  <div class="pw-actions">
    <button type="submit" class="btn-c btn-accent js-ajax-submit">保存</button>
    <!-- ❌ 嵌套 form -->
    <form method="post" action="/rbac/logout" style="display:inline">
      <button type="submit">退出登录</button>
    </form>
  </div>
</form>
```

## 2. 根因

重构时将退出登录功能从 `<a>` 链接改为 POST `<form>`（出于 CSRF 安全考虑），但直接放在了密码表单的 `<div class="pw-actions">` 内部，未意识到此位置仍在外层 `<form>` 作用域内。HTML5 规范（§4.10.3）明确禁止 form 嵌套，浏览器会忽略内层 `<form>` 开标签，导致内层 submit 按钮实际触发外层表单提交。

## 3. 测试漏洞

现有测试覆盖了密码修改的 Ajax 提交成功路径，但未覆盖 `force_reset=True` 场景下退出登录按钮的点击行为。单元测试不涉及 HTML 结构合规性验证，无静态门禁能发现嵌套 form。

## 4. 修复

- 将嵌套 `<form>` 替换为 `<button type="button" id="pw-logout-btn">`
- 在 JS 块中通过动态创建 form + `form.submit()` 实现 POST 退出登录
- 使用原生 `form.submit()` 绕过 jQuery 事件链，避免被全局守卫拦截
- 去除了 `style="display:inline"` 内联样式

## 5. 防护测试

自检命令：

```
rg -c '<form' app/templates/redesign/*.html | awk -F: '$2 > 1 {print "CHECK:", $1, "has", $2, "forms"}'
```

多 form 文件需人工确认是否为平级关系（如 `complete_profile.html`）或 JS 动态创建（如 `users.html`）。

## 6. 同类排查

| 文件 | Form 数 | 结论 |
| --- | --- | --- |
| `complete_profile.html` | 2 | 平级（L159-217 和 L219-222），合规 |
| `users.html` | 1 HTML + JS 动态 | JS `$('<form...')` append 到 body，非嵌套 |
| 其他 redesign 模板 | 0-1 | 均为单 form 或无 form，无同类问题 |

## 7. 预防方案

| 措施 | 落地位置 | 验证命令 |
| --- | --- | --- |
| AGENTS.md 追加「禁止 form 嵌套」规范条目 | `AGENTS.md`「表单交互变更影响分析」节 | `grep '禁止 form 嵌套' AGENTS.md` |
| 自检命令纳入交付闭环 | 本复盘文档 §5 | `rg -c '<form' app/templates/redesign/*.html` |

[Markdown 版](2026-08-change-password-nested-form.md) · [文档索引](../index.html)

---

[← 文档索引（HTML）](../index.html) · [← 文档索引（Markdown）](../index.md)
