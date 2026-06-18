# CronPilot — Agent 指南

本仓库 AI 协作规范见 **`.cursor/rules/`**（Cursor 自动加载）：

| 规则文件 | 作用 |
|----------|------|
| `cronpilot-project.mdc` | 项目定位、仓库边界、路线图、Git/测试总则（始终生效） |
| `cronpilot-backend.mdc` | 后端安全、服务层、API 与 `/docs` 路由 |
| `cronpilot-documentation.mdc` | HTML+Markdown 双格式文档与 CI 同步 |
| `cronpilot-release-deploy.mdc` | 非 Docker 部署、发布与 GitHub CI |
| `rbac.mdc` | RBAC v2（OPT-P2-10；分层、白名单、rbac_enable 兼容；见详设） |

依赖升级路线（OPT-P2-11）：`doc/依赖升级RFC.html` — Tier 0 `flask db` → Tier 1 SA 1.4 → Tier 2 gevent → Tier 3/4；RBAC 在 Tier 0 后可并行。

**快速命令**

```bash
sudo bash scripts/install_linux.sh --production   # Linux 裸机
bash scripts/cronpilot.sh start   # 自动匹配 Python 3.8–3.11，无需 PY=
bash scripts/cronpilot.sh test
bash scripts/verify_all.sh              # 本地单测 + HTTP + Docker 全量验收
bash scripts/verify_all.sh --local-only   # 仅本地
bash scripts/verify_all.sh --with-compose # 含 docker compose（较慢）
python scripts/html_docs_to_markdown.py --check
```

**勿改**：上游 `xiaoniu_cron` 仓库（除非用户明确要求）。
