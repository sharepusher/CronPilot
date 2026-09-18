# PinnedIPAdapter HTTP 协议参数错误复盘

> HTML 版：[2026-09-PinnedIPAdapter-HTTP协议参数错误.html](2026-09-PinnedIPAdapter-HTTP协议参数错误.html) · [文档索引](../index.html) · [索引 Markdown](../index.md)

复盘文档 · 2026-09 · 已修复

# PinnedIPAdapter HTTP 协议参数错误复盘

**结论：**HTTP 任务失败的直接原因是 CronPilot 自定义 `_PinnedIPAdapter` 无条件向 `HTTPConnection` 传入 HTTPS 专用的 `assert_hostname`/`server_hostname` 参数。修复后 HTTP 与 HTTPS 按协议分支初始化连接池，未修改依赖版本或降低 HTTPS 校验。

## 1. Bug 定位

`make_pinned_session(..., scheme="http")` 创建的 session 在首次建立 HTTP 连接时抛出 `HTTPConnection.__init__() got an unexpected keyword argument 'assert_hostname'`，请求尚未发送，也没有 HTTP 响应。

## 2. 根因

`app/services/url_security.py::_PinnedIPAdapter.init_poolmanager` 原先只判断 hostname 是否存在，就把 TLS 参数写入 urllib3 连接池。HTTP 使用 `HTTPConnection`，其构造函数不接受这些参数；HTTPS 才需要它们来维持 SNI 和证书 hostname 校验。因此根因是应用适配器的协议分支错误，不是可以靠升级 requests/urllib3 泛化解决的“依赖兼容性”。

## 3. 测试漏洞

- 原测试只断言 URL/Host 重写和 session 挂载，没有断言 HTTP 连接池参数。
- 没有真实 HTTP pinned session 集成测试，未触发 `HTTPConnection` 构造路径。
- HTTPS 保留 SNI/证书语义的回归约束未被显式表达。

## 4. 修复

| 文件 | 变更 |
| --- | --- |
| `app/services/url_security.py` | 适配器保存 `scheme`；仅当 scheme 为 HTTPS 时传递 `assert_hostname` 和 `server_hostname`；HTTP 仍保留固定 IP、Host header 与端口重写。 |
| `tests/test_p0_phase_a.py` | 新增 HTTP 无 TLS 参数、HTTPS 保留 TLS 参数断言，并校验 session 传入 scheme。 |

## 5. 防护测试

- `.venv-py311/bin/python -m unittest tests.test_p0_phase_a.TestPinnedSession -v`：5 项通过。
- 真实本地 HTTP pinned session 返回 `200 / ok`，不再出现 TypeError。
- 执行观测相关定向套件：68 项通过；`ruff`、86 条路由冒烟均通过。
- HTTPS 参数断言确保修复不会移除 SNI/证书 hostname 校验。

## 6. 同类排查

检索了 `_PinnedIPAdapter`、`make_pinned_session`、`init_poolmanager` 及所有 scheme 调用方；未发现其他路径向 HTTP 连接池注入 TLS 专用参数，也未发现通过捕获 TypeError 后重试来掩盖协议错误的逻辑。

## 7. 预防方案

1. 将 HTTP/HTTPS 连接池参数矩阵固化在 `tests/test_p0_phase_a.py`，后续修改适配器必须同时通过两种协议断言。
2. 发布验收保留本地真实 HTTP pinned session smoke，并将命令纳入执行侧观测变更清单。
3. 设计文档明确“协议错误优先修复适配器，不以依赖升级或吞异常规避”，避免把应用 bug 误标为基础依赖问题。

关联设计：[执行侧观测失败分类与 HTTP 响应语义优化设计](../design/执行侧观测-失败分类与HTTP响应语义优化设计-2026-09.html)

[文档索引](index.html) · [Markdown](2026-09-PinnedIPAdapter-HTTP协议参数错误.md)

---

[← 文档索引（HTML）](../index.html) · [← 文档索引（Markdown）](../index.md)
