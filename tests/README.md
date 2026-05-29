# P0 测试说明

## 自动化（推荐 Python 3.8–3.11，与项目 requirements 一致）

```bash
cd /path/to/xiaoniu_cron
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m unittest tests.test_p0_phase_a -v
```

当前 **12 项单元测试** 覆盖：

| OPT | 测试点 |
|-----|--------|
| P0-01 | `trim` / `delete` 逻辑由 ORM 实现（见 `cron_service`） |
| P0-02 | 明文兼容 + `pbkdf2` 哈希校验 |
| P0-03 | 拦截 127.0.0.1、169.254.x、白名单、观察模式 |
| P0-04 | `json_response` 的 `errcode` 为 int |
| P0-05 | Cron 字段校验、`mon,wed` API 星期、SSRF 联动拒绝 |

> 注意：在 Python 3.12+ 上 Flask 1.1 / Werkzeug 1.0 可能无法启动完整应用，请用 3.8–3.11 做端到端验证。

## 手工冒烟清单

1. **密码**：`python scripts/hash_login_password.py 你的密码` 写入 `conf.ini` 后登录管理端。
2. **SSRF**：新建任务 `req_url=http://127.0.0.1/...` 应保存失败；`block_private_ip=0` 可放开（不推荐生产）。
3. **Ajax**：列表页操作后应正常提示（`requests.js` 已改为 `errcode === 0`）。
4. **API**：`POST /api/cron` 与 Web 添加同一 `task_name` 规则应一致。
5. **删除任务**：删除 cron 后 `job_log` 关联记录应一并清除（无 SQL 拼接）。
