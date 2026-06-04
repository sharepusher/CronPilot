# CronPilot — Agent 指南

本仓库 AI 协作规范见 **`.cursor/rules/`**（Cursor 自动加载）：

| 规则文件 | 作用 |
|----------|------|
| `cronpilot-project.mdc` | 项目定位、仓库边界、路线图、Git/测试总则（始终生效） |
| `cronpilot-backend.mdc` | 后端安全、服务层、API 与 `/docs` 路由 |
| `cronpilot-documentation.mdc` | HTML+Markdown 双格式文档与 CI 同步 |
| `cronpilot-release-deploy.mdc` | 非 Docker 部署、发布与 GitHub CI |

**快速命令**

```bash
bash scripts/check_python.sh    # Python 3.8–3.11
PY=python3.10 bash scripts/start_local.sh
python -m unittest tests.test_p0_phase_a tests.test_cronpilot_sign -v
python scripts/html_docs_to_markdown.py --check
```

**勿改**：上游 `xiaoniu_cron` 仓库（除非用户明确要求）。
