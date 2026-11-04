# v4.1.1 后全部提交 Bugbot 复审（HEAD 0e31f8f）

> HTML 版：[post-v4.1.1-bugbot-review-head-0e31f8f-2026-11-04.html](post-v4.1.1-bugbot-review-head-0e31f8f-2026-11-04.html) · [文档索引](../index.html) · [索引 Markdown](../index.md)

# v4.1.1 后全部提交 Bugbot 复审

2026-11-04（Asia/Shanghai） · v1 · 基线 v4.1.1（ed8155a3db7ebe5c9c6a0110bf6fd80d62a0c93d）→ HEAD 0e31f8f469b004d095e2a980862a8f661a4750ce。

## 版本记录

v1：针对六个已提交变更重新审查，区分当前缺陷、已修复历史问题与已知延期问题。本轮只新增审查材料和索引登记，没有修复业务实现，也未提交 Git。

## 审查范围与结论

范围为 `v4.1.1..0e31f8f`，共六个提交、491 个变更文件，其中 app/datas/.github/release/scripts/tests 下 82 个。使用一次 Bugbot 子代理审查，主代理补充全量测试、路由冒烟与文档门禁。代码及测试工作区与 HEAD 一致；已有未提交的 README、Release Notes、路线图及发布收尾设计不属于本轮提交审查对象。文档检查基于当前工作区，不能替代候选发布提交的验收。

**未发现新增的高置信业务缺陷。**保留一个已知延期的自动发布问题。此结论表示本轮静态检查与已执行验证未发现新增问题，不代表所有环境和外部流程都已验证，也不等于发布就绪批准。

## 逐提交覆盖

- `8e3a1b0`：发布资产白名单与清单边界、Release Notes 提取、版本一致性及对应测试。
- `061f73f`：只读构建与受控发布拆分、Action 固定 SHA、远端下载比较、就绪检查及发布 job 的仓库定位。
- `3b7583f`：发布信任审计文档，与 workflow 的边界描述对照；未查询远端环境保护及 tag 规则。
- `c727146`：任务编辑意图、基线、ORM 版本条件、标签关系、启停目标与签名重试、暂停任务注册；用户编辑范围投影、当前授权、角色与组耦合冲突、SQLite 写边界、审计及副作用；前端表单交互、迁移和相关工具。
- `d3298c7`：历史审查报告与证据；旧失败仅用于追踪，不直接作为当前缺陷。
- `0e31f8f`：提交前快照与稳定标量、提交后缓存失效和返回边界；旧测试契约、基线工具、图片迁移及术语分类门禁的修正与回归。

## 已知延期问题

**P1：自动发布 job 缺少 GitHub 仓库上下文。**位置：`.github/workflows/release-asset.yml:103–112`，由 `061f73f` 引入。publish 使用独立 runner，仅下载 artifact，未 checkout，也没有设置 `GH_REPO` 或为 `gh release` 传入 `--repo`。在干净 runner 中无法定位仓库，自动发布阶段会失败。建议后续显式指定仓库，保留受控发布 job 不执行仓库代码的信任边界。本轮为静态复核，未执行远端发布。

此前用户已明确继续手动发布，并延期处理该项；因此它不列为本次手动发布的新增阻断。恢复自动发布前应重新验收。本轮不修改这一既定决策，参见[此前审查与用户决策](post-v4.1.1-commit-review-2026-11-04.html)。

## 历史问题复核

- 启停与用户编辑的提交后 ORM 读取：当前已采用预提交快照或稳定标量；过期对象读取失败和缓存故障注入回归通过。
- 旧 Scope/CSRF/内联脚本断言：以当前服务和前端脚本契约复核；本轮聚焦回归通过。
- 图片迁移与术语门禁：本轮重新执行均通过；不沿用旧报告的失败结论。
- UI 返回的 result/data 双键兼容：静态复核正常。用户认可的有权限时发起的在途操作允许完成，未作为缺陷重新提出。

## 本轮验证

`.venv-py311/bin/python -m unittest discover -s tests -p 'test_*.py'`：Ran 1168 tests in 486.602s；OK (skipped=12)，退出码 0。跳过项不视为已验证通过。全量测试输出保存在本机 `/private/tmp/cronpilot-review-0e31f8f-unittest.log`；路由输出在 `/private/tmp/cronpilot-review-0e31f8f-routes.log`，临时日志可能被系统清理，复验以本节命令为准。

聚焦回归命令：

```
.venv-py311/bin/python -m unittest tests.test_cron_edit_concurrency tests.test_cron_edit_apply tests.test_cron_status_apply_d2 tests.test_status_postcommit_snapshot tests.test_rbac_postcommit_boundary tests.test_user_edit_change_set tests.test_user_edit_scope_projection tests.test_user_edit_sqlite_boundary -q
```

结果：122 tests / 79.723s / OK / exit 0。日志中的故意异常来自故障注入，不单独计作失败。

- `.venv-py311/bin/python scripts/smoke_routes.py --check`：86 路由，86 通过，0 失败（5.3s）。
- `.venv-py311/bin/ruff check app/`：All checks passed。
- `.venv-py311/bin/python scripts/check_qa_image_migration.py`：all frozen paths mapped with unchanged bytes。
- `.venv-py311/bin/python scripts/check_terminology.py --check`：通过。
- `sqlite3 datas/job_log.sqlite '.tables'`：18 张现有表仍存在；本轮测试使用隔离夹具。

## 未验证边界

本轮未运行真实 MySQL、Docker、Python 3.8–3.10、目标角色真实浏览器矩阵或远端 GitHub 发布；没有将旧截图或旧专项报告冒充本轮新验收。静态前端复核和测试客户端路由冒烟不能证明所有浏览器交互正常。没有更改服务或模板，因此没有重启现有本地服务。发布版本清单与未提交的发布归档另按发布收尾设计验收。

## 审查文档验收

以下命令通过：`.venv-py311/bin/python scripts/html_docs_to_markdown.py --check`、`.venv-py311/bin/python scripts/check_doc_completeness.py --check`、`.venv-py311/bin/python scripts/check_doc_links.py --check`、`bash scripts/check_pending_sync.sh`。411 个 HTML 均已登记，链接检查无 broken。HTML 已通过本地 `/docs/qa/post-v4.1.1-bugbot-review-head-0e31f8f-2026-11-04.html` 返回 HTTP 200，且已在浏览器实际打开并确认报告标题与正文；此项仅是审查报告预览，不代表产品多角色浏览器验收。

[Markdown](post-v4.1.1-bugbot-review-head-0e31f8f-2026-11-04.md) · [文档索引](../index.html)

---

[← 文档索引（HTML）](../index.html) · [← 文档索引（Markdown）](../index.md)
