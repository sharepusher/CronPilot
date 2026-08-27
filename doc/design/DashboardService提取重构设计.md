# DashboardService 提取重构设计

> HTML 版：[DashboardService提取重构设计.html](DashboardService提取重构设计.html) · [文档索引](../index.html) · [索引 Markdown](../index.md)

# DashboardService 提取重构设计

重构 优先级 P2  
**日期**：2026-08-26  
**触发原因**：Dashboard 统计指标 Scope 隔离修复后识别的架构债务  
**影响范围**：`app/main/views.py`（`cron_list()` 函数）→ 新增 `app/services/dashboard_service.py`

## 1. 问题

`cron_list()` 视图函数当前 **242 行**，承载 7 种不同职责（请求解析、Scope 构建、统计计算、列表查询、标签作用域、v1/v2/partial 三路径渲染、croniter 调度计算），违反 Single Responsibility Principle，导致：

- **Bug 风险**：scope\_filters vs filter\_arr 混用（已触发一次 Bug）
- **可测试性差**：统计逻辑只能通过集成测试（Flask app + session）覆盖
- **维护成本高**：每轮 Dashboard 需求叠加在同一函数中，认知负载持续增长
- **Code Review 困难**：242 行函数中的变量作用域和执行路径难以追踪

## 2. 根因

### 2.1 演进路径

| 阶段 | 功能引入 | 行数增长 |
| --- | --- | --- |
| v1 简单列表 | filter + paginate + render | ~60 |
| OPT-P2-12 RBAC Scope | scope\_clause 构建 | +40 |
| OPT-P1-16 Redesign v2 | metrics / stats / overdue / next\_run / v2 render | +100 |
| OPT-P1-17 AJAX Partial | 三种返回模式 | +50 |
| OPT-P1-11 标签筛选 | tag scope 逻辑 | +20 |
| 本次修复 | scope\_filters 拆分 | +10 |

### 2.2 结构性根因

1. **缺乏「读操作 Service」概念**：`cron_service.py` 只处理写操作（add/edit/retire），读路径直接 View → Repository
2. **v1/v2 共用路由**：「渐进式迁移」策略导致一个函数服务两种 UI 需求
3. **无复杂度门禁**：CI 没有 McCabe/Radon 拦截 >100 行的函数
4. **helper 外溢**：`_compute_next_runs`、`_compute_overdue_map`、`_cached_overdue_stats` 虽然是独立函数，但定义在 `views.py` 中而非 Service 层

## 3. 方案

### 3.1 新增 DashboardService

```
# app/services/dashboard_service.py

class DashboardService:
    """Dashboard 统计指标计算服务。

    职责：
    - 基于 scope_filters 计算全局统计（不含 UI 展示过滤）
    - 计算当前页任务的运行详情（last_run, next_run, overdue_map）
    - 管理逾期缓存生命周期
    """

    def __init__(self, repo):
        self.repo = repo

    def compute_stats(self, scope_filters, cron_config=None):
        """返回 Dashboard 统计卡片数据。

        Args:
            scope_filters: 权限 + 组过滤条件（不含 UI 展示条件）
            cron_config: CRON_CONFIG 字典

        Returns:
            dict: {metrics, consecutive_failing, status_counts,
                   today_success_rate, overdue_count}
        """
        metrics = self.repo.metrics(list(scope_filters), cron_config=cron_config)
        return {
            'metrics': metrics,
            'consecutive_failing': self.repo.count_consecutive_failing(scope_filters),
            'status_counts': self.repo.status_counts(scope_filters),
            'today_success_rate': self.repo.today_success_rate(scope_filters),
            'overdue_count': self._cached_overdue_count(scope_filters),
        }

    def compute_page_context(self, page_items):
        """返回当前页任务的运行详情。

        Args:
            page_items: 当前页 CronInfos 对象列表

        Returns:
            dict: {last_run_map, next_run_map, overdue_map}
        """
        task_ids = [item.id for item in page_items]
        page_last_exec = self.repo.last_exec_time_by_ids(task_ids)
        return {
            'last_run_map': self.repo.last_run_details_by_ids(task_ids),
            'next_run_map': self._compute_next_runs(page_items),
            'overdue_map': self._compute_overdue_map(page_items, page_last_exec),
        }

    def overdue_ids_for_list(self, cache_key, filter_arr):
        """列表过滤 health='overdue' 时获取逾期 ID 集合。"""
        _, ids = self._cached_overdue_stats(cache_key, filter_arr)
        return ids

    # --- 私有方法（从 views.py 迁移） ---

    def _cached_overdue_count(self, scope_filters):
        """统计卡片用：仅计数，缓存 key 基于 scope。"""
        ...

    def _cached_overdue_stats(self, cache_key, filter_arr):
        """带 TTL 缓存的逾期计算（计数 + ID 集合）。"""
        ...  # 迁移自 views.py _cached_overdue_stats

    def _compute_next_runs(self, items):
        """croniter 计算下次执行时间。"""
        ...  # 迁移自 views.py _compute_next_runs

    def _compute_overdue_map(self, items, last_exec_map):
        """逾期检测。"""
        ...  # 迁移自 views.py _compute_overdue_map
```

### 3.2 重构后的 View 函数（伪代码）

