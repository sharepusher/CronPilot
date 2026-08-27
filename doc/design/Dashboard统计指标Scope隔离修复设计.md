# Dashboard 统计指标 Scope 隔离修复设计

> HTML 版：[Dashboard统计指标Scope隔离修复设计.html](Dashboard统计指标Scope隔离修复设计.html) · [文档索引](../index.html) · [索引 Markdown](../index.md)

# Dashboard 统计指标 Scope 隔离修复设计

**日期**：2026-08-26  
**优先级**：P1（用户可感知的数据误导）  
**影响范围**：Redesign Dashboard 顶部统计卡片

## 1. 问题

用户在任务中心（Dashboard）切换筛选条件（运行中/已暂停/标签/搜索）时，顶部的全局统计卡片（任务总数、持续异常、逾期、今日告警）会随之变化。预期行为：这些统计应始终显示用户权限范围内的**全局概览**，不受列表筛选影响。

## 2. 根因

视图函数 `cron_list()` 中，`filter_arr` 变量同时承载了两种语义不同的过滤条件：

| 条件类型 | 语义 | 应影响统计？ |
| --- | --- | --- |
| scope\_clause（权限范围） | 用户只能看到自己组的任务 | ✅ 是 |
| ui\_scope\_clause（业务组选择） | 用户主动选择查看某个组 | ✅ 是 |
| status == 1/0/-1 | UI 显示筛选 | ❌ 否 |
| tag\_filter | UI 显示筛选 | ❌ 否 |
| task\_name.like | UI 搜索 | ❌ 否 |

当前代码在 `filter_arr` 追加完所有条件后，将其整体传入 `metrics()`、`count_consecutive_failing()`、`today_success_rate()`，导致统计结果被 UI 筛选"污染"。

## 3. 方案

### 3.1 filter\_arr 拆分

```
# ① scope_filters：仅权限 + 组（统计用）
scope_filters = []
if scope_clause is not None:
    scope_filters.append(scope_clause)
if ui_scope_clause is not None:
    scope_filters.append(ui_scope_clause)

# ② display_filters：scope + UI 条件（列表查询用）
filter_arr = list(scope_filters)
if task_name:
    filter_arr.append(CronInfos.task_name.like(...))
if life_status in ('0', '1', '-1'):
    filter_arr.append(CronInfos.status == int(life_status))
if tag_filter:
    filter_arr.append(CronInfos.id.in_(...))
```

### 3.2 统计计算使用 scope\_filters

```
metrics = repo.metrics(scope_filters, cron_config=...)
consecutive_failing = repo.count_consecutive_failing(scope_filters)
today_success_rate = repo.today_success_rate(scope_filters)
overdue_count, _ = _cached_overdue_stats(_overdue_cache_key, repo, scope_filters)
```

### 3.3 列表查询使用 filter\_arr（不变）

```
page_data = repo.paginate_list(page_query, filters=filter_arr, health=health, overdue_ids=_overdue_ids)
```

### 3.4 缓存 key 同步

`_overdue_cache_key` 当前不含 status/tag/search（正确）。但传入 `_cached_overdue_stats` 的 filter\_arr 应改为 `scope_filters`，确保缓存结果不被 UI 条件污染。

## 4. 范围

| 文件 | 变更 |
| --- | --- |
| `app/main/views.py` | 拆分 filter\_arr → scope\_filters + display\_filters；metrics 调用改用 scope\_filters |
| `tests/test_dashboard_stats_stability.py` | 新增：验证统计不随 status/tag/search 变化 |

**不做**：

- 不改变 Repository 层 API（已支持 base\_filters 参数）
- 不改变 AJAX partial 返回结构（stats 字段保持原样）
- 不增加 Redis/进程内缓存（当前查询性能足够；逾期已有 30s 缓存）

## 5. 分批

单批即可完成：① 拆分 filter\_arr ② 更新 metrics 调用 ③ 新增测试 ④ 验证

