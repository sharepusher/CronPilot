# CronPilot — Agent 指南

本仓库 AI 协作规范见 `**.cursor/rules/**`（Cursor 自动加载）：


| 规则文件                           | 作用                                           |
| ------------------------------ | -------------------------------------------- |
| `cronpilot-project.mdc`        | 项目定位、仓库边界、路线图、Git/测试总则（始终生效）                 |
| `cronpilot-backend.mdc`        | 后端安全、服务层、API 与 `/docs` 路由；**新增枚举值扩展检查清单**（强制）|
| `cronpilot-documentation.mdc`  | HTML+Markdown 双格式文档与 CI 同步                   |
| `cronpilot-release-deploy.mdc` | 非 Docker 部署、发布与 GitHub CI                    |
| `rbac.mdc`                     | RBAC v4（OPT-P2-10；login/has_perm、三角色分权始终启用；见详设） |


**协作闭环（强制）**：**设计文档（`doc/design/*.html`） → 用户 Review 并明确确认 → 实现 → 复盘（凡有修复） → 验证 → 可验证本地环境 → 文档 → commit**。**所有功能和页面变更（含 CSS/JS 代码质量修复）必须先创建正式设计文档（`doc/design/*.html`），禁止仅在聊天中给出设计而不落库**。设计文档须包含 7 项必备要素（问题/根因/方案/范围/分批/验收/风险）。用户要求补充信息（如对比图、影响分析等）时，须补充后**再次等待明确确认**，不得在补充过程中开始实现。确认前禁止写实现代码。「请完成 XX」不等于设计已确认。详 `.cursor/rules/cronpilot-project.mdc`「设计先行」「交付闭环」。

**所有修复必须复盘（强制）**：**修复了问题 ≡ 必须复盘**，无论来源（用户报告 / 自查审计 / Review 发现 / CI 失败）。交付回复必须包含 **7 项要素**：Bug 定位 → 根因 → 测试漏洞 → 修复 → 防护测试 → 同类排查 → **预防方案**（≥1 项可落地措施 + 明确落地位置）。**预防方案是复盘的核心目的**——缺少预防方案的复盘等于没有复盘。**在给出 AskQuestion 下一步选项之前，必须自检**：本轮是否执行了修复动作？有 → 先输出复盘再给选项；无 → 可直接给选项。详 `.cursor/rules/cronpilot-project.mdc`「Bug 修复复盘」。

**编号读法**：OPT（功能）/ Tier（依赖大阶段）/ Phase（ORM·框架子阶段）/ DEC（RFC 决策）不是同一套号。权威页：`doc/需求编号与缩写规范.html`。对外须写全称，如 `OPT-P1-03`、`Phase D3（OPT-P2-11）`。

依赖升级路线（OPT-P2-11）：`doc/deps/依赖升级RFC.html` — Tier 0–2 ✓ → Phase A/B/C ✓ → Phase D0/D1/D2 ✓ → **下一依赖动作 Phase D3** → Tier 3b/3c。

**交付总览**：`doc/交付状态与路线图.html` — 已发布版本、已完成 OPT/RFC 与未完成项对照。

**优化 / 功能 / UI**：一律设计确认后再改代码（含无 UI 的依赖/模型/Repo 等工作）；管理端 Ajax 表单须 `js-ajax-form` + `js-ajax-submit`（对照 `cron_add.html`）；静态门禁 `tests.test_ajax_form_guard`；仅测 JSON **不算** UI 交付。

**表单防重复提交（强制）**：所有 POST 表单须有防重复提交保护。`js-ajax-form` 已有 `common.js` loading 守卫；非 Ajax POST 表单由 `common.js` 全局守卫自动保护（`cp-submitting` 标记）。独立页面（不继承 `admin_base.html`）须显式引入 `common.js`。静态门禁 `tests.test_ajax_form_guard.TestAntiDoubleSubmitGuard`。

