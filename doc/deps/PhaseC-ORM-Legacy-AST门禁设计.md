# CronPilot · Phase C · ORM Legacy AST 门禁设计

> HTML 版：[PhaseC-ORM-Legacy-AST门禁设计.html](PhaseC-ORM-Legacy-AST门禁设计.html) · [文档索引](../index.html) · [索引 Markdown](../index.md)

[← 文档索引](../index.html)
依赖演进Phase C已交付

# Phase C · ORM Legacy AST 门禁

用 AST 静态检查锁住 Phase A 清零结果；挂入本地 test 与 GitHub CI

状态：Confirmed · 已交付 · 2026-07-20

**定位：**数据访问层演进的 **Phase C**（见计划与 [依赖升级 RFC](依赖升级RFC.html) DEC-007）。
Phase A（Query Contract / 分页硬门）已交付；本项**不 bump pin**、**不改业务行为**，只增加「禁止 Legacy ORM API 回潮」的静态门禁。
对照先例：`tests/test_ajax_form_guard.py`（模板 Ajax 表单配对）。

**已确认并交付（2026-07-20）：**L1+L2+L3；仅扫 `app/**/*.py`；Allowlist 空；
CI 方案 **C-CI-A**（`unit-tests.yml` 追加 `test_orm_legacy_guard` + `test_ajax_form_guard`）；
实现：`tests/test_orm_legacy_guard.py`，已挂 `cronpilot.sh test`。

**前置已满足（2026-07-20 实测）：**
`app/` 下无 `session.query(` / `.paginate(`（除合法的 `paginate_select`）；
管理端列表已走 `select()` + `app/services/pagination.py`。
因此可直接上「违例 = 测试失败」门禁，无需先清债。

## 一、问题 / 根因 / 方案

| 项 | 内容 |
| --- | --- |
| 问题 | Phase A 已清零列表 Legacy API；若无自动门禁，后续 PR / Agent 易再次引入 `db.session.query` 或 Query.`paginate`，导致文档「已清零」与代码漂移，并阻塞 Framework Generation（Phase D）。 |
| 根因 | 行为单测只保证「当前路径能跑」，不保证「禁止某类写法」；人工 `rg` 易漏且对 docstring/字符串误报。 |
| 方案 | 新增 `tests/test_orm_legacy_guard.py`：用标准库 `ast` 扫描 `app/**/*.py`；命中 L1/L2/L3 → unittest 失败。挂入 `cronpilot.sh test` 与 GitHub `unit-tests.yml`（CI 挂载方式见 §五，须确认）。 |

## 二、禁止规则（契约）

| ID | 禁止模式 | AST 识别（摘要） | 正确替代 |
| --- | --- | --- | --- |
| **L1** | `Model.query`（Declarative 遗留属性） | `Attribute(attr='query')`，且 value 为 Name/Attribute（排除 `paginate_select` 等无关名） | `db.session.get` / `select(...)` + `scalars` |
| **L2** | `session.query(` / `db.session.query(` | `Call` → `func` 为 `Attribute(attr='query')`，且链式 value 含 `session` | `select(...)` + `session.execute` / `scalars` |
| **L3** | Query 扩展 `.paginate(` | `Call` → `Attribute(attr='paginate')`，且接收者为 `.query(...)` Call 或 `.query` Attribute；**允许** `paginate_select`、`BaseRepository.paginate` / `self.paginate` | `paginate_select(...)` 或 Repo.`paginate` |

### 2.1 明确允许（非例外清单，而是合法 API）

- `paginate_select(...)`（Query Contract 执行器）
- `select(...)` / `db.session.execute` / `scalars` / `scalar` / `session.get`
- `text(...)` 绑定参数 SQL（调度 JobStore 等，见 [Tier 3 前置](Tier3前置收束设计.html)）
- 注释、docstring、字符串字面量中的文字说明（AST 自然忽略）

### 2.2 扫描范围

| 范围 | 是否扫描 | 理由 |
| --- | --- | --- |
| `app/**/*.py` | 是 | 生产代码契约 |
| `tests/**` | 否（默认） | 避免夹具/反例干扰；守卫自身反例用内联源码字符串测 |
| `datas/model/**` | 否（当前无 query API） | 模型定义层；若未来出现再扩 |
| `scripts/`、`doc/`、venv | 否 | 非运行时业务路径 |

### 2.3 Allowlist（路径级例外）

**默认空。**仅当确有无法改写的第三方同名 `.paginate` 或阶段性豁免时，才在测试模块内维护显式元组：

```
ALLOWLIST = (
    # ('app/foo.py', 'L3'),  # 须附注释说明原因与拆除日期
)
```

