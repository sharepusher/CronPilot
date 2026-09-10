# 2026-09 auth_version Session 缺键 Fail-Open 深入复盘

> HTML 版：[2026-09-auth-version-session-failopen.html](2026-09-auth-version-session-failopen.html) · [文档索引](../index.html) · [索引 Markdown](../index.md)

[← 返回复盘索引](index.html)

# 2026-09 auth\_version Session 缺键 Fail-Open 深入复盘

**日期**：2026-09-09（rev.2 深入版）　**关联**：OPT-P0-22 B2　**上一版问题**：初版复盘只写了表象（「用了 or 0」），未追到为何会写出该代码、为何测试绿着却漏检。

**事故一句话**：设计已选定「方案 A · 缺键失效 + 一次性 bump」，抢跑实现却写成「缺键当 0」且只 ADD COLUMN 不 bump，使**升级前签发、不含 auth\_version 键**的 Web Session 在库值为 0 时继续被视为合法登录。

## 1) Bug 定位（证据链）

### 1.1 故障代码

文件 `app/rbac/services.py::web_session_user_is_valid()`（B2 修复前）：

```
return int(session.get('auth_version') or 0) == int(user.auth_version or 0)
```

调用链：任意已登录请求 → `rbac.before_app_request::enforce_password_reset` → `web_session_user_is_valid()` → 为 True 则**不** `session.clear()`。

### 1.2 可复现状态机

| 时刻 | Session | DB `auth_version` | 旧实现判定 | 设计期望（§4.4） |
| --- | --- | --- | --- | --- |
| 功能启用前已登录（Cookie 无此键） | `'auth_version' not in session` | `0`（ADD COLUMN DEFAULT） | `get→None→or 0` ⇒ `0==0` → **放行** | **失效**（缺键） |
| 登录成功后（有键） | `auth_version=0` | `0` | 放行 | 放行（在未 bump 前） |
| 停用后（DB +1） | 仍为旧值 `0` | `1` | 失效 ✓ | 失效 ✓ |

因此：**停用踢人路径「看起来测绿」**，但**「升级瞬间的存量 Session」路径完全敞开**——而这正是方案 A 要解决的主威胁。

### 1.3 第二缺口：迁移半截

`ensure_business_tables._ensure_rbac_users_columns` 仅：

```
ALTER TABLE rbac_users ADD COLUMN auth_version INTEGER NOT NULL DEFAULT 0
```

未执行设计要求的：

```
UPDATE rbac_users SET auth_version = COALESCE(auth_version, 0) + 1
```

结果：存量行保持 0，与「缺键→当作 0」叠加，形成**双重 fail-open**。

## 2) 根因（行为层，非「粗心」）

问题不是「某次手滑写错一行」，而是**三条独立失败模式叠乘**。

### 2.1 流程失败：设计确认前抢跑实现

| 规范要求 | 实际发生 |
| --- | --- |
| OPT / 功能须设计确认后再改业务代码（`cronpilot-project.mdc` 设计先行） | 确认 OPT-P0-22 rev.3 **之前**，工作区已有 `auth_version` 列、校验函数、登录写 Session 的抢跑 diff |
| 分批 B2 才落地「缺键失效 + bump」 | 抢跑把 B2 的一部分提前做成「有字段、有比较」，但**未按 §4.4 全文**实现 |

**行为层结论**：在设计未冻结时写安全关键路径，实施者只能凭「常见 Session 写法」补全细节；而安全语义恰恰藏在细节里（缺键 vs 0）。抢跑把「半成品」固化进主路径，后续 B1/B2 容易**默认半成品已正确**。

### 2.2 语义失败：把「取值缺省」当成「安全缺省」

Python / Flask 惯用写法：

```
int(session.get('auth_version') or 0)
```

在**应用配置**场景表示「没配就当 0」通常无害。但在**鉴权比较**场景：

- `None`（键不存在）=「此 Cookie 签发于版本机制启用**之前**」→ 不可信 → 应拒绝
- `0`（键存在且值为 0）=「机制启用后登录、当时库版本为 0」→ 可与 DB 比较

二者被 `or 0` **塌缩成同一值**。设计 §4.4 已用伪代码明示：

```
if 'auth_version' not in session: return False
return int(session['auth_version']) == int(user.auth_version or 0)
```

