# CSS 死代码清理与命名统一设计 — CronPilot

> HTML 版：[CSS死代码清理与命名统一设计.html](CSS死代码清理与命名统一设计.html) · [文档索引](../index.html) · [索引 Markdown](../index.md)

# CSS 死代码清理与命名统一设计

**文档编号**：OPT-CSS-CLEANUP-01  
**状态**：待确认  
**关联**：Phase R1（已完成）、Phase R2（CSS 命名规范化）后续  
**日期**：2026-08-24

---

## 一、问题

经全量审计，`redesign-components.css`（825 行）中 55% 的代码（71/129 选择器块）从未被任何模板或 JS 引用。跨 5 个 CSS 文件还存在 12 组语义重叠（同一功能多套实现）和 5 处命名冲突。

### 量化现状

| 指标 | 当前值 | 目标 |
| --- | --- | --- |
| components.css 死代码率 | 55%（~450 行） | <5% |
| 语义重叠组数 | 12 组 | 0（每种功能单一规范实现） |
| 未定义 Token 引用 | 2 处 | 0 |
| 表格系统并行数 | 4 套（.cp-table / .c-table / .el-table / .tg-task-tbl） | 1 规范 + N 合理扩展 |
| 按钮系统并行数 | 5 套（.btn-c / .cp-btn / .btn / .el-btn / .auth-btn） | ≤3（有明确边界） |
| 分页系统并行数 | 4 套（.cp-pagination / .c-pg / .hf-pg / .el-pg） | 1 规范 + 1 页面扩展 |
| 筛选条系统并行数 | 6 套 | 1 基础 + N 语义扩展 |

## 二、根因分析

### 2.1 架构演化时间线

Phase 0 — 组件库先行设计
:   在 Mockup 确定前，基于「通用组件库」思维设计了 `.cp-table`、`.cp-pagination`、`.cp-form-*`、`.cp-badge-*`、`.cp-health-*`、`.cp-chip` 等全套组件。假设前提：**「一套组件适配所有页面」**。

Phase 1 — Mockup 确定
:   设计师交付的 Mockup 使用了独立命名体系（`.c-table`、`.btn-c`、`.f-input`、`.page-head`），与 Phase 0 的 `.cp-*` 不兼容。为快速对齐 Mockup，新增 `redesign-mockup-shared.css` 直接复刻 Mockup 命名。

Phase 2 — 逐页实现
:   每个页面实现时，开发者面临「用 .cp-\* 还是用 Mockup .c-\*」的选择。由于 Mockup 是验收标准，绝大多数选择了 Mockup 命名。同时为页面特化需求（如 Dashboard 动画、Exec Logs 黏性表头），创建了 `.hf-*`、`.el-*` 等页面前缀。

Phase 3 — Phase R1 CSS 架构统一
:   Phase R1 重点解决了**内联 CSS 迁移**（2010 行 → 0 行）和**硬编码颜色消除**，但未触及组件库死代码和命名分裂问题。原因：R1 的设计约束是「零视觉变化」——删除死代码虽无视觉影响，但属于独立工作项，超出 R1 范围。

### 2.2 五层根因追溯（Why × 5）

| 层级 | 问题 | 回答 |
| --- | --- | --- |
| **Why 1** | 为什么有 55% 死代码？ | Phase 0 组件库被 Mockup 体系完整替代，但未清理旧代码 |
| **Why 2** | 为什么 Mockup 体系替代了组件库？ | Mockup 由设计师交付，命名体系与工程预设的 `.cp-*` 不同，团队选择"对齐 Mockup"而非"重构 Mockup 命名" |
| **Why 3** | 为什么没在 Mockup 确定时统一命名？ | 快速迭代压力 + 组件库已写好 → 两套并存成本在当时看来比"推翻重写"更低 |
| **Why 4** | 为什么后续（Phase R1）没清理？ | R1 聚焦内联 CSS 迁移（已有明确 ROI），死代码清理被定义为独立 OPT 项，等待工程空闲窗口 |
| **Why 5** | 为什么缺少自动化门禁阻止死代码累积？ | 现有 CI 门禁覆盖**活跃代码质量**（颜色审计、内联 CSS 体积），但无**死代码检测**工具 |

### 2.3 结构性产因分类

