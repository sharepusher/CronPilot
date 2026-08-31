# V1 下线 Batch 4-5 方案设计

> HTML 版：[V1下线Batch4-5方案设计.html](V1下线Batch4-5方案设计.html) · [文档索引](../index.html) · [索引 Markdown](../index.md)

# V1 下线 Batch 4–5 方案设计

|  |  |
| --- | --- |
| 文档类型 | 设计方案 |
| 前置依赖 | Batch 1-3 已完成（[完成报告](V1下线完成报告-Batch1-3-2026-08.html)） |
| 日期 | 2026-08-31 |

## 0. 现状摘要

Batch 1-3 已完成 V1 的主体移除：所有 V1 模板（36）、独立 JS（8）、CSS（2）、第三方插件（5 目录）均已物理删除。当前仓库中 V1 残余仅存在于**注释**、**Dead CSS**、**Legacy 路由 shim** 和**目录命名历史**四个维度。

**注意**：原方案设计中的 Batch 4（删除 V1 静态资源）已在 Batch 3 执行中合并完成。以下 Batch 4-5 为**重编号后的剩余清理工作**。

## 1. 问题：V1 残余引用分析

### 1.1 注释中的 V1 引用（无功能影响）

| # | 文件 | 行号 | 内容 | 影响 |
| --- | --- | --- | --- | --- |
| C1 | console-theme.css | 14 | `--cp-* 前缀避免与 simpleboot/bootstrap 冲突` | 注释，已无实际冲突 |
| C2 | console-theme.css | 30 | `admin_base topbar a:hover` | 注释，token 仍有效 |
| C3 | console-theme.css | 67 | `label-danger 覆写 — simpleboot 恢复语义红` | 注释，类仍被使用 |
| C4 | console-theme.css | 82 | `执行状态机 (admin_base.html label 覆写)` | 注释，标题 |
| C5 | console-theme.css | 292-296 | 迁移说明块：`从 admin_base.html inline style 迁移` | 过时说明 |
| C6 | common-redesign.js | 4 | `Replaces common.js + wind.js` | 历史上下文 |
| C7 | common-redesign.js | 7 | `ZERO Wind.use / artDialog / ajaxForm` | 约束说明 |
| C8 | execution\_logs.html | 286 | `connect to Wind datePicker if available` | 过时注释 |

### 1.2 Dead CSS：V1 Topbar 遗留（~25 行）

| 类型 | 内容 | 行号 | V2 消费者 |
| --- | --- | --- | --- |
| Token（Light） | `--cp-topbar-bg`、`--cp-topbar-text`、`--cp-topbar-muted` | 99-101 | **无**（仅 .rbac-topbar 引用） |
| Token（Dark） | 同上（dark theme 覆写） | 237-239 | **无** |
| Selector | `.rbac-topbar` 及 `.topbar-role-*`、`.topbar-sep` | 305-316 | **无**（V2 topbar 使用 .cp-topbar） |

验证方法：`grep -rn "rbac-topbar\|topbar-role-\|topbar-sep\|cp-topbar-bg\|cp-topbar-text\|cp-topbar-muted" app/templates/ app/static/js/` — 预期返回空。

### 1.3 Legacy 路由 Shim（功能性）

| 路由 | 方法 | 行为 | 内部引用 | 外部可能性 |
| --- | --- | --- | --- | --- |
| /check\_pass | GET/POST | 307/302 redirect → /rbac/login | 无模板/代码引用 | 旧版书签、第三方集成 |
| /logout | GET | 302 redirect → /rbac/login | 无模板/代码引用 | 旧版书签 |

这两个 shim 的测试覆盖：`test_rbac_phase.py`（5 个用例）+ `test_logout_csrf.py`（1 个用例）。

### 1.4 目录命名：`redesign/` 前缀

| 维度 | 数据 |
| --- | --- |
| Python 中 `'redesign/'` 引用 | 60 处（views 39 + views 20 + errors 2 + decorators 1 + services 1 + tests/scripts 7） |
| 模板内 `{% extends` / `{% include` | ~30 处（所有继承 \_base 和 include 局部模板的引用） |
| 变更涉及文件 | ~15 个 Python 文件 + 38 个模板文件 |

## 2. 根因：为什么有这些残余

| 残余类型 | 根因 |
| --- | --- |
| 注释 | Batch 3 执行时聚焦于功能性文件删除，注释中的历史引用不影响功能，未列入清理范围 |
| Dead CSS | `.rbac-topbar` 类组在 V1→V2 过渡期用于共享 topbar 样式，V2 启用独立 topbar 后失去消费者 |
| Legacy shim | 设计预留的向后兼容层，防止旧版书签/外部集成断链 |
| redesign/ 命名 | V1/V2 共存期间的命名空间隔离策略，设计时即标注为"下线后可选重组" |

## 3. 方案

### Batch 4：注释更新 + Dead CSS 清理（低风险，建议执行）

| 子项 | 操作 | 风险 |
| --- | --- | --- |
| 4a | 更新 `console-theme.css` 中 6 处注释：移除过时的 admin\_base/simpleboot 引用，改为当前上下文描述 | 零风险（仅注释） |
| 4b | 删除 `console-theme.css` 中 Dead CSS：`.rbac-topbar` 相关选择器（12 行）+ `--cp-topbar-*` token（6 行） | 低风险（已确认无消费者） |
| 4c | 更新 `common-redesign.js` 文件头注释（2 处）和 `execution_logs.html` 注释（1 处） | 零风险（仅注释） |

