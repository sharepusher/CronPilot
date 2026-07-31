# CronPilot · RBAC 与群组权限管理评审报告

> HTML 版：[RBAC与群组权限管理评审报告.html](RBAC与群组权限管理评审报告.html) · [文档索引](index.html) · [索引 Markdown](index.md)

[← 文档索引](index.html)
评审报告RBACResource Scope

# RBAC 与群组权限管理评审报告

基于代码通读的专业评审：能力模型（Permission）· 可见范围（Scope）· 账户与会话安全 · API 层缺口

状态：评审稿 · 2026-07-29 · 2026-07-30 增补（API 最小止损 + S6 用户级 Token 完整方案已交付；Session Cookie 降级至 P1）· 面向 [RBAC 详细设计方案 v4](RBAC架构设计方案.html) 与 [资源隔离与 Scope 设计](资源隔离与Scope设计.html) 的现状核查与增补建议

**定位：**本报告不改变已交付的 RBAC v4 / Resource Scope（OPT-P2-12）架构，而是对现状代码做一次独立专业评审，核查其与设计文档的一致性，并提出设计文档尚未覆盖或优先级可再评估的问题。**本报告本身不构成实现设计稿**；其中列出的优化建议均需按仓库「设计先行」纪律另行出稿并经确认后才可改代码。

## 一、评审范围与方法

代码级通读（非仅读文档）覆盖：

- `app/rbac/`：`policy.py` / `scope.py` / `authorize.py` / `decorators.py` / `context.py` / `services.py` / `views.py` / `group_code.py`
- `datas/model/rbac_user.py`、`resource_group.py`、`user_group.py`、`rbac_audit_log.py`
- `app/main/views.py` 中所有 Scope 相关调用点；`app/api/views.py`、`app/api/__init__.py`、`app/api/auth.py`（API 鉴权）
- `app/security/csrf.py`、`app/auth/password.py`、`config.py`（会话/密钥/Cookie 配置）
- `tests/test_rbac_phase.py`（1452 行）、`tests/test_rbac_scope.py`、`tests/test_api_scope_min.py`
- 对照文档：<RBAC架构设计方案.html>、<资源隔离与Scope设计.html>、<交付状态与路线图.html>

## 二、系统架构速览

权限体系分三层，彼此解耦，是本次评审中最值得肯定的架构决策：

| 层 | 职责 | 核心文件 | 状态 |
| --- | --- | --- | --- |
| Permission | 三内置角色 `viewer / operator / admin` → 能力集合 | `app/rbac/policy.py` | 已交付 v1.0.0 |
| Scope | 业务组（`resource_groups`）多对多用户，`cron_infos.scope_type/group_id` 标记归属 | `app/rbac/scope.py` | 已交付 v1.1.0 |
| Policy | 资源级业务规则 | `check_policy` stub | 预留 · 未启用 |

三层通过 `app/rbac/authorize.py::authorize()` 串联，`decorators.py::authorize_resource()` 是视图层统一入口。`views.py` 中每个涉及具体 Cron 对象的路由（`cron_edit`/`update_status`/`cron_run_now`/`cron_retire`/`job_log_*`）在 `db.session.get()` 之后立即调用它——评审未发现散落的 `if group_id == ...` 手写判断，符合 `.cursor/rules/rbac.mdc` 的禁止项。

角色 × 权限矩阵（`ROLE_PERMISSIONS`）：

| 权限点 | viewer | operator | admin | 种子 admin |
| --- | --- | --- | --- | --- |
| `cron:read` / `log:read` | ✓ | ✓ | ✓ | ✓ |
| `cron:write` | ✗ | ✓ | ✓ | ✗（裁剪） |
| `cron:retire` | ✗ | ✗ | ✓ | ✗（裁剪） |
| `operation:read` | ✗ | ✓ | ✓ | ✓ |
| `user:manage` / `audit:read` | ✗ | ✗ | ✓ | ✓ |

"种子 admin 裁剪"（`SEED_ADMIN_PERMISSIONS`）是个聪明的设计：避免默认账号被误用为日常操作账号，强制运维用它创建"真正的" admin 后即降级为纯管理岗。

## 三、RBAC（Permission 层）评审

### 3.1 优点

- **无角色爆炸、无 Role↔Group 绑定**——`user_group.py` 是纯粹的资源可见性映射，不参与权限判断，避免了"为一个业务需求新增一个角色"的常见腐化路径。
- **装饰器职责单一**：`require_permission` 只做 Permission；对象级鉴权强制走 `authorize_resource`，两者不混淆，降低"以为鉴权了其实只查了权限没查范围"的 IDOR 隐患。
- **前后端权限字符串对齐**：`has_perm('cron:write')` 模板判断与装饰器 `@require_permission('cron:write')` 用同一套常量，`TestNavHasPerm` 专门测试导航按钮显隐，防止"按钮藏了接口没锁"或反之。
- **`make_has_perm()` 防 N+1**：闭包创建时一次性拉权限集合而非逐按钮查询，是从 v3 到 v4 的一次真实性能修正，文档如实记录了根因。
- **测试覆盖扎实**：`test_rbac_phase.py` + `test_rbac_scope.py` 覆盖三角色路由矩阵、自改密码墙、强制改密流程、审计日志、种子账号权限裁剪、Scope 隔离，密度处于同类项目较高水平。

