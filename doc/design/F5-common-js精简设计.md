# F5: common.js 精简 — 设计文档

> HTML 版：[F5-common-js精简设计.html](F5-common-js精简设计.html) · [文档索引](../index.html) · [索引 Markdown](../index.md)

# F5: common.js 精简 — 设计文档

**编号**：F5（Redesign-P0P1 修复计划第 5 批）  
**状态**：待确认  
**创建日期**：2026-08-24  
**关联**：`doc/design/Redesign-P0P1问题根因分析与修复设计.html` F5 节

## 1. 问题陈述

### 1.1 现状

当前 Redesign 每个页面的 `_base.html` 加载以下 JS 文件链：

```
jquery.js       →  92,554 bytes
wind.js         →  26,770 bytes   ← 模块加载器（仅 v1 需要）
common.js       →  38,969 bytes   ← 1,083 行（含 v1-only 功能 ~850 行）
  ├── Wind.use('ajaxForm')       →  37,413 bytes (lazy)
  ├── Wind.use('artDialog')      →  16,359 bytes (lazy)
  ├── Wind.use('validate')       →  46,342 bytes (lazy)
  └── Wind.use('noty')           →  24,970 bytes (lazy, unused in Redesign)
```

**Redesign 页面实际触发的 JS 总载荷：~257 KB**（含 lazy-load 的 3 个插件，因为 `common.js` 初始化代码在 DOM ready 时检测到 `.js-ajax-form` 即触发加载）

### 1.2 Redesign 的实际需求

通过全量 `grep` 分析 `app/templates/redesign/` 中的引用：

| 功能 | 使用点 | 来源 |
| --- | --- | --- |
| `js-ajax-form` + `js-ajax-submit` 表单提交 | 7 个模板 | common.js (line 62-226) |
| POST 防重复提交守卫 | 全局（自动） | common.js (line 1065-1083) |
| `$.ajax` CSRF header 注入 | tags.html (4处) | 各页面自行注入 |
| `getCookie()` | 0（Redesign 不直接调用） | common.js (line 475-490) |

**不需要但被加载的功能：**

| 功能模块 | 行数 | 对 Redesign 的价值 |
| --- | --- | --- |
| IE placeholder polyfill | 19-41 | 零（IE 不支持） |
| artDialog 弹窗打开（`js-dialog`） | 44-59 | 零（Redesign 用 CpConfirm/CpModal） |
| artDialog 批量删除（`js-ajax-delete`） | 242-287 | 零 |
| artDialog 通用确认（`js-ajax-dialog-btn`） | 290-346 | 零 |
| 复选框全选（`js-check-wrap`） | 348-414 | 零 |
| datePicker 初始化 | 417-444 | 零 |
| tabs 插件初始化 | 447-452 | 零 |
| `open_iframe_dialog` / map / upload 系列 | 509-657 | 零 |
| `artdialog_alert` / `error()` / `success()` | 658-722 | 零（有 CpToast） |
| `upload_file()` | 725-778 | 零 |
| v1 Console 搜索模块（`_cpSearch`） | 831-1063 | 零（有 CpShell Command Palette） |
| v1 UI mode/theme/sidebar 函数 | 791-822 | 零（有 redesign-shell.js） |

**核心发现**：Redesign 需要 `common.js` 的 **仅 ~130 行**（表单提交守卫 + 防重复提交），却被迫加载 1,083 行 + 3 个 jQuery 插件（~100 KB lazy）。

### 1.3 影响量化

**165 KB**冗余 JS 载荷

**19 次**Wind.use 调用（含 HTTP 请求）

**850 行**永不执行的死代码

**2 套**重复功能（Toast/Confirm/Search）

## 2. 根因分析（5-Why 复盘）

### 2.1 结构性根因

