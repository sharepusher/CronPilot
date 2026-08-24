#!/bin/bash
# L2-Deterministic: Pre-commit gate — blocks git commit if postmortem docs are missing
# Fires before shell commands matching "git commit"
#
# Checks:
# 1. If app/ or .cursor/rules/ files are staged → RELEASE_NOTES.md must also be staged
# 2. If postmortem HTML was created → corresponding MD must exist
#
# This is DETERMINISTIC (no AI evaluation needed) and catches the exact failure mode:
# "code was fixed but documentation wasn't synced"

input=$(cat)

# Extract the command from stdin JSON using pure bash (no jq)
# The input format is: {"command": "git commit ..."}
command_line=$(echo "$input" | grep -o '"command"[[:space:]]*:[[:space:]]*"[^"]*"' | sed 's/"command"[[:space:]]*:[[:space:]]*"//;s/"$//')

# Only check git commit commands
case "$command_line" in
  git\ commit*|git\ -c*commit*)
    ;;
  *)
    echo '{"permission": "allow"}'
    exit 0
    ;;
esac

# Check 1: If app/ or .cursor/rules/ files are staged, RELEASE_NOTES.md should be too
staged_files=$(git diff --cached --name-only 2>/dev/null)
has_app_changes=$(echo "$staged_files" | grep -c "^app/\|^\.cursor/rules/")
has_release_notes=$(echo "$staged_files" | grep -c "RELEASE_NOTES.md")

if [ "$has_app_changes" -gt 0 ] && [ "$has_release_notes" -eq 0 ]; then
  echo '{
    "permission": "ask",
    "user_message": "⚠️ Staged changes include app/ or .cursor/rules/ files but RELEASE_NOTES.md is not staged. Per postmortem documentation rules, code changes must be reflected in RELEASE_NOTES.",
    "agent_message": "L2 Gate: You are committing code/rule changes without updating RELEASE_NOTES.md. Please update RELEASE_NOTES.md and stage it before committing."
  }'
  exit 0
fi

# Check 2: If postmortem HTML exists without MD sync
for html in doc/postmortem/*.html; do
  [ -f "$html" ] || continue
  md="${html%.html}.md"
  if [ ! -f "$md" ]; then
    echo "{
      \"permission\": \"ask\",
      \"user_message\": \"⚠️ Postmortem HTML exists ($html) but Markdown sync is missing ($md). Run: python scripts/html_docs_to_markdown.py\",
      \"agent_message\": \"L2 Gate: Postmortem documentation is incomplete. Generate Markdown before committing.\"
    }"
    exit 0
  fi
done

echo '{"permission": "allow"}'
exit 0