### 3.2 问题与风险

| 严重度 | 问题 | 位置 | 说明 |
| --- | --- | --- | --- |
| 已修复 | API 层完全不受 RBAC/Scope 约束 | `app/api/views.py`、`app/api/__init__.py` | ✅ S6 完整方案已交付，见 §5.1 |
| 中 | 登录无失败次数限制/限流 | `app/rbac/views.py::login` | 暴力破解无防护；无失败锁定、验证码、退避 |
| 中 | Session Cookie 未强制 `Secure`/`SameSite` | `config.py` | 未显式设置，若忘记在反代层强制 HTTPS，Cookie 可能明文传输 |
| 中 | 无会话超时/吊销机制（文档已自述，未实现） | 设计 §4.6 | 停用/降权用户旧会话要等下一次访问受保护页才失效；改密之外无"立即踢下线"手段 |
| 低 | `check_policy` 恒真 | `policy.py` | 符合"预留 stub"定位，非缺陷；长期悬空建议要么启用要么移除 |

## 四、群组权限 / Resource Scope（Visibility 层）评审

### 4.1 优点

- **`GLOBAL`/`GROUP` 二态模型简单可靠**：`cron_infos.scope_type` + `group_id`，避免"用 `NULL` 同时表达『未设置』与『全局』"的常见语义坑（文档明确写了这条禁忌，代码也确实照做）。
- **`build_scope_filter_clause` 是唯一权威过滤入口**：`cron_list`、`job_log_all_list`、`operation_log_list` 三处列表查询统一调用，`admin` 返回 `None` 而非"拼大 IN 子句"，性能取舍正确。
- **派生资源隔离链路完整**：执行日志经 `cron_info_id → CronInfos.scope`；操作记录经 `target_id`；对 `target_type != 'cron'` 或无 `target_id` 的记录，非 admin 一律不可见——默认拒绝（deny-by-default），比"漏判就放行"安全得多。
- **"禁止删除业务组"是经过深思的取舍**：避免 `group_id` 悬挂，UI 也有文案提示，而非留隐藏坑等生产事故。
- **`group_code.py` 的编码生成有完整中文转英文 slug 链路**（含冲突去重、HTML 实体转义防御），测试覆盖了 `R&D` 边界情况，说明是真实踩坑后补的。
- **`test_rbac_scope.py::TestScopeIntegration` 是端到端集成测试**而非纯单元测试——用真实 Flask app + SQLite 内存库跑登录态下的列表可见性断言，符合仓库对"集成层测试"的要求。

### 4.2 问题与风险

| 严重度 | 问题 | 位置 | 说明 |
| --- | --- | --- | --- |
| 中 | 业务组变更不会使当前 Session 立即生效 | `views.py::login` 写 `session['group_ids']` 一次性快照 | 管理员把用户从 A 组移到 B 组后，其当前会话仍能操作 A 组资源直到重新登录；"离职/转岗"场景存在实际越权窗口期 |
| 中 | 组名不唯一，仅编码唯一 | `resource_group.py`、`create_resource_group` | 可创建两个同名组，管理员在下拉/列表中难以区分；数据完整性/可用性问题，非安全问题 |
| 中 | 组列表无分页 | `groups_list` → `list_resource_groups()` | 组数量小时无影响；增长到几百个后下拉可用性与查询性能会下降 |
| 低 | 组编码生成依赖外部翻译 API（同步调用） | `group_code.py::translate_to_english` | 创建中文名业务组时同步等待最长 3 秒外网调用；有 fallback 到哈希编码，不影响正确性，但存在时延与三方数据出境的隐性依赖 |
| 低 | `user_can_assign_group` 与 `_apply_scope_from_form` 存在两套相近但不完全复用的校验逻辑 | `app/rbac/scope.py` vs `app/main/views.py` | 非阻塞性问题，未来改需求需两处同步维护 |

## 五、⚠️ 重大发现：API 层完全在 RBAC/Scope 之外

这是本次评审中**最值得重视**的一点，也是设计文档中已经如实承认、但容易被低估严重性的"已知缺口"。

文档已明确记录：