> **Why-1**：为什么 Redesign 页面加载了 1,083 行的 `common.js`？  
> → 因为 `_base.html` 直接复制了 v1 `admin_base.html` 的 script 引用链。
>
> **Why-2**：为什么复制而不是从零设计 JS 依赖？  
> → 因为 `js-ajax-form` 表单机制被 7 个 Redesign 模板复用，它依赖 `common.js` 内的 handler。
>
> **Why-3**：为什么不先将 handler 单独提取？  
> → 因为 handler 内部硬编码依赖 `Wind.use('ajaxForm', 'artDialog', 'validate', ...)`，三者形成不可拆分的依赖束。
>
> **Why-4**：为什么 handler 需要 artDialog 和 validate？  
> → artDialog 用于批量操作确认对话框（`data-subcheck`），validate 用于 jQuery Validate 客户端校验。**但 Redesign 模板不使用这两个功能**——Redesign 用 HTML5 `required` + CpConfirm。
>
> **Why-5（根因）**：为什么 handler 没有按职责拆分？  
> → `common.js` 是 2018 年原始项目的"单一入口" JS 文件，当时所有页面共用一个行为层，不存在模块边界概念。Redesign 开发时以「功能优先、快速上线」为 DoD，没有将 **JS 依赖切割** 纳入架构治理，导致新旧两套 UI 共享了一个未拆分的行为层。

### 2.2 问题模式分类

| 模式 | 表现 | 根本原因 |
| --- | --- | --- |
| **Dead Coupling**（死耦合） | 850 行从不执行的代码被每页加载 | 单文件 + 无条件初始化 |
| **Plugin Cascade**（插件级联） | 3 个 jQuery 插件通过 Wind.use lazy-load 但每页都触发 | handler 内 `if ($('form.js-ajax-form').length)` 为 true → 触发 cascade |
| **Feature Duplication**（功能重复） | Toast/Confirm/Search 在 common.js 和 redesign-\*.js 中各有一套 | 新模块创建时未移除旧模块引用 |

### 2.3 历史演进图

```
2018:  common.js (v1-only, 单入口)
         │
2026-07: Redesign 启动 → _base.html 引入 common.js（"先跑通再优化"）
         │
2026-07: 创建 redesign-shell.js → 重复实现了 sidebar/search
         │
2026-07: 创建 redesign-toast.js → 重复实现了通知
         │
2026-07: 创建 redesign-confirm.js → 重复实现了对话框
         │
2026-08: 功能完备 → common.js 中 850 行成为 Dead Code
         │
2026-08(now): F5 → 正式切割，消除 Dead Coupling
```

## 3. 方案设计

### 3.1 架构目标

```
┌─────────── v1 (admin_base.html) ───────────┐
│  jquery.js + wind.js + common.js           │  ← 不动，保持 v1 功能完整
│  + artDialog + ajaxForm + validate + noty  │
└────────────────────────────────────────────┘

┌─────────── v2 Redesign (_base.html) ───────┐
│  jquery.js + common-redesign.js            │  ← 新建 ~150 行
│  + redesign-shell.js                       │
│  + redesign-theme.js                       │
│  + redesign-toast.js                       │
│  + redesign-confirm.js                     │
└────────────────────────────────────────────┘
```

### 3.2 `common-redesign.js` 功能清单

| # | 功能 | 实现方式 | 行数估算 |
| --- | --- | --- | --- |
| 1 | CSRF token 全局注入 | `$.ajaxSetup({ beforeSend: ... })` 读取 `<meta name="csrf-token">` | ~15 |
| 2 | `js-ajax-form` 提交 handler | 使用 `$.ajax()` + `$form.serialize()` 替代 Wind.use('ajaxForm') 的 `$.fn.ajaxSubmit` | ~70 |
| 3 | 表单提交成功/失败反馈 | 使用 `CpToast.success()` / `CpToast.error()` 替代 artDialog/noty 的 `tips_success/tips_error` | ~10 |
| 4 | POST 防重复提交守卫 | 对非 `js-ajax-form` 的 POST 表单禁用按钮 + 文案变更 | ~20 |
| 5 | `getCookie()` / `setCookie()` | 直接复制（无外部依赖） | ~25 |
| 6 | IIFE 包裹 + 'use strict' | — | ~5 |
| **总计** | | | **~145 行** |

