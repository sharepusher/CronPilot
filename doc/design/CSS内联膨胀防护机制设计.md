# CSS 内联膨胀防护机制设计 — 从 R1 治标到治本

> HTML 版：[CSS内联膨胀防护机制设计.html](CSS内联膨胀防护机制设计.html) · [文档索引](../index.html) · [索引 Markdown](../index.md)

# CSS 内联膨胀防护机制设计 — 从 R1 治标到治本

**关联文档**：`doc/design/Phase-R1-CSS架构统一实施方案.html`、`doc/design/Redesign前端代码质量评估与优化计划.html`  
**优先级**：P1（Phase R1 后续防护层，属治本措施）  
**预计工时**：0.5 天  
**目标**：建立 CI 可执行的结构性防护，使内联 CSS 膨胀在开发阶段即被拦截，而非依赖事后清理

## 一、问题：为什么 Phase R1 之后还需要这个文档

Phase R1 成功地将 2010 行内联 CSS 降至 0 行，但它是**一次性人工操作**。在没有结构性防护的情况下，下一次功能迭代完全可能复现同样的问题。

### 1.1 问题的本质不是"代码写得差"

在 R1 之前，每个页面的开发模式是：

```
开发者拿到 Mockup → 在模板 <style> 中写 CSS → 功能验收通过 → 发布
                                                    ↑
                                         唯一 DoD = "功能是否工作"
```

这种模式是**激励结构**决定的：内联比外联更快（不需要理解 6 个 CSS 文件的分工）、功能验收不检查 CSS 架构、CI 没有内联量门禁。开发者选择了**对个人效率最优但对系统长期可维护性最差**的路径。这是系统设计问题，不是个人纪律问题。

### 1.2 现有防护的覆盖面

| 已有门禁 | 检查范围 | 盲区 |
| --- | --- | --- |
| `audit_hardcoded_colors.py` | CSS/模板中的硬编码十六进制颜色 | 不检查 CSS 是否在正确的文件中 |
| `check_ui_contract.py` | `style=""` 属性、Bootstrap class、style 中的 hex | **不检查 `<style>` 块内的 CSS 行数** |
| `ui-contract.yml` CI | 执行上述检查 | 200 行合规内联 CSS → 全绿 |

**核心盲区**：开发者可以在模板 `<style>` 中写 200 行完全合规的 CSS（使用 `var(--cp-*)`、无 Bootstrap class），所有现有 CI 门禁全部通过——但 R1 清理的问题完整复现。

## 二、根因：系统激励与期望产出的不对齐

### 2.1 五层 Why 分析

| 层级 | 问题 | 原因 |
| --- | --- | --- |
| Why-1 | 内联 CSS 膨胀到 2010 行 | 每个页面独立开发时 CSS 就地编写 |
| Why-2 | 为什么就地编写？ | 不知道（或不关心）应该放到哪个外联文件 |
| Why-3 | 为什么不知道？ | 没有文档化的「CSS 归属决策树」，也无自动提示 |
| Why-4 | 为什么没有决策树？ | 项目早期页面少，一人开发无需规范；后来快速堆积时无人回头补 |
| Why-5 | 为什么快速堆积时没补？ | DoD 只验功能不验架构，CI 无内联量门禁 → 无反馈 → 无改进压力 |

### 2.2 结构性根因总结

**根因公式**：  
`缺乏架构验收门禁` + `错误路径（内联）比正确路径（外联）更省力` + `开发者无决策指引` = **必然的内联 CSS 膨胀**

解法必须同时解决这三个因子，否则无效：

- 只补文档（决策树）→ 依赖自律，约 70% 遵守率
- 只加门禁 → 开发者被拦后不知道正确做法，效率降低
- 只改工作流 → 没有自动化卡点，规范漂移

## 三、方案：三层防护体系

**核心设计原则**：让错误做法比正确做法更费力。  
正确路径（写到 `redesign-pages.css`）= 一步到位，CI 绿。  
错误路径（写在 `<style>`）= CI 红 → 需要修 → 反而多花时间。

### 3.1 层级架构

| 防护层 | 位置 | 作用 | 触发时机 |
| --- | --- | --- | --- |
| **L1 · CI 门禁**（硬卡点） | `scripts/check_ui_contract.py` | 扫描模板 `<style>` 块内非注释 CSS 行 > 阈值则 exit 1 | push / PR |
| **L2 · 决策引导**（认知辅助） | `.cursor/rules/cronpilot-project.mdc` | CSS 归属决策树 + 新页面模板脚手架 | Agent 开发时自动注入 |
| **L3 · 模板约束**（最佳实践） | `AGENTS.md` | 新页面必须声明 `{% block main_class %}`；Scope class 索引 | 代码 Review / Agent 参考 |

