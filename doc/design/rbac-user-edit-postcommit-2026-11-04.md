# 用户授权编辑提交后读取故障分析与修复设计

> HTML 版：[rbac-user-edit-postcommit-2026-11-04.html](rbac-user-edit-postcommit-2026-11-04.html) · [文档索引](../index.html) · [索引 Markdown](../index.md)

独立统一方案已形成：[RBAC 缓存失效与提交后处理边界统一修复设计](rbac-cache-postcommit-boundary-2026-11-04.html)。后续实施范围以该待确认设计为准，本文保留分析依据。

# 用户授权编辑提交后读取故障分析与修复设计

rev.1 · 2026-11-04 · 待用户 Review 确认。本轮仅分析和隔离探针，没有修改业务实现。

后续同类排查已复现其他生命周期入口的相似问题，见[缓存专项排查](../qa/cache-postcommit-audit-2026-11-04.html)。本文原推荐范围尚未扩展，实施前须结合该结果确认。

## 1. 问题及触发条件

用户管理修改角色或业务组时，update\_user\_management 已经把用户信息、认证版本、Token 和审计一起提交；接着执行 \_invalidate\_api\_scope\_cache(user.id)。Session 在 commit 后默认将 ORM 属性过期，求值 user.id 可能再查询数据库。若此查询失败，异常在调用缓存失效函数之前发生，服务没有返回 updated，缓存也没有被清除。

需要三个条件：本次实际改变角色或组、事务提交成功、提交后的过期属性查询失败。普通成功路径不必然出错；资料-only 保存不执行这行。数据库中已保存的变更不会自动撤销。该问题能造成“已保存却报错”；若旧 Token 在该进程已有缓存，后续请求还可能使用旧权限。

## 2. 复现与证据

原探针确认角色已写成 operator，服务却抛出提交后读取异常。本次增加降权及缓存探针：先将专用测试用户置为 operator 并缓存其旧 Token，再保存 viewer，使用 SQLAlchemy after\_commit 标记以及 do\_orm\_execute 的 is\_column\_load 分支阻止提交后的列加载。输出：

```
{"raised_after_commit": true, "stored_role": "viewer", "old_token_resolves_role": "operator", "scope_before": "operator"}
```

脚本：[cache\_probe.py](../qa/evidence/rbac-postcommit-assessment-2026-11-04/cache_probe.py)。执行 `PYTHONPATH=. .venv-py311/bin/python doc/qa/evidence/rbac-postcommit-assessment-2026-11-04/cache_probe.py`，仅操作 tests.test\_user\_edit\_change\_set 的内存数据库，清理自身缓存夹具。该探针证明提交后读取可阻断本进程缓存失效及旧 Token 解析；本轮未通过浏览器或实际 API 写接口重新执行该故障。

已读取 app/rbac/services.py 的提交和缓存函数、app/api/\_\_init\_\_.py 的 \_resolve\_user\_token 与缓存命中分支：命中缓存时直接返回旧 scope，不查当前数据库。旧缓存最终受 \_CACHE\_TTL 限制；该边界不是撤权立即生效的证明。用户认可的“有权限时发起的在途操作允许完成”继续成立，本问题涉及提交完成后的新请求。

## 3. 根因与测试漏洞

事务返回路径把持久化对象当作稳定标量使用；主键属性同样可能被 ORM 过期机制加载。缓存函数内部虽捕获异常，却无法保护调用前的参数求值。服务已有经整数校验的 user\_id，可以避免这一额外数据库依赖。

现有 test\_u2\_authorization\_change\_bumps\_once\_and\_invalidates\_after\_commit 在健康内存库中检查成功和失效次数，没有阻断 commit 后的列加载；commit\_unknown 测试只模拟 commit 抛错，不等价于“提交成功后下一次查询失败”。因此已有测试可全部通过而遗漏此分支。

## 4. 推荐方案