### 3.3 关键设计决策

#### D1: 为什么用 `$.ajax()` 替代 `$.fn.ajaxSubmit()`？

`ajaxForm.js`（37 KB）的核心功能是将 `<form>` 的输入序列化后通过 AJAX 提交。jQuery 内置的 `$.ajax({ data: $form.serialize() })` 可完全等价替代此行为。Redesign 表单无文件上传需求（文件上传在 v1 用 `upload_file()`），因此不需要 `ajaxForm.js` 的 iframe-based file upload 能力。

#### D2: 为什么不再需要 jQuery Validate？

分析 7 个 Redesign `js-ajax-form` 模板：

- `task_form.html`：HTML5 `required` + 后端校验
- `cron_retire.html`：单 textarea `required`
- `group_form.html`：单 input `required`
- `users_set_active.html`：radio `required`
- `user_profile.html`：后端校验
- `change_password.html`：HTML5 `minlength` + 后端
- `user_form.html`：HTML5 `required` + 后端

无一使用 jQuery Validate 的 `rules` / `messages` 配置。HTML5 内置校验 + 后端验证已覆盖全部需求。

#### D3: 为什么移除 `wind.js`？

`wind.js`（27 KB）是一个自定义模块加载器（类 AMD），其唯一用途是按需加载 `artDialog`、`ajaxForm`、`validate`、`noty`、`datePicker`、`layer` 等 v1 插件。Redesign 不使用任何这些插件（已有原生替代），因此 `wind.js` 无存在价值。

#### D4: `data-subcheck` 功能如何处理？

`grep` 确认 `app/templates/redesign/` 中无任何 `data-subcheck`、`data-msg`、`data-action` 属性使用。此功能仅在 v1 模板中存在（批量选择 + artDialog 确认），完全不迁移到 `common-redesign.js`。

#### D5: 成功/失败反馈的行为差异

| 行为 | common.js (v1) | common-redesign.js (v2) |
| --- | --- | --- |
| 成功通知 | `$('<span class="tips_success">').appendTo($btn.parent())` | `CpToast.success(data.errmsg)` |
| 失败通知 | `$('<span class="tips_error">').appendTo($btn.parent())` | `CpToast.error(data.errmsg)` |
| 跳转 | `window.location.href = data.url` | 相同 |
| 无 url 且 errcode===0 | `reloadPage(window)` | `location.href = location.pathname + location.search`（内联） |

## 4. 范围

### 4.1 变更文件

| 文件 | 操作 | 说明 |
| --- | --- | --- |
| `app/static/js/common-redesign.js` | 新建 | ~145 行 IIFE 模块 |
| `app/templates/redesign/_base.html` | 修改 | 移除 `wind.js` + `common.js`，替换为 `common-redesign.js` |

### 4.2 不动文件

- `app/static/js/common.js` — 不修改（v1 继续使用）
- `app/static/js/wind.js` — 不删除（v1 继续使用）
- `app/templates/admin_base.html` — 不修改
- 所有 v1 模板（`app/templates/*.html`、`app/templates/rbac/*.html`）— 不修改
- 所有 Redesign 功能模板 — 不修改（`js-ajax-form` class 约定不变）

## 5. 详细实现

### 5.1 `common-redesign.js` 完整代码设计

