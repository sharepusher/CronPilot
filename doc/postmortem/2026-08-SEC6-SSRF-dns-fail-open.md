# 复盘：SEC-6 SSRF DNS Fail-Open 安全漏洞修复

> HTML 版：[2026-08-SEC6-SSRF-dns-fail-open.html](2026-08-SEC6-SSRF-dns-fail-open.html) · [文档索引](../index.html) · [索引 Markdown](../index.md)

# 复盘：SEC-6 SSRF DNS Fail-Open 安全漏洞修复

**日期**：2026-08-24  
**严重度**：P1 安全  
**关联编号**：SEC-6（Redesign 全面 Review 修复方案 §3.1）  
**设计文档**：[Redesign代码全面Review修复方案-2026-08.html](../design/Redesign代码全面Review修复方案-2026-08.html)

## 1. Bug 定位

**文件**：`app/services/url_security.py`

**Layer 1**（`validate_trigger_url`，第 104–109 行）：

```
except ValueError:
    ips = _resolve_host_ips(hostname)
    if ips is None:
        return True, ''   # ← fail-open: DNS 失败直接放行
```

**Layer 2**（`validate_and_resolve_url`，第 125–128 行）：

```
ips = _resolve_host_ips(hostname)
if ips is None:
    return True, '', None  # ← fail-open: DNS 失败放行且无 IP pinning
```

两层 SSRF 防护在 DNS 解析失败（`socket.gaierror`）时均返回 `True`，允许请求继续。
这意味着攻击者可以在 DNS 瞬断期间提交指向内网 IP 的恶意域名，绕过 IP 黑名单检查。

## 2. 根因

| 层面 | 分析 |
| --- | --- |
| 设计决策 | 原始实现优先考虑「可用性」——DNS 暂时不可用时不影响正常任务调度。这是 SSRF 防护初期（OPT-P0-12）的权衡决策，当时假设内网环境 DNS 稳定 |
| 安全建模不足 | 未考虑攻击者主动制造 DNS 故障的场景（如 DNS Rebinding、短 TTL 切换、恶意 DNS 服务器返回 SERVFAIL） |
| 双层都有同一漏洞 | Layer 2 复制了 Layer 1 的 fail-open 逻辑，未独立审视安全语义 |
| 行为层根因 | OPT-P0-12 实现时无「fail-open vs fail-closed 决策清单」，安全函数的异常路径未被要求单独 review |

## 3. 测试漏洞

原有测试 `test_dns_unavailable_returns_none_ip` 验证了 DNS 失败时返回 `ip=None`，
但**断言方向是 `assertTrue(ok)`**——即测试本身把 fail-open 作为「正确行为」来验证。
这意味着测试覆盖了该场景但**预期值是错误的**，反而固化了漏洞。

Layer 1（`validate_trigger_url`）完全没有 DNS 失败场景的测试用例。

## 4. 修复

| 变更 | 描述 |
| --- | --- |
| `_dns_fail_open(cron_config)` | 新增配置读取函数，检查 `url_ssrf_dns_fail_open` 配置项 |
| `_resolve_host_ips(hostname, retries=1)` | 新增 1 次 DNS 重试（间隔 0.5s），减少瞬时 DNS 抖动误拦 |
| `validate_trigger_url` Layer 1 | DNS 失败 + `dns_fail_open=0` → `return False, 'DNS 解析失败...'` |
| `validate_and_resolve_url` Layer 2 | DNS 失败 + `dns_fail_open=0` → `return False, 'DNS 解析失败...', None` |
| `conf.ini.example` | 新增 `url_ssrf_dns_fail_open=0` 配置项（默认 fail-closed） |
| `configs.py`（2026-09 补线） | 把 `url_ssrf_dns_fail_open` 读入 `configs()` 返回字典（缺省 `'0'`），与 `block_private_ip` / `url_ssrf_observe_only` 同款写法 |

### 4.1 后续修复：逃生开关曾是死键（2026-09-11）

本次交付把配置项写进了 `conf.ini.example`、设计文档与 Release Notes，但**漏了 `configs.py`**：
`configs()` 返回的字典里从来没有 `url_ssrf_dns_fail_open` 键，而
`_dns_fail_open()` 只做 `(cron_config or {}).get('url_ssrf_dns_fail_open', '0')`、
没有 `configs('<key>')` 兜底，于是运维即使按示例设成 1，运行时读到的仍是默认 0——
逃生开关完全无效，DNS 抖动环境无法降级。

对照组说明了这个不对称：`health_failing_threshold` 同样不在 `configs()` 字典里，
但 `get_failing_threshold()` 在字典取空时会回落到 `configs('health_failing_threshold')`，
因此照样生效；`api_access_token_required` 则是全程走单键读取。
三个键写法各不相同，唯独没有兜底的那个成了死键。

行为层根因：交付验收把「示例文件里有这一项」当成了「配置项可用」，
验证命令写的是 `grep 'url_ssrf_dns_fail_open' conf.ini.example`——
这条命令在键完全不生效的情况下依然通过。SEC-6 的 7 个单测则全部直接构造
`dict(self.cfg, url_ssrf_dns_fail_open='1')` 传入，绕过了 `configs()` 这一层，
因此测试与 grep 双双为绿。

修复后自证（`conf.ini` 分别设 0 / 1，对不可解析域名调用 `validate_trigger_url`）：

