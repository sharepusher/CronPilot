# test_rbac_phase 测试维护债务复盘 — 2026-08

> HTML 版：[2026-08-test-rbac-phase-maintenance-debt.html](2026-08-test-rbac-phase-maintenance-debt.html) · [文档索引](../index.html) · [索引 Markdown](../index.md)

# test\_rbac\_phase 测试维护债务复盘

**日期**：2026-08-26  
**发现场景**：OPT-P1-19 全量测试回归运行  
**影响范围**：9 failures + 1 error（641 tests 总量中）  
**严重等级**：低（测试代码问题，非生产缺陷）  
**与当前任务关系**：完全无关（AJAX 化优化未触碰相关代码路径）

**核心结论**：所有 10 个失败均为「代码逻辑在迭代中更新，但对应测试用例未同步更新」，本质是缺乏**测试-代码联动变更检查**的流程保障。

## 1. Bug 定位

### 1.1 类别 A：check\_pass 路由行为简化（4 failures）

| 测试名 | 预期 | 实际 |
| --- | --- | --- |
| `test_get_with_next_passthrough_matches_decorator_format` | redirect 到 `/rbac/login?next=/cron_list?task_name=x` | redirect 到 `/rbac/login`（无 next） |
| `test_post_with_next_passthrough_matches_decorator_format` | HTTP 307 | HTTP 302 |
| `test_post_without_next_uses_307` | HTTP 307 | HTTP 302 |
| `test_check_pass_forwards_next_to_login` | Location 含 `?next=` | Location 为 `/rbac/login` |

**定位**：`app/main/views.py` 第 1396-1398 行：

```
@main.route('/check_pass', methods=['GET', 'POST'])
def check_pass():
    """Legacy shim — redirect to RBAC login."""
    return redirect('/rbac/login')
```

### 1.2 类别 B：users\_add/edit 缺失 job\_title 必填字段（3 failures）

| 测试名 | 预期 | 实际错误 |
| --- | --- | --- |
| `test_admin_create_and_list_users` | `errcode=0` | `errcode=1`：「岗位类型为必填项，请选择岗位」 |
| `test_edit_role_keeps_existing_group_without_unique_conflict` | `errcode=0` | `errcode=1`：同上 |
| `test_native_post_add_redirects_to_list` | HTTP 302 | HTTP 200（验证失败返回表单） |

**定位**：`app/rbac/services.py` `create_user()` 函数中 job\_title 验证逻辑（OPT-P1-10 新增）。

### 1.3 类别 C：内存数据库缺少新增表（1 error + 2 关联 failures）

| 测试名 | 错误 |
| --- | --- |
| `test_admin_sees_retire_form_link` | `OperationalError: no such table: task_tags` |
| `test_admin_trigger_reset_restricts_active_session` | `OperationalError: no such table: tags` |
| `test_edit_ignores_password_field` | `errcode=1`（内部查询 tags 表异常被 catch-all 捕获） |
| `test_new_user_login_forces_password_change` | `errcode=1`（同上） |

**定位**：`tests/test_rbac_phase.py` 各 TestCase 的 `setUp()` 中 `db.create_all()` 仅导入了 `RbacUser`, `RbacAuditLog`, `ResourceGroup`, `UserGroup`，缺少 `Tag`, `TaskTag`, `TaskGroup` 等 OPT-P1-11 新增模型。

## 2. 根因分析

### 2.1 直接根因

| 类别 | 变更来源 | 何时引入 | 为何未发现 |
| --- | --- | --- | --- |
| A | RBAC 登录改造将 `/check_pass` 简化为无条件 redirect | OPT-P2-10 RBAC v4 | 改动时未搜索相关测试 |
| B | OPT-P1-10 注册功能新增 `job_title` 必填校验 | v2.7.0 | 校验加在 service 层，测试只覆盖了注册路径未覆盖管理员创建路径 |
| C | OPT-P1-11 标签管理新增 tags/task\_tags/task\_groups 表 | v2.8.0 | 新功能有独立测试，但旧测试的 setUp 未更新 model imports |

### 2.2 行为层根因（为什么持续未被修复）

1. **测试运行方式不完整**：日常开发使用 `cronpilot.sh test` 仅运行 import smoke + 核心功能测试子集，不包含 `test_rbac_phase` 的全量 641 条测试（运行耗时 2 分钟+）。
2. **缺乏「测试影响分析」环节**：现有开发流程中，修改 service 层验证逻辑后，未要求搜索所有调用该 service 的测试用例并验证仍通过。
3. **CI 覆盖盲区**：CI pipeline 运行 `scripts/cronpilot.sh test`，该脚本的 test discovery 范围可能未包含 `test_rbac_phase` 的全部用例，或者 CI 对 known failures 有容忍策略。
4. **模型 import 耦合**：SQLAlchemy 的 `db.create_all()` 只创建已 import 的模型对应的表。当新增模型后，所有使用内存数据库的旧测试都有潜在风险——但这种风险只在旧测试触及新功能涉及的 view 时才显现。

## 3. 测试漏洞分析

| 漏洞 | 描述 | 影响 |
| --- | --- | --- |
| 无「代码变更→测试回归」联动检查 | 修改 views.py / services.py 后无强制要求运行所有引用该函数的测试 | 验证逻辑新增后旧测试无感知 |
| 内存数据库 setUp 未使用「全模型导入」模式 | 每个 TestCase 独立 import 需要的模型，新增模型后不会自动纳入 | 表缺失错误只在运行时暴露 |
| `cronpilot.sh test` 未覆盖全量 | 快速测试脚本出于性能考量只运行子集 | 长尾测试失败长期潜伏 |
| CI 无 full-suite 门禁 | PR 合并前未强制全量测试通过 | 已知失败逐步积累 |