```
/**
 * CronPilot Redesign — Common Utilities
 * ======================================
 * Replaces common.js + wind.js for Redesign pages.
 * Dependencies: jQuery (only), CpToast (redesign-toast.js)
 *
 * Provides:
 *  1. CSRF token global AJAX injection
 *  2. js-ajax-form submit handler (no Wind/ajaxForm/validate dependency)
 *  3. POST form anti-double-submit guard
 *  4. getCookie / setCookie utilities
 */
;(function($) {
  'use strict';

  /* ====== 1. CSRF Token Global Injection ====== */
  $.ajaxSetup({
    beforeSend: function(xhr, settings) {
      if (!/^(GET|HEAD|OPTIONS|TRACE)$/i.test(settings.type)) {
        var token = $('meta[name=csrf-token]').attr('content');
        if (token) {
          xhr.setRequestHeader('X-CSRFToken', token);
        }
      }
    }
  });

  /* ====== 2. js-ajax-form Submit Handler ====== */
  $(document).on('click', 'button.js-ajax-submit', function(e) {
    var $btn = $(this);
    var $form = $btn.closest('form.js-ajax-form');
    if (!$form.length) return;

    // Prevent native form submission
    e.preventDefault();

    // Loading guard
    if ($btn.data('loading')) return;

    // HTML5 validation check
    if ($form[0].checkValidity && !$form[0].checkValidity()) {
      $form[0].reportValidity();
      return;
    }

    // Enter loading state
    $btn.data('loading', true);
    var origText = $btn.text();
    $btn.text(origText + '中…').prop('disabled', true).addClass('disabled');

    // Determine action URL
    var url = $btn.data('action') || $form.attr('action');

    // Inject CSRF token into form data
    var formData = $form.serialize();
    var csrfToken = $('meta[name=csrf-token]').attr('content');
    var csrfParam = $('meta[name=csrf-param]').attr('content') || 'csrf_token';
    if (csrfToken) {
      formData += '&' + encodeURIComponent(csrfParam)
                + '=' + encodeURIComponent(csrfToken);
    }

    $.ajax({
      url: url,
      type: 'POST',
      data: formData,
      dataType: 'json',
      success: function(data) {
        // Reset button
        $btn.removeClass('disabled').prop('disabled', false)
            .text(origText);

        // Show feedback via CpToast
        if (data.errmsg && window.CpToast) {
          if (data.errcode === 0) {
            CpToast.success(data.errmsg);
          } else {
            CpToast.error(data.errmsg);
          }
        }

        // Handle redirect or reload
        if (data.url) {
          window.location.href = data.url;
        } else if (data.errcode === 0) {
          var loc = window.location;
          loc.href = loc.pathname + loc.search;
        }
      },
      error: function(xhr) {
        $btn.removeClass('disabled').prop('disabled', false)
            .text(origText);
        try {
          var resp = JSON.parse(xhr.responseText);
          if (window.CpToast) CpToast.error(resp.errmsg || '操作失败');
        } catch(ex) {
          if (window.CpToast) CpToast.error('网络错误，请重试');
        }
      },
      complete: function() {
        $btn.data('loading', false);
      }
    });
  });

  // Prevent native form submission for js-ajax-form
  $(document).on('submit', 'form.js-ajax-form', function(e) {
    e.preventDefault();
  });

  /* ====== 3. POST Anti-Double-Submit Guard ====== */
  $(document).on('submit', 'form:not(.js-ajax-form)', function() {
    var $form = $(this);
    if ($form.attr('method') &&
        $form.attr('method').toLowerCase() !== 'post') return;
    var $btn = $form.find('[type="submit"]');
    if (!$btn.length) return;
    if ($btn.data('cp-submitting')) return false;
    $btn.data('cp-submitting', true);
    var origText = $btn.is('input') ? $btn.val() : $btn.text();
    if ($btn.is('input')) {
      $btn.val(origText + '中…');
    } else {
      $btn.text(origText + '中…');
    }
    $btn.prop('disabled', true).addClass('disabled');
    setTimeout(function() {
      $btn.data('cp-submitting', false)
          .prop('disabled', false).removeClass('disabled');
      if ($btn.is('input')) { $btn.val(origText); }
      else { $btn.text(origText); }
    }, 3000);
  });

  /* ====== 4. Cookie Utilities ====== */
  window.getCookie = function(name) {
    var nameEQ = name + '=';
    var ca = document.cookie.split(';');
    for (var i = 0; i < ca.length; i++) {
      var c = ca[i].replace(/^\s+/, '');
      if (c.indexOf(nameEQ) === 0) {
        return c.substring(nameEQ.length);
      }
    }
    return null;
  };

  window.setCookie = function(name, value, days) {
    var expire = new Date();
    if (!days) days = 1;
    expire.setTime(expire.getTime() + 86400000 * days);
    document.cookie = name + '=' + encodeURIComponent(value)
      + ';path=/;expires=' + expire.toUTCString() + ';samesite=lax';
  };

})(jQuery);
```