### 3.2 L1 · CI 门禁实现细节

#### 检查逻辑（新增函数 `check_inline_css_volume()`）

```
scripts/check_ui_contract.py

+INLINE_CSS_MAX_LINES = 3  # 允许极少量动态覆写（如 Jinja 条件变量）
+
+def check_inline_css_volume(lines: list, filepath: str) -> list:
+    """Flag <style> blocks with > INLINE_CSS_MAX_LINES of actual CSS."""
+    violations = []
+    in_style = False
+    css_lines = 0
+    style_start = 0
+
+    for lineno, line in enumerate(lines, 1):
+        stripped = line.strip()
+        if '<style' in stripped.lower() and '</style' not in stripped.lower():
+            in_style = True
+            css_lines = 0
+            style_start = lineno
+        elif '</style' in stripped.lower():
+            if in_style and css_lines > INLINE_CSS_MAX_LINES:
+                violations.append({
+                    'file': filepath,
+                    'line': style_start,
+                    'type': 'inline-css-volume',
+                    'detail': (
+                        f'<style> block has {css_lines} CSS lines '
+                        f'(max {INLINE_CSS_MAX_LINES}) — '
+                        f'move to redesign-pages.css with .cp-page-xxx scope'
+                    ),
+                })
+            in_style = False
+        elif in_style:
+            # Skip empty lines, pure comment lines, comment placeholder lines
+            if stripped and not stripped.startswith('/*') and not stripped.startswith('//'):
+                if not stripped.endswith('*/') or not stripped.startswith('/*'):
+                    css_lines += 1
+
+    return violations
```

#### 阈值决策

| 阈值候选 | 允许场景 | 拦截场景 | 推荐度 |
| --- | --- | --- | --- |
| 0 行（绝对禁止） | 无 | 全部 | 过严——需禁止所有 `<style>` 标签 |
| **3 行**（推荐） | 注释占位 + 1-2 行 Jinja 动态覆写 | 任何结构性 CSS | ✅ 平衡严格与灵活 |
| 5 行 | 小段微调 | 大段 CSS | 略宽松，仍可接受 |
| 10 行 | 短页面样式 | 仅大段 | 过宽——不足以预防 |

**推荐阈值 = 3 行**。当前所有模板的 `<style>` 块要么为空、要么只含 1 行注释（R1 清理的结果），3 行阈值与现状完全兼容。唯一例外是 `task_detail.html`（1 行实际 CSS），在阈值内。

#### 误报排除

- 纯注释行（`/* ... */`）不计入
- 空行不计入
- `{% block css %}` 或 `<style>` 标签本身行不计入
- 单行格式注释（如 `/* Dashboard — see redesign-pages.css */`）不计入

### 3.3 L2 · CSS 归属决策树

需要写 CSS？  
├─ 是 Design Token 新增/修改？  
│ └─→ **console-theme.css** :root { --cp-xxx: ... }  
├─ 是通用 UI 组件（任何页面可能复用）？  
│ └─→ **redesign-components.css**  
├─ 是全局 Layout/Shell（sidebar, topbar, grid）？  
│ └─→ **redesign-layout.css**  
├─ 是跨页面共享表格/卡片标准？  
│ └─→ **redesign-mockup-shared.css**  
├─ 是认证页（不继承 \_base.html）？  
│ └─→ **redesign-auth.css**  
└─ 是页面专属样式？  
└─→ **redesign-pages.css**，使用 `.cp-page-xxx` 作用域  
  
**绝对禁止**：在模板 <style> 块中新增超过 3 行的 CSS

### 3.4 L3 · 新页面模板脚手架

```
新页面标准结构

{# CronPilot Redesign — [页面名称] #}
{% extends "redesign/_base.html" %}
{% block title %}页面标题{% endblock %}
{% block main_class %} cp-page-xxx{% endblock %}

{% block content %}
<div class="cp-page-xxx-content">
  {# 页面结构 #}
</div>
{% endblock %}

{% block js %}
<script>
{# 页面专属 JS（< 30 行可内联；> 30 行提取为独立文件）#}
</script>
{% endblock %}

{# CSS 归属：app/static/css/redesign-pages.css → .cp-page-xxx 作用域 #}
{# 禁止：在此文件中新增 <style> 块 #}
```

## 四、范围

### 4.1 需修改的文件

