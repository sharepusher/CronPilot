#!/bin/bash
# L2: Stop hook placeholder (actual gate logic is in hooks.json "type": "prompt")
#
# The stop event uses a prompt-based hook, not a command hook.
# This script exists for documentation and as a fallback reference.
#
# How L2 works:
# 1. Agent finishes its turn (stop event fires)
# 2. The prompt hook in hooks.json evaluates:
#    - Were file edits made that constitute a "fix"?
#    - Was a 7-element postmortem included?
# 3. If fix exists but postmortem is missing:
#    - Returns followup_message asking agent to add postmortem
#    - loop_limit=2 prevents infinite loops
# 4. If no fix, or postmortem present: allows stop
#
# Verification: the prompt hook is the "type": "prompt" entry under
# "stop" in .cursor/hooks.json. This script is not executed by the hook
# system (prompt hooks don't use command scripts).

echo '{}'
exit 0
