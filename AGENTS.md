# CronPilot — Agent 指南

本仓库 AI 协作规范见 `**.cursor/rules/**`（Cursor 自动加载）：


| 规则文件                           | 作用                                           |
| ------------------------------ | -------------------------------------------- |
| `cronpilot-project.mdc`        | 项目定位、仓库边界、路线图、Git/测试总则（始终生效）                 |
| `cronpilot-backend.mdc`        | 后端安全、服务层、API 与 `/docs` 路由；**新增枚举值扩展检查清单**（强制）|
| `cronpilot-documentation.mdc`  | HTML+Markdown 双格式文档与 CI 同步                   |
| `cronpilot-release-deploy.mdc` | 非 Docker 部署、发布与 GitHub CI                    |
| `rbac.mdc`                     | RBAC v4（OPT-P2-10；login/has_perm、三角色分权始终启用；见详设） |


**协作闭环（强制）**：**清晰完整准确的设计（含分批 + 验收）→ 经用户确认 → 再实现 → 验证 → 可验证本地环境 → 文档 → commit**。确认前禁止写实现代码。「请完成 XX」不等于设计已确认。详 `.cursor/rules/cronpilot-project.mdc`「设计先行」「交付闭环」。

**Bug 修复复盘（强制）**：每次修复用户报告的 bug，必须在交付回复中包含：Bug 定位 → 根因 → 测试漏洞分析 → 修复 → 防护测试 → 同类排查。测试分层须明确（单元 / 集成 / E2E），集成或 E2E 层的 bug 必须在对应层新增测试（`tests/test_*_integration.py`）。详 `.cursor/rules/cronpilot-project.mdc`「Bug 修复复盘」。

**编号读法**：OPT（功能）/ Tier（依赖大阶段）/ Phase（ORM·框架子阶段）/ DEC（RFC 决策）不是同一套号。权威页：`doc/需求编号与缩写规范.html`。对外须写全称，如 `OPT-P1-03`、`Phase D3（OPT-P2-11）`。

依赖升级路线（OPT-P2-11）：`doc/依赖升级RFC.html` — Tier 0–2 ✓ → Phase A/B/C ✓ → Phase D0/D1/D2 ✓ → **下一依赖动作 Phase D3** → Tier 3b/3c。

**交付总览**：`doc/交付状态与路线图.html` — 已发布版本、已完成 OPT/RFC 与未完成项对照。

**优化 / 功能 / UI**：一律设计确认后再改代码（含无 UI 的依赖/模型/Repo 等工作）；管理端 Ajax 表单须 `js-ajax-form` + `js-ajax-submit`（对照 `cron_add.html`）；静态门禁 `tests.test_ajax_form_guard`；仅测 JSON **不算** UI 交付。

**本地预览必重启**：本地以 `debug=False` / `use_reloader=False` 常驻，**改模板或 Python 后「刷新浏览器」无效**。对外让用户看效果前必须 `bash scripts/cronpilot.sh restart --daemon`，并用登录会话 curl/浏览器断言新文案或 class；详见 `.cursor/rules/cronpilot-project.mdc`「本地进程与热更新」。

**交付后可验证本地环境（强制）**：宣称交付前须 restart、给出 **URL + 登录方式 + 可执行验收步骤与期望断言**，并在回复中附 **Agent 自证输出**；默认**保持服务运行**供用户复验。禁止只报「单测通过」。详 `.cursor/rules/cronpilot-project.mdc`「交付后可验证本地环境」。

**颜色规范（强制）**：模板和 Vue 组件中**禁止硬编码十六进制颜色**（`#xxxxxx`），必须使用 `app/static/css/console-theme.css` 中定义的 CSS 变量（`var(--cp-*)`）。新增颜色需先在 `console-theme.css` 的 `:root` 中定义对应语义变量，再引用。CI 门禁 `scripts/audit_hardcoded_colors.py --check` 会阻断含硬编码颜色的 PR。

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
python scripts/html_docs_to_markdown.py --check
bash scripts/check_pending_sync.sh
```

**勿改**：上游 `xiaoniu_cron` 仓库（除非用户明确要求）。