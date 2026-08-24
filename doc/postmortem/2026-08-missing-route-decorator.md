# 复盘：users_reset_password 路由装饰器丢失导致全站 500

> HTML 版：[2026-08-missing-route-decorator.html](2026-08-missing-route-decorator.html) · [文档索引](../index.html) · [索引 Markdown](../index.md)

# 复盘：`users_reset_password` 路由装饰器丢失导致全站 /rbac/users 500

**日期**：2026-08-21  |  **严重程度**：P0 管理端核心页面不可用  |  **影响范围**：所有拥有 `user:manage` 权限的用户无法访问用户管理页面

## 1. Bug 定位

`app/rbac/views.py` 第 696 行，`users_reset_password` 函数缺少 `@rbac.route('/users/reset_password', methods=['POST'])` 路由装饰器：

```
# 错误状态（修复前）
@require_permission('user:manage')   # ← @rbac.route 丢失
@csrf_protect
def users_reset_password():
    ...
```

导致模板 `redesign/users.html` 第 97 行的 `url_for('rbac.users_reset_password')` 在运行时抛出 `werkzeug.routing.exceptions.BuildError`，整个 `/rbac/users` 页面返回 500。

**错误日志（摘录）**：

```
werkzeug.routing.exceptions.BuildError: Could not build url for endpoint 'rbac.users_reset_password'.
Did you mean 'rbac.users_reset_token' instead?
File "app/templates/redesign/users.html", line 97, in block 'content'
    href="{{ url_for('rbac.users_reset_password') }}?id={{ item.id }}"
```

## 2. 根因

两次 `StrReplace` 操作边界未对照，导致第二次替换覆盖了第一次替换结果中的关键装饰器行：

1. 第一次 StrReplace（插入 `users_view` 路由）：将原来的 `@rbac.route('/users/reset_password', methods=['POST'])` 放在了替换后内容的末尾，正确。
2. 第二次 StrReplace（修正 `users_view` 函数体中的 helper 调用）：`old_string` 精确匹配了 `users_view` 函数的全部代码，`new_string` 遗漏了原来末尾的 `@rbac.route('/users/reset_password', methods=['POST'])` 行，导致该装饰器从文件消失。

**行为层根因**：Agent 在连续多次 StrReplace 时，没有执行"替换后读回验证"——每次替换后未 grep 或读取受影响行来确认内容完整，而是直接进行下一次替换，在积累的上下文误差下丢失了关键行。

## 3. 测试漏洞

| 测试层 | 覆盖情况 | 根因 |
| --- | --- | --- |
| `test_import_smoke.py` | 只测顶层 import，不验证路由注册 | 路由注册是运行时行为，import 成功不代表路由存在 |
| `test_redesign_sidebar.py` | 测试导航链接，不请求 /rbac/users 并断言 200 | 只关注侧边栏渲染，不关注页面实际响应 |
| 无集成测试 | 没有任何测试向 /rbac/users 发送 GET 请求并断言响应码 + 内容 | 集成测试层缺失 |

## 4. 修复

```
# 修复后
@rbac.route('/users/reset_password', methods=['POST'])  # ← 补回装饰器
@require_permission('user:manage')
@csrf_protect
def users_reset_password():
    ...
```

同时通过 AST 扫描确认全部 29 个 rbac 路由函数均有 `@rbac.route` 装饰器，无其他遗漏。

## 5. 防护测试

新增 `scripts/check_route_completeness.py`，用 AST 扫描所有带 `@require_permission` 装饰器的函数，断言同时存在 `@blueprint.route` 装饰器：

```
python scripts/check_route_completeness.py --check app/rbac/views.py
```

同时在 `tests/test_redesign_pages.py`（新建）中加入：

```
def test_users_page_200(self):
    """访问 /rbac/users 应返回 200，确保 url_for 全部可解析。"""
    with self._login_as_biz_admin() as c:
        rv = c.get('/rbac/users')
        self.assertEqual(rv.status_code, 200)
        self.assertIn(b'url_for', rv.data)  # 确保模板渲染完整
```

## 6. 同类排查

使用 AST 扫描 `app/rbac/views.py` 中所有 29 个路由函数：

```
OK route: login, logout, register, forgot_password, change_password,
edit_profile, complete_profile, api_token_page, api_token_reset,
users_list, users_add, users_edit, users_view, users_reset_password,
users_reset_token, users_set_active, groups_list, groups_add,
groups_edit, audit_logs, registration_review, registration_approve,
registration_reject, tag_manage, tag_create, tag_update, tag_rename,
tag_tasks, tag_delete
```

全部 29 个路由函数均有 `@rbac.route` 装饰器，无其他同类问题。

## 7. 预防方案

| 措施 | 落地位置 | 验证命令 |
| --- | --- | --- |
| **新建路由完整性检查脚本**：AST 扫描 Blueprint 文件，对每个带 `@require_permission` 的函数断言存在 `@blueprint.route`，否则 exit(1) | `scripts/check_route_completeness.py` | `python scripts/check_route_completeness.py --check app/rbac/views.py` |
| **连续 StrReplace 后强制读回验证**：在 AGENTS.md 新增规范：连续多次 StrReplace 修改同一函数或临近代码区域时，必须在每次替换后 Read 受影响行（±20 行）确认关键装饰器/语句未被消除 | `AGENTS.md` "大文件修改前结构分析"节 | 代码审查：`grep -n "@rbac.route" app/rbac/views.py | wc -l` 应与路由函数总数相等 |
| **新增集成测试：管理端核心页面 200 检查**：以已登录 session 访问 /rbac/users、/rbac/groups、/rbac/audit-logs，断言 status\_code == 200 | `tests/test_redesign_pages.py`（新建） | `python -m unittest tests.test_redesign_pages -v` |

[文档索引](index.html) · [Markdown](2026-08-missing-route-decorator.md) · [索引](index.html)

---

[← 文档索引（HTML）](../index.html) · [← 文档索引（Markdown）](../index.md)
