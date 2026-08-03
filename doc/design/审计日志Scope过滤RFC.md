# 审计日志 Scope 过滤 RFC

> HTML 版：[审计日志Scope过滤RFC.html](审计日志Scope过滤RFC.html) · [文档索引](../index.html) · [索引 Markdown](../index.md)

RFC已交付

# 审计日志 Scope 过滤 RFC

编号：OPT-P2-16/AUDIT-SCOPE · 日期：2026-07-31 · 状态：**已交付**（方案 A · 按操作者组过滤）  
前置依赖：OPT-P2-15（管理员 admin Scope 差异化）已交付  
注：原误标为 OPT-P2-13（已占用 = 规模化信息架构 v2.0.0），2026-08-03 更正为 OPT-P2-16

## 一、问题

管理员 admin Scope 差异化（OPT-P2-15）已交付后，按组管理员在任务列表、执行日志、操作记录、用户管理等页面均已按业务组隔离。
但 **审计日志**（`/rbac/audit-logs`）仍为全量展示，按组管理员可看到所有用户的登录/登出、权限拒绝、以及其他管理员对非本组用户的操作记录。

**用户视角**：

- 按组管理员看到不属于自己管理范围的用户审计信息（登录频率、IP 地址、操作详情）→ 信息泄露
- 与任务列表/操作记录已按组过滤的体验不一致 → 认知割裂

## 二、根因

| 位置 | 现状 | 问题 |
| --- | --- | --- |
| `datas/model/rbac_audit_log.py` | 模型无任何业务组关联字段 | 无法在查询时按组过滤；`resource` 字段存的是用户名文本（非结构化），无法高效 JOIN |
| `app/repositories/rbac_audit_log_repository.py` | 仅有 `paginate_all()` | 无 scope 过滤能力 |
| `app/rbac/views.py::audit_logs()` | 直接调 `paginate_all()` | 不判断当前用户是否 bypass scope |
| `app/rbac/services.py::write_audit_log()` | 写入时不记录操作者或目标的业务组信息 | 即使在查询端想过滤，也缺乏数据支撑 |

## 三、方案

### 3.1 核心思路：写入时记录组信息，查询时按组过滤

对比三个备选方案：

| 方案 | 描述 | 优点 | 缺点 |
| --- | --- | --- | --- |
| **A · 按操作者组过滤** (推荐) | 写入审计日志时记录操作者当时的 `group_ids`；查询时按操作者组与查看者组的交集过滤 | 实现简洁；语义清晰（「你能管的用户的审计记录」）；  与操作记录的 scope 过滤方式一致；  历史数据可通过 `user_groups` 表回填 | 跨组操作（admin B 操作 admin A 管辖的用户）的审计记录按 B 的组归属，A 可能看不到 |
| **B · 按目标用户组过滤** | 写入时额外记录目标用户的 `group_ids`；查询时按目标用户组过滤 | 语义更精确：「你管辖用户被操作的记录」 | `user:login/logout` 操作者即目标，需特殊处理；  `permission:deny` 无明确目标用户；  需在 `write_audit_log` 所有调用点传入目标信息 → 改动面大 |
| **C · 混合过滤（A+B）** | 同时记录操作者和目标的组，查询时取并集 | 最全面 | 实现复杂；审计记录可能出现在多个管理员的视图中 → 部分用户可能不理解 |

**推荐方案 A**：按操作者组过滤。理由：

1. 审计日志的核心关注是「我管理的用户做了什么」，而非「我管理的用户被做了什么」。
2. 按组管理员对 scope 外的用户**既不可见也不可操作**（OPT-P2-15 已落地），因此跨组操作的审计记录实际上不存在。
3. 实现面最小，与现有操作记录（`operation_log`）的 scope 逻辑一致。

### 3.2 数据模型改动

`rbac_audit_logs` 新增一列：

| 列名 | 类型 | 说明 |
| --- | --- | --- |
| `actor_group_ids` | `TEXT`，默认 `''` | 操作者写入时的业务组 ID 列表，逗号分隔（如 `"1,3"`）；种子 admin / 未登录为空字符串 |

