# CronPilot HTTP 冒烟辅助
# shellcheck shell=bash

smoke_http_check() {
  local name="$1" expect="$2" url="$3" method="${4:-GET}" data="${5:-}"
  local code
  if [[ "$method" == "POST" ]]; then
    code=$(curl -s -o /dev/null -w "%{http_code}" --connect-timeout 5 -X POST -d "$data" "$url" 2>/dev/null || echo "000")
  else
    code=$(curl -s -o /dev/null -w "%{http_code}" --connect-timeout 5 -L "$url" 2>/dev/null || echo "000")
  fi
  if echo "$code" | grep -qE "$expect"; then
    echo "PASS $name ($code)"
    return 0
  fi
  echo "FAIL $name (got $code, want $expect)"
  return 1
}

smoke_http_cron_list() {
  local base="$1" password="$2"
  local jar body
  jar=$(mktemp)
  curl -s -c "$jar" -b "$jar" -X POST -d "password=${password}" -o /dev/null "$base/rbac/login" 2>/dev/null || true
  body=$(curl -s -b "$jar" -L "$base/cron_list" 2>/dev/null || true)
  rm -f "$jar"
  if echo "$body" | grep -qi 'system err'; then
    echo "FAIL cron_list (body contains system err)"
    return 1
  fi
  if ! echo "$body" | grep -q '任务列表'; then
    echo "FAIL cron_list (missing 任务列表 in body)"
    return 1
  fi
  echo "PASS cron_list (page OK)"
  return 0
}

smoke_http_suite() {
  local base="$1" password="$2"
  local fail=0
  smoke_http_check home '200|302' "$base/" || fail=$((fail + 1))
  smoke_http_check docs '200' "$base/docs/" || fail=$((fail + 1))
  smoke_http_check docs_index '200' "$base/docs/index.html" || fail=$((fail + 1))
  smoke_http_check docs_rfc '200' "$base/docs/依赖升级RFC.html" || fail=$((fail + 1))
  smoke_http_check login_page '200' "$base/rbac/login" || fail=$((fail + 1))
  smoke_http_check login_post '302' "$base/rbac/login" POST "password=${password}" || fail=$((fail + 1))
  smoke_http_check api_test '200' "$base/api/test" || fail=$((fail + 1))
  smoke_http_cron_list "$base" "$password" || fail=$((fail + 1))
  return "$fail"
}