注意：设计允许 `user.auth_version or 0`（DB 侧），**禁止** Session 侧同样写法——初版实现把两侧对称化了，属于**未对照设计伪代码做差异阅读**。

**行为层结论**：实施时用「对称默认值」心智模型覆盖了「非对称安全语义」；没有把设计伪代码当作验收断言逐行对照。

### 2.3 迁移失败：把「加列」当成「启用功能」

方案 A 的安全保证 = `缺键失效` **∧** `存量行 bump`。只做 ADD COLUMN DEFAULT 0 时：

- 旧 Session 无键 → 被当成 0
- DB 全是 0 → 比较成功
- 效果等同于**偷偷退化成方案 B**（「只有停用后才踢」），与文档选定的 A 相反

**行为层结论**：把「schema 可运行」误当成「安全策略已生效」。缺独立的迁移验收项（「bump 后旧 Cookie 必 302」）。

**因果链（压缩）**：设计确认前抢跑 → 用惯用 `or 0` 填鉴权细节 → 只加列不 bump → 存量无键 Session 与 DB 0 对齐 → 方案 A 名存实亡。

## 3) 测试漏洞（为何绿测拦不住）

同样不是「忘写一个用例」，而是**测试策略与分批结构共同制造了假阳性**。

### 3.1 用例只覆盖「停用后踢人」，未覆盖「升级瞬间踢人」

| 威胁（设计验收 #6） | B1 实际测了什么 | 结果 |
| --- | --- | --- |
| 功能首次启用后，既有 Web Session 下一请求失效 | `test_disable_revokes_existing_web_session`：先写入 `sess['auth_version']=0`，再停用使 DB→1 | 只证明「版本号不一致会踢」——与缺键威胁**正交** |
| Session 缺少键必须失效 | 无 | 漏检 |
| 一次性 bump 幂等且使 0→1 | 无（B2 前） | 漏检 |

### 3.2 Fixture 主动消灭了「真实旧 Cookie」形态

测试里构造会话时**总是**：

```
sess['auth_version'] = 0
```

这模拟的是「新机制下已登录用户」，不是「机制启用前签发的 Cookie」。生产事故态恰恰是后者。**测试数据生成方式与威胁模型不一致**，再多断言也无法碰到缺键分支。

### 3.3 分批错位：B1「锁定失败用例」却锁定了半成品行为

设计 B1 写的是锁定「Session 不失效」等旧策略。抢跑代码已能在**停用**后踢人，于是 B1 写成对抢跑行为的回归并变绿——等于给半成品发了合格证。B2 本应补的「缺键 / bump」在 B1 绿测后失去紧迫感（「会话撤销好像已经有了」）。

**行为层结论**：分批标题「会话」过宽，B1 未把 §4.4 的两条独立门禁（缺键、bump）写成**必须失败的用例清单**；结果 B1 验收了弱于设计的实现。

### 3.4 无静态/契约门禁对照设计伪代码

设计 HTML 里已有推荐实现，但仓库没有：

- 禁止 `session.get('auth_version') or 0` 的 grep/CI
- 「设计伪代码 ↔ 实现」的逐行核对步骤（类似 2026-09「设计 API 假设验证」规则，但当时未覆盖 Session 契约）

因此错误写法可以长期与设计文档共存。

**测试漏洞因果链**：威胁模型是「无键旧 Cookie」→ Fixture 只造「有键新 Cookie」→ 只断言停用 bump → B1 绿测固化半成品 → 缺静态对照设计伪代码 → 漏检直到 B2 人工对照 §4.4。

## 4) 修复（最小且对齐 §4.4）

1. `web_session_user_is_valid`：`if 'auth_version' not in session: return False`，再比较整型版本。
2. `_bump_auth_version_once()`：全表 `auth_version += 1`；幂等标记 `cp_schema_flags.opt_p0_22_auth_version_bump`；SQLite `busy_timeout` 降低锁失败留下「有 flag 无 bump」的风险。
3. 登录路径保持写入 `session['auth_version'] = int(user.auth_version)`。

## 5) 防护测试

