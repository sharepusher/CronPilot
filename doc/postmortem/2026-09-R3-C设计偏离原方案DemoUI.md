# R3-C 设计偏离原方案 Demo UI 复盘（2026-09）

> HTML 版：[2026-09-R3-C设计偏离原方案DemoUI.html](2026-09-R3-C设计偏离原方案DemoUI.html) · [文档索引](../index.html) · [索引 Markdown](../index.md)

# R3-C 设计偏离原方案 Demo UI 复盘

**日期**：2026-09-16 · **类型**：文档 / 设计交付 · **关联**：R3-C · **rev.3**（2026-09-17：页面对比改为 Demo §B 原文照录）

## 1. Bug 定位

R3-C 短设计的 `#page-compare` 多次自造变体（点列+标签、保留 HTTP、五行注释），
与权威源
`doc/design/任务执行链路可观测性-页面对比Demo.html` **§B**
的 AS-IS / TO-BE 画面不一致。用户要求：「改造后页面 demo 应该和上面文档的一致」。

## 2. 根因

行为层：写子设计时未把 Demo §B 的 HTML **逐行抄进** AFTER，而是「语义对齐 + 现网列保留」自行折中
（先拼圆点+标签，再保留 HTTP）。门禁只查有无 `page-compare`，不强制与父 Demo 列数/样例行同构。

## 3. 测试漏洞

`grep page-compare|BEFORE|AFTER` 与「含 ● 超时」对「Demo+HTTP」变体仍绿。
无「AFTER 列数 / 样例行 = 父 Demo TO-BE」机械对照。

## 4. 修复

- rev.3：R3-C `#page-compare` **原文照录** Demo §B 的 AS-IS / TO-BE（标题、三行、文案、变化说明相同）。
- 删掉自造 BEFORE（空白时间/HTTP/行注）、纠偏说明与折中列讨论；方案节只指向该对照。

## 5. 防护测试

```
# 与 Demo §B TO-BE 关键文案一致
grep -nF '● 超时' doc/design/R3-C-任务详情最近执行状态语义收口设计-2026-09.html
grep -nF '◎ 执行中' doc/design/R3-C-任务详情最近执行状态语义收口设计-2026-09.html
grep -nF '改造后：状态机语义' doc/design/R3-C-任务详情最近执行状态语义收口设计-2026-09.html
# 不应再出现自造「列头 HTTP / 空心圆 BEFORE」
grep -nE 'before-ball|td-rr-code|col-head before' \
  doc/design/R3-C-任务详情最近执行状态语义收口设计-2026-09.html && echo FAIL || echo OK
python3 scripts/html_docs_to_markdown.py --check
```

## 6. 同类排查

| 文档 | 结论 |
| --- | --- |
| R1 执行记录列表 | 对齐列表徽章，非 Demo §B |
| R2 Run Inspector | 对齐 Demo §C |
| 承接页面对比 Demo 的短设计 | AFTER 须抄录父节 HTML 结构，禁止「语义对 + 现网列折中」 |

## 7. 预防方案

已有「子设计锚定父 Demo TO-BE」规范（rev.1）。**rev.2 补强**：锚定 =
**抄录父 TO-BE 的列结构与关键样例行**，不得以「现网已有某列」为由在 AFTER 加回父 Demo 未画的列。
落点同 rev.1（`cronpilot-project.mdc` / `AGENTS.md`）；本复盘补记「禁止折中加列」。

验证：打开父 Demo §B 与子设计 `#page-compare` AFTER 并排，列数与三行文案一致。

[文档索引](index.html) · [Markdown](2026-09-R3-C设计偏离原方案DemoUI.md) · [索引](index.html)

---

[← 文档索引（HTML）](../index.html) · [← 文档索引（Markdown）](../index.md)