**Redesign JS 依赖规则（强制 · F5）**：Redesign `_base.html` 使用 `common-redesign.js` 替代 `common.js` + `wind.js`。**jQuery 必须同步加载（无 `defer`）**——inline `<script>` 中的 `$(function(){})` 依赖 `$` 在解析时可用。其他 Redesign 模块（common-redesign, shell, theme, toast, confirm）使用 `defer`，因为它们仅通过 DOM ready 回调或用户事件访问。**禁止**在 `_base.html` 的 `jquery.js` 标签上添加 `defer`/`async`。自检：`grep 'defer.*jquery\|async.*jquery' app/templates/redesign/_base.html && echo "FAIL" || echo "OK"`。**违反教训**：2026-08 F5 保留了 Phase R5 添加的 `defer`，导致 API Token 页面 Copy/Reset 按钮完全失效，详见 `doc/postmortem/2026-08-F5-jQuery-defer-inline-script.html`。

**表单必填字段标注规范（强制）**：必填字段必须在 `<label>` 内用 `<span class="uf-req">*</span>` 标注，禁止在 label 外单独添加「必填」文字 span 或使用 inline style 标明必填；下拉 placeholder option 不写「（必填）」。验证命令：`grep -n '必填' app/templates/redesign/user_form.html` 应只出现在 hint 描述文本内，而非独立 span 标签中。

**大文件修改前结构分析（强制）**：修改 300+ 行的 JS/Python/模板文件前，必须用 AST 或手动追踪 `{}`/`def`/`class` 嵌套确认插入点的实际作用域；插入后须在运行时（CDP/`python -c`）确认代码在预期时机执行，禁止仅靠静态 `grep` 判断。详 `.cursor/rules/cronpilot-project.mdc`「大文件修改前结构分析」。

**连续 StrReplace 后必须读回验证（强制 · 2026-08 路由丢失事故教训）**：对同一文件连续执行 ≥ 2 次 StrReplace 时，每次替换完成后**必须 Read 受影响行（±20 行）**确认关键装饰器/语句未被下一次替换覆盖或消除。验证路由完整性：`python scripts/check_route_completeness.py --check app/rbac/views.py`。**跨批次重命名后**，须 `rg` 全仓库确认被调用方的旧方法名/旧属性名不存在于任何调用方中。自检：`rg "旧方法名" app/ --glob '*.py' && echo FAIL || echo OK`。**违反教训**：2026-08 B2 重命名 Repo 方法后，B4 未同步 views.py 调用方，导致详情页 500。

**关键路由冒烟测试（强制 · 2026-08 trace_id 重命名事故教训）**：凡涉及跨层重命名（model→service→repo→view→template）、Jinja2 filter 注册变更、模板语法变更等影响渲染链路的改动，实现完成后必须运行 `python scripts/smoke_routes.py --check` 确认 86 条路由（v1+v2 双版本，含 GET/POST/API/错误路径）渲染无 500。对运行中的服务可用 `--live` 模式。该脚本覆盖 view→repo→model→template 完整链路，弥补单元测试无法覆盖的盲区。**违反教训**：2026-08 `log_id → trace_id` 跨 5 批重命名，单元测试全通过但详情页 500，因 `views.py` 调用了已重命名的 Repository 方法。

**表单交互变更影响分析（强制）**：改 button type、引入模态框确认、改用 AJAX 提交等表单交互变更时，必须 `grep` 全局 JS（`common.js` 等）中 `[type="submit"]`、`form:not(...)` 等选择器的监听，确认改动后选择器仍能匹配；明确提交方式（原生 `form.submit()` vs jQuery `.submit()`）与全局守卫的交互结果；**端到端验证必须覆盖「填写→模态→确认→跳转/响应」全流程**。详 `.cursor/rules/cronpilot-project.mdc`「表单交互变更影响分析」。

**禁止 form 嵌套（强制 · 2026-08 change_password 事故教训）**：HTML5 规范禁止 `<form>` 嵌套。浏览器会忽略内层 `<form>` 开标签，导致内层 submit 按钮触发外层表单提交。需要在表单内放置独立 POST 操作时，使用 `<button type="button">` + JS 动态创建 form 并 `document.body.appendChild(f); f.submit()` 提交。自检：`rg -c '<form' app/templates/redesign/*.html | awk -F: '$2 > 1 {print "CHECK:", $1}'`。详见 `doc/postmortem/2026-08-change-password-nested-form.html`。

