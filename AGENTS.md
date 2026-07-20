# CronPilot — Agent 指南

本仓库 AI 协作规范见 `**.cursor/rules/**`（Cursor 自动加载）：


| 规则文件                           | 作用                                           |
| ------------------------------ | -------------------------------------------- |
| `cronpilot-project.mdc`        | 项目定位、仓库边界、路线图、Git/测试总则（始终生效）                 |
| `cronpilot-backend.mdc`        | 后端安全、服务层、API 与 `/docs` 路由                    |
| `cronpilot-documentation.mdc`  | HTML+Markdown 双格式文档与 CI 同步                   |
| `cronpilot-release-deploy.mdc` | 非 Docker 部署、发布与 GitHub CI                    |
| `rbac.mdc`                     | RBAC v4（OPT-P2-10；login/has_perm、三角色分权始终启用；见详设） |


**协作闭环**：设计确认 → 实现 → 验证 → 文档 → commit（任一步失败则修复后重验并重更文档）。详 `.cursor/rules/cronpilot-project.mdc`「交付闭环」。

依赖升级路线（OPT-P2-11）：`doc/依赖升级RFC.html` — Tier 0–2 ✓ → Phase A/B/C ✓ → D0 DEC-008 ✓ → **D1 pin ✓**（Flask 2.3.3 + SA 2.0.36 + FSA 3.1.1）→ D2 Mapped / D3 未开始。

**交付总览**：`doc/交付状态与路线图.html` — 已发布版本、已完成 OPT/RFC 与未完成项对照。

**UI / 功能可见改动**：先出设计说明并获确认，再改 `app/templates/` 等；见项目总则「交付闭环」步骤 1。管理端 Ajax 表单须 `js-ajax-form` + `js-ajax-submit`（对照 `cron_add.html`）；静态门禁 `tests.test_ajax_form_guard`；仅测 JSON **不算** UI 交付。

**本地预览必重启**：本地以 `debug=False` / `use_reloader=False` 常驻，**改模板或 Python 后「刷新浏览器」无效**。对外让用户看效果前必须 `bash scripts/cronpilot.sh restart --daemon`，并用登录会话 curl/浏览器断言新文案或 class；详见 `.cursor/rules/cronpilot-project.mdc`「本地进程与热更新」。

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
python scripts/html_docs_to_markdown.py --check
bash scripts/check_pending_sync.sh
```

**勿改**：上游 `xiaoniu_cron` 仓库（除非用户明确要求）。