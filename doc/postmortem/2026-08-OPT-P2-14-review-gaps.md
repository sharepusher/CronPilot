# 复盘：OPT-P2-14 Review 阶段测试覆盖缺失

> 日期：2026-08-10 · 关联：OPT-P2-14 S5/S8 · 严重程度：低（功能正常，测试遗漏）

## 1. Bug 定位

| 问题 | 位置 |
|------|------|
| `sidebar_collapsed` 上下文变量未被测试覆盖 | `tests/test_ui_mode.py` |
| RELEASE_NOTES 声称 "8 tests" 实际为 11 | `RELEASE_NOTES.md` 第 27 行 |

## 2. 根因

- **A（测试遗漏）**：S5 为 `ui_mode.py` 新增 `sidebar_collapsed` 返回字段时，未同步新增测试。功能实现与测试编写未作为原子操作。
- **B（数字不一致）**：RELEASE_NOTES 在 S4 阶段首次写入（8 tests），S7 Review 新增 3 测试后未触发文档同步。

## 3. 测试漏洞

- 无"每个 context processor 返回字段必须有对应测试"的检查机制
- 无 CI 门禁强制覆盖率

## 4. 修复

- 新增 3 个测试：`test_sidebar_collapsed_default`/`_true`/`_zero`
- 修正 RELEASE_NOTES "8" → "11"

## 5. 防护测试

```bash
.venv-py311/bin/python -m unittest tests.test_ui_mode.TestUiModeContextProcessor.test_sidebar_collapsed_default tests.test_ui_mode.TestUiModeContextProcessor.test_sidebar_collapsed_true tests.test_ui_mode.TestUiModeContextProcessor.test_sidebar_collapsed_zero -v
```

## 6. 同类排查

`inject_ui_mode` 返回的 3 个字段（`ui_mode`/`theme`/`sidebar_collapsed`）现已全部覆盖。

## 7. 预防方案

1. **测试文件头部字段清单**（`tests/test_ui_mode.py`）：显式列出所有返回字段，新增字段时作为检查锚点
2. **文档即时同步规则**（已存在于 `.cursor/rules/cronpilot-project.mdc`）：强化执行——在 AskQuestion 前自检"本轮是否有数字/事实变更未同步到文档"
3. **验证命令**：`grep -c "{{" tests/test_ui_mode.py` 确认字段数与 `inject_ui_mode` 返回值数量一致
