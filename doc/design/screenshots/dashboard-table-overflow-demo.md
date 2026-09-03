# Dashboard 操作下拉菜单重叠修复 — 对比 Demo

> HTML 版：[dashboard-table-overflow-demo.html](dashboard-table-overflow-demo.html) · [文档索引](../../index.html) · [索引 Markdown](../../index.md)

# Dashboard 操作下拉菜单重叠修复 — 对比 Demo

点击每行的 ⋮ 按钮打开下拉菜单，观察菜单与下方行的交互效果

## 当前（overflow: hidden — 下拉菜单被裁剪）

BUG

点击第 2 行或第 3 行的 ⋮ 按钮，菜单底部被 `overflow: hidden` 裁剪，无法完整显示。

| 任务 | 调度策略 | 健康度 | 最近执行 | 下次执行 | 操作 |
| --- | --- | --- | --- | --- | --- |
| payment-callback-scheduler 支付回调  运行中 | 每 2 小时  0 0 \*/2 \* \* \* | 异常 | 503 2.3s | in <1 min | ▶ 📄 ⋮ 暂停编辑  下线 |
| notification-service-check 通知监控  运行中 | 每小时  0 30 \* \* \* \* | 健康 | 200 0.5s | in 45 min | ▶ 📄 ⋮ 暂停编辑  下线 |
| data-etl-sync 数据同步  运行中 | 每 6 小时  0 0 \*/6 \* \* \* | 健康 | 200 12.7s | in 3 hr | ▶ 📄 ⋮ 暂停编辑  下线 |

## 修复后（overflow: visible + 增强阴影）

FIXED

点击任意行的 ⋮ 按钮，菜单完整显示在行上方，阴影清晰分层，不被裁剪。

| 任务 | 调度策略 | 健康度 | 最近执行 | 下次执行 | 操作 |
| --- | --- | --- | --- | --- | --- |
| payment-callback-scheduler 支付回调  运行中 | 每 2 小时  0 0 \*/2 \* \* \* | 异常 | 503 2.3s | in <1 min | ▶ 📄 ⋮ 暂停编辑  下线 |
| notification-service-check 通知监控  运行中 | 每小时  0 30 \* \* \* \* | 健康 | 200 0.5s | in 45 min | ▶ 📄 ⋮ 暂停编辑  下线 |
| data-etl-sync 数据同步  运行中 | 每 6 小时  0 0 \*/6 \* \* \* | 健康 | 200 12.7s | in 3 hr | ▶ 📄 ⋮ 暂停编辑  下线 |

**对比要点**：分别在上方 BUG 版和下方 FIXED 版中点击第 2、3 行的 ⋮ 按钮。

BUG 版：菜单底部被裁剪 | FIXED 版：菜单完整显示，阴影明确分层

[文档索引](index.html) · [Markdown](dashboard-table-overflow-demo.md) · [索引](index.html)

---

[← 文档索引（HTML）](../../index.html) · [← 文档索引（Markdown）](../../index.md)