1. 成功提交后的缓存失效使用既有整数参数 user\_id，不访问过期 ORM 对象。返回结果继续由已经计算的标量及 effective\_change\_set 组成；角色、组、认证版本、Token 与审计仍在原事务中提交。
2. 核对 users\_edit 路由在服务返回后的分支：already\_applied、conflict、commit\_unknown 的原生跳转使用已解析的 user\_id，避免 rollback/commit 后只为拼 URL 又读取 user.id。成功 Ajax/原生响应由 \_users\_form\_response 构造，无需重新载入目标模型。
3. 保留现有“commit 正常返回 → 已知保存成功”“commit 抛异常 → 结果待核实”的语义；不得在提交后的辅助处理失败时反向写回旧角色或重复轮换 Token。
4. 缓存函数已有 best-effort 异常保护，本批不改变其异常策略。必须通过真实缓存失效用例验证本次目标，不能只模拟一个总会成功的缓存函数。多 worker 缓存传播及其 TTL 是既有架构边界，另行评估；本修复不能宣称实现跨进程即时撤权。

备选：关闭 expire\_on\_commit 会影响整个应用对象生命周期；在外层 catch-all 中吞掉异常则可能保留旧缓存；两者均不采用。先刷新模型仍依赖故障中的数据库，没有必要。

## 5. 范围与分批

预计修改 app/rbac/services.py 的该函数提交后处理、app/rbac/views.py 的对应返回跳转，以及针对性测试和复盘。无数据库迁移、API 返回字段、产品文案和布局变更，无需页面 Before/After。没有扩展为全部生命周期服务的批量重写。

1. B0：记录当前指纹并确认两个隔离探针；对大型服务/路由用 AST 分析函数及分支边界后实施。
2. B1：消除本函数及对应跳转的额外 ORM 读取，加入提交后列加载拒绝和真实缓存防护测试。
3. B2：相关回归、目标角色浏览器和后端核验、复盘、HTML/Markdown 同步、可验证环境及提交准备。

## 6. 验收与否定控制

- 在真实 commit 成功后阻止 ORM 列加载，角色或组保存仍返回 updated，持久化结果正确，认证版本只增加一次，Token 只轮换一次，审计只有一条。
- 预热旧 Token 的真实进程缓存，降权提交后旧缓存被清除，旧 Token 重新解析不再返回原角色；新 Token 按新角色校验。资料-only 保存保持零认证副作用。
- 直接把失效调用恢复为 user.id，故障注入测试必须重新失败；禁止把 expire\_on\_commit=False 作为测试夹具规避故障。
- 真实 commit 完成后再抛错的否定用例与提交前失败分别测试，维持 commit\_unknown 分类；原生 already\_applied/conflict/commit\_unknown 跳转使用稳定 ID，不因额外列加载变成 500。
- 执行 `python -m unittest tests.test_user_edit_change_set tests.test_user_edit_scope_projection tests.test_user_edit_sqlite_boundary -v`，新增测试、Ruff、路由完整性及 86 条 smoke\_routes；SQL 不变，但核验 MySQL 既有编辑事务探针，记录实际后端。不得为测试启动会自动恢复共享数据调度容器的 Docker daemon。
- 使用目标管理员账号在隔离浏览器验证角色编辑保存与 Viewer 新请求拒绝；不得用种子 admin 替代。正式故障注入仍在隔离测试库完成，不对开发库或真实账号模拟 DB 故障。

## 7. 风险与同类排查

替换为稳定 ID 的业务风险低；主要风险是遗漏返回路径或误把“全部提交后 DB 查询”都当作可以删除。只移除返回和缓存失效所需的冗余属性读取，保留事务内鉴权与三方比较。静态搜索还发现停用、重置密码、分组和注册审批等函数存在提交后对象读取；尚未逐项证明其故障影响，作为后续同类审查项记录，不能宣称本批一次修完全部入口。

实施后须持久化七项复盘：定位、参数求值根因、测试遗漏、稳定 ID 修复、列加载拒绝与真实缓存测试、同类入口排查，以及新增测试路径和命令。只有测试证明缓存失效在故障场景仍执行，才可关闭本项。

[Markdown](rbac-user-edit-postcommit-2026-11-04.md) · [索引](../index.html)

---

[← 文档索引（HTML）](../index.html) · [← 文档索引（Markdown）](../index.md)
