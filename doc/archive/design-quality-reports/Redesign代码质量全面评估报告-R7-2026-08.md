# CronPilot 代码质量全面评估报告 R7（2026-08）

> HTML 版：[Redesign代码质量全面评估报告-R7-2026-08.html](Redesign代码质量全面评估报告-R7-2026-08.html) · [文档索引](../../index.html) · [索引 Markdown](../../index.md)

# CronPilot 代码质量全面评估报告 R7（2026-08-28）

状态：评估完成，待讨论

本轮为 R1–R6 安全/质量修复后的第七次全面评估，覆盖后端（Python/Flask）与前端（Jinja2/CSS/JS）。

## 评估总览

| 层面 | P0 | P1 | P2 | 合计 |
| --- | --- | --- | --- | --- |
| 后端 | 1 | 6 | 6 | 13 |
| 前端 | 0 | 9 | 11 | 20 |
| **总计** | **1** | **15** | **17** | **33** |

## 一、后端 P0 — 关键

### BE-P0-1：B-15 API 创建任务 scope 未持久化

|  |  |
| --- | --- |
| 位置 | `app/services/cron_service.py:315-336`（`upsert_cron_by_task_name`） |
| 问题 | `_apply_api_scope()` 正确地向 `datas` 字典注入了 `scope_type` 和 `group_id`， 但 `upsert_cron_by_task_name()` 将 `datas` 传入 `validate_cron_form()` 后拿到的 `normalized` 字典中 **不包含这两个字段**（`validate_cron_form` 不传递 scope 字段）。 `create_cron(normalized)` 因此使用 `scope_type` 默认值 `'GLOBAL'`，不写 `task_groups` 行。 |
| 影响 | Scoped operator 通过 API 创建的任务全部变成 GLOBAL，**突破租户隔离**。 |
| 对照 | Web 路径 `add_cron_web()` 在 validate 后有 `normalized['scope_type'] = datas.get('scope_type')`（行 343-345），API 路径缺少等效合并。 |
| 修复方向 | 在 `upsert_cron_by_task_name()` 的 `validate_cron_form()` 之后，增加与 `add_cron_web()` 相同的 scope 字段合并逻辑。 |

## 二、后端 P1 — 重要

### BE-P1-1：job\_log.content 写入原始异常文本（信息泄露）

|  |  |
| --- | --- |
| 位置 | `app/crons.py:312, 341, 362` 及相关路径 |
| 问题 | HTTP/DB 失败时 `"发生严重错误:%s" % str(e)` 直接写入 `job_log.content`， 包含连接字符串、主机名、库内部堆栈等。Viewer 角色通过 Run Inspector 或 API 即可查看。 |
| 修复方向 | 引入 `_safe_error_content(exc)`，返回通用错误描述；详细信息仅写 `logger.exception()`。 |

### BE-P1-2：DNS 解析失败时 SSRF 固定绕过（DNS rebinding 窗口）

|  |  |
| --- | --- |
| 位置 | `app/services/url_security.py:96-99, 143-145`；`app/crons.py:236-239` |
| 问题 | DNS 解析失败时 `validate_callback_url()` 返回 `(True, '')`。 执行时 `resolved_ip=None`，走无固定 IP 的 `requests.get/post`。 攻击者可利用 DNS rebinding：验证时解析公网 IP，执行时解析 `127.0.0.1`。 |
| 修复方向 | 当 `block_private_ip=1` 时，DNS 解析失败应拒绝而非放行。 |

### BE-P1-3：create\_cron/update\_cron scheduler 注册失败无补偿

|  |  |
| --- | --- |
| 位置 | `app/services/cron_service.py:185-186, 229-230` |
| 问题 | `db.session.commit()` 在 `register_cron_job()` 之前。 若 `scheduler.add_job()` 抛异常，DB 行已存在但调度器无对应 job → 静默孤儿任务。 |
| 修复方向 | post-commit scheduler 失败时标记 `status=0` + 返回警告，或采用补偿事务模式。 |

### BE-P1-4：retire\_cron 事务顺序与 toggle\_status 不一致

|  |  |
| --- | --- |
| 位置 | `app/services/cron_service.py:281-286, 306-310` |
| 问题 | `retire_cron_*` 先 `remove_job()` 后 `commit()`， 而 `toggle_status()` 先 `commit()` 后 scheduler 操作。 若 commit 失败，scheduler 已删但 DB 仍显示活跃。 |
| 修复方向 | 对齐 `toggle_status()` 的 commit-first 模式。 |

### BE-P1-5：旧版 GET /api/cron/add 允许状态修改操作

|  |  |
| --- | --- |
| 位置 | `app/api/views.py:670-706` |
| 问题 | `@api.route('/cron/add', methods=['GET', 'POST'])` 允许通过 GET 创建/更新任务。 违反 HTTP 安全语义，易受 CSRF（`<img src=...>`）攻击。 |
| 修复方向 | 限制为 POST only；GET 返回 405。 |