**策略变更影响分析（强制）**：引入或修改业务策略（如"停用不可恢复"、权限限制等）时，必须 grep 策略影响字段的**所有赋值点**，逐点加固或文档说明豁免原因；为每个修改入口编写独立测试；检查同类函数的逻辑一致性；回溯设计文档中策略相关描述。禁止仅在"最显眼"的入口加策略而忽略间接修改路径。**新功能路由 scope 对齐**：凡新增 `@require_permission` 路由，必须检查同模块已有路由是否使用了 `_actor_bypasses_scope()` scope 校验，若有则新路由必须对齐。防护测试：`python3 -m unittest tests.test_tag_scope -v`（9 条用例）。**违反教训**：2026-08 标签 CRUD 路由开发时未对齐组管理路由已有的 scope 检查（S3）。详 `.cursor/rules/cronpilot-project.mdc`「策略变更影响分析」。

**本地预览必重启**：本地以 `debug=False` / `use_reloader=False` 常驻，**改模板或 Python 后「刷新浏览器」无效**。对外让用户看效果前必须 `bash scripts/cronpilot.sh restart --daemon`，并用登录会话 curl/浏览器断言新文案或 class。**重启后须先 `curl -s http://127.0.0.1:5001/rbac/login -w "%{http_code}"` 确认 200**，排除 DB 表缺失等全局 500，再进入功能验收。详见 `.cursor/rules/cronpilot-project.mdc`「本地进程与热更新」。

**交付后可验证本地环境（强制）**：宣称交付前须 restart、给出 **URL + 登录方式 + 可执行验收步骤与期望断言**，并在回复中附 **Agent 自证输出**；默认**保持服务运行**供用户复验。禁止只报「单测通过」。详 `.cursor/rules/cronpilot-project.mdc`「交付后可验证本地环境」。

**大变更浏览器关键路径验证（强制）**：凡涉及 RBAC 鉴权、Scope 过滤、权限矩阵、导航/页面可见性等大变更（≥3 文件或涉及权限/可见性语义），必须用**目标角色账号**在浏览器中验证正向+反向路径并截图留证。禁止仅用种子 admin 或 curl 200 宣称通过。详 `.cursor/rules/cronpilot-project.mdc`「大变更浏览器关键路径验证」。

**Redesign 侧边栏角色权限回归（强制 · 2026-08）**：凡修改 `app/templates/redesign/_sidebar.html`、`app/rbac/policy.py`、`app/rbac/context.py` 或权限字符串定义，必须运行 `python -m unittest tests.test_redesign_sidebar -v` 确认 4 种角色（Seed Admin / Biz Admin / Operator / Viewer）的导航可见性与反向 403 拦截均符合预期。回归测试覆盖内容：

| 角色 | 预期可见导航数 | 关键拦截点 |
|------|:-----------:|----------|
| Seed Admin | 12 | 全管理权限，无 `cron:write`/`cron:retire` |
| Biz Admin | 12 | 与 Seed Admin 同（带组分配） |
| Operator | 7 | 403: `/rbac/users`、`/rbac/audit`；允许: `/cron_add` |
| Viewer | 6 | 403: `/cron_add`、`/rbac/users`、`/operation_log_list` |

**GitHub Release 文案（强制）**：Release title / notes 统一使用**专业英文**（结构化写 `What changed` / `Why` / `Validation` / `Compatibility & Risk`），禁止口语化或中英混杂标题。该规范已落库于 `.cursor/rules/cronpilot-project.mdc`。

**颜色规范（强制）**：模板和 Vue 组件中**禁止硬编码十六进制颜色**（`#xxxxxx`），必须使用 `app/static/css/console-theme.css` 中定义的 CSS 变量（`var(--cp-*)`）。新增颜色需先在 `console-theme.css` 的 `:root` 中定义对应语义变量，再引用。CI 门禁 `scripts/audit_hardcoded_colors.py --check` 会阻断含硬编码颜色的 PR。