新增 allowlist 条目视为例外，须在 PR 说明与本设计「变更记录」中写明；**禁止**整目录豁免。

## 三、实现形态（确认后才写代码）

```
tests/test_orm_legacy_guard.py
  find_violations(source: str, filename: str) -> list[Violation]
  scan_app(root) -> list[Violation]
  TestOrmLegacyGuard
    test_no_legacy_orm_in_app          # 扫盘，failures == []
    test_detector_catches_l2_fixture   # 内联源码断言能检出
    test_detector_allows_paginate_select
    test_detector_ignores_string_literal
```

失败信息须可操作，例如：

```
ORM Legacy API 禁止进入 app/（Phase C）。
  app/main/views.py:214: L2 — db.session.query(CronInfos)
  请改用 select() + paginate_select（见 app/services/pagination.py）。
```

## 四、本地挂载

在 `scripts/cronpilot.sh` 的 unittest 列表中追加 `tests.test_orm_legacy_guard`（与 `tests.test_ajax_form_guard`、`tests.test_pagination` 同级）。

验收：

```
bash scripts/cronpilot.sh test
# 故意在 app/ 加一行 db.session.query(X) → 该测红；删回后绿
```

## 五、CI 挂载（须二选一确认）

**现状：**`.github/workflows/unit-tests.yml` 目前仅跑
`tests.test_p0_phase_a` 与 `tests.test_cronpilot_sign`，
**未**跑完整 `cronpilot.sh test`。因此仅改本地脚本不够，远程仍可能漏门禁。

| 方案 | 改动 | 优点 | 代价 |
| --- | --- | --- | --- |
| **C-CI-A（推荐 · 最小 diff）** | 在 `unit-tests.yml` 的 unittest 命令中**追加** `tests.test_orm_legacy_guard` （可选同批追加 `tests.test_ajax_form_guard`，同类静态门禁） | diff 小；立刻挡住 Legacy 回潮 | 本地全量与 CI 集合仍不完全一致 |
| **C-CI-B（更干净）** | CI 改为调用 `bash scripts/cronpilot.sh test` （或与脚本保持同一用例清单） | 本地 = CI，长期无漂移 | 需确认 CI 环境（venv 命名、core 依赖、耗时）；首 PR 面更大 |

**设计稿默认推荐：C-CI-A**（本轮只加 ORM guard；ajax guard 是否同批追加见确认项）。C-CI-B 可单开后续小 PR。

## 六、明确不做

- 不 bump SQLAlchemy / Flask / FSA（Phase D）
- 不抽 `BaseRepository`（Phase B）
- 不改 `app/main/views.py` / 模板业务逻辑
- 不做污点分析 / 不拦 `getattr(session, 'query')`（残余风险可接受；文档注明）
- 不新建独立 GitHub workflow（挂入现有 Unit tests）

## 七、验收清单（确认并实现后）

| # | 门禁 |
| --- | --- |
| 1 | `python -m unittest tests.test_orm_legacy_guard -v` 全绿 |
| 2 | `bash scripts/cronpilot.sh test` 含该模块且全绿 |
| 3 | CI 按确认方案跑到该测（矩阵 3.8–3.11） |
| 4 | 故意违例 → 红；移除 → 绿（本地证明） |
| 5 | 文档：本页标「已交付」；[交付状态](../交付状态与路线图.html) / [RELEASE\_NOTES [2.1.0]](../RELEASE_NOTES.html#210) / RFC 同步；`html_docs_to_markdown.py --check` |

## 八、与 Phase B / D 关系

Phase A ✓ Query Contract
→ Phase C（本项）AST 锁清零
→ Phase B（可选）薄 BaseRepository
→ Phase D Framework Generation（Flask2 + SA2 + FSA3）

C 不依赖 B；B 可与 C 并行或稍后。D 之前有 C，避免升级窗口再堆积 Legacy 债。

## § 确认记录

1. 规则范围：L1 + L2 + L3 — **已确认**
2. 扫描根：仅 `app/**/*.py` — **已确认**
3. CI 方案：C-CI-A — **已确认**
4. 同批追加 `tests.test_ajax_form_guard` — **已确认**
5. Allowlist 首版空 — **已确认**
6. 实现并本地 commit — **已执行**

[依赖升级 RFC](依赖升级RFC.html) ·
[交付状态与路线图](../交付状态与路线图.html) ·
[Tier 3 前置](Tier3前置收束设计.html) ·
[文档索引](../index.html)

CronPilot · Phase C ORM Legacy AST 门禁 · 已交付 v2.1.0 · [Markdown](PhaseC-ORM-Legacy-AST门禁设计.md) · [索引](../index.html)

---

[← 文档索引（HTML）](../index.html) · [← 文档索引（Markdown）](../index.md)