### BE-P1-6：API GET 端点缺少 check\_api\_permission（防御缺口）

|  |  |
| --- | --- |
| 位置 | `app/api/views.py:142-426`（多个 GET 处理函数） |
| 问题 | 读端点仅做 scope 过滤，未调用 `check_api_permission('cron:read')`。 POST 端点在 S-5 中已补齐，读端点未对齐。 |
| 修复方向 | 在各 GET handler 顶部添加 `check_api_permission` 调用。 |

## 三、后端 P2 — 改善

### BE-P2-1：TestApiCreateScope 仅测 helper 函数，缺端到端持久化验证

位置：`tests/test_api_scope_s6.py:676-764`。现有测试只调用 `_apply_api_scope()`，
不验证 POST `/api/cron` 后 DB 中 `scope_type` 和 `task_groups` 是否正确。
**正是此盲区导致 BE-P0-1 未被发现。**

### BE-P2-2：job\_log\_detail BIGINT 时间戳作为 datetime 处理

位置：`app/main/views.py:701-707`。`started_raw` 是 BIGINT（hms epoch），
但代码按 `isinstance(started_raw, str)` 或 datetime 对象处理，
整数值走 else 分支后 `datetime.now() - integer` 抛 TypeError，
被 `except` 静默捕获 → `time_ago` 永远为空。

### BE-P2-3：LIKE 搜索未转义 % 和 \_ 通配符

位置：`app/api/views.py:164`；`app/main/views.py:214` 等。
用户输入 `%` 或 `_` 会意外扩大匹配范围（非注入，SQLAlchemy 参数化）。

### BE-P2-4：登录限流器为进程本地（多 worker 绕过）

位置：`app/rbac/login_limiter.py`。内存限流器在 gunicorn 多 worker 部署下
每个 worker 独立计数，有效预算 ×worker 数。

### BE-P2-5：回调签名使用 MD5

位置：`app/common/functions.py:53-56`（`get_cronpilot_sign`）。
HMAC-MD5 低于现代密码基线。建议 v2 协议升级为 HMAC-SHA256。

### BE-P2-6：access\_token 通过 query string 传递

位置：`app/api/__init__.py:49`。Token 出现在 URL 中，有日志/Referer 泄露风险。
已在 API 安全评估文档中记录（Q-1），建议未来 major 版本仅接受 Bearer header。

## 四、前端 P0

**无新 P0。** Redesign 模板使用 Jinja2 自动转义 + CSRF meta + `samesite=lax` cookie，
无 `eval`、无 Bootstrap modal、无模板硬编码色值。

## 五、前端 P1 — 重要

### FE-P1-1：Escape 快捷键与 Command Palette 冲突

位置：`task_detail.html:265-268`, `task_form.html:356-359`, `run_inspector.html:142-149`。
页面级 Escape 处理未检查 `#cp-cmd-overlay.open`，导致 Command Palette 打开时按 Esc 触发页面导航。

### FE-P1-2：Dashboard 下拉菜单操作项键盘不可达

位置：`_dashboard_rows.html:92-100`。
`<a onclick="...">` 无 `href`、无 `role="button"`、无 `tabindex`。

### FE-P1-3：用户菜单触发器不可聚焦

位置：`_topbar.html:35-41`。
`#cp-user-menu-trigger` 是 `<div>`，缺少 `role="button" tabindex="0" aria-haspopup`。

### FE-P1-4：任务详情头部按钮缺 accessible names

位置：`task_detail.html:50-58`。
"立即执行/暂停/恢复" 按钮无 `aria-label`。

### FE-P1-5：Modal 缺焦点陷阱和 aria-labelledby

位置：`redesign-confirm.js:47-57, 113-118`。
`CpConfirm`/`CpModal` 无 Tab 循环、无焦点恢复、无 `aria-labelledby`。

### FE-P1-6：escHtml 回退返回原始字符串

位置：`tags.html:91`, `registration_review.html:155`。
当 `common-redesign.js` 加载失败时，`escHtml` 回退直接返回 `s`，用户输入未转义流入 `innerHTML`。

### FE-P1-7：AJAX fetch 未检查 HTTP 状态码

位置：`dashboard.html:288`, `execution_logs.html:143` 等 5 处。
`.then(r => r.json())` 未 `if (!r.ok)`，403/500 HTML 响应触发 JSON 解析异常。

### FE-P1-8：Toast 关闭按钮键盘不可操作

位置：`redesign-toast.js:52-57`。
有 `role="button" tabindex="0"` 但仅绑定 `click`，无 Enter/Space 处理。

### FE-P1-9：Clipboard API 失败静默无反馈

