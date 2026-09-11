# 2026-09 术语治理复盘：触发模型旧术语清理

> HTML 版：[2026-09-trigger-terminology-cleanup.html](2026-09-trigger-terminology-cleanup.html) · [文档索引](../index.html) · [索引 Markdown](../index.md)

[← 返回复盘索引](index.html)

# 2026-09 术语治理复盘：触发模型旧术语清理

日期：2026-09-07

## 1) Bug 定位

仓库内多处文档、日志文案、注释和指标描述对 CronPilot 的“主动 HTTP 触发请求”使用了历史旧术语，与真实执行模型不一致。

## 2) 根因

早期术语沿用后缺少跨层词汇门禁，代码、文档、规则没有统一审计流程。

## 3) 测试漏洞

现有 CI 无术语准确性检查，导致问题长期潜伏。首版门禁若只做全仓字面扫描、且只挂在 `docs-sync.yml` 的 `doc/**` 路径上，则：① 引用旧 `job_log` 文案的兼容分支与复盘会被误杀；② 已发布 Release Notes 会被改写成当前术语，丢失当时实际交付事实；③ 只改 `app/` 的 PR 不会跑术语扫描。

## 4) 修复

- URL 安全校验函数统一为 `validate_trigger_url`，同步调用链与测试。
- 用户文案统一到“触发请求”语义。
- 活跃文档、规则、指标与日志清理业务旧术语；`doc/archive/` 与已发布 changelog 保持当时原文。
- 门禁增加技术回调（含 `beforeSubmit`）与历史引用白名单；排除已发布 `doc/RELEASE_NOTES.*` 与引用旧文案的复盘。

## 5) 防护测试

| 类型 | 命令 | 结论 |
| --- | --- | --- |
| 术语扫描 | `python scripts/check_terminology.py --check` | 通过 |
| 门禁单测 | `python -m unittest tests.test_check_terminology -v` | 含历史引用与 `beforeSubmit` 放行 |
| 代码质量 | `.venv-py311/bin/ruff check app/` | 通过 |
| 回归测试 | `.venv-py311/bin/python -m unittest tests.test_p0_phase_a tests.test_job_log_display tests.test_job_log_outcome tests.test_lifecycle_logging tests.test_job_log_id -v` | 64/64 通过 |
| 文档同步 | `.venv-md/bin/python scripts/html_docs_to_markdown.py --check` | 通过 |

## 6) 同类排查

已覆盖 `app/`、`tests/`、`scripts/`、活跃 `doc/`、规则与根发布说明。残留仅第三方 vendor、前端构建产物、`doc/archive/`，以及 changelog/复盘中的历史引用。

## 7) 预防方案

- 新增 `scripts/check_terminology.py`：业务旧术语拦截；技术回调与历史引用放行。
- `.github/workflows/docs-sync.yml` 路径扩展到 `app/**`、`tests/**`、规则与发布说明；`unit-tests.yml` 在 discover 之后执行 `python scripts/check_terminology.py --check`，并监听 `scripts/check_terminology.py`。
- 协作规范与 `AGENTS.md` 命令清单增加术语门禁。验证：`python scripts/check_terminology.py --check`；`python -m unittest tests.test_check_terminology -v`。

[文档索引](index.html) · [Markdown](2026-09-trigger-terminology-cleanup.md) · [索引](index.html)

---

[← 文档索引（HTML）](../index.html) · [← 文档索引（Markdown）](../index.md)
