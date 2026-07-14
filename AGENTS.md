# CronPilot — Agent 指南

本仓库 AI 协作规范见 `**.cursor/rules/**`（Cursor 自动加载）：


| 规则文件                           | 作用                                           |
| ------------------------------ | -------------------------------------------- |
| `cronpilot-project.mdc`        | 项目定位、仓库边界、路线图、Git/测试总则（始终生效）                 |
| `cronpilot-backend.mdc`        | 后端安全、服务层、API 与 `/docs` 路由                    |
| `cronpilot-documentation.mdc`  | HTML+Markdown 双格式文档与 CI 同步                   |
| `cronpilot-release-deploy.mdc` | 非 Docker 部署、发布与 GitHub CI                    |
| `rbac.mdc`                     | RBAC v4（OPT-P2-10；login/has_perm、rbac_enable；见详设） |


**协作闭环**：设计确认 → 实现 → 验证 → 文档 → commit（任一步失败则修复后重验并重更文档）。详 `.cursor/rules/cronpilot-project.mdc`「交付闭环」。

依赖升级路线（OPT-P2-11）：`doc/依赖升级RFC.html` — Tier 0 `flask db` → Tier 1 SA 1.4 → Tier 2 gevent → Tier 3/4；RBAC 在 Tier 0 后可并行。

**交付总览**：`doc/交付状态与路线图.html` — 已发布版本、已完成 OPT/RFC 与未完成项对照。

**UI / 功能可见改动**：先出设计说明并获确认，再改 `app/templates/` 等；见项目总则「交付闭环」步骤 1。管理端 Ajax 表单须 `js-ajax-form` + `js-ajax-submit`（对照 `cron_add.html`）；静态门禁 `tests.test_ajax_form_guard`；仅测 JSON **不算** UI 交付。

**快速命令**

```bash
sudo bash scripts/install_linux.sh --production   # Linux 裸机
bash scripts/cronpilot.sh start   # 自动匹配 Python 3.8–3.11，无需 PY=
bash scripts/cronpilot.sh restart        # 本地停+启（推荐）
bash scripts/cronpilot.sh stop
bash scripts/cronpilot.sh test
bash scripts/verify_golden_path.sh          # 裸机 SQLite 黄金路径
bash scripts/verify_docker_compose.sh --keep-running   # docker compose 黄金路径
bash scripts/verify_all.sh               # 全量验收（含黄金路径）
bash scripts/verify_all.sh --local-only
bash scripts/verify_all.sh --docker-fresh  # Docker 空库 + changeme 登录冒烟
python scripts/html_docs_to_markdown.py --check
bash scripts/check_pending_sync.sh
```

**勿改**：上游 `xiaoniu_cron` 仓库（除非用户明确要求）。