**Redesign CSS 归属（强制）**：Redesign 模板中 `<style>` 块内非注释 CSS 行**不得超过 3 行**（CI 门禁 `check_ui_contract.py --check` 拦截 `inline-css-volume` 违规）。新增/修改 CSS 按决策树归档：Design Token → `console-theme.css` / 通用组件 → `redesign-components.css` / Layout → `redesign-layout.css` / 跨页面表格 → `redesign-mockup-shared.css` / 认证页 → `redesign-auth.css` / **页面专属 → `redesign-pages.css` + `.cp-page-xxx` 作用域**。新页面必须声明 `{% block main_class %} cp-page-xxx{% endblock %}`。详 `.cursor/rules/cronpilot-format-guard.mdc`「Redesign CSS 归属约束」。

**数据库字段删除/迁移前置分析（强制）**：凡涉及删除、迁移、合并数据库字段，设计文档中必须对**每个被操作字段**逐行回答：① 该字段的独立语义是什么？② 该语义是否被新结构完全等价表达？③ 如果删除是否存在无法区分的状态？禁止因字段在代码中常一起出现就当一个整体处理。

**验证自主性原则（强制）**：验证阶段遇到的技术障碍（缺测试用户/权限/数据），Agent **必须自行解决**，不得弹 AskQuestion 询问用户。创建测试用户、重置密码、准备测试数据等操作必须自主完成。AskQuestion 仅用于需求歧义澄清、等价方案偏好选择、破坏性操作授权。

**迁移脚本双后端兼容（强制）**：`ensure_business_tables.py` 等迁移脚本中的原生 SQL 必须通过 `business_db_backend()` 判断后端，分别写 SQLite / MySQL 语法。禁止仅在 SQLite 开发环境验证就提交。

**API 返回结构变更标注（强制）**：任何 API 字段增删改必须在 RELEASE_NOTES 标注 `⚠️ API Breaking Change`。commit 前 `git diff -- app/api/` 检查字段变化。

**模板兜底值语义化（强制）**：模板 `.get(key, default)` 中禁止 default 为空字符串 `''`，必须使用有语义的兜底文案（`—`、`未知`等）。

**测试数据库隔离（强制 · 2026-08 事故教训）**：测试文件中**严禁** `from manage import app` 或 `from manage import db`（`manage.py` 在模块级别 `create_app('development')` 绑定开发数据库）。所有测试必须使用 `sqlite:///:memory:`。改动测试文件后须在测试完成后 `sqlite3 datas/job_log.sqlite ".tables"` 确认表未被破坏。交付前须 `cronpilot.sh restart` → 浏览器 **POST 登录**（非仅 GET）→ 确认主页正常。详 `.cursor/rules/cronpilot-project.mdc`「测试数据库隔离」。

**快速命令**