> 「`/api/*` 仍使用部署级 `api_access_token`，可操作全库任务。按组 token / 调用方身份挂 Scope 见 §八 远期。」——[资源隔离与Scope设计 §七](资源隔离与Scope设计.html#future)

代码层面验证结果：

- `/api/cron/status`、`/api/cron/retire`、`/api/cron/add_log` 只经过 `app/api/__init__.py` 中一个**全局单一静态 token**（`conf.ini` 的 `api_access_token`）校验，与 `rbac_users`、角色、业务组**完全无关**——不存在"用户身份"概念，只有"知道 token 或不知道"。
- **`api_access_token` 默认是空字符串**（`conf.ini.example`），此时鉴权逻辑直接放行所有请求。即**默认配置下，任何能访问到这些端点的人都可以下线/启停任意任务，无需任何认证**。
- 即便配置了 `api_access_token`，它是**部署级单一密钥**，等价于所有业务线共用一把万能钥匙：业务线 A 的调用方理论上也能操作业务线 B 的任务（`retire_cron_by_task_name` 内部不检查 `scope_type`/`group_id`）。**Web 端辛苦建立的业务组隔离，在 API 层被完全绕开**。

这不是代码 bug——文档已明确标注为"S6 远期"未实现项，团队是知情的。但从专业评审角度，本报告认为**其风险等级应从"已知远期缺口"提升为"应尽快评估的 P0 风险"**：Web UI 上一个 operator 看不到别组任务、改不了别组任务，容易给人一种"隔离已经生效"的错觉，而只要对方知道（或猜到/泄露）那一个全局 token，Scope 的防护形同虚设。

### 5.1 2026-07-30 增补：S6 完整方案已交付

评审稿发出后，仓库已完成 S6 完整方案（用户级 API Token + Scope 隔离），**本节核心结论已解决**。详细设计见 [资源隔离与 Scope 设计 §八](资源隔离与Scope设计.html)。

| 项 | 实现 | 状态 |
| --- | --- | --- |
| 生产 opt-in fail-fast | `conf.ini` 设 `api_access_token_required=1` 且 `api_access_token` 为空时，`ProductionConfig.init_app` 与 `scripts/check_conf_production.py` 拒绝启动 | ✅ 已交付 |
| 鉴权失败审计 | `_api_token_guard` 失败写 `rbac_audit_logs.action='api:deny'` | ✅ 已交付 |
| 用户级 API Token | 每个 `rbac_user` 自动生成 `api_token`（30 天过期）；`Authorization: Bearer <token>` 鉴权；密码/组变更自动重置 token | ✅ 已交付 |
| Token 获取端点 | `POST /api/auth/token`（Basic Auth 或表单）→ 返回 token + 过期时间 | ✅ 已交付 |
| API Scope 隔离 | `check_api_scope` 根据 token 持有者的 `group_ids` 校验目标任务归属；反枚举（越权与不存在返回同一提示） | ✅ 已交付 |
| 缓存与失效 | 进程内 `_SCOPE_CACHE`（120s TTL）+ 用户变更时主动失效 | ✅ 已交付 |
| 全局 token 兼容 | `conf.ini` 的 `api_access_token` 仍可用，优先级高于用户 token，admin 等效（全库访问） | ✅ 已交付 |
| 测试 | `tests/test_api_scope_s6.py`（19 用例）+ `tests/test_api_scope_min.py` | ✅ 已交付 |

## 六、账户安全与会话管理评审

| 维度 | 现状 | 评价 |
| --- | --- | --- |
| 密码存储 | `werkzeug.generate_password_hash`（PBKDF2），兼容明文迁移期 | 达标 |
| 强制首次改密 | 新建用户默认密码 `changeme` + `must_reset_password=1`，`before_app_request` 拦截 | 达标；`enforce_password_reset` 实时查库，管理员触发重置后立即对已登录会话生效 |
| 最后一名 admin 保护 | `_count_active_admins` 防止停用/降权最后一个启用中的 admin | 达标，测试覆盖 |
| 自我操作限制 | 不能停用自己、不能重置自己密码、不能在用户管理里编辑自己 | 达标，良好的最小权限习惯 |
| CSRF | Session synchronizer token，写操作强制校验，`hmac.compare_digest` 防时序攻击 | 达标 |
| SECRET\_KEY | 生产 fail-fast（`is_weak_secret_key`） | 达标，OPT-P0-10 已交付 |
| 登录失败反馈 | 用户名不存在与密码错误返回同一句提示 | 达标，防用户名枚举 |
| 登录限流/防爆破 | 无 | 缺失，见第三节 |
| Cookie 安全属性 | 未显式设置，但 Flask 2.3.3 默认 HTTPONLY=True, SAMESITE='Lax' | P1 · 建议显式声明以消除歧义；SECURE 需按部署环境条件开启 |
| 会话闲置/绝对超时 | 无，仅退出/改密时清 | 文档已自述"待确认"，非本次新发现 |
| 密码策略 | 仅要求 ≥6 位，无复杂度/历史密码要求 | 偏弱，内部管理后台可接受，非高优先级 |

## 七、后续优化建议清单（按优先级）

按仓库「设计先行」纪律，**尚未落地**的项落地前均需先出设计稿并经用户确认；本节给出方向与理由，供排期参考。**§5.1 已交付项**不在此重复。

### P0（建议尽快评估，安全相关）

1. **✅ API 层 Scope 完整方案（S6）**——**已交付**（2026-07-30）
   - 用户级 API Token（30 天自动过期）+ Scope 隔离 + 反枚举 + 缓存失效，详见 §5.1。
   - `tests/test_api_scope_s6.py`（19 用例）全部通过。
2. **登录暴力破解防护**
   - 建议按用户名+IP 维度做失败次数计数（可复用 `rbac_audit_logs` 中 `action='user:login', status='deny'` 记录做滑动窗口统计，避免为此单独引入新依赖）。
   - 影响面：`app/rbac/views.py::login`、`app/rbac/services.py::authenticate_user`。

### P1（体验/工程债，建议纳入下一轮迭代）

3. **Session Cookie 安全属性**（原 P0，降级为 P1）
   - **降级理由**：Flask 2.3.3 默认 `HTTPONLY=True`、`SAMESITE='Lax'`，两项最关键的 Cookie 安全属性已由框架默认值覆盖。唯一非默认安全的 `SECURE` 在 CronPilot 典型内网 HTTP 部署场景下不能强开（会导致无法登录），需要环境感知开关，属工程改进而非紧迫安全缺口。
   - 建议 `config.py` 显式声明三项属性以消除歧义，`SECURE` 通过环境变量控制（`SESSION_COOKIE_SECURE = os.environ.get('SESSION_COOKIE_SECURE', '').lower() in ('1', 'true')`）。
4. **业务组变更后旧会话仍生效的窗口期**
   - 建议参考"强制改密"已有的"实时查库拦截"模式：`rbac_users` 增加 `groups_version` 字段，登录时写入 session，受保护页对比库内版本号，不一致则要求重新登录。
   - 与文档 §4.6 提到的"会话吊销"是同一类问题，建议合并到一次设计中统一解决。
5. **会话闲置超时**——[RBAC架构设计方案 §4.6](RBAC架构设计方案.html#account-session) 已列出的 6 项待确认优化中，"可配置会话超时"与本报告的账户安全建议高度重合，建议优先于其余几项排期。
6. **业务组管理可用性小改进**
   - 组名唯一性校验（创建/更新时增加同名检查或提示）；
   - 组列表分页（当前全量返回，组数增长后处理）；
   - 编码翻译改为可选/异步，或增加本地拼音转写兜底，减少对外网翻译服务的同步依赖。

### P2（远期/锦上添花）

8. **`check_policy` 层要么落地要么移除**：恒 `True` 的 stub 长期存在会增加理解成本；建议下一次真正引入对象级策略（如 Owner-based）时启用，或在文档中更明确标注"设计保留位，无迭代计划"。
9. **密码复杂度与历史密码策略**：如未来面向更大规模团队或纳入合规要求，可参考设计 §4.6 第 5 条排期。
10. **MFA/OAuth**：文档已归入 PRD Phase C 远期，本报告不重复展开。

## 八、与现有文档的一致性核查结论

<RBAC架构设计方案.html>（v4）与 <资源隔离与Scope设计.html>（v1.1.0）**与代码实现高度一致**——连"性能修正的根因""废弃方案版本""已知缺口"都如实记录，文档维护质量较高。本次评审未发现"文档说已实现但代码没有"的情况；反而代码部分细节比文档更完整（如业务组编码生成的 HTML 实体转义处理）。

本报告的新增价值主要是三类：

- **风险再评级与落地**：API 层缺口从"已知远期缺口"提升为 P0 风险，并已交付 S6 完整方案（用户级 Token + Scope 隔离 + 30 天过期 + 反枚举）；
- **Session Cookie 降级**：原评为 P0，经复核 Flask 2.3.3 默认值已覆盖 `HTTPONLY` 和 `SAMESITE`，实际风险有限，降级为 P1；
- **文档未覆盖的细节**：登录限流、组名唯一性——不在 RBAC/Scope 设计文档范围内（更偏通用 Web 安全基线），但应补充进项目安全清单。

CronPilot · RBAC 与群组权限管理评审报告 · 2026-07-29 · 2026-07-30 增补 ·
[RBAC 详设 v4](RBAC架构设计方案.html) ·
[Resource Scope 设计](资源隔离与Scope设计.html) ·
[交付状态](交付状态与路线图.html) ·
[索引](index.html)
· [Markdown](RBAC与群组权限管理评审报告.md) · [索引](index.html)

---

[← 文档索引（HTML）](index.html) · [← 文档索引（Markdown）](index.md)
