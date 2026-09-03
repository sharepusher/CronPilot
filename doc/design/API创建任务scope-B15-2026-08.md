# B-15 API 创建任务 Scope 赋值 — 设计文档

> HTML 版：[API创建任务scope-B15-2026-08.html](API创建任务scope-B15-2026-08.html) · [文档索引](../index.html) · [索引 Markdown](../index.md)

# B-15 API 创建任务 Scope 赋值

**状态**：已交付  
**关联**：[API 安全与质量全面评估](API安全与质量全面评估-2026-08.html) §3.3 B-15  
**日期**：2026-08-28

## 1. 问题

API 创建任务时，所有新任务默认 `scope_type='GLOBAL'`。
operator token 的用户已有明确的组归属（`request._api_scope['group_ids']`），
但服务端不使用这些信息，导致 operator 可通过 API 创建 GLOBAL 任务（Web 端不允许）。

## 2. 根因

API 最初仅面向全局 `api_access_token`；引入用户 token 后未对齐 scope 逻辑。

## 3. 方案：服务端自动推断 scope

### 核心原则

用户的 token 已携带完整的组信息和权限。服务端应**自动推断** scope，
而非要求 API 调用方重复传递已知数据。

### 3.1 接口入参变更

| 端点 | 变更 |
| --- | --- |
| `POST /api/cron` （`CronUpsertIn` schema） | 新增 1 个可选字段 `group_name`（String）：  大部分场景无需传递（服务端自动推断），仅在 token 用户属于多个业务组时用于指定目标组。  传入值为业务组名称（`ResourceGroup.name`，全局唯一），服务端内部做 name→id 转换。 |
| `GET/POST /api/cron/add` （旧端点，无 schema） | 同上，通过 `request.values` 接受 `group_name` |

**不新增 `scope_type` / `group_id` 参数** — API 调用方不需要知道内部 ID，按组名传递即可。

### 3.2 按 Token 类型的自动推断矩阵

| Token 类型 | 不传 group\_name | 传 group\_name | 接口变化 |
| --- | --- | --- | --- |
| **全局 token** | scope\_type = GLOBAL | scope\_type = GROUP，按名称查找组并归入 | **零变化**（原行为 = 默认 GLOBAL） |
| **bypass 用户 token** （admin / seed admin） | scope\_type = GLOBAL | scope\_type = GROUP，按名称查找组并归入 | **零变化** |
| **operator 单组** | scope\_type = GROUP group\_id = 自动推断唯一组 | 校验 group\_name 对应组在用户组内 → GROUP 不在组内 → 403 | **零变化**（自动推断） |
| **operator 多组** | 返回 400： `"属于多个业务组，请指定 group_name"` | 校验 group\_name 对应组在用户组内 → GROUP 不在组内 → 403 | 多组场景需传 `group_name` |

### 3.3 出参变更

**成功响应无变化**：仍返回 `{"errcode": 0, "errmsg": "ok"}`。

新增错误响应：

| 场景 | HTTP | 响应 |
| --- | --- | --- |
| operator 多组未传 group\_name | 400 | `{"errcode":1, "errmsg":"属于多个业务组，请指定 group_name"}` |
| group\_name 对应的组不在用户组内 | 403 | `{"errcode":1, "errmsg":"只能在本人所属业务组内创建任务"}` |
| group\_name 对应的组不存在 | 400 | `{"errcode":1, "errmsg":"业务组不存在"}` |

### 3.4 向后兼容

| 调用方 | 影响 |
| --- | --- |
| 全局 `api_access_token` 脚本 | **零影响** |
| bypass 用户 token 脚本 | **零影响** |
| operator token + 单组 | **零影响**（自动推断） |
| operator token + 多组 | ⚠️ 需添加 `group_name` 参数（传组名称，不是 ID） |

## 4. 范围

| 文件 | 变更 |
| --- | --- |
| `app/api/views.py` | 新增 `_apply_api_scope(datas)`，在 `crons()` 和 `crons_legacy()` 的 `upsert_cron_by_task_name()` 前调用； 内部做 `group_name → group_id` 转换（查 `ResourceGroup` 表） |
| `app/api/schemas.py` | `CronUpsertIn` 新增 `group_name`（String, optional） |
| `tests/test_api_scope_s6.py` | 新增 `TestApiCreateScope`，覆盖上述矩阵全部 6 个场景 |