**验收**：`python scripts/check_dead_css.py --check`（dead ≤ 0）+ `python scripts/check_css_token_reachability.py --check`（all reachable）+ 432 tests pass。

### Batch 5a：Legacy 路由 Shim 处理（低风险，需决策）

**决策点**：是否保留 `/check_pass` 和 `/logout` redirect shim？

| 选项 | 优点 | 缺点 |
| --- | --- | --- |
| **A. 保留 + 标注废弃**（推荐） | 旧书签/外部集成不断链；维护成本极低（共 10 行代码） | 多 2 个路由 |
| B. 删除 | 代码更干净 | 可能断裂外部集成；需删 6 个测试 |
| C. 保留但返回 410 Gone | 语义更准确；外部调用方能感知废弃 | 破坏现有重定向行为 |

**执行决策**：用户确认删除。已在 Batch 5 中删除 `/check_pass` 和 `/logout` shim，连同 7 个对应测试。

### Batch 5b：模板目录重组 `redesign/` → 根目录（高影响，需决策）

| 选项 | 工作量 | 优点 | 缺点 |
| --- | --- | --- | --- |
| **A. 不重组**（推荐） | 0 | 无风险、无 diff、无 merge 冲突；`redesign/` 目录名作为历史标记无害 | 目录名不够简洁 |
| B. 重组（`redesign/` → 根） | 高（~90+ 文件改动） | 目录结构更干净 | 60+ Python render\_template 路径变更 + 30+ 模板内 extends/include 变更 + 15 测试/脚本变更 = ~90+ 处修改；产生巨大 diff；高 merge 冲突风险 |

**推荐方案 A**：不重组。理由如下：

1. **收益/成本比极低**：~90 处改动仅为目录名美化，不带来任何功能改进或性能提升
2. **Flask 模板目录支持子目录**：`render_template('redesign/xxx.html')` 是 Flask 标准用法，不存在技术债务
3. **高回归风险**：涉及 views、errors、decorators、services、pagination、tests、CI scripts 共 ~15 个 Python 文件，任一遗漏都会导致 500
4. **"redesign" 命名无误导**：V1 已删除，目录名只是历史命名，不影响新开发者理解
5. **与并行开发冲突**：若有其他分支在开发中，大规模路径变更将导致严重 merge 冲突

## 4. 范围

| Batch | 涉及文件 | 预计 diff 行数 |
| --- | --- | --- |
| 4（注释 + Dead CSS） | `console-theme.css`、`common-redesign.js`、`execution_logs.html` | ~25 行删除 + ~10 行注释修改 |
| 5a（Legacy shim 标注） | `app/main/views.py` | ~5 行修改（docstring 更新） |
| 5b（目录重组） | **推荐不做** | — |

### 明确不做

- 不重组 `redesign/` 目录（方案 A）
- 不删除 `/check_pass`、`/logout` legacy shim（方案 A，保留兼容）
- 不修改 `console-theme.css` 中仍在使用的 token/class（如 `.label-timeout`、`--cp-role-*`）

## 5. 分批

| 步骤 | 内容 | 可独立验收 |
| --- | --- | --- |
| Step 1（Batch 4） | 更新 console-theme.css 注释（6 处）+ 删除 Dead CSS（18 行）+ 更新 JS/模板注释（3 处） | ✓ dead\_css + token\_reachability + 全量测试 |
| Step 2（Batch 5a） | 更新 legacy shim docstring 标注废弃 | ✓ 全量测试 |

## 6. 验收

| 门禁 | 命令 | 预期 |
| --- | --- | --- |
| Dead CSS | `python scripts/check_dead_css.py --check` | ≤ 0 |
| Token 可达性 | `python scripts/check_css_token_reachability.py --check` | all reachable |
| V1 引用清零 | `grep -n "admin_base\|simpleboot\|artDialog\|wind\.js" app/static/css/console-theme.css` | 0 matches（仅注释也已更新） |
| 全量测试 | `bash scripts/cronpilot.sh test` | 432 pass |
| 服务启动 | `bash scripts/cronpilot.sh restart --daemon` | PID 存在 |

## 7. 风险

| 风险 | 等级 | 缓解 |
| --- | --- | --- |
| Dead CSS 误删导致样式丢失 | 极低 | 已通过 grep 确认 `.rbac-topbar` 在 V2 模板/JS 中无消费者 |
| Legacy shim 删除导致外部断链 | — | 方案选择保留（不删除） |
| 注释更新引入语法错误 | 极低 | 注释不影响运行时，CI 全量测试覆盖 |

## 8. 必要性评估总结

| 项目 | 必要性 | 工作量 | 建议 |
| --- | --- | --- | --- |
| Batch 4：注释 + Dead CSS | **建议执行**（代码卫生 + CI 门禁趋零） | 低（~30 分钟） | ✅ 执行 |
| Batch 5a：Legacy shim 标注 | 可选（维护性提升） | 极低（~5 分钟） | ✅ 顺手执行 |
| Batch 5b：目录重组 | **不推荐**（收益 ≈ 0，风险高） | 高（~2 小时 + review） | ❌ 不做 |

[文档索引](index.html) · [Markdown](V1下线Batch4-5方案设计.md) · [索引](index.html)

---

[← 文档索引（HTML）](../index.html) · [← 文档索引（Markdown）](../index.md)
