# CronPilot — Agent 指南

本仓库 AI 协作规范见 `**.cursor/rules/**`（Cursor 自动加载）：


| 规则文件                           | 作用                                           |
| ------------------------------ | -------------------------------------------- |
| `cronpilot-project.mdc`        | 项目定位、仓库边界、路线图、Git/测试总则（始终生效）                 |
| `cronpilot-backend.mdc`        | 后端安全、服务层、API 与 `/docs` 路由；**新增枚举值扩展检查清单**（强制）|
| `cronpilot-documentation.mdc`  | HTML+Markdown 双格式文档与 CI 同步                   |
| `cronpilot-release-deploy.mdc` | 非 Docker 部署、发布与 GitHub CI                    |
| `rbac.mdc`                     | RBAC v4（OPT-P2-10；login/has_perm、三角色分权始终启用；见详设） |


**协作闭环（强制）**：**设计 → 用户确认 → 实现 → 复盘（凡有修复） → 验证 → 可验证本地环境 → 文档 → commit**。确认前禁止写实现代码。「请完成 XX」不等于设计已确认。详 `.cursor/rules/cronpilot-project.mdc`「设计先行」「交付闭环」。

**所有修复必须复盘（强制）**：**修复了问题 ≡ 必须复盘**，无论来源（用户报告 / 自查审计 / Review 发现 / CI 失败）。交付回复必须包含 **7 项要素**：Bug 定位 → 根因 → 测试漏洞 → 修复 → 防护测试 → 同类排查 → **预防方案**（≥1 项可落地措施 + 明确落地位置）。**预防方案是复盘的核心目的**——缺少预防方案的复盘等于没有复盘。**在给出 AskQuestion 下一步选项之前，必须自检**：本轮是否执行了修复动作？有 → 先输出复盘再给选项；无 → 可直接给选项。详 `.cursor/rules/cronpilot-project.mdc`「Bug 修复复盘」。

**编号读法**：OPT（功能）/ Tier（依赖大阶段）/ Phase（ORM·框架子阶段）/ DEC（RFC 决策）不是同一套号。权威页：`doc/需求编号与缩写规范.html`。对外须写全称，如 `OPT-P1-03`、`Phase D3（OPT-P2-11）`。

依赖升级路线（OPT-P2-11）：`doc/deps/依赖升级RFC.html` — Tier 0–2 ✓ → Phase A/B/C ✓ → Phase D0/D1/D2 ✓ → **下一依赖动作 Phase D3** → Tier 3b/3c。

**交付总览**：`doc/交付状态与路线图.html` — 已发布版本、已完成 OPT/RFC 与未完成项对照。

**优化 / 功能 / UI**：一律设计确认后再改代码（含无 UI 的依赖/模型/Repo 等工作）；管理端 Ajax 表单须 `js-ajax-form` + `js-ajax-submit`（对照 `cron_add.html`）；静态门禁 `tests.test_ajax_form_guard`；仅测 JSON **不算** UI 交付。

**表单防重复提交（强制）**：所有 POST 表单须有防重复提交保护。`js-ajax-form` 已有 `common.js` loading 守卫；非 Ajax POST 表单由 `common.js` 全局守卫自动保护（`cp-submitting` 标记）。独立页面（不继承 `admin_base.html`）须显式引入 `common.js`。静态门禁 `tests.test_ajax_form_guard.TestAntiDoubleSubmitGuard`。

**大文件修改前结构分析（强制）**：修改 300+ 行的 JS/Python/模板文件前，必须用 AST 或手动追踪 `{}`/`def`/`class` 嵌套确认插入点的实际作用域；插入后须在运行时（CDP/`python -c`）确认代码在预期时机执行，禁止仅靠静态 `grep` 判断。详 `.cursor/rules/cronpilot-project.mdc`「大文件修改前结构分析」。

**表单交互变更影响分析（强制）**：改 button type、引入模态框确认、改用 AJAX 提交等表单交互变更时，必须 `grep` 全局 JS（`common.js` 等）中 `[type="submit"]`、`form:not(...)` 等选择器的监听，确认改动后选择器仍能匹配；明确提交方式（原生 `form.submit()` vs jQuery `.submit()`）与全局守卫的交互结果；**端到端验证必须覆盖「填写→模态→确认→跳转/响应」全流程**。详 `.cursor/rules/cronpilot-project.mdc`「表单交互变更影响分析」。

**策略变更影响分析（强制）**：引入或修改业务策略（如"停用不可恢复"、权限限制等）时，必须 grep 策略影响字段的**所有赋值点**，逐点加固或文档说明豁免原因；为每个修改入口编写独立测试；检查同类函数的逻辑一致性；回溯设计文档中策略相关描述。禁止仅在"最显眼"的入口加策略而忽略间接修改路径。详 `.cursor/rules/cronpilot-project.mdc`「策略变更影响分析」。

**本地预览必重启**：本地以 `debug=False` / `use_reloader=False` 常驻，**改模板或 Python 后「刷新浏览器」无效**。对外让用户看效果前必须 `bash scripts/cronpilot.sh restart --daemon`，并用登录会话 curl/浏览器断言新文案或 class。**重启后须先 `curl -s http://127.0.0.1:5001/rbac/login -w "%{http_code}"` 确认 200**，排除 DB 表缺失等全局 500，再进入功能验收。详见 `.cursor/rules/cronpilot-project.mdc`「本地进程与热更新」。

**交付后可验证本地环境（强制）**：宣称交付前须 restart、给出 **URL + 登录方式 + 可执行验收步骤与期望断言**，并在回复中附 **Agent 自证输出**；默认**保持服务运行**供用户复验。禁止只报「单测通过」。详 `.cursor/rules/cronpilot-project.mdc`「交付后可验证本地环境」。

