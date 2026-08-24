# 复盘：Phase 2 Dashboard/执行记录实现偏离 Mockup

> HTML 版：[2026-08-Phase2-Mockup偏离复盘.html](2026-08-Phase2-Mockup偏离复盘.html) · [文档索引](../index.html) · [索引 Markdown](../index.md)

# 复盘：Phase 2 Dashboard/执行记录实现偏离 Mockup

**日期**：2026-08-12  
**涉及**：OPT-P1-16 UI 重设计 Phase 2  
**影响**：Dashboard + 执行记录页全量重写

## 1. Bug 定位

首次 Phase 2 实现的 `redesign/dashboard.html` 和 `redesign/execution_logs.html`
与 `doc/design/CronPilot-2026-redesign-mockup.html` 存在**结构性偏离**：

| 区域 | Mockup 规范 | 首次实现 | 偏离程度 |
| --- | --- | --- | --- |
| Stats Row | 异常任务/连续失败/运行中/今日失败 + sub-text | 总任务/运行中/异常/今日失败 (无 sub-text) | 严重 |
| Exception Panel | 红边框面板 + ×N + 任务列表 + 查看详情 | 完全缺失 | 致命 |
| Filter Chips | 含数量 (全部 128 / 异常 3...) | 无数量显示 | 中等 |
| 表格列数 | 7 列 (任务/调度/健康度/最近执行/下次执行/业务组/操作) | 5 列 (缺健康度/下次执行两列) | 严重 |
| Task Cell | name + task\_id(mono) + lifecycle + tags | name + req\_url + scope + tags | 中等 |
| 操作列 | Icon-only SVG 按钮 (▶ ❚❚ ⋮) | 文字按钮 (暂停/编辑/执行/下线) | 严重 |
| 执行记录行高亮 | 失败行 background:danger-bg | 无高亮 | 中等 |
| 执行记录列 | 7 列 (含响应码 + 失败原因) | 6 列 (缺 fail\_reason 独立列) | 中等 |

## 2. 根因

- **直接原因**：Agent 未在编码前 `Read` Mockup HTML 的对应 `view-dashboard` 区块完整源码。依赖对 Mockup 的"记忆印象"而非实际结构比对。
- **结构性原因**：缺少「Mockup → 实现对照清单」机制。Mockup 是 2500+ 行 HTML，靠记忆无法准确提取所有设计细节（列数、组件层级、CSS class、按钮类型等）。
- **行为层原因**：Agent 在 Phase 2 启动时直接进入编码，跳过了"提取结构清单"步骤；交付验证时只检查"页面能渲染、数据正确"，未逐区域对照 Mockup 截图。

## 3. 测试漏洞

- 无结构对照测试：没有自动化测试验证渲染 HTML 是否包含 Mockup 规定的关键 class/结构
- 浏览器验证走马观花：首次验证只确认"页面能渲染"，未逐列、逐区域对照

## 4. 修复

全量重写 `dashboard.html` 和 `execution_logs.html`，新增后端方法 `count_consecutive_failing()` 和 `status_counts()`。

## 5. 防护测试

```
# Dashboard 结构检查
curl -s -b cookie.txt -b "cp_ui_version=v2" http://127.0.0.1:5001/cron_list | \
  grep -c 'hf-stats\|exc-panel\|hf-table.*thead\|row-acts\|hf-pagination'
# 期望 ≥ 5

# 执行记录结构检查
curl -s -b cookie.txt -b "cp_ui_version=v2" http://127.0.0.1:5001/job_log_all_list | \
  grep -c 'el-table.*thead\|el-status\|el-fail-reason\|el-action-btn\|row-fail'
# 期望 ≥ 5
```

## 6. 同类排查

- `redesign/_sidebar.html` — ✅ 已通过 `test_redesign_sidebar.py` 回归
- `redesign/_topbar.html` — ✅ 结构简单，对齐度高
- 未来新增页面（用户管理、业务组、审计日志等）— **需在实现时执行逐节对照**

## 7. 预防方案

| 措施 | 落地位置 | 验证方式 |
| --- | --- | --- |
| 新增「Mockup 逐节对照」强制步骤（4 步） | `.cursor/rules/cronpilot-project.mdc` § "Redesign Mockup 逐节对照" | `grep "Mockup 逐节对照" .cursor/rules/cronpilot-project.mdc` |
| 新增同规范到 AGENTS.md | `AGENTS.md` § "Redesign Mockup 逐节对照" | `grep "Mockup 逐节对照" AGENTS.md` |
| 交付前结构断言脚本化 | Agent 工作流（本文档定义的 curl+grep 命令） | 在下一次 UI 页面交付时执行 |

[文档索引](../index.html) · [Markdown](2026-08-Phase2-Mockup偏离复盘.md) · [索引](../index.html)

---

[← 文档索引（HTML）](../index.html) · [← 文档索引（Markdown）](../index.md)