选择逗号分隔而非 JSON 的原因：与 SQLite 兼容性最佳；`LIKE '%1%'` 虽不精确但辅以 Python 端过滤可满足需求。
MySQL 环境可升级为 `JSON` 类型并使用 `JSON_CONTAINS`，但 SQLite 不支持。

### 3.3 写入改动

`write_audit_log()` 增加 `actor_group_ids` 参数：

```
def write_audit_log(action='', resource='', status='allow',
                    user_id=None, username=None, ip=None):
    # 已有参数不变
    # 新增：从 session 获取操作者的 group_ids
    group_ids = session.get('group_ids') or []
    actor_group_ids_str = ','.join(str(g) for g in group_ids)

    entry = RbacAuditLog(
        user_id=...,
        username=...,
        action=action,
        resource=resource,
        ip=...,
        status=status,
        actor_group_ids=actor_group_ids_str,   # ← 新增
    )
    db.session.add(entry)
    db.session.commit()
```

API 鉴权失败（`api:deny`）场景下无 session，`actor_group_ids` 为空字符串 → 仅 bypass 用户可见。

### 3.4 查询改动

#### 3.4.1 Repository 层

```
class RbacAuditLogRepository(BaseRepository):
    def paginate_all(self, page_query):
        """种子 admin / 全局管理员 admin — 不过滤。"""
        stmt = select(RbacAuditLog).order_by(desc(RbacAuditLog.id))
        return self.paginate(stmt, page_query)

    def paginate_by_scope(self, page_query, viewer_group_ids):
        """按组管理员 — 仅展示操作者组与 viewer_group_ids 有交集的审计记录。"""
        # 策略：先查全量，Python 端过滤组交集
        # 原因：SQLite 不支持 JSON_CONTAINS；逗号分隔字段的 SQL LIKE 不精确
        # 性能：审计日志量通常不大（日级百条），分页后 Python 过滤可接受
        stmt = select(RbacAuditLog).order_by(desc(RbacAuditLog.id))
        return self.paginate_with_filter(
            stmt, page_query,
            python_filter=lambda row: _groups_intersect(
                row.actor_group_ids, viewer_group_ids
            ),
        )
```

备选：如审计日志量增长，可改用 SQLite 的 `INSTR()` + 多 `OR` 条件构建 SQL 级过滤；
但当前规模下 Python 端过滤足够。

#### 3.4.2 组交集判定辅助函数

```
def _groups_intersect(actor_group_ids_str, viewer_group_ids):
    """判断操作者的组 ID 列表与查看者的组 ID 列表是否有交集。"""
    if not actor_group_ids_str:
        return False  # 空 = 种子 admin 或系统行为 → 按组管理员不可见
    try:
        actor_ids = {int(x) for x in actor_group_ids_str.split(',') if x.strip()}
    except ValueError:
        return False
    return bool(actor_ids & set(viewer_group_ids))
```

#### 3.4.3 路由层

```
@rbac.route('/audit-logs', methods=['GET'])
@require_permission('audit:read')
def audit_logs():
    page_query = PageQuery.from_args(request.args)
    repo = RbacAuditLogRepository(db.session)

    if _actor_bypasses_scope():
        page_data = repo.paginate_all(page_query)
    else:
        viewer_group_ids = session.get('group_ids') or []
        page_data = repo.paginate_by_scope(page_query, viewer_group_ids)

    return render_template(
        'rbac/audit_logs.html',
        page_data=page_data,
        audit_action_label=audit_action_label,
        audit_status_label=audit_status_label,
        audit_resource_label=audit_resource_label,
    )
```

### 3.5 历史数据回填

升级后，已有审计记录的 `actor_group_ids` 为空字符串（默认值）。处理策略：