| 产因类型 | 占比 | 具体表现 |
| --- | --- | --- |
| **设计→实现命名断层** | ~60% | 组件库 `.cp-*` vs Mockup `.c-*/.btn-c/.f-input` 全面冲突 |
| **乐观预设（YAGNI 反面）** | ~25% | Skeleton loading、badge 色彩变体、form 系统在当时无消费者即已定义 |
| **页面特化漂移** | ~10% | 各页独立创建 filter/chip/pagination 变体而非复用公共组件 |
| **重构遗留** | ~5% | R1 迁移后 `.cp-muted`、`.cp-faint` 等工具类被 Token 变量替代但未删除 |

## 三、必要性分析

### 3.1 为什么现在必须清理？

| 维度 | 当前痛点 | 不清理的后果 |
| --- | --- | --- |
| **开发效率** | 新开发者面对 5 套按钮系统、4 套表格系统，无法判断该用哪个 | 持续生成新的变体系统，债务指数级增长 |
| **维护风险** | 修改 `.btn` 或 `.cp-btn` 时无法确定影响面（因为部分定义从未被引用） | 重构时误删活跃代码 or 不敢删任何代码 |
| **认知负载** | 825 行组件 CSS 中 450 行是噪声，阅读时需脑内过滤 | Code review 效率下降，Bug 定位时间增加 |
| **加载体积** | ~450 行死代码 ≈ 12KB gzip 前（实际 gzip ≈ 2–3KB），对首屏渲染无感知影响 | 体积影响可忽略，但信号噪声比持续恶化 |
| **CI 门禁缺口** | 无自动检测防止新增死 CSS | 每次迭代可能新增未消费的"预留"样式 |

### 3.2 预期收益

| 收益 | 量化 |
| --- | --- |
| 组件文件体积减少 | 825 → ~375 行（-54%） |
| 选择器块减少 | 129 → 58（-55%） |
| 按钮系统收敛 | 5 套 → 3 套（规范 + 兼容 + auth，有明确文档边界） |
| 表格系统收敛 | 4 套 → 2 套（.c-table 规范 + .el-table 合理扩展） |
| 新增 CI 门禁 | 防止同类问题复发 |

### 3.3 不做 / 推迟的风险评估

> **结论：清理死代码的 ROI 极高（零回归风险 + 高可维护性收益）**。这不是一个"锦上添花"的优化，而是阻止技术债复利增长的必要操作。

当前时机最佳的原因：Phase R1 刚完成全量 CSS 迁移，所有模板已稳定在新结构上；再过 1–2 个迭代周期后，开发者可能基于死代码创建新变体，清理成本会上升。

## 四、方案

### 4.1 清理策略：分三批递进

| 批次 | 范围 | 风险 | 行数影响 |
| --- | --- | --- | --- |
| **Batch A** | 删除 100% 确认死代码（0 引用） | 零 | -~380 行 |
| **Batch B** | 修复命名冲突 + 合并重复定义 | 低 | 净减 ~50 行 |
| **Batch C** | 新增 CI 门禁脚本 | 零 | +~80 行（新脚本） |

### 4.2 Batch A — 死代码删除清单

以下选择器块经全量 `grep` 确认在 `app/templates/redesign/*.html`、`app/static/js/redesign-*.js`、`app/static/js/common.js` 中**零引用**：

| 分类 | 选择器 | 行范围（approx） |
| --- | --- | --- |
| 表格 | `.cp-table-wrap`, `.cp-table`, `.cp-table th/td/tr` | 96–136 |
| 分页 | `.cp-pagination`, `.cp-pg-btn`, `.cp-pg-info` | 391–434 |
| 表单 | `.cp-form-section*`, `.cp-form-row`, `.cp-form-group*`, `.cp-form-actions` | 311–388 |
| 筛选 | `.cp-filters`, `.cp-chip*`, `.cp-search*` | 245–308 |
| 徽章 | `.cp-badge*`（全部 6 个变体） | 189–223 |
| 健康度 | `.cp-health*`（3 色变体 + base） | 226–242 |
| 按钮变体 | `.cp-btn--danger/ghost/sm/lg/success` | 64–93, 794–804 |
| Legacy .btn 变体 | `.btn.btn-primary/ghost/danger`（含 hover） | 458–489 |
| Stat 色彩 | `.cp-stat--danger/warning/success` | 184–186 |
| 骨架屏 | `.cp-skeleton*`（含 keyframe） | 653–672 |
| Command 结果项 | `.cp-cmd-group-label`, `.cp-cmd-item*` | 722–745 |
| 工具类 | `.cp-mono`, `.cp-muted`, `.cp-faint`, `.cp-danger-text`, `.cp-mb-12` | 767–770, 789 |
| Motion（错误选择器） | `.toast-item`, `.cp-confirm-box`, `.cp-shimmer`, `[class*="shimmer"]` | 810–824 |