| `url_ssrf_dns_fail_open` | `configs()` 读到 | `_dns_fail_open` | 校验结果 |
| --- | --- | --- | --- |
| 0 | `'0'` | False | `(False, 'DNS 解析失败（…），请确认域名正确后重试')` |
| 1 | `'1'` | True | `(True, '')` |

## 5. 防护测试

新增 7 个测试用例（总测试数 679 → 685）：

| 测试类 | 用例 | 验证内容 |
| --- | --- | --- |
| TestUrlSecurity | `test_dns_fail_closed_layer1` | Layer 1 DNS 失败 → 默认拒绝 |
| TestUrlSecurity | `test_dns_fail_open_layer1_config` | Layer 1 DNS 失败 + config=1 → 放行 |
| TestValidateAndResolve | `test_dns_unavailable_fail_closed` | Layer 2 DNS 失败 → 默认拒绝 |
| TestValidateAndResolve | `test_dns_unavailable_fail_open_config` | Layer 2 DNS 失败 + config=1 → 放行 |
| TestDnsRetry | `test_retry_succeeds_on_second_attempt` | 首次失败 + 第二次成功 → 返回 IP |
| TestDnsRetry | `test_all_retries_exhausted_returns_none` | 全部重试耗尽 → 返回 None |
| TestDnsRetry | `test_no_retry_when_retries_zero` | retries=0 → 仅尝试 1 次 |

验证命令：

```
.venv-py311/bin/python -m unittest tests.test_p0_phase_a.TestUrlSecurity.test_dns_fail_closed_layer1 \
  tests.test_p0_phase_a.TestUrlSecurity.test_dns_fail_open_layer1_config \
  tests.test_p0_phase_a.TestValidateAndResolve.test_dns_unavailable_fail_closed \
  tests.test_p0_phase_a.TestValidateAndResolve.test_dns_unavailable_fail_open_config \
  tests.test_p0_phase_a.TestDnsRetry -v
```

## 6. 同类排查

| 检查项 | 结果 |
| --- | --- |
| `_resolve_host_ips` 所有调用点 | 仅 2 处：`validate_trigger_url` 和 `validate_and_resolve_url`，均已修复 |
| 其他 `socket.gaierror` 处理 | 项目中无其他 DNS 解析代码 |
| `observe_only` 模式 | 已有独立配置 `url_ssrf_observe_only`，不受本次修改影响 |
| 白名单模式 | 白名单检查在 DNS 解析前执行，白名单域名仍需通过 DNS 解析，行为一致 |
| 其余 `conf.ini.example` 键是否也是死键（2026-09 追加） | 逐键比对示例文件 `[default]` 与 `configs()` 返回值：差集为 `api_access_token_required`（`config.py` 单键读取，正常）、`health_failing_threshold`（`get_failing_threshold()` 有 `configs()` 兜底，正常）、`url_ssrf_dns_fail_open`（**无兜底，唯一真死键，已修**）。反向差集 `metrics_token` 在 `configs()` 中但示例未列出，属文档缺口，不影响运行 |
| `conf.example.ini`（遗留副本） | 该文件缺整段 SSRF 配置，且仅被文档引用；所有安装/启动脚本用的是 `conf.ini.example`（项目规则亦只要求提交后者）。本次不动，另行处理 |

## 7. 预防方案

| # | 措施 | 落地位置 | 验证命令 |
| --- | --- | --- | --- |
| 1 | **Fail-closed 测试覆盖**：7 个新测试用例确保 DNS 失败默认拒绝，防止未来回退 | `tests/test_p0_phase_a.py`（TestUrlSecurity + TestValidateAndResolve + TestDnsRetry） | `.venv-py311/bin/python -m unittest tests.test_p0_phase_a.TestDnsRetry -v` |
| 2 | **安全函数异常路径 Review 清单**：url\_security.py 中每个 except 分支必须在注释中标明「fail-open」或「fail-closed」及其理由 | `app/services/url_security.py` 源码注释 | `grep -n 'fail-open\|fail-closed' app/services/url_security.py`（应有 ≥ 2 处标注） |
| 3 | **配置项可恢复**：提供 `url_ssrf_dns_fail_open` 配置项，允许内网 DNS 不稳定环境降级 | `conf.ini.example` + `configs.py` | `.venv-py311/bin/python -m unittest tests.test_config_keys -v`（原验证命令 `grep … conf.ini.example` 在键完全不生效时仍通过，已废弃） |
| 4 | **示例配置键可达性门禁（2026-09 追加）**：以 `conf.ini.example` 为准，逐键断言必须出现在 `configs()` 返回字典中；确实走单键读取的键须登记在 `SINGLE_KEY_READERS` 豁免表并写明消费位置，禁止无声豁免 | `tests/test_config_keys.py`，随 `unittest discover` 进入 `unit-tests.yml` | `.venv-py311/bin/python -m unittest tests.test_config_keys -v`（3 条） |
| 5 | **规范条目**：新增 `conf.ini` 配置项时，验收必须证明该键抵达运行时配置（`configs()` 字典或显式单键读取），不得以「示例文件已写」或「单测直接构造 dict 传参」代替 | `.cursor/rules/cronpilot-backend.mdc` + `AGENTS.md` | 同上 |

[文档索引](index.html) · [Markdown](2026-08-SEC6-SSRF-dns-fail-open.md) · [索引](index.html)

---

[← 文档索引（HTML）](../index.html) · [← 文档索引（Markdown）](../index.md)