| 策略 | 说明 |
| --- | --- |
| **不回填**（推荐） | 历史审计记录的 `actor_group_ids` 保持空 → 仅 bypass 用户（种子 admin / 全局管理员 admin）可见。  按组管理员只能看到**升级后**的新审计记录 → 安全、保守。  审计日志是安全敏感数据，宁可少展示不可多展示。 |
| **可选回填**（运维脚本） | 提供 `scripts/backfill_audit_groups.py` 脚本：  遍历 `rbac_audit_logs`，根据 `user_id` 查 `user_groups` 当前值回填。  注意：这反映**当前**组绑定，非审计事件发生时的组绑定 → 可能不精确。  非自动执行，由管理员手动评估后运行。 |

### 3.6 paginate\_with\_filter 实现说明

现有 `BaseRepository.paginate()` 直接对 SQL 语句分页。新增 `paginate_with_filter()` 需在 Python 端过滤后再分页。

**实现方式**：

1. 取当前页 × 2 的数据（预拉取）
2. Python 端过滤
3. 如不足一页，继续拉取下一批
4. 构造与 `paginate()` 相同的分页对象返回

局限：`total` 数量不精确（因为 SQL 层不知道哪些会被 Python 过滤掉）。可标注为"约 N 条"或只展示"上一页/下一页"。

**备选（更简单）**：不用 `paginate_with_filter`，而是在 SQL 层用多个 `OR` 条件近似过滤：

```
# 对每个 viewer_group_id 生成 LIKE 条件（不精确但实用）
# 如 viewer_group_ids = [1, 3]
# WHERE actor_group_ids LIKE '%1%' OR actor_group_ids LIKE '%3%'
# 可能误匹配（如 group_id=1 匹配 group_id=11, 13）
# 可通过逗号包围方式改善：actor_group_ids 存储为 ",1,3,"
# 查询时 LIKE '%,1,%'
```

**推荐使用逗号包围存储**（如 `,1,3,`），可在 SQL 层精确 LIKE 过滤，避免 Python 端分页复杂性。

### 3.7 最终推荐：逗号包围存储 + SQL 层过滤

| 项 | 说明 |
| --- | --- |
| 存储格式 | `,1,3,`（首尾加逗号）；空组为 `''` |
| SQL 查询 | `WHERE actor_group_ids LIKE '%,1,%' OR actor_group_ids LIKE '%,3,%'` |
| 优势 | 无误匹配；可直接使用 `paginate()`，`total` 精确；SQLite / MySQL 通用 |
| Repository 改动 | `paginate_by_scope(page_query, viewer_group_ids)` 构建 `OR` 条件链   ``` filters = [     RbacAuditLog.actor_group_ids.like('%,{},%'.format(gid))     for gid in viewer_group_ids ] stmt = select(RbacAuditLog).where(or_(*filters)).order_by(desc(RbacAuditLog.id)) ``` |

## 四、范围（改什么、不改什么）

### 改

| 路径 | 改动类型 |
| --- | --- |
| `datas/model/rbac_audit_log.py` | 新增 `actor_group_ids` 列（`TEXT`，默认 `''`） |
| `scripts/ensure_business_tables.py` | 补列逻辑覆盖 `rbac_audit_logs.actor_group_ids` |
| `app/rbac/services.py::write_audit_log()` | 写入时从 session 获取 group\_ids 并转为逗号包围格式 |
| `app/repositories/rbac_audit_log_repository.py` | 新增 `paginate_by_scope(page_query, viewer_group_ids)` |
| `app/rbac/views.py::audit_logs()` | 按 bypass 状态选择 `paginate_all` 或 `paginate_by_scope` |
| `tests/test_rbac_scope.py` | 新增审计日志 Scope 过滤用例 |

### 不改

- 审计日志模板 `audit_logs.html` 不变（列不变、展示不变）
- 操作记录（`operation_log`）不变——已有独立的 scope 过滤逻辑
- 审计日志的 `action` / `resource` / `status` 字段不变
- `write_audit_log()` 的调用点无需修改（group\_ids 从 session 自动获取）
- 种子 admin / 全局管理员 admin 的审计日志展示不受影响（继续全量展示）

## 五、分批