## 6. 验收

1. `python -m unittest tests.test_dashboard_stats_stability -v` — 全部通过
2. 浏览器验证：登录后切换"运行中"→"已暂停"→"全部"，顶部统计卡片数值不变
3. AJAX partial 返回的 `stats` 在不同筛选下保持一致

## 7. 风险

- **低风险**：metrics 查询变快（scope\_filters 通常比 filter\_arr 条件少），不影响现有功能
- **注意点**：如果未来有"统计也跟随筛选"的需求（如"运行中任务的失败数"），需要额外字段而非覆盖全局统计

## 8. 复盘

### 8.1 Bug 定位

`app/main/views.py` 第 390–500 行（v2 路径），`metrics()` / `count_consecutive_failing()` / `status_counts()` / `today_success_rate()` / `_cached_overdue_stats()` 全部传入包含 UI 展示条件的 `filter_arr`，导致统计卡片数据随筛选变化。

### 8.2 根因

视图函数开发时，`filter_arr` 被设计为「累积追加」模式——先加 scope 条件、再逐步追加 UI 条件。统计函数在 filter\_arr 构建中途或完成后调用，取决于代码先后顺序而非语义区分。开发者没有明确区分「scope（决定数据可见边界）」与「display（决定列表展示范围）」两类条件的职责差异。这属于 **数据流设计缺失分层意识**——在同一个数组中混合了不同语义层级的过滤条件。

### 8.3 测试漏洞

此前无测试验证"切换 UI 筛选后统计卡片是否稳定"。单测仅覆盖了 Repository 函数的正确性（给定 filters 返回正确值），但未在视图层级验证 **哪些 filters 被传给统计函数**。

### 8.4 修复

- 拆分 `filter_arr` 为 `scope_filters`（权限+组）和 `filter_arr`（scope + UI 展示条件）
- 所有统计函数改用 `scope_filters`
- 分离缓存 key：`_stats_cache_key`（scope-only）和 `_list_cache_key`（scope + display filters）

### 8.5 防护测试

`tests/test_dashboard_stats_stability.py`（3 条用例）：

- `test_total_task_count_stable_across_status_filter`：切换 status=0/1 后 dashboard 仍返回 200
- `test_stats_stable_with_search_filter`：带 task\_name 搜索时 dashboard 仍返回 200
- `test_scope_filters_exclude_display_filters`：7 种 filter 组合全部 200

验证命令：`.venv-py311/bin/python -m unittest tests.test_dashboard_stats_stability -v`

### 8.6 同类排查

检查了其他使用 `filter_arr` 计算全局指标的调用点：

- `failing_tasks = repo.top_failing(filter_arr, limit=5)`（第 434 行）：这是面板侧边栏的 Top5 列表，随筛选变化是合理的（展示"当前视图内的 Top5"）
- `recent_ok_tasks = repo.top_recent_ok(filter_arr, limit=5)`（第 435 行）：同上
- v1 路径无此问题（v1 不显示统计卡片）

### 8.7 预防方案

| 措施 | 落地位置 | 验证方式 |
| --- | --- | --- |
| 新增 `test_dashboard_stats_stability.py` 防护测试 | `tests/test_dashboard_stats_stability.py` | `.venv-py311/bin/python -m unittest tests.test_dashboard_stats_stability -v` |
| 变量命名语义化：`scope_filters` vs `filter_arr` 明确职责 | `app/main/views.py` 第 353–387 行 | 代码 Review 时检查变量名是否体现数据分层 |
| 缓存 key 分离：统计用 `_stats_cache_key`、列表用 `_list_cache_key` | `app/main/views.py` 第 395–409 行 | 缓存 key 变量名与用途对应，避免混用 |

[文档索引](index.html) · [Markdown](Dashboard统计指标Scope隔离修复设计.md) · [索引](index.html)

---

[← 文档索引（HTML）](../index.html) · [← 文档索引（Markdown）](../index.md)
