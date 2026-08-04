# CronPilot — Agent 指南

本仓库 AI 协作规范见 `**.cursor/rules/**`（Cursor 自动加载）：


| 规则文件                           | 作用                                           |
| ------------------------------ | -------------------------------------------- |
| `cronpilot-project.mdc`        | 项目定位、仓库边界、路线图、Git/测试总则（始终生效）                 |
| `cronpilot-backend.mdc`        | 后端安全、服务层、API 与 `/docs` 路由；**新增枚举值扩展检查清单**（强制）|
| `cronpilot-documentation.mdc`  | HTML+Markdown 双格式文档与 CI 同步                   |
| `cronpilot-release-deploy.mdc` | 非 Docker 部署、发布与 GitHub CI                    |
| `rbac.mdc`                     | RBAC v4（OPT-P2-10；login/has_perm、三角色分权始终启用；见详设） |


**协作闭环（强制）**：**清晰完整准确的设计（含分批 + 验收）→ 经用户确认 → 再实现 → 复盘（仅 bug 修复时，实现后、验证前） → 验证 → 可验证本地环境 → 文档 → commit**。确认前禁止写实现代码。「请完成 XX」不等于设计已确认。**Bug 修复复盘是门禁步骤**：必须在同一条回复中写出 `## 复盘：<bug名>` + 6 要素（Bug 定位 / 根因 / 测试漏洞 / 修复 / 防护测试 / 同类排查），缺任一项视为交付不完整。详 `.cursor/rules/cronpilot-project.mdc`「设计先行」「交付闭环」。

**Bug 修复复盘（强制 · 所有问题修复）**：**修复了问题 ≡ 必须复盘**，无论来源（用户报告 / 自查审计 / Review 工具）。交付回复必须包含：Bug 定位 → 根因 → 测试漏洞分析 → 修复 → 防护测试 → 同类排查。批量同根因可合并复盘但不得省略。测试分层须明确（单元 / 集成 / E2E），集成或 E2E 层的 bug 必须在对应层新增测试（`tests/test_*_integration.py`）。**交付前自检**：本轮有修复动作 → 回复中是否有复盘？缺失则先补再发。详 `.cursor/rules/cronpilot-project.mdc`「Bug 修复复盘」。

**编号读法**：OPT（功能）/ Tier（依赖大阶段）/ Phase（ORM·框架子阶段）/ DEC（RFC 决策）不是同一套号。权威页：`doc/需求编号与缩写规范.html`。对外须写全称，如 `OPT-P1-03`、`Phase D3（OPT-P2-11）`。

依赖升级路线（OPT-P2-11）：`doc/deps/依赖升级RFC.html` — Tier 0–2 ✓ → Phase A/B/C ✓ → Phase D0/D1/D2 ✓ → **下一依赖动作 Phase D3** → Tier 3b/3c。

**交付总览**：`doc/交付状态与路线图.html` — 已发布版本、已完成 OPT/RFC 与未完成项对照。

**优化 / 功能 / UI**：一律设计确认后再改代码（含无 UI 的依赖/模型/Repo 等工作）；管理端 Ajax 表单须 `js-ajax-form` + `js-ajax-submit`（对照 `cron_add.html`）；静态门禁 `tests.test_ajax_form_guard`；仅测 JSON **不算** UI 交付。

**表单防重复提交（强制）**：所有 POST 表单须有防重复提交保护。`js-ajax-form` 已有 `common.js` loading 守卫；非 Ajax POST 表单由 `common.js` 全局守卫自动保护（`cp-submitting` 标记）。独立页面（不继承 `admin_base.html`）须显式引入 `common.js`。静态门禁 `tests.test_ajax_form_guard.TestAntiDoubleSubmitGuard`。

**大文件修改前结构分析（强制）**：修改 300+ 行的 JS/Python/模板文件前，必须用 AST 或手动追踪 `{}`/`def`/`class` 嵌套确认插入点的实际作用域；插入后须在运行时（CDP/`python -c`）确认代码在预期时机执行，禁止仅靠静态 `grep` 判断。详 `.cursor/rules/cronpilot-project.mdc`「大文件修改前结构分析」。

**策略变更影响分析（强制）**：引入或修改业务策略（如"停用不可恢复"、权限限制等）时，必须 grep 策略影响字段的**所有赋值点**，逐点加固或文档说明豁免原因；为每个修改入口编写独立测试；检查同类函数的逻辑一致性；回溯设计文档中策略相关描述。禁止仅在"最显眼"的入口加策略而忽略间接修改路径。详 `.cursor/rules/cronpilot-project.mdc`「策略变更影响分析」。

**本地预览必重启**：本地以 `debug=False` / `use_reloader=False` 常驻，**改模板或 Python 后「刷新浏览器」无效**。对外让用户看效果前必须 `bash scripts/cronpilot.sh restart --daemon`，并用登录会话 curl/浏览器断言新文案或 class。**重启后须先 `curl -s http://127.0.0.1:5001/rbac/login -w "%{http_code}"` 确认 200**，排除 DB 表缺失等全局 500，再进入功能验收。详见 `.cursor/rules/cronpilot-project.mdc`「本地进程与热更新」。

**交付后可验证本地环境（强制）**：宣称交付前须 restart、给出 **URL + 登录方式 + 可执行验收步骤与期望断言**，并在回复中附 **Agent 自证输出**；默认**保持服务运行**供用户复验。禁止只报「单测通过」。详 `.cursor/rules/cronpilot-project.mdc`「交付后可验证本地环境」。

**大变更浏览器关键路径验证（强制）**：凡涉及 RBAC 鉴权、Scope 过滤、权限矩阵、导航/页面可见性等大变更（≥3 文件或涉及权限/可见性语义），必须用**目标角色账号**在浏览器中验证正向+反向路径并截图留证。禁止仅用种子 admin 或 curl 200 宣称通过。详 `.cursor/rules/cronpilot-project.mdc`「大变更浏览器关键路径验证」。

**GitHub Release 文案（强制）**：Release title / notes 统一使用**专业英文**（结构化写 `What changed` / `Why` / `Validation` / `Compatibility & Risk`），禁止口语化或中英混杂标题。该规范已落库于 `.cursor/rules/cronpilot-project.mdc`。

**颜色规范（强制）**：模板和 Vue 组件中**禁止硬编码十六进制颜色**（`#xxxxxx`），必须使用 `app/static/css/console-theme.css` 中定义的 CSS 变量（`var(--cp-*)`）。新增颜色需先在 `console-theme.css` 的 `:root` 中定义对应语义变量，再引用。CI 门禁 `scripts/audit_hardcoded_colors.py --check` 会阻断含硬编码颜色的 PR。

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

**勿改**：上游 `xiaoniu_cron` 仓库（除非用户明确要求）。