```
@main.route('/cron_list', methods=['GET', 'POST'])
@require_permission('cron:read')
def cron_list():
    # ① 解析请求参数（~10 行）
    keyword = request.args.to_dict()
    page_query = PageQuery.from_args(request.args)
    task_name = keyword.get('task_name')
    ...

    # ② 构建 filters（~15 行）
    scope_filters = _build_scope_filters(role, group_ids, username, keyword)
    filter_arr = _build_display_filters(scope_filters, keyword)

    # ③ 列表查询 + 辅助数据（~15 行）
    repo = _cron_repo()
    page_data = repo.paginate_list(page_query, filters=filter_arr, ...)
    health_by_id = repo.health_by_cron_ids([item.id for item in page_data.items])
    task_group_map = _build_task_group_map(...)
    task_tag_map = build_task_tag_map(...)

    # ④ v1 partial 快速返回（~5 行）
    if partial and ui_version == 'v1':
        return _render_v1_partial(page_data, ...)

    # ⑤ v2 统计 + 渲染（委托 DashboardService）（~20 行）
    if ui_version == 'v2':
        svc = DashboardService(repo)
        stats = svc.compute_stats(scope_filters, cron_config)
        page_ctx = svc.compute_page_context(page_data.items)
        if partial:
            return _render_v2_partial(stats, page_ctx, ...)
        return _render_v2_full(stats, page_ctx, ...)

    # ⑥ v1 全量渲染（~10 行）
    return _render_v1_full(page_data, ...)
```

预期总行数：**~80 行**（从 242 行降低 67%）。

### 3.3 保留在 View 中的内容

| 内容 | 原因 |
| --- | --- |
| `request.args` 解析 | Controller 天然职责 |
| `session` 读取 | Flask context 绑定 |
| scope\_filters 构建 | 依赖 session，适合留在 view 层（或提取为工具函数） |
| 渲染分支（v1/v2/partial） | 响应格式选择是 Controller 的工作 |

### 3.4 迁移函数清单

| 当前位置（views.py） | 目标位置 | 行数 |
| --- | --- | --- |
| `_compute_next_runs()` | `DashboardService._compute_next_runs()` | 59 |
| `_compute_overdue_map()` | `DashboardService._compute_overdue_map()` | ~30 |
| `_cached_overdue_stats()` | `DashboardService._cached_overdue_stats()` | 23 |
| `_format_relative_time()` | `DashboardService._format_relative_time()` | 10 |
| `_overdue_cache` + `_OVERDUE_CACHE_TTL` | Service 实例变量或模块级 | 2 |
| **合计** |  | **~124 行** |

## 4. 范围

| 文件 | 变更类型 |
| --- | --- |
| `app/services/dashboard_service.py` | **新增**：DashboardService 类 + 迁移函数 |
| `app/main/views.py` | 修改：cron\_list() 重构 + 删除迁移出的 helper |
| `tests/test_dashboard_stats_stability.py` | 修改：增加 Service 层纯单元测试 |

**不做**：

- 不改变 Repository 层 API
- 不改变模板渲染逻辑
- 不改变 v1 路径行为
- 不改变 AJAX partial 返回结构
- 不引入新依赖

## 5. 分批

| 批次 | 内容 | 验收 |
| --- | --- | --- |
| Batch 1 | 创建 `dashboard_service.py` + 迁移 `_compute_next_runs` / `_format_relative_time` | 新测试通过 + 原测试不破 |
| Batch 2 | 迁移 `_compute_overdue_map` + `_cached_overdue_stats` + 缓存逻辑 | 同上 + `test_dashboard_stats_stability` 通过 |
| Batch 3 | 在 `cron_list()` 中引入 `DashboardService`，替换内联调用 | 全量测试 + restart 验证 |
| Batch 4 | 从 `views.py` 删除已迁移的 helper；提取 `_build_scope_filters()` / `_build_display_filters()` | views.py 行数 <100 行（cron\_list） + CI 绿 |

## 6. 验收

1. `.venv-py311/bin/python -m unittest tests.test_dashboard_stats_stability -v` — 全部通过
2. `bash scripts/cronpilot.sh test` — 无新增失败
3. `cron_list()` 函数体行数 ≤ 100 行（`wc -l` 或 `radon cc` 验证）
4. `DashboardService` 有独立单元测试（不依赖 Flask app context）
5. 浏览器验证：Dashboard 统计卡片在筛选切换时保持稳定

## 7. 风险

| 风险 | 概率 | 缓解 |
| --- | --- | --- |
| 重构引入回归 Bug | 低 | 逐批迁移 + 每批测试验证 |
| 缓存行为变化（进程级 → 实例级） | 低 | 保持模块级缓存 dict，不绑定实例 |
| v1 路径意外受影响 | 极低 | v1 不使用 DashboardService |
| Service 粒度过细（over-engineering） | 低 | 仅提取已证明的域逻辑；不做 interface 抽象 |

## 8. 行业对标

| 设计原则 | 来源 | 对齐度 |
| --- | --- | --- |
| Single Responsibility Principle | SOLID | ✅ Service 只管统计 |
| Thin Controller | Rails/Django/Flask best practice | ✅ View 仅协调 |
| Extract when changing for two reasons | Fowler - Refactoring | ✅ stats vs list 是两种变更原因 |
| Service Layer pattern | PoEAA | ✅ 读写分离 Service |
| Domain Logic ≠ Application Logic | DDD | ✅ croniter/overdue 是域逻辑 |

[文档索引](index.html) · [Markdown](DashboardService提取重构设计.md)

---

[← 文档索引（HTML）](../index.html) · [← 文档索引（Markdown）](../index.md)