### 4.3 Batch B — 命名冲突修复

| 问题 | 修复方案 | 影响 |
| --- | --- | --- |
| `[data-tooltip]` 在 pages.css 中重复定义（L633 和 L1279） | 将 L1279 的 Dashboard 覆盖规则加 `.cp-page-dashboard` scope | 其他页面 tooltip 颜色恢复一致 |
| `prefers-reduced-motion` 中引用不存在的 `.toast-item` | 改为 `.toast`（实际 class） | Toast 在 reduce-motion 下正确降级 |
| `prefers-reduced-motion` 中引用不存在的 `.cp-confirm-box` | 改为 `.cp-modal`（实际 class） | Modal 在 reduce-motion 下正确降级 |
| mockup-shared 中 `[data-tip]` 从未使用 | 删除该规则 | 零影响 |
| `--cp-active-bg` Token 引用但未定义 | 在 console-theme.css 中定义，或改用 `--cp-signal-bg` | tag-suggest hover 正常着色 |

### 4.4 Batch C — CI 门禁

新增脚本 `scripts/check_dead_css.py`：

```
逻辑：
1. 解析 redesign-components.css 中所有类名选择器
2. 对每个类名在 app/templates/redesign/*.html + app/static/js/*.js 中 grep
3. 仅标记模板/JS 中引用为 0 且不属于"CSS-internal"（如 keyframe 被同文件引用）的类
4. 输出警告；--check 模式下非零计数则 exit 1

集成：
- .github/workflows/ui-contract.yml 新增 step
- 阈值：初始允许 ≤5 个未引用类（为 CSS-internal 预留），后续收紧到 0
```

## 五、范围

### 改动文件

| 文件 | 操作 |
| --- | --- |
| `app/static/css/redesign-components.css` | 删除 Batch A 所列选择器块（-~380 行），修复 Batch B 中 motion selectors |
| `app/static/css/redesign-pages.css` | Batch B：scope [data-tooltip] 覆盖规则 |
| `app/static/css/redesign-mockup-shared.css` | Batch B：删除 [data-tip] |
| `app/static/css/console-theme.css` | Batch B：定义 `--cp-active-bg` 或改引用 |
| `scripts/check_dead_css.py` | Batch C：新建 |
| `.github/workflows/ui-contract.yml` | Batch C：新增 step |

### 明确不做

- 不改任何模板 HTML（本次只删 CSS 死代码）
- 不合并 `.btn-c` / `.cp-btn` / `.btn` 三套按钮（它们各有活跃消费者，合并需单独设计）
- 不合并 `.el-table` 进 `.c-table`（exec-logs 的黏性表头是合理特化）
- 不修改 `redesign-auth.css`（独立系统，零冲突）
- 不删 `.cp-btn` / `.cp-btn--primary`（在 task\_detail/task\_form/dashboard 中活跃使用）
- 不改页面级前缀（`.hf-*`, `.el-*` 等已通过 `.cp-page-*` scope 隔离）

## 六、分批实施

| 批次 | 交付物 | 验收门禁 | 预估耗时 |
| --- | --- | --- | --- |
| **Batch A** | 删除 components.css 死代码 | ① `.venv-py311/bin/python -m unittest tests.test_redesign_sidebar -v`（12 green） ② CSS brace balance 检查 ③ `curl` 验证 5 个关键页面无 500 ④ 硬编码颜色审计通过 | 15 min |
| **Batch B** | 修复 5 处命名冲突 | ① 同 Batch A 门禁 ② `grep "toast-item\|cp-confirm-box\|data-tip" app/static/css/` = 0 ③ `grep "cp-active-bg" app/static/css/console-theme.css` 有定义 | 10 min |
| **Batch C** | CI 脚本 + workflow 集成 | ① `python scripts/check_dead_css.py --check` exit 0 ② GitHub Actions dry-run 通过 | 20 min |

