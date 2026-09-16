#!/bin/bash
# L1-Enhanced: Post-file-edit hook — MANDATORY postmortem gate
# Fires after every StrReplace/Write/EditNotebook
# 
# This is the PRIMARY enforcement mechanism (proven 100% trigger rate).
# L2 (stop hook) is a best-effort safety net.
#
# History: Created 2026-08-11 after 3+ failures of text-only rules.
# Enhanced same day after RELEASE_NOTES sync was missed.

# Read stdin (tool output JSON)
cat > /dev/null

# Inject comprehensive checklist
cat <<'EOF'
{
  "additional_context": "🚨 POSTMORTEM GATE (L1 Hook · MANDATORY) 🚨\n\nYou just edited a file. BEFORE you can invoke AskQuestion or finish this turn:\n\n━━━ STEP 1: CLASSIFY ━━━\nIs this edit a FIX (correcting something wrong) or CREATION (adding something new)?\n\n━━━ STEP 2: IF FIX → FULL CHECKLIST ━━━\nYour response MUST contain '## 复盘' with ALL 7 elements:\n□ Bug 定位\n□ 根因（追到行为层，非「粗心」）\n□ 测试漏洞\n□ 修复\n□ 防护测试\n□ 同类排查\n□ 预防方案（具体措施 + 落地位置 + 验证命令）\n\n━━━ STEP 3: 文档化（与 STEP 2 是原子操作，禁止拆到下一轮） ━━━\n□ doc/postmortem/*.html 已创建/更新（复盘内容持久化）\n□ python scripts/html_docs_to_markdown.py 生成 MD 并 --check 通过\n□ RELEASE_NOTES.md [Unreleased] 节已包含本次变更\n□ AGENTS.md 已同步（如预防方案涉及规范新增）\n\n⛔ STEP 2 + STEP 3 是一个整体。写完 7 要素文字但未执行文档化 = 未完成复盘。\n⛔ 未完成 STEP 1-3 就 invoke AskQuestion = VIOLATION\n⛔ 历史教训：至少 4 次出现「7 要素写了但文档化遗漏」，根因是将文档化视为独立步骤。"
}
EOF
exit 0