```bash
sudo bash scripts/install_linux.sh --production   # Linux 裸机
bash scripts/cronpilot.sh start --daemon   # 自动匹配 Python 3.8–3.11
bash scripts/cronpilot.sh restart --daemon # 改代码/模板后必跑（先停后启，默认 --force）
bash scripts/cronpilot.sh stop
bash scripts/cronpilot.sh test
ruff check app/                            # Python lint 门禁（E/W/F/I 规则，0 违规）
python -m unittest tests.test_redesign_sidebar -v  # Redesign 侧边栏 4 角色权限回归
python -m unittest tests.test_rbac_scope.TestScopeIntegration -v  # Scope 隔离回归（含多组/Biz Admin）
bash scripts/ensure_business_tables.sh   # SQLite/MySQL 业务库建表补列（生产启动亦会调用）
bash scripts/verify_golden_path.sh          # 裸机 SQLite 黄金路径
bash scripts/verify_docker_compose.sh --keep-running   # docker compose 黄金路径
bash scripts/verify_all.sh               # 全量验收（含黄金路径）
bash scripts/verify_all.sh --local-only
bash scripts/verify_all.sh --docker-fresh  # Docker 空库 + changeme 登录冒烟
bash scripts/assert_framework_pins.sh   # Phase D3：断言 Framework pin 与 requirements.txt 一致
python scripts/audit_hardcoded_colors.py --check  # 颜色审计：检查模板/Vue 中是否有硬编码颜色
python scripts/audit_hardcoded_colors.py --mapping # 查看色值→令牌完整映射表
python scripts/check_ui_contract.py --check        # UI 契约门禁：inline-style / legacy-class / inline-css-volume（≤3 行）/ a11y-button / a11y-input
python scripts/check_dead_css.py --check            # CSS 死代码检测：components.css 中每个类须有模板/JS 消费者
python scripts/check_css_token_reachability.py --check  # CSS token 可达性：var(--cp-*) 定义存在 + animation-name 有 @keyframes
python scripts/check_version_consistency.py --check  # 版本一致性：git tag vs README/路线图/RELEASE_NOTES + Unreleased 残留 + 版本总览表
python scripts/check_doc_completeness.py --check    # 文档完整性：doc/*.html 是否在 index.html 中注册
python scripts/check_doc_links.py --check           # 全仓库文档链接可达性（README/INSTALL/.cursor/rules/ → doc/）
python scripts/check_opt_consistency.py --check     # OPT 编号一致性 + 设计文档状态 vs 路线图对照
python scripts/check_postmortem_completeness.py --check  # 复盘文档化完整性：HTML↔MD + RELEASE_NOTES 引用 + 代码变更同步
python scripts/check_brand_svg_consistency.py --check  # 品牌 SVG include 链完整性：_brand_paths → _brand_block/sidebar → 4 auth 模板
python scripts/smoke_routes.py --check             # 关键路由冒烟：86 条路由 v1+v2 含 GET/POST/API/错误路径（跨层重命名/模板变更后必跑）
python scripts/smoke_routes.py --live --check      # 对运行中的服务做 HTTP 冒烟（16 条非 seed 路由）
python scripts/html_docs_to_markdown.py --check
bash scripts/check_pending_sync.sh
```

**JS hidden input 命名冲突防护（强制）**：凡 JS 动态追加 `<input type="hidden" name="xxx">`，必须检查同表单内无同名可见 input，如有则移除可见 input 的 `name`，确保隐藏 input 独占字段名（Flask `request.form.get()` 返回第一个同名值，可见 input 在前导致后端拿到空值）。

**Ruff lint 门禁（强制 · 2026-08）**：`ruff check app/` 必须通过（0 违规）。凡 commit 涉及函数废弃、变量移除、模板参数删减、import 变更，须在提交前运行 `ruff check app/` 确认无新增 F841（未使用变量）/ F811（未使用导入）/ F821（不可达代码）违规。配置：`pyproject.toml`（select E/W/F/I；target py38）。CI：`.github/workflows/ruff-lint.yml`。**违反教训**：2026-08 重命名事件中多次引入未使用 import 和废弃变量残留，手动 review 均未发现，ruff 一次扫描即全捕获。

**Import 可达性验证（强制）**：编写 `from xxx import yyy` 前**必须** `grep` 确认 `yyy` 在目标模块中存在，禁止凭记忆写 import。`tests/test_import_smoke.py` 覆盖所有 Blueprint 路由模块的顶层 import。

**复盘质量门禁（强制）**：预防方案必须①新增可验证措施（非「已有规范应执行」）、②可被第三方重现验证（给出路径+命令）、③根因追到行为层（非「粗心」）、④与根因因果对应。不合格须重写。

**复盘文档化（强制）**：所有复盘必须持久化到文档（`doc/design/*.html`、`doc/rfc/*.html` 或 `doc/postmortem/YYYY-MM-功能名.html`），并确保 HTML↔Markdown 同步。涉及用户可感知变更的复盘须记入 `RELEASE_NOTES.md`。禁止复盘只在对话中给出而不落库。

**禁止在中间整合文档中重复源文档数值（强制）**：凡创建/编辑「整合型文档」（手册/索引/总结），禁止将源文档中的精确数值（色值、字号、间距等）复制到整合文档中。整合文档只允许包含架构决策 + 源文档定位索引。实现代码必须 `Read` 源文档获取数值，禁止从整合文档或记忆中获取。详 `.cursor/rules/cronpilot-project.mdc`「禁止在中间整合文档中重复源文档数值」。

**浏览器验证自动化（强制）**：凡涉及 UI/模板/前端交互的变更，功能完成后**必须自动执行浏览器验证**（含自动登录、操作、截图），不得询问用户"是否需要验证"。登录切换账号等操作属于验证准备工作，无需用户确认。