| 用例 | 断言的威胁 |
| --- | --- |
| `test_missing_auth_version_key_fails_closed` | 无键 Session → 302 登录，Session 清空 |
| `test_auth_version_mismatch_revokes_session` | 有键但与 DB 不一致 → 失效 |
| `test_disable_revokes_existing_web_session` | 停用 bump 后旧会话失效（保留） |
| `test_bump_once_increments_and_is_idempotent` | 0→1 且二次调用不叠加 |

文件：`tests/test_user_reactivation.py`。

## 6) 同类排查

| 检查项 | 结论 |
| --- | --- |
| `session.get('auth_version') or 0` 放行点 | 修复后 `app/rbac/services.py` 已无；登录写入用显式赋值 |
| API Token 路径 | 独立于 Web Session，不依赖此键（按设计） |
| 其它 `session.get(x) or 0` 用于鉴权？ | 未发现第二处「版本类」比较；一般业务缺省仍可用 or 0，但**不得**用于「键存在性即信任边界」 |
| 「有 flag 无 bump」残留 | 本机曾因 SQLite journal 锁出现；已手工对齐 bump；代码侧加 busy\_timeout |

## 7) 预防方案（可验证 · 因果对应）

必须同时堵住「抢跑半成品」「语义塌缩」「测试假绿」三条根因。

| # | 措施 | 落地位置 | 验证命令 |
| --- | --- | --- | --- |
| P1 | **鉴权 Session 键存在性规则**：凡用 Session 字段与 DB 做安全等价比较，禁止 `session.get(k) or <default>` 掩盖缺键；缺键必须 fail-closed。DB 侧 `or 0` 可保留。 | `.cursor/rules/rbac.mdc` Session 节（已写）；本复盘为权威案例 | `grep -n "get('auth_version') or 0" app/rbac/ && echo FAIL || echo OK` |
| P2 | **安全迁移测试矩阵强制项**：新增「认证/会话版本」类能力时，测试至少覆盖：(a) 缺键旧 Cookie；(b) 版本不匹配；(c) 迁移 bump 幂等。禁止只用「业务动作后 bump」代替 (a)。 | `AGENTS.md` + `cronpilot-project.mdc` 追加短条款；用例落在 `tests/test_user_reactivation.py` | `python -m unittest tests.test_user_reactivation.TestDisabledSessionRevocation tests.test_user_reactivation.TestAuthVersionOneTimeBump -v` |
| P3 | **设计伪代码对照门禁**：设计文档若给出安全相关推荐实现片段，实施批次验收须 `Read` 设计伪代码并 diff 实现；B1 若声称锁定该能力，用例必须直接断言伪代码分支（含否定路径）。 | 扩展既有「设计 API 假设验证」为「设计安全契约验证」——写入 `AGENTS.md` | 人工：打开 `doc/design/停用用户同名恢复设计.html` §4.4 与 `web_session_user_is_valid` 逐行对照 |
| P4 | **禁止抢跑安全半成品充当回归基线**：设计未确认前写入的鉴权代码，确认后必须以设计全文为唯一准绳重审；不得用「已有测试绿」跳过缺键/迁移类用例。 | `cronpilot-project.mdc`「抢跑代码」提示强化（与 OPT-P0-22 设计 §6 呼应） | Review 清单：确认后 PR 是否含「对照 §4.x 的否定用例」 |

**与根因对应**：P4→2.1 抢跑；P1→2.2 语义塌缩；P2+P3→2.3/§3 测试假绿与设计对照缺失。

## 8) 质量门禁自检（Q1–Q4）

| # | 检查 | 本复盘 |
| --- | --- | --- |
| Q1 | 预防方案是否新增可验证措施？ | 是：规则 + 三否定用例 + grep 命令 + 设计对照规程 |
| Q2 | 第三方可否重现验证？ | 是：上表验证命令 |
| Q3 | 根因是否追到行为层？ | 是：抢跑流程、or 0 语义塌缩、加列≠启用、Fixture 造错威胁态 |
| Q4 | 方案与根因是否因果对应？ | 是：见 §7 末框 |

OPT-P0-22 B2 · rev.2 深入复盘 ·
[Markdown](2026-09-auth-version-session-failopen.md) ·
[索引](index.html) ·
设计：[§4.4](../design/停用用户同名恢复设计.html#session)

---

[← 文档索引（HTML）](../index.html) · [← 文档索引（Markdown）](../index.md)
