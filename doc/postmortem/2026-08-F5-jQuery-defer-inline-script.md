# 复盘：F5 jQuery defer 导致 inline script 失效

> HTML 版：[2026-08-F5-jQuery-defer-inline-script.html](2026-08-F5-jQuery-defer-inline-script.html) · [文档索引](../index.html) · [索引 Markdown](../index.md)

# 复盘：F5 jQuery defer 导致 inline script 失效

**日期**：2026-08-24  
**触发**：F5 common.js 精简后，API Token 页面复制/重置按钮失效  
**严重程度**：P0（功能不可用）  
**修复时间**：<5 分钟

## 1. Bug 定位

`app/templates/redesign/api_token.html` 的 `{% block js %}` 内联脚本：

```
<script>
$(function() {         // ← 此处 $ 为 undefined
    $('#tk-copy-btn').on('click', function() { ... });
    $('#tk-reset-btn').on('click', function() { ... });
});
</script>
```

当 `jquery.js` 带 `defer` 属性时，inline script 在 HTML 解析过程中立即执行，而 jQuery 延迟到解析完毕后才执行。导致 `$` 未定义 → 所有按钮事件绑定失败。

## 2. 根因分析

**直接原因**：F5 变更保留了 Phase R5 添加的 `defer` 属性在 `jquery.js` 上。

**深层原因**：Phase R5 性能优化时对 `defer` 语义理解不完整——`defer` 仅适用于不被 inline script 直接依赖的库。jQuery 作为 inline script 的基础依赖，不应 defer。

**为什么之前未暴露**：Phase R5 之后存在 `<script>var GV={...}</script>` inline 块在 jQuery 之前，可能在某些浏览器/缓存条件下改变了解析时序。F5 移除该行后，时序竞争变得确定性，问题 100% 复现。

## 3. 测试漏洞

| 现有测试 | 能否拦截 | 原因 |
| --- | --- | --- |
| `test_ajax_form_guard` | 否 | 仅检查 HTML 结构，不涉及 JS runtime |
| curl 验证 | 否 | 只检查 HTTP 状态和静态 HTML |
| 手动浏览器验证 | 是 | 需打开 DevTools console 查看 ReferenceError |

## 4. 修复

`app/templates/redesign/_base.html`：移除 `jquery.js` 的 `defer` 属性。

```
-  <script defer src="jquery.js"></script>
+  <script src="jquery.js"></script>
```

其他 Redesign 模块（common-redesign, shell, theme, toast, confirm）保持 `defer`，因为它们仅通过 DOM ready 回调或用户交互事件访问。

## 5. 防护测试

CI 门禁命令：

```
grep 'defer.*jquery\|jquery.*defer' app/templates/redesign/_base.html && echo "FAIL: jQuery must not be deferred" && exit 1 || echo "OK"
```

## 6. 同类排查

| 模板 | inline JS 中的 $ 使用 | 是否安全 |
| --- | --- | --- |
| api\_token.html | `$(function(){...})` | ✓ jQuery 同步加载 |
| change\_password.html | `$(function(){...})` | ✓ |
| user\_profile.html | `$(function(){...})` | ✓ |
| users.html | `$(function(){...})` | ✓ |
| registration\_review.html | `$(function(){...})` | ✓ |
| dashboard.html | `$.post` 在用户交互 handler 内 | ✓ |
| tags.html | `$.ajax` 在 click handler 内 | ✓ |

## 7. 预防方案

| 措施 | 落地位置 | 验证命令 |
| --- | --- | --- |
| CI 门禁：禁止 jquery.js 使用 defer | `scripts/check_ui_contract.py` 或 CI yaml | `grep 'defer.*jquery' app/templates/redesign/_base.html && exit 1` |
| 规范：jQuery 同步加载约束写入 AGENTS.md | `AGENTS.md` "JS 依赖" 节 | grep "jQuery.\*同步\|jQuery.\*sync" AGENTS.md |
| 设计文档增加 defer 使用规则 | `doc/design/F5-common-js精简设计.html` | 文档审阅 |

**核心规则**：凡被 inline `<script>` 直接依赖的外部库（如 jQuery），**禁止使用 `defer`**。`defer` 仅适用于通过 DOM ready 回调或事件 handler 间接引用的模块。

[文档索引](index.html) · [Markdown](2026-08-F5-jQuery-defer-inline-script.md) · [索引](index.html)

---

[← 文档索引（HTML）](../index.html) · [← 文档索引（Markdown）](../index.md)