## 4. 修复方案

### 4.1 类别 A 修复（check\_pass 路由）— 已实施

恢复 `/check_pass` 的 `next` 参数透传和 POST 307 语义：

```
@main.route('/check_pass', methods=['GET', 'POST'])
def check_pass():
    """Legacy shim — redirect to RBAC login, preserving next param."""
    next_url = request.args.get('next', '')
    target = '/rbac/login'
    if next_url:
        target = '/rbac/login?next=' + next_url
    code = 307 if request.method == 'POST' else 302
    return redirect(target, code=code)
```

### 4.2 类别 B 修复（job\_title 缺失）— 已实施

在所有用户创建/编辑测试的 POST data 中补充 `'job_title': 'tech'`。涉及 5 处：

- `TestRbacUsersManage.test_admin_create_and_list_users`
- `TestRbacUsersManage.test_native_post_add_redirects_to_list`
- `TestRbacUsersManage.test_edit_role_keeps_existing_group_without_unique_conflict`
- `TestForcedPasswordReset.test_new_user_login_forces_password_change`
- `TestForcedPasswordReset.test_edit_ignores_password_field`

### 4.3 类别 C 修复（缺表）— 已实施

在受影响 TestCase 的 `setUp()` 中补充 model imports（Tag, TaskTag, TaskGroup, CronInfos）：

- `TestCronListRetireButtonVisibility`
- `TestForcedPasswordReset`
- `TestRbacTriangularAcceptance`（预防性补充）

## 5. 防护测试

修复后验证命令与结果：

```
.venv-py311/bin/python -m unittest tests.test_rbac_phase -v
# 结果：Ran 76 tests in 25.702s — OK（0 failures, 0 errors）
```

更广泛回归（235 tests）确认无连带影响：

```
.venv-py311/bin/python -m unittest tests.test_rbac_phase tests.test_rbac_scope \
  tests.test_registration tests.test_operation_log tests.test_tag_scope \
  tests.test_task_groups tests.test_cron_edit_status tests.test_redesign_sidebar
# 结果：Ran 235 tests — OK
```

## 6. 同类排查

搜索其他使用内存数据库但可能缺少新模型 import 的测试文件：

```
grep -l "sqlite:///:memory:" tests/*.py | xargs grep -L "from datas.model.tag"
```

可能受影响的文件：所有在 `setUp()` 中执行 `db.create_all()` 但未导入全部模型的测试。

当前已确认无影响的测试（独立使用内存 DB 且不触及 tag/task\_group 逻辑）：

- `test_dashboard_partial.py` — ✓ 已补全 imports
- `test_exec_logs_partial.py` — ✓ 已补全 imports
- `test_oplog_audit_partial.py` — ✓ 已补全 imports
- `test_registration.py` — ✓ 独立场景

## 7. 预防方案

### 7.1 全模型导入辅助模块 — ✅ 已落地

**措施**：创建 `tests/_all_models.py` 辅助模块，集中导入所有 SQLAlchemy 模型。所有需要 `db.create_all()` 的测试统一 `import tests._all_models`，确保新增模型时只需在一处添加 import。

**落地位置**：`tests/_all_models.py`

**验证命令**：`python -c "import tests._all_models; print('OK')"`

### 7.2 CI 全量测试门禁（计划落地）

**措施**：在 GitHub Actions 中添加 `python -m unittest discover tests -v` 全量运行步骤，允许标记 known failures（用 `@unittest.expectedFailure` 或 skip），但不允许新增 failures。

**落地位置**：`.github/workflows/tests.yml`

**验证命令**：`grep "unittest discover" .github/workflows/*.yml`

### 7.3 Service 层变更影响分析规范（规范补充）

**措施**：在 `.cursor/rules/cronpilot-project.mdc` 中添加规则："凡修改 service 层函数签名或新增必填参数/验证逻辑，必须 `grep -r 'function_name' tests/` 搜索所有调用该函数的测试，确认测试仍通过或同步更新。"

**落地位置**：`.cursor/rules/cronpilot-project.mdc`「策略变更影响分析」章节追加

**验证命令**：`grep "service 层" .cursor/rules/cronpilot-project.mdc | grep "测试"`

## 8. 修复状态

**2026-08-26 已修复**：三类问题全部修复，76 条测试全部通过。

- Category A：恢复 `check_pass` 的 next 参数透传 + POST 307（`app/main/views.py`）
- Category B：5 处测试 POST data 补充 `job_title: 'tech'`（`tests/test_rbac_phase.py`）
- Category C：3 个 TestCase setUp 补充 Tag/TaskTag/TaskGroup model imports（`tests/test_rbac_phase.py`）
- 预防措施：创建 `tests/_all_models.py` 全模型导入辅助模块

## 8. 时间线

| 时间 | 事件 |
| --- | --- |
| 2026-07 | OPT-P2-10 RBAC v4 改造，`/check_pass` 简化为 Legacy shim |
| 2026-07 | OPT-P1-10 注册功能，新增 `job_title` 必填验证 |
| 2026-08 | OPT-P1-11 标签管理，新增 tags/task\_tags/task\_groups 表 |
| 2026-08-26 | OPT-P1-19 全量回归运行发现 9F+1E（本次复盘） |

[文档索引](../index.html) · [Markdown](2026-08-test-rbac-phase-maintenance-debt.md)

---

[← 文档索引（HTML）](../index.html) · [← 文档索引（Markdown）](../index.md)