**不做**：不修改 `create_cron()` / `update_cron()`；不修改 Web 端。

## 5. 分批

单批交付。

## 6. 验收

1. 全局 token 不传 group\_name → GLOBAL ✓
2. 全局 token 传 group\_name="测试组" → GROUP ✓
3. operator token 单组不传 → 自动 GROUP ✓
4. operator token 多组不传 → 400 ✓
5. operator token 传非本组 group\_name → 403 ✓
6. operator token 传本组 group\_name → GROUP ✓
7. 传不存在的 group\_name → 400 ✓
8. `bash scripts/cronpilot.sh test` 全量通过
9. `python scripts/smoke_routes.py --check` 通过

## 7. 风险

- operator 多组 + 不传 group\_name 现在会 400（原来默认 GLOBAL 成功）— 这是期望的安全收紧
- 更新已有任务时 scope 不变（`update_cron()` 仅在有 scope 字段时覆盖）

## 8. 实现细节

```
def _resolve_group_name(group_name):
    """group_name → group_id，返回 (group_id, err_msg)。"""
    from datas.model.resource_group import ResourceGroup
    rg = db.session.scalars(
        select(ResourceGroup).where(ResourceGroup.name == group_name)
    ).first()
    if not rg:
        return None, '业务组不存在'
    return rg.id, None

def _apply_api_scope(datas):
    """根据 API scope 自动向 datas 注入 scope_type / group_id。"""
    scope = getattr(request, '_api_scope', None) or {'role': 'admin'}
    raw_gname = (datas.pop('group_name', None) or '').strip() or None

    # 全局 token → 默认 GLOBAL，可选传 group_name 创建组任务
    if scope.get('role') == 'admin':
        if raw_gname:
            gid, err = _resolve_group_name(raw_gname)
            if err:
                return err
            datas['scope_type'] = 'GROUP'
            datas['group_id'] = gid
        else:
            datas.setdefault('scope_type', 'GLOBAL')
        return None

    from app.rbac.policy import user_bypasses_scope
    user_role = scope.get('user_role', '')
    username = scope.get('username', '')
    group_ids = scope.get('group_ids', [])

    # bypass 用户 → 同全局 token
    if user_bypasses_scope(user_role, username=username, group_ids=group_ids):
        if raw_gname:
            gid, err = _resolve_group_name(raw_gname)
            if err:
                return err
            datas['scope_type'] = 'GROUP'
            datas['group_id'] = gid
        else:
            datas.setdefault('scope_type', 'GLOBAL')
        return None

    # 非 bypass 用户 → 强制 GROUP
    if not raw_gname:
        if len(group_ids) == 1:
            datas['scope_type'] = 'GROUP'
            datas['group_id'] = group_ids[0]
            return None
        return '属于多个业务组，请指定 group_name'

    gid, err = _resolve_group_name(raw_gname)
    if err:
        return err

    if gid not in set(int(x) for x in group_ids):
        return '只能在本人所属业务组内创建任务'

    datas['scope_type'] = 'GROUP'
    datas['group_id'] = gid
    return None
```

### 8.1 调用示例

```
# 全局 token / bypass 用户 — 创建全局任务（零变化）
curl -X POST /api/cron -H "Authorization: Bearer <token>" \
  -d '{"task_name":"my_task", "url":"http://..."}'

# 全局 token — 指定组名创建组任务
curl -X POST /api/cron -H "Authorization: Bearer <token>" \
  -d '{"task_name":"my_task", "url":"http://...", "group_name":"运维组"}'

# operator 单组 — 自动推断，无需传 group_name
curl -X POST /api/cron -H "Authorization: Bearer <token>" \
  -d '{"task_name":"my_task", "url":"http://..."}'

# operator 多组 — 必须指定 group_name
curl -X POST /api/cron -H "Authorization: Bearer <token>" \
  -d '{"task_name":"my_task", "url":"http://...", "group_name":"运维组"}'
```

[文档索引](index.html) · [Markdown](API创建任务scope-B15-2026-08.md) · [索引](index.html)

---

[← 文档索引（HTML）](../index.html) · [← 文档索引（Markdown）](../index.md)
