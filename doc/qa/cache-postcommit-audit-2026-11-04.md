# 缓存失效与提交后读取同类排查

> HTML 版：[cache-postcommit-audit-2026-11-04.html](cache-postcommit-audit-2026-11-04.html) · [文档索引](../index.html) · [索引 Markdown](../index.md)

独立统一方案已形成：[RBAC 缓存失效与提交后处理边界统一修复设计](../design/rbac-cache-postcommit-boundary-2026-11-04.html)。后续实施范围以该待确认设计为准，本文保留分析依据。

后续交付：RBAC 缓存及提交后读取已按确认设计在工作区修复并验收，见[统一修复结果](../design/rbac-cache-postcommit-boundary-2026-11-04.html)。下文保留修复前观察；尚未手动提交，原 HEAD 结论仍按原版本理解。

# 缓存失效与提交后读取同类排查

2026-11-04 · 分析记录，未修改业务代码。基于当前工作区，追踪 app/ Python 后端的缓存定义、失效调用及其前序代码。

## 结论

存在同类问题。API Scope 缓存失效涉及 services.py 中 9 个服务函数、10 个调用点（用户编辑成功和结果不明各一个）。其中 6 个函数已通过提交后列加载失败探针复现不同影响，另外 3 个仅静态确认危险读取路径。不能仅把失效调用的参数从 user.id 改为 user\_id，就认为所有入口已解决：缓存失效前构造审计参数时读取 user.username，同样可能先抛错。

## 已复现：业务已提交，缓存失效未执行

- **用户管理编辑：**update\_user\_management 提交后读取 user.id。此前降权探针显示数据库已为 viewer，旧 Token 缓存仍解析为 operator；见[专项设计](../design/rbac-user-edit-postcommit-2026-11-04.html)。
- **停用用户：**set\_user\_active 的失效调用虽然使用标量 user\_id，但其前序 write\_audit\_log 参数先读取 user.username。探针中数据库用户已停用、旧 Token 已清空，服务抛错，旧 Token 仍由缓存解析。
- **管理员重置密码：**trigger\_password\_reset 在缓存失效前读取 user.username 构造审计。探针中 Token 已轮换，但返回报错且旧 Token 仍由缓存解析。
- **修改业务组：**set\_user\_groups 在缓存失效前读取 user.username 构造审计。探针中组和 Token 已保存，返回报错且旧 Token 仍由缓存解析。

以上均为真实 commit 成功后，故意让 ORM 的过期列读取失败的隔离结果；不是普通请求必然失败，也不是有权限时已发起操作的在途竞态。缓存命中时 \_resolve\_user\_token 不查数据库，因此旧状态可继续被新请求使用，直到进程缓存失效或 TTL 到期。多 worker 缓存同步是独立既有边界，本轮没有验证或改造。

## 已复现：缓存已清除，后续响应仍可能报错

- **自行修改密码：**change\_own\_password 先以标量 ID 清理缓存，之后构造审计参数时读取 user.username/user.id。探针中保存成功且旧 Token 不再解析，但函数抛错。
- **签发/重置 Token：**issue\_user\_api\_token 先清缓存，再读取 user.username、user.api\_token 和过期时间。探针中旧 Token 不再解析，但函数抛错；可能无法正常返回已生成的新 Token。

## 静态风险，尚未用专有场景复现

- create\_user 的同名覆盖启用分支：commit 后以 existing.id 调用失效函数。
- approve\_registration：commit 后以 user.id 调用失效函数，随后还读取申请和用户对象来写审计及构造返回。
- 旧 update\_user：commit 后读取 user.username 写审计，再清缓存。app/ 搜索未找到该函数调用方，本轮不认定它是当前页面可达路径。

## 其他缓存的排查边界

- Dashboard 逾期统计：读查询结果转换为标量/集合后存入 TTL 缓存，没有本次“业务提交后读取对象以触发失效”的调用链。
- 孤儿任务缓存：周期核对及重新注册后更新内存集合；已读路径没有此类 DB commit 后缓存失效链。
- API 文档目录：以权限集合为 key 的 lru\_cache；无对应事务提交路径。
- 用户管理及注册审批的 flask.g 缓存：请求内复用 actor 解析结果，请求结束即丢弃；与跨请求 Token Scope 缓存不同。
- 企业微信 access\_token 文件缓存：文件读写及过期判断，与 ORM commit 无关。

这些缓存没有发现本次相同机制，不代表已证明它们不存在其他一致性、并发、过期或数据安全问题。没有进行前端缓存、浏览器存储、第三方服务缓存和跨进程一致性的完整审计。

## 探针与实际验证

[探针源码](evidence/cache-postcommit-audit-2026-11-04/probe.py)、[5 个场景结果](evidence/cache-postcommit-audit-2026-11-04/result.json)。执行 `PYTHONPATH=. .venv-py311/bin/python doc/qa/evidence/cache-postcommit-audit-2026-11-04/probe.py`。使用测试内存库、虚构 Token 和账号，先预热真实缓存，再通过 after\_commit 与 do\_orm\_execute/is\_column\_load 注入故障，最后移除事件并用新 Session 核对数据及 Token 解析；不把模拟的缓存函数当作缓存已清除的证据。此前用户编辑降权另有独立探针。

## 建议修复范围

原用户编辑专项设计应补充本次清单后重新确认实施范围。建议统一在提交前保存所需 ID、用户名、Token 返回值及审计投影，提交后用稳定值处理缓存、审计和响应；先保证必要缓存失效不被无关展示读取阻断。不得用全局关闭 expire\_on\_commit、吞掉所有错误或反向回滚已提交业务掩盖问题。分别保留提交结果不明、已知成功后的附属处理失败与缓存失败的边界，并逐入口增加故障测试；本轮尚未实施这些变更。

[Markdown](cache-postcommit-audit-2026-11-04.md) · [索引](../index.html)

---

[← 文档索引（HTML）](../index.html) · [← 文档索引（Markdown）](../index.md)