**Redesign 确认对话框规范（强制）**：Redesign 页面（`app/templates/redesign/`）中，凡需弹出对话框，必须使用以下方式，**严禁 Bootstrap modal**：
- **危险确认**（删除/重置等）：`CpConfirm.show()` API（`redesign-confirm.js`）— 对话框正文必须使用 **`body:`** 属性（**禁止 `message:`**，API 不识别该属性，正文将渲染为空白）
- **表单型对话框**（含输入框/选择器）：页面内自定义 `CpModal(opts)` 工厂函数（使用 `.cp-modal-overlay` / `.cp-modal` 结构，见 `tags.html`）
- **禁止**：`$().modal('show')` / `bootstrap.min.js` / `bootstrap.min.css`（Bootstrap modal 在 redesign shell 中 CSS 命名空间冲突，对话框不可见）
- **CI 自检命令**：`grep -r "\.modal('show')\|bootstrap.min" app/templates/redesign/ && echo "FAIL: Bootstrap modal detected" || echo "OK"`
- **CpConfirm 参数自检**：`grep -rn "CpConfirm.show" app/templates/ | grep "message:" && echo "FAIL: use body: not message:" || echo "OK"`
- **E2E 验证要求**：改动对话框后必须 CDP click 触发 + 检查 snapshot 中对话框 heading/按钮出现，禁止仅凭"DOM 中有按钮"宣称可用

**querySelector CSS class 可达性（强制）**：模板中 `document.querySelector('.xxx')` 引用的 CSS class 必须先 `grep` 确认在 CSS 文件或 JS 创建的 DOM 中有实际定义。禁止凭记忆或假设的 class 名编写选择器。自检命令：`grep -rn "cp-confirm-overlay" app/templates/ && echo "FAIL: non-existent class" || echo "OK"`。**违反教训**：2026-08 Escape 键守卫使用了不存在的 `.cp-confirm-overlay`（实际为 `.cp-modal-overlay`），导致对话框打开时按 Escape 仍触发页面导航。

**异常信息脱敏（强制）**：`except Exception` 的 catch-all 分支中，**禁止** `web_api_return(msg=str(e))` 或 `api_return(errmsg=str(e))` 将异常原始文本返回前端/API 调用方。必须返回通用错误信息（如 `'服务器内部错误，请稍后重试'`），异常详情仅写入 `current_app.logger.error` 或 `logging.getLogger().error()`。自检：`grep -rn "errmsg=.*str(e)\|msg=str(e)" app/ | grep -v "logger\|logging" && echo FAIL || echo OK`（注意搜索范围是整个 `app/` 目录，不限于特定文件）。**违反教训**：2026-08 P0-3 修复 `cron_add` 的 `str(e)` 时搜索范围仅限 `main/views.py` + `rbac/views.py`，遗漏了 `decorated.py` 中 API 装饰器的同源问题（S5）。

**配置读取异常必须拒绝而非放行（强制 · 2026-08 安全审计）**：凡在 `except Exception` 中处理配置文件读取（`configs()`、`conf.ini` 解析等）失败，**禁止**降级为"放行"或"赋予高权限"。**必须**返回拒绝响应（HTTP 500/401）+ `logger.error(exc_info=True)`。原则：基础设施故障时倾向"拒绝/限制"而非"放行/提权"。自检：`grep -n "request._api_scope.*admin" app/api/__init__.py | grep -c "except" && echo WARN || echo OK`。**违反教训**：2026-08 `_api_token_guard()` 配置读取失败时赋予 admin 权限并放行所有 API 请求。详 `.cursor/rules/cronpilot-backend.mdc`。

**innerHTML XSS 防护（强制 · S4）**：模板 JS 中凡从 `data-*` / `dataset` 取值后拼入 `innerHTML` / `bodyHtml`，**必须**经 `escHtml()` 转义或改用 `textContent` + DOM API。Jinja2 自动转义仅保护 HTML 解析阶段，浏览器解码后 jQuery `.data()` 返回原始字符串 → 拼入 innerHTML 即为二次注入。自检：`rg -n "innerHTML\s*=" app/templates/redesign/ | grep -v "= ''" | grep -v escHtml && echo WARN || echo OK`。**违反教训**：2026-08 `registration_review.html` 的 `username` 和 `tags.html` 的 `tagName` 未转义直接拼 HTML，可触发存储型 XSS。