| 文件 | 变更类型 | 描述 |
| --- | --- | --- |
| `scripts/check_ui_contract.py` | 功能扩展 | 新增 `check_inline_css_volume()` + 在 `scan()` 中调用 |
| `tests/test_check_ui_contract.py` | 新增测试 | 覆盖阈值检查的正向（拦截）和反向（放行）场景 |
| `.cursor/rules/cronpilot-project.mdc` | 追加规范 | 「CSS 归属决策树」+ 「新页面模板约束」 |
| `AGENTS.md` | 追加引用 | 新页面 CSS 规范快速命令 + 决策树摘要 |

### 4.2 明确不做

- **不做 R2（命名统一）**：作用域隔离已解决冲突问题，重命名 ROI 过低
- **不做 R3（JS 模块化）**：JS 架构质量已达 A 级，无结构性问题
- **不修改现有已清理的模板**：R1 成果保持原样
- **不引入新的 CSS 文件**：6 文件架构已足够
- **不改 CI workflow**：`ui-contract.yml` 已覆盖该脚本，无需额外配置

## 五、分批

本方案规模小（0.5 天），**单批交付**：

| 步骤 | 内容 | 验收点 |
| --- | --- | --- |
| 1 | 扩展 `check_ui_contract.py` 新增 inline-css-volume 检查 | `python scripts/check_ui_contract.py --check` 在现有代码上通过（0 violations） |
| 2 | 新增测试用例 | `python -m unittest tests.test_check_ui_contract -v` 全绿 |
| 3 | 更新 `.cursor/rules/cronpilot-project.mdc` | Agent 创建新页面时自动遵循决策树 |
| 4 | 更新 `AGENTS.md` | 快速命令区新增 `check_ui_contract.py` 说明 |

## 六、验收

### 6.1 门禁通过性

```
# 现有代码应全部通过（0 violations）
python scripts/check_ui_contract.py --check

# 模拟违规：临时在任意模板 <style> 中加 5 行 CSS
# → 应报 inline-css-volume violation 并 exit 1
```

### 6.2 测试覆盖

```
python -m unittest tests.test_check_ui_contract -v
# 新增用例：
#   test_inline_css_volume_exceeds_threshold  — 4+ CSS 行 → 违规
#   test_inline_css_volume_within_threshold   — 1-3 CSS 行 → 通过
#   test_inline_css_volume_comments_excluded  — 注释行不计入
#   test_inline_css_volume_empty_block        — 空 <style> → 通过
```

### 6.3 规范有效性

```
# 验证 AGENTS.md 中新增了决策树引用
grep "CSS 归属" AGENTS.md

# 验证 .cursor/rules/ 中包含决策树
grep "redesign-pages.css" .cursor/rules/cronpilot-project.mdc
```

### 6.4 回归

```
# 侧边栏权限回归
python -m unittest tests.test_redesign_sidebar -v

# 颜色审计
python scripts/audit_hardcoded_colors.py --check

# 现有 UI contract 测试
python -m unittest tests.test_check_ui_contract -v
```

## 七、风险

| 风险 | 概率 | 影响 | 缓解 |
| --- | --- | --- | --- |
| `task_detail.html` 的 1 行实际 CSS 触发误报 | 低 | 低 | 阈值 3 > 1，不会触发；若未来扩充则须迁移到 `redesign-pages.css` |
| 开发者绕过门禁（把大段 CSS 拆为多个 <style> 块每块 ≤ 3 行） | 极低 | 中 | Code Review 关注 `<style>` 标签数量；可后续扩展为"单模板 <style> 标签最多 1 个" |
| 新增需求确实需要动态 CSS（如 Jinja 变量注入样式） | 中 | 低 | 3 行阈值允许 `:root { --dynamic-val: {{ value }}px; }` 等极少量注入 |

## 八、预期长期效果

实施后的开发闭环：

```
[开发者新增/修改页面]
  → Agent/人工参考决策树 → CSS 写入正确的外联文件
  → git push
  → CI: check_ui_contract.py --check
      → inline-css-volume > 3?  → ❌ 阻断（附带修复提示）
      → inline-style 违规?      → ❌ 阻断
      → hardcoded-color?         → ❌ 阻断
      → legacy-class?            → ❌ 阻断
  → ✅ PR 合并

效果：
  · 不依赖开发者自律
  · 错误路径（内联）比正确路径更费力（CI 红 → 需修改 → 多花时间）
  · 正确路径有明确指引（决策树 + 脚手架）
  · 技术债在入口处被拦截，永不积累
```

**核心转变**：从「事后清理技术债」→ 「结构上不可能积累技术债」。

[文档索引](index.html) · [Markdown](CSS内联膨胀防护机制设计.md) · [索引](index.html)

---

[← 文档索引（HTML）](../index.html) · [← 文档索引（Markdown）](../index.md)