## 6. 分批执行计划

此变更范围小且原子化，**不分批**，单次交付：

| 步骤 | 操作 | 验收 |
| --- | --- | --- |
| 1 | 创建 `app/static/js/common-redesign.js` | 文件存在，语法正确 (`node -c`) |
| 2 | 修改 `_base.html`：移除 wind.js + common.js 行，添加 common-redesign.js | `grep 'wind.js\|common.js' app/templates/redesign/_base.html` 无结果 |
| 3 | restart 服务 | `lsof -nP -iTCP:5001 -sTCP:LISTEN` |
| 4 | 验证 js-ajax-form 7 模板 | 逐一 CRUD 测试（见验收章节） |
| 5 | 验证 v1 页面不受影响 | v1 `/cron_list` 功能正常 |

## 7. 验收标准

### 7.1 功能验收

| # | 场景 | 步骤 | 期望结果 |
| --- | --- | --- | --- |
| V1 | CSRF 注入 | 浏览器 DevTools → Network → 任意 `$.ajax POST` | 请求头含 `X-CSRFToken` |
| V2 | js-ajax-form 提交 | 创建任务组 → 填写表单 → 点击保存 | ① 按钮显示"保存中…" ② Toast 成功 ③ 跳转/刷新 |
| V3 | js-ajax-form 失败 | 提交无效数据（如空必填字段绕过 HTML5 校验） | Toast 错误提示 + 按钮恢复 |
| V4 | 防重复提交 | 搜索表单快速连击提交按钮 | 首次提交后按钮禁用 3 秒 |
| V5 | HTML5 校验 | task\_form 不填名称直接提交 | 浏览器原生 required 提示 |
| V6 | tags.html 自定义 AJAX | 创建/重命名/删除标签 | 正常工作（不依赖 common.js） |
| V7 | v1 页面隔离 | 访问 `/cron_list`（v1） | artDialog/datePicker/全选正常 |

### 7.2 性能验收

| 指标 | Before | After | 验证方式 |
| --- | --- | --- | --- |
| JS 文件数 | 6 (jquery + wind + common + shell + theme + toast + confirm) | 6 (jquery + **common-redesign** + shell + theme + toast + confirm) | Network 面板 |
| JS 总载荷 | ~257 KB | ~108 KB | `curl -s` 各文件 | `wc -c` |
| Lazy-load HTTP 请求 | 3 (ajaxForm + artDialog + validate) | 0 | Network 面板无额外 .js 请求 |

### 7.3 CI 门禁验证

```
python -m unittest tests.test_ajax_form_guard -v    # 表单守卫静态门禁
python scripts/audit_hardcoded_colors.py --check    # 颜色审计
python scripts/check_css_token_reachability.py --check  # Token 可达性
bash scripts/cronpilot.sh test                      # 全量单测
```

## 8. 风险评估与缓解