**状态修改操作必须 POST + CSRF（强制 · S1）**：凡状态修改操作（登出、删除、停用、修改等），路由 **必须** 限定 `methods=['POST']`，配合 `@csrf_protect` 装饰器。**禁止**使用 GET 执行状态修改。前端对应的触发元素必须通过隐藏 `<form method="POST">` + CSRF token 提交，或使用 `postNavigate()` 动态构建 POST 表单。自检：`grep -n "methods=\['GET'\]" app/rbac/views.py | grep -v "login\|password\|register\|complete_profile" && echo WARN || echo OK`。防护测试：`.venv-py311/bin/python -m unittest tests.test_logout_csrf -v`（4 条用例）。**违反教训**：2026-08 `/rbac/logout` 接受 GET，攻击者可通过 `<img src="/rbac/logout">` 强制登出已登录用户。

**重定向参数校验（强制 · P0-2 Open Redirect）**：所有 `request.args.get('next')` / `request.values.get('next')` 必须经 `safe_next_url()` 包裹（`from app.rbac.safe_redirect import safe_next_url`）。禁止将用户提供的 `next` 参数直接用于 `redirect()` 或模板渲染。自检：`grep -rn "request\.\(args\|values\)\.get('next" app/ | grep -v safe_next_url && echo FAIL || echo OK`。防护测试：`python3 -m unittest tests.test_safe_redirect -v`（11 条用例）。**违反教训**：2026-08 登录页 `next` 参数未校验，攻击者可构造钓鱼跳转 URL。

**Cookie SameSite 属性（强制 · C1）**：所有 JS 中 `document.cookie = '...'` 写入必须包含 `;samesite=lax`。自检：`rg "document\.cookie\s*=" app/static/js/ app/templates/ | grep -v "samesite" && echo "WARN: missing samesite" || echo "OK"`。

**AJAX 请求 URL 规范（强制 · F1 Dashboard 404 教训）**：模板中 AJAX 请求的 URL **必须**使用 `url_for()` 或与已有调用点（v1 模板 / 同页面其他调用）对齐，禁止凭记忆或惯例构造 URL。CronPilot 后端统一使用 query param / form data 传递 `id`（`request.values.get('id')`），不使用 path param（`/resource/{id}`）。自检：`rg "\.post\('/[a-z_]+/'" app/templates/ && echo "WARN: path-param URL found" || echo "OK"`。**违反教训**：2026-08 Dashboard 三个 AJAX 按钮使用 `/update_status/{id}` 格式导致 404 全部失效，而同项目 `task_detail.html` 已正确使用 `/update_status?id=`。

**AJAX 响应字段名规范（强制）**：本项目前端 AJAX `success` 回调中必须使用 `r.errcode` / `r.errmsg`（对应 `web_api_return()` 的 `errcode/errmsg`），禁止使用 `r.code` / `r.msg`。**后端 except 分支禁止在 code=1 错误响应中携带 `url` 字段**（js-ajax-form 无论 errcode 是否为 1 都会重定向到 data.url，导致用户表单数据丢失）。自检：`grep -n "url.*code=1\|web_api_return.*code=1.*url=" app/main/views.py app/rbac/views.py`，仅允许资源守卫场景（函数顶部非提交路径）。

**Redesign 确认对话框规范（强制）**：所有新增弹窗必须使用全局 `CpConfirm.show()`（简单确认，无 HTML body）或 `CpModal()`（表单/HTML body），**禁止使用 Bootstrap modal（`$().modal('show')` / `bootstrap.min.js/css`）**。两者均已在 `redesign-confirm.js` 中全局注册，无需在页面内重复定义。自检命令：`grep -r "\.modal('show')\|bootstrap.min" app/templates/redesign/ && exit 1 || echo OK`。