| 批次 | 内容 | 验收标准 |
| --- | --- | --- |
| **Batch 1** 数据模型 + 写入 | - `rbac_audit_log.py`：新增 `actor_group_ids` 列 - `ensure_business_tables.py`：补列逻辑 - `services.py::write_audit_log()`：写入逗号包围格式 - 测试：写入后断言 `actor_group_ids` 格式正确 | `bash scripts/cronpilot.sh test` 通过；  `bash scripts/ensure_business_tables.sh` 无报错；  新增审计记录含正确的 `actor_group_ids` |
| **Batch 2** 查询过滤 + 路由 | - `rbac_audit_log_repository.py`：新增 `paginate_by_scope()` - `rbac/views.py::audit_logs()`：按 bypass 选择分页方法 - 测试：按组管理员仅可见组交集内的审计记录 | `bash scripts/cronpilot.sh test` 通过；  `restart` 后浏览器验证：  · 种子 admin 看到全部审计记录  · 按组管理员仅看到自身组相关的审计记录  · 历史（无 `actor_group_ids`）记录对按组管理员不可见 |

## 六、验收

### 6.1 权限矩阵（改后预期）

| 查看者 | 可见审计记录范围 |
| --- | --- |
| 种子 admin（`username='admin'`） | 全部审计记录（不受过滤影响） |
| 管理员 admin（全部，`group_ids=[]`） | 全部审计记录（bypass scope） |
| 管理员 admin（按组，`group_ids=[1,2]`） | **仅**操作者 `actor_group_ids` 与 `[1,2]` 有交集的记录  包含：自己的操作记录、组 1/2 内用户的登录/登出/权限拒绝等  不含：种子 admin 的记录、组 3/4 用户的记录、无组信息的历史记录 |
| operator / viewer | ❌ 无权限（`require_permission('audit:read')` 拦截） |

### 6.2 最低验收命令

- `bash scripts/cronpilot.sh test`
- `bash scripts/cronpilot.sh restart --daemon`
- 种子 admin 登录 → 审计日志页 → 全部记录可见
- 按组管理员登录 → 审计日志页 → 仅组内用户记录可见
- 按组管理员操作（如重置密码）→ 审计日志新增记录含正确 `actor_group_ids`

## 七、风险

| 风险 | 影响 | 缓解 |
| --- | --- | --- |
| 历史审计记录对按组管理员不可见 | 升级后按组管理员无法查看升级前的审计记录 | **预期行为**：审计日志是安全敏感数据，宁可少展示。  可选：提供 `scripts/backfill_audit_groups.py` 回填脚本（按当前组绑定回填，不自动执行） |
| `actor_group_ids` 反映写入时的组绑定，非当前 | 用户组变更后，旧审计记录的 `actor_group_ids` 不会更新 | **符合审计原则**：审计记录应反映事件发生时的状态，而非当前状态。  管理员组变更是低频操作，影响有限 |
| 逗号包围格式的 LIKE 查询性能 | 当审计记录量极大（万级+）且 viewer\_group\_ids 较多时，多 `OR LIKE` 可能较慢 | 审计日志日增量通常在百级以内；  如需优化可添加 `actor_group_ids` 索引或改用关联表 |
| API 鉴权失败记录（`api:deny`）无 session | `actor_group_ids` 为空 → 按组管理员不可见 | `api:deny` 通常需要全局视角排查 → 仅 bypass 用户可见合理；  如需按组管理员可见，可在 `_api_token_guard` 中从 token 关联的用户获取 group\_ids |

## 八、与现有文档的一致性

- 改后需同步更新：`doc/管理员admin-Scope差异化设计.html`（移除「审计日志本批次不做 Scope 过滤」注释）
- `doc/RBAC架构设计方案.html`：审计日志章节补充 Scope 过滤说明
- `RELEASE_NOTES.md`：纳入版本说明
- `doc/交付状态与路线图.html`：更新条目

[文档索引](../index.html) · [admin Scope 设计](管理员admin-Scope差异化设计.html) · [RBAC 架构设计](RBAC架构设计方案.html)
· [Markdown](审计日志Scope过滤RFC.md) · [索引](../index.html)

---

[← 文档索引（HTML）](../index.html) · [← 文档索引（Markdown）](../index.md)