**大变更浏览器关键路径验证（强制）**：凡涉及 RBAC 鉴权、Scope 过滤、权限矩阵、导航/页面可见性等大变更（≥3 文件或涉及权限/可见性语义），必须用**目标角色账号**在浏览器中验证正向+反向路径并截图留证。禁止仅用种子 admin 或 curl 200 宣称通过。详 `.cursor/rules/cronpilot-project.mdc`「大变更浏览器关键路径验证」。

**GitHub Release 文案（强制）**：Release title / notes 统一使用**专业英文**（结构化写 `What changed` / `Why` / `Validation` / `Compatibility & Risk`），禁止口语化或中英混杂标题。该规范已落库于 `.cursor/rules/cronpilot-project.mdc`。

**颜色规范（强制）**：模板和 Vue 组件中**禁止硬编码十六进制颜色**（`#xxxxxx`），必须使用 `app/static/css/console-theme.css` 中定义的 CSS 变量（`var(--cp-*)`）。新增颜色需先在 `console-theme.css` 的 `:root` 中定义对应语义变量，再引用。CI 门禁 `scripts/audit_hardcoded_colors.py --check` 会阻断含硬编码颜色的 PR。

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
bash scripts/ensure_business_tables.sh   # SQLite/MySQL 业务库建表补列（生产启动亦会调用）
bash scripts/verify_golden_path.sh          # 裸机 SQLite 黄金路径
bash scripts/verify_docker_compose.sh --keep-running   # docker compose 黄金路径
bash scripts/verify_all.sh               # 全量验收（含黄金路径）
bash scripts/verify_all.sh --local-only
bash scripts/verify_all.sh --docker-fresh  # Docker 空库 + changeme 登录冒烟
bash scripts/assert_framework_pins.sh   # Phase D3：断言 Framework pin 与 requirements.txt 一致
python scripts/audit_hardcoded_colors.py --check  # 颜色审计：检查模板/Vue 中是否有硬编码颜色
python scripts/audit_hardcoded_colors.py --mapping # 查看色值→令牌完整映射表
python scripts/check_version_consistency.py --check  # 版本一致性：git tag vs README/路线图/RELEASE_NOTES + Unreleased 残留 + 版本总览表
python scripts/check_doc_completeness.py --check    # 文档完整性：doc/*.html 是否在 index.html 中注册
python scripts/check_doc_links.py --check           # 全仓库文档链接可达性（README/INSTALL/.cursor/rules/ → doc/）
python scripts/check_opt_consistency.py --check     # OPT 编号一致性 + 设计文档状态 vs 路线图对照
python scripts/html_docs_to_markdown.py --check
bash scripts/check_pending_sync.sh
```

**JS hidden input 命名冲突防护（强制）**：凡 JS 动态追加 `<input type="hidden" name="xxx">`，必须检查同表单内无同名可见 input，如有则移除可见 input 的 `name`，确保隐藏 input 独占字段名（Flask `request.form.get()` 返回第一个同名值，可见 input 在前导致后端拿到空值）。

**Import 可达性验证（强制）**：编写 `from xxx import yyy` 前**必须** `grep` 确认 `yyy` 在目标模块中存在，禁止凭记忆写 import。`tests/test_import_smoke.py` 覆盖所有 Blueprint 路由模块的顶层 import。

**复盘质量门禁（强制）**：预防方案必须①新增可验证措施（非「已有规范应执行」）、②可被第三方重现验证（给出路径+命令）、③根因追到行为层（非「粗心」）、④与根因因果对应。不合格须重写。

**复盘文档化（强制）**：所有复盘必须持久化到文档（`doc/design/*.html`、`doc/rfc/*.html` 或 `doc/postmortem/YYYY-MM-功能名.html`），并确保 HTML↔Markdown 同步。涉及用户可感知变更的复盘须记入 `RELEASE_NOTES.md`。禁止复盘只在对话中给出而不落库。

**浏览器验证自动化（强制）**：凡涉及 UI/模板/前端交互的变更，功能完成后**必须自动执行浏览器验证**（含自动登录、操作、截图），不得询问用户"是否需要验证"。登录切换账号等操作属于验证准备工作，无需用户确认。

**AJAX 响应字段名规范（强制）**：本项目前端 AJAX `success` 回调中必须使用 `r.errcode` / `r.errmsg`（对应 `web_api_return()` 的 `errcode/errmsg`），禁止使用 `r.code` / `r.msg`。

**JS keydown 可打印字符拦截（强制）**：`keydown` 中拦截可打印字符（空格、逗号等）时，`e.preventDefault()` 后必须附加 `setTimeout(function() { $input.val(''); }, 0)` 二次清除，防止部分浏览器在事件循环下一 tick 仍插入字符。

**CDP 验证局限性声明（强制）**：涉及 JS 键盘交互修复时，不得仅凭 CDP 自动化验证宣称"已修复"。CDP 键盘模拟不走浏览器完整 input 事件管道，需明确告知用户"需手动确认键盘行为"。

**AskQuestion 前置门禁（强制）**：Agent 在 invoke `AskQuestion` 之前必须自检"本轮是否有修复性变更？如有，是否已包含 7 项复盘要素？"缺失则先补复盘再提问。**修复 = 改代码 + 测试通过 + 复盘**，三者为原子整体，缺一不可。适用于所有修复（含自发现的问题、文案/文档修正）。

**勿改**：上游 `xiaoniu_cron` 仓库（除非用户明确要求）。