**JS keydown 可打印字符拦截（强制）**：`keydown` 中拦截可打印字符（空格、逗号等）时，`e.preventDefault()` 后必须附加 `setTimeout(function() { $input.val(''); }, 0)` 二次清除，防止部分浏览器在事件循环下一 tick 仍插入字符。

**CDP 验证局限性声明（强制）**：涉及 JS 键盘交互修复时，不得仅凭 CDP 自动化验证宣称"已修复"。CDP 键盘模拟不走浏览器完整 input 事件管道，需明确告知用户"需手动确认键盘行为"。

**Redesign Mockup 逐节对照（强制 · 2026-08 追加）**：实现 `doc/design/CronPilot-2026-redesign-mockup.html` 中已定义的任何页面时，必须：① 先 `Read` Mockup 对应 `view-*` 区块的**完整 HTML**（不可凭记忆）；② 列出所有关键结构（CSS class、列数、组件层级、按钮类型）；③ 实现后 `curl + grep` 验证关键 class 存在于渲染 HTML；④ 交付前截图逐区域对照。**违反教训**：2026-08 首次 Phase 2 实现因未逐节对照源码，导致 Exception Panel 完全缺失、7 列降为 5 列、icon 按钮变文字按钮，触发全量重写。

**Redesign 交互回归约束（强制 · 2026-08 追加）**：凡 v1 已有 AJAX 交互的功能（筛选、翻页、搜索），v2 Redesign 必须保持等效或优化交互方式，不得降级为整页刷新。设计文档须包含"交互模式对比"维度（v1 行为 vs v2 行为）。验证命令：`grep -n "onchange.*location.href" app/templates/redesign/dashboard.html | wc -l`（修复后应为 0）。详见 `doc/postmortem/2026-08-Redesign筛选交互降级.html`。

**Mockup 评估权威文件（强制 · 2026-08 追加）**：进行 Mockup 对比评估前，必须先确认参考文件为 `doc/design/CronPilot-2026-redesign-mockup.html`（项目内部设计规格，含完整 view-* 区块）。`Downloads` 目录中的 HTML 文件为外部演示版（简化版），不得作为实施依据。若用户提供 Downloads 路径，必须交叉核查内部文件，以内部文件为准。验证命令：`grep -l "mockup" doc/design/*.html`（应包含 `CronPilot-2026-redesign-mockup.html`）。**违反教训**：2026-08 连续 7 轮评估均错误使用外部简化版 Mockup，导致操作记录目标列数完全相反（5 列 vs 正确的 7 列），详见 `doc/postmortem/2026-08-错误Mockup文件评估复盘.html`。

**Tooltip 分类规范（强制 · 2026-09）**：Redesign 模板中交互按钮（`act-btn`、`um-icon-btn`、`cp-copy-btn`、`cp-theme-btn`、`cp-topbar-icon-btn`）**必须**使用 `data-tooltip="简短文案"`（CSS-only 即时显示），**禁止**使用原生 `title`（800ms+ 延迟）。内容预览 tooltip（截断文本展示，含动态长内容）和侧边栏折叠标签可保持 `title`。自检：`grep -r 'act-btn.*title="[^"]\+"\|um-icon-btn.*title="[^"]\+"\|cp-copy-btn.*title="[^"]\+"' app/templates/redesign/ && echo FAIL || echo OK`（`title=""` 空值为抑制原生 tooltip 的正常用法，不应检出）。详 `.cursor/rules/cronpilot-format-guard.mdc`「Tooltip 分类规范」。

**AskQuestion 前置门禁（强制 + Hook 程序化强制）**：Agent 在 invoke `AskQuestion` 之前必须自检"本轮是否有修复性变更？如有，是否已包含 7 项复盘要素？"缺失则先补复盘再提问。**修复 = 改代码 + 测试通过 + 复盘**，三者为原子整体，缺一不可。适用于所有修复（含自发现的问题、文案/文档修正）。**程序化强制**：`.cursor/hooks.json` 配置了 L1（`postToolUse` 每次编辑后注入提醒）+ L2（`stop` prompt hook 结束前评估是否遗漏复盘）。纯文字规范已被证明反复失效（3+ 次），Hook 为硬约束层。

**勿改**：上游 `xiaoniu_cron` 仓库（除非用户明确要求）。