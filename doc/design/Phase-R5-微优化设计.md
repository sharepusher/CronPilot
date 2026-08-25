# Phase R5 微优化 — prefers-reduced-motion 补全 + Script defer

> HTML 版：[Phase-R5-微优化设计.html](Phase-R5-微优化设计.html) · [文档索引](../index.html) · [索引 Markdown](../index.md)

# Phase R5 微优化 — prefers-reduced-motion 补全 + Script defer

**关联文档**：`doc/design/Redesign前端代码质量评估与优化计划.html` §九 Phase R5  
**优先级**：P2（可访问性合规 + 低风险微优化）  
**预计工时**：0.5 天  
**目标**：① 补全 WCAG 2.1 Level AA 动画可访问性要求 ② 改善首屏渲染时序

## 一、问题

### 1.1 prefers-reduced-motion 覆盖不全

项目定义了 15 个 `@keyframes` 动画 + 多处 CSS transition，但仅 2 处响应 `prefers-reduced-motion`（exec-logs 行入场和 fail-dot pulse）。无限循环动画（pulse/shimmer）对前庭障碍用户造成不适。

### 1.2 Script 加载无 defer

7 个 `<script>` 标签无 defer 属性，浏览器串行下载 + 执行 166 KB JS 阻塞 DOMContentLoaded 触发。

## 二、根因

- **reduced-motion**：开发时无可访问性检查清单；动画增量添加未系统审计
- **defer**：继承 v1 模板的 body 末尾 script 模式（2010 年代最佳实践），Redesign 未重新评估

## 三、方案

### 3.1 prefers-reduced-motion 补全

在 `redesign-pages.css` 和 `redesign-components.css` 末尾添加统一的 `@media (prefers-reduced-motion: reduce)` 块，覆盖所有非必要动画：

- 所有 `animation` → `animation: none !important`
- 所有 `transition` → `transition: none !important`（保留 opacity 用于功能性过渡如 tooltip 显隐）

### 3.2 Script defer

在 `_base.html` 的 7 个外联 `<script>` 标签添加 `defer` 属性。保留执行顺序，允许 HTML 解析继续。

## 四、范围

| 文件 | 变更 |
| --- | --- |
| `app/static/css/redesign-pages.css` | 末尾追加 `@media (prefers-reduced-motion: reduce)` 块 |
| `app/static/css/redesign-components.css` | 末尾追加 reduced-motion 覆盖（toast/modal/shimmer） |
| `app/templates/redesign/_base.html` | 7 个 `<script>` 标签添加 `defer` |

**不做**：IntersectionObserver、CSS 拆分、SVG sprite、去 jQuery

## 五、分批

单批交付（范围极小）：① reduced-motion CSS → ② defer 属性 → ③ 验证

## 六、验收

```
# 1. 可访问性
grep -c "prefers-reduced-motion" app/static/css/redesign-pages.css    # ≥ 1
grep -c "prefers-reduced-motion" app/static/css/redesign-components.css  # ≥ 1

# 2. defer
grep -c 'defer' app/templates/redesign/_base.html  # = 7

# 3. 回归
python -m unittest tests.test_redesign_sidebar -v  # 12/12
python scripts/check_ui_contract.py 2>&1 | grep "inline-css-volume" | wc -l  # = 0
```

## 七、风险

| 风险 | 概率 | 缓解 |
| --- | --- | --- |
| defer 导致内联 script 在 jQuery 前执行 | 低 | 内联 script 在 body 内，defer scripts 在 head 或 body 末尾均保证先执行 |
| reduced-motion 覆盖影响功能性动画（如 loading spinner） | 低 | 仅覆盖装饰性动画；shimmer 在 reduce-motion 下改为静态背景色 |

[文档索引](index.html) · [Markdown](Phase-R5-微优化设计.md) · [索引](index.html)

---

[← 文档索引（HTML）](../index.html) · [← 文档索引（Markdown）](../index.md)