## 七、验收标准

1. `redesign-components.css` 行数 ≤ 400（当前 825）
2. 全量 `grep` 确认 components.css 中每个类名在模板/JS 中有 ≥1 引用（或为 CSS-internal 如 keyframe 被同文件引用）
3. `prefers-reduced-motion` 中所有选择器在非-motion 上下文中有定义
4. `python scripts/check_dead_css.py --check` = 0 violations
5. 所有现有测试通过（`bash scripts/cronpilot.sh test`）
6. 5 个关键页面（Dashboard、Users、Tags、Execution Logs、Task Detail）浏览器可正常渲染

## 八、风险

| 风险 | 概率 | 影响 | 缓解 |
| --- | --- | --- | --- |
| 误删活跃代码 | 极低 | 页面样式异常 | 每个待删类名经 `rg` 三重验证（HTML/JS/CSS cross-ref）；仅删零引用项 |
| JS 动态生成的类名遗漏 | 低 | Toast/Modal 样式丢失 | JS 文件已被扫描；`redesign-confirm.js`/`redesign-toast.js` 中的类名已标记为 JS-ONLY（保留） |
| 未来功能需要被删组件 | 中 | 需重写 | Skeleton loading / Form system 未来如需实现，应基于当时的设计重新定义（YAGNI 原则），而非复用 Phase 0 遗留 |
| CI 脚本误报 | 低 | 开发者 confusion | 白名单机制（CSS-internal keyframes / 动态创建 class） |

## 九、复盘与预防机制

### 9.1 此类问题为何未被早期发现？

| 检测环节 | 缺失原因 |
| --- | --- |
| Code Review | 新增 CSS 时只关注「能否工作」，未关注「旧定义是否应删除」 |
| CI 门禁 | 现有门禁覆盖活跃代码质量（颜色/内联体积），无死代码检测 |
| 设计文档 | Phase 0 → Phase 1 切换时未产出「组件库废弃清单」 |
| 重构 checklist | Phase R1 scope 明确排除了死代码清理，但未将其列为明确的后续 TODO |

### 9.2 预防措施（Batch C 实现）

1. **CI 死代码检测**：`scripts/check_dead_css.py --check` 在每次 PR 中运行
2. **组件库新增规范**：在 `.cursor/rules/cronpilot-format-guard.mdc` 追加「新增组件类必须在同 PR 中至少有 1 个模板/JS 消费者」
3. **定期审计**：在 Phase R2 或 v2.1.0 发布前执行一次全量扫描

## 十、附录：完整活跃类清单（Batch A 后保留）

| 分类 | 保留的选择器 | 消费者 |
| --- | --- | --- |
| 按钮 | `.cp-btn`, `.cp-btn--primary` | task\_form, task\_detail, dashboard |
| Legacy 按钮 | `.btn`（base only） | tags.html modals, registration\_review, task\_detail |
| 卡片 | `.cp-card`, `.cp-card-title` | \_welcome.html |
| 统计 | `.cp-stats`, `.cp-stat`, `.cp-stat-label/value` | \_welcome.html |
| 空状态 | `.cp-empty-state`, `.empty-title/desc` | execution\_logs, task\_detail, run\_inspector |
| Toast | `.toast-container`, `.toast*` | \_base.html + redesign-toast.js |
| Modal | `.cp-modal-overlay/modal/header/body/footer` | redesign-confirm.js + 模板 Escape 守卫 |
| Command Palette | `.cp-cmd-overlay/box/input/results/footer/kbd` | \_base.html + redesign-shell.js |
| 工具类 | `.cp-success-text`, `.cp-fw-600`, `.cp-text-xs`, `.cp-text-muted-sm`, `.cp-text-faint-sm`, `.cp-mt-8/40`, `.cp-opacity-60` | 多页面 |

[文档索引](index.html) · [Markdown](CSS死代码清理与命名统一设计.md) · [索引](index.html)

---

[← 文档索引（HTML）](../index.html) · [← 文档索引（Markdown）](../index.md)