位置：`task_detail.html:239-244`, `api_token.html:65-69` 等。
`navigator.clipboard.writeText(...).then(...)` 无 `.catch()`。非 HTTPS 或权限被拒时无提示。

## 六、前端 P2 — 改善

### FE-P2-1：5 个页面 AJAX 筛选 IIFE 近 400 行重复

位置：`dashboard.html`, `execution_logs.html`, `users.html`,
`audit_logs.html`, `operation_log.html`。相同 fetch→innerHTML→分页重绑模式。

### FE-P2-2：大 inline <script> 块（dashboard ~270 行, tags ~250 行）

阻碍缓存，增大 HTML 负载。建议移至独立 JS 文件。

### FE-P2-3：Tags 页使用 `javascript:;` + 缺 pill aria-label

位置：`tags.html:22-25, 50, 61-67`。

### FE-P2-4：表单 label 未关联 for/id

位置：`task_form.html:17-21`。`<label class="tf-label">` 无 `for=`。

### FE-P2-5：Command Palette 缺 dialog 语义

位置：`_base.html:34-44`, `redesign-shell.js:93-107`。
无 `role="dialog"`、`aria-modal`、`aria-live`。

### FE-P2-6：updateStats 用 innerHTML + inline style 重建统计行

位置：`dashboard.html:340-343`。应使用 class + textContent。

### FE-P2-7：Vue cron validator 引用 Font Awesome（Redesign 未加载）

位置：`frontend/src/components/CronFormValidator.vue:5,8,14,17`。图标不可见。

### FE-P2-8：redesign-pages.css 硬编码 rgba()

位置：`redesign-pages.css:1244`。`rgba(0,0,0,0.1)` 应使用 shadow token。

### FE-P2-9：CpConfirm.show title 经 escHtml + textContent 双重转义

位置：`tags.html:298-299`。标签名含 `<` 时显示转义实体。

### FE-P2-10：重复的 document-level dropdown-close 监听

位置：`dashboard.html:206-213`, `execution_logs.html:104-108`。

### FE-P2-11：执行记录 "复制ID"/"展开内容" 仅 click 无键盘支持

位置：`execution_logs.html:185-199`。

## 七、测试覆盖盲区（关键路径）

| 领域 | 缺口 |
| --- | --- |
| API scope 持久化 | 无 HTTP 级测试验证 operator 创建的任务落入正确组（**直接导致 BE-P0-1 未被发现**） |
| Scheduler/DB 一致性 | 无测试覆盖 `register_cron_job()` 失败后的补偿 |
| Retire 事务顺序 | 无测试模拟 `commit` 失败后 `remove_job` 已执行的场景 |
| Job log 内容脱敏 | 无断言验证 `job_log.content` 中不含异常类名 |
| DNS 失败 SSRF | 无测试验证 DNS 解析失败时阻止执行 |
| API 读权限 | `TestApiRolePermission` 仅覆盖 POST |

## 八、R7 整体评价

经过 R1–R6 六轮安全/质量修复，项目核心 RBAC/API 防护已达到较好水平：
scope 写入校验、POST 角色权限、登录限流、CSRF on admin POST、scope 缓存形状一致性等关卡已就位。

本轮发现的唯一 P0 是 **B-15 scope 注入→持久化断裂**——功能隔离 bug 而非安全漏洞，
但对多租户场景影响严重。P1 层面后端集中在 scheduler/DB 事务一致性和历史遗留的 GET 语义问题；
前端集中在无障碍（a11y）短板和交互健壮性。

前端 **无新 P0**，Redesign 模板安全基线良好（自动转义 + CSRF + samesite）。

## 九、建议行动优先级

| 优先级 | 批次 | 工作量 | 内容 |
| --- | --- | --- | --- |
| P0 | BE-P0-1 修复 | ~30min | API scope 持久化修复 + 端到端测试 |
| P1 | 后端安全批次 | ~2h | BE-P1-1 job\_log 脱敏 + BE-P1-2 DNS 拒绝 + BE-P1-5 GET→POST |
| P1 | 后端一致性批次 | ~1h | BE-P1-3 scheduler 补偿 + BE-P1-4 retire 事务顺序 |
| P1 | 前端 a11y 批次 | ~2h | FE-P1-2～5 键盘/ARIA 改进 |
| P1 | 前端交互批次 | ~1h | FE-P1-1 Esc 冲突 + FE-P1-7 fetch r.ok + FE-P1-6 escHtml + FE-P1-9 clipboard |
| P2 | 技术债务 | ~3h | AJAX 模块提取、inline JS 外移、label for/id 等 |

[文档索引](../../index.html) · [Markdown](Redesign代码质量全面评估报告-R7-2026-08.md) · [索引](../../index.html)

---

[← 文档索引（HTML）](../../index.html) · [← 文档索引（Markdown）](../../index.md)