| 风险 | 概率 | 影响 | 缓解 |
| --- | --- | --- | --- |
| 某 Redesign 模板隐式依赖 common.js 未发现的功能 | 低 | 高 | `grep` 已确认无直接调用；7 模板逐一功能测试 |
| `$.ajax()` 的 `data: $form.serialize()` 与 `$.fn.ajaxSubmit` 行为差异 | 中 | 中 | 差异仅在文件上传（iframe 方式），Redesign 无文件上传表单 |
| 第三方 Redesign 页面 JS（`{% block js %}`）间接依赖 Wind/artDialog | 低 | 高 | `grep Wind` + `grep artDialog` 全量扫描 Redesign templates |
| v1 页面受影响 | 零 | — | v1 使用独立的 `admin_base.html`，script 引用链完全独立 |
| Toast 在 AJAX handler 调用时未加载（执行顺序） | 低 | 中 | 所有 script 均 `defer`，按文档顺序执行；toast 在 common-redesign 之前无需加载，因为 AJAX handler 在用户交互时触发，此时所有 defer 脚本已完成 |

### 8.1 回滚方案

恢复 `_base.html` 中的 `wind.js` + `common.js` 行即可（单行 git revert）。`common-redesign.js` 文件存留不影响任何功能。

## 9. 测试漏洞分析

### 9.1 现有测试覆盖

| 测试 | 覆盖范围 | 能否发现本问题 |
| --- | --- | --- |
| `test_ajax_form_guard.py` | 检查模板中 `js-ajax-form` 必须配对 `js-ajax-submit` | 否 — 仅检查 HTML 结构，不检查 JS runtime |
| `cronpilot.sh test` | 后端单元测试 | 否 — 不涉及前端 JS |
| 浏览器手动验证 | 端到端 | 是 — 但依赖人工执行 |

### 9.2 建议新增测试

F5 完成后建议添加：

- **JS 语法检查**：`node -c app/static/js/common-redesign.js`（加入 CI）
- **依赖隔离断言**：`grep -c 'Wind\.' app/static/js/common-redesign.js` 应为 0
- **页面 JS 加载断言**：`curl /redesign/dashboard | grep 'common-redesign.js'` 且 `grep -v 'common.js'`

## 10. 预防方案

| # | 措施 | 落地位置 | 验证方式 |
| --- | --- | --- | --- |
| P1 | CI 门禁：Redesign base 模板禁止引用 `wind.js` / `common.js` | `scripts/check_ui_contract.py` 新增规则 | `grep 'wind.js\|common.js' app/templates/redesign/_base.html && exit 1` |
| P2 | AGENTS.md 规范：Redesign 新增 JS 依赖时禁止引入 v1 模块加载器 | `AGENTS.md` "JS 依赖"节 | Code Review 检查 |
| P3 | `common-redesign.js` 头部注释声明零 Wind 依赖约束 | 文件顶部 JSDoc | `grep 'Wind' common-redesign.js | wc -l` === 0 |

## 11. \_base.html 变更 Diff 预览

```
--- a/app/templates/redesign/_base.html
+++ b/app/templates/redesign/_base.html
@@ -47,9 +47,8 @@
   {# Core JS — jQuery + shared utilities #}
   <script>var GV = {ROOT: "/", WEB_ROOT: "", JS_ROOT: "{{ url_for('static', filename='js/') }}", UPLOAD_URL: "/"};</script>
   <script defer src="{{ url_for('static', filename='js/jquery.js') }}"></script>
-  <script defer src="{{ url_for('static', filename='js/wind.js') }}"></script>
-  <script defer src="{{ url_for('static', filename='js/common.js') }}"></script>
+  <script defer src="{{ url_for('static', filename='js/common-redesign.js') }}"></script>
   {# Redesign JS modules #}
   <script defer src="{{ url_for('static', filename='js/redesign-shell.js') }}"></script>
```

## 12. 文档引用

- `doc/design/Redesign-P0P1问题根因分析与修复设计.html` — F5 章节
- `doc/design/Redesign前端代码质量评估与优化计划.html` — 整体优化规划
- `doc/design/Phase-R2-R3必要性分析与根因复盘.html` — JS 模块化根因

[文档索引](index.html) · [Markdown](F5-common-js精简设计.md) · [索引](index.html)

---

[← 文档索引（HTML）](../index.html) · [← 文档索引（Markdown）](../index.md)
