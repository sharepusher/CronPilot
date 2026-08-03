# CronPilot · OPT-P0-11 管理端 CSRF 防护设计

> HTML 版：[OPT-P0-11-管理端CSRF设计.html](OPT-P0-11-管理端CSRF设计.html) · [文档索引](../index.html) · [索引 Markdown](../index.md)

[← 文档索引](../index.html)
OPT-P0-11R3已交付v2.1.1

# 管理端 CSRF 防护设计

堵住 Session Cookie 下「跨站诱导状态变更」；不引入 Flask-WTF 全量表单栈

状态：已确认并交付 · v2.1.1 · 2026-07-21

**交付结论：**Session Token + meta 注入；写操作 `POST` + `@csrf_protect`；
`js-ajax-dialog-btn` 改为 POST 并附带 token；`/api/*` 豁免。

## 一、问题

| 现象 | 用户 / 安全影响 |
| --- | --- |
| 管理端大量**状态变更**可通过 `GET` 触发（如 `/update_status`、`/cron_run_now`、用户启停等） | 已登录管理员若访问恶意页，可被 `<img src>` / 链接诱导执行启停、立即执行等写操作 |
| `js-ajax-dialog-btn` → `requests.js` 默认 `type:'GET'` | 确认框后的 Ajax 仍是 GET，与「幂等读」语义不符 |
| `ajaxForm.js` 已读 `meta[name=csrf-token]`，但模板**未注入** meta | 前端预留未接线，表单 POST 亦无服务端 CSRF 校验 |

## 二、根因

- 历史 simpleboot 风格：对话框操作走 GET + Session Cookie（浏览器自动带 Cookie）。
- 未采用同步器令牌（Synchronizer Token）；依赖「仅内网」假设不足。
- 依赖升级 RFC 明确**本代不做 Flask-Login / Flask-WTF 全量迁移**——故不应借 CSRF 顺手引入整套 WTForms。

## 三、方案（推荐）

### 3.1 选型

| 方案 | 优点 | 缺点 | 结论 |
| --- | --- | --- | --- |
| A. Flask-WTF `CSRFProtect` only | 成熟 | 新增依赖；易与「不做 WTF 迁移」叙事冲突；API 豁免配置易漏 | 备选 |
| **B. 自研 Session Token（推荐）** | 零新依赖（`secrets` + 现有 Session）；对齐已有 meta 约定；可控豁免 | 需自维护装饰器 / 校验函数 | **采用** |

### 3.2 机制

```
登录成功 / 首次需要时：
  session['csrf_token'] = secrets.token_urlsafe(32)

布局模板（base / 管理端骨架）：
  <meta name="csrf-token" content="{{ csrf_token }}">
  <meta name="csrf-param" content="csrf_token">
  （context_processor 注入）

状态变更请求（管理端 Session）：
  仅允许 POST（或 PUT/DELETE，本期统一 POST）
  校验：form / JSON / header X-CSRFToken / X-CSRF-Token
       与 session['csrf_token'] 常量时间比较

豁免：
  /api/*（access_token 认证，非 Cookie Session）
  /docs/*（只读静态）
  纯展示 GET 列表 / 详情
```

### 3.3 前端契约

| 入口 | 改动 |
| --- | --- |
| `js-ajax-dialog-btn` | `requests({ type:'POST', data:{ csrf_token, ... } })`；禁止再默认 GET 改状态 |
| `js-ajax-form` | 已有 ajaxForm csrf 分支；注入 meta 后自动带上；服务端校验 |
| 普通表单（若有） | 隐藏域 `<input name="csrf_token">` 或依赖 Ajax 路径 |

### 3.4 后端契约

- 新增 `app/security/csrf.py`：`ensure_csrf_token()`、`validate_csrf()`、`csrf_protect` 装饰器（或 `before_request` 白名单模式，二选一；推荐**装饰器挂在写路由**，避免误伤只读 GET）。
- 下列路由改为 `methods=['POST']`（去掉 GET）并挂校验：至少
  `update_status`、`cron_run_now`、`cron_retire`（若已是表单 POST 则补 token）、
  RBAC `users/set_active`、`users/reset_password` 等对话框写操作；
  以及现有 `js-ajax-form` POST 写接口。
- 参数仍可读 `request.form` / `request.args` 过渡：**id 等业务参数**可继续 query（POST URL 带 `?id=`），但**方法必须是 POST**。
- 失败：JSON `errcode≠0`，文案明确「CSRF 校验失败，请刷新页面重试」。

## 四、范围

| 做 | 不做 |
| --- | --- |
| 管理端 Session 写操作 CSRF；对话框改 POST；meta 注入；单测 + 浏览器验收 | Flask-WTF / WTForms 全量；改 `/api/*` 契约；SameSite 全面策略大改（可另立小项）；回调重试（R4） |

## 五、分批

| 批 | 内容 | 可独立验收 |
| --- | --- | --- |
| **R3-a** | `csrf.py` + context\_processor meta + 单测（token 缺失/错误/正确） | 单元测试 |
| **R3-b** | 高危对话框：`update_status` / `cron_run_now` → POST + token；改 `common.js` / `requests` 调用 | 浏览器：启停、立即执行 |
| **R3-c** | RBAC 对话框写操作 + 其余 `js-ajax-dialog-btn` 写路由扫尾 | 用户启停 / 重置密码路径 |
| **R3-d** | 确认 `js-ajax-form` 写路径均校验；补 `test_ajax_form_guard` 相关断言（若适用） | 添加/编辑任务表单提交 |

## 六、验收

```
bash scripts/cronpilot.sh test
bash scripts/verify_golden_path.sh
bash scripts/cronpilot.sh restart --daemon
# 本地：http://127.0.0.1:5001/  登录后：
# 1) 无 token 的 GET /update_status?id=… → 405 或拒绝
# 2) 无 token 的 POST → CSRF 失败 JSON
# 3) 页面对话框「暂停/启动」「立即执行」→ 成功（带 token）
# 4) Agent 自证 curl/会话输出写入交付回复；保持服务运行
```

## 七、风险

- 漏改某条对话框仍 GET → 405，表现为「按钮坏了」——用全库搜 `js-ajax-dialog-btn` + 写路由清单扫尾。
- 多标签页旧页面无 meta → 须刷新；文案引导「刷新重试」。
- 与 OPT-P0-10 强密钥配合：伪造 Session 难度已提高；CSRF 补的是「已登录会话被跨站滥用」。

前置：[OPT-P0-09/10](OPT-P0-09-10-锁与密钥设计.html) 已交付。
相关：[交付状态](../交付状态与路线图.html) ·
[管理端 UI](../design/管理端UI优化设计.html)

[Markdown 版](OPT-P0-11-管理端CSRF设计.md) ·
[文档索引](../index.html)

---

[← 文档索引（HTML）](../index.html) · [← 文档索引（Markdown）](../index.md)
