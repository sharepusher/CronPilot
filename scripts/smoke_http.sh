# CronPilot HTTP 冒烟辅助
# shellcheck shell=bash

# GET login → extract csrf_token → POST login (OPT-P0-11)
smoke_http_extract_csrf() {
  local html="$1"
  local token
  token=$(printf '%s' "$html" | sed -n 's/.*name="csrf_token"[[:space:]]*value="\([^"]*\)".*/\1/p' | head -1)
  if [[ -z "$token" ]]; then
    token=$(printf '%s' "$html" | sed -n 's/.*value="\([^"]*\)"[[:space:]]*name="csrf_token".*/\1/p' | head -1)
  fi
  if [[ -z "$token" ]]; then
    token=$(printf '%s' "$html" | sed -n 's/.*name="csrf-token"[[:space:]]*content="\([^"]*\)".*/\1/p' | head -1)
  fi
  printf '%s' "$token"
}

smoke_http_login_post() {
  local base="$1" password="$2" jar="$3"
  local html token code
  html=$(curl -s -c "$jar" -b "$jar" --connect-timeout 5 "$base/rbac/login" 2>/dev/null || true)
  token=$(smoke_http_extract_csrf "$html")
  if [[ -z "$token" ]]; then
    echo "000"
    return 0
  fi
  code=$(curl -s -c "$jar" -b "$jar" -o /dev/null -w "%{http_code}" --connect-timeout 5 \
    -X POST -d "username=admin&password=${password}&csrf_token=${token}&next=/cron_list" \
    "$base/rbac/login" 2>/dev/null || echo "000")
  printf '%s' "$code"
}

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
  local jar body code
  jar=$(mktemp)
  code=$(smoke_http_login_post "$base" "$password" "$jar")
  if ! echo "$code" | grep -qE '302|200'; then
    rm -f "$jar"
    echo "FAIL cron_list (login got $code)"
    return 1
  fi
  body=$(curl -s -b "$jar" -L "$base/cron_list" 2>/dev/null || true)
  rm -f "$jar"
  if echo "$body" | grep -qi 'system err'; then
    echo "FAIL cron_list (body contains system err)"
    return 1
  fi
  if ! echo "$body" | grep -q '任务中心'; then
    echo "FAIL cron_list (missing 任务中心 in body)"
    return 1
  fi
  if ! echo "$body" | grep -q 'csrf-token'; then
    echo "FAIL cron_list (missing csrf-token meta)"
    return 1
  fi
  echo "PASS cron_list (page OK)"
  return 0
}

smoke_http_not_found() {
  local base="$1" password="$2"
  local jar body code

  body=$(curl -s -w $'\n%{http_code}' --connect-timeout 5 "$base/__smoke_404_probe__" 2>/dev/null || true)
  code=$(echo "$body" | tail -1)
  body=$(echo "$body" | sed '$d')
  if [[ "$code" != "404" ]]; then
    echo "FAIL not_found_guest (got HTTP $code, want 404; restart server after deploy?)"
    return 1
  fi
  if echo "$body" | grep -q 'page not found'; then
    echo "FAIL not_found_guest (old plain-text 404 handler — restart server?)"
    return 1
  fi
  if ! echo "$body" | grep -q '页面不存在'; then
    echo "FAIL not_found_guest (missing 页面不存在 in body)"
    return 1
  fi
  if ! echo "$body" | grep -q '前往登录'; then
    echo "FAIL not_found_guest (missing 前往登录 in body)"
    return 1
  fi

  jar=$(mktemp)
  code=$(smoke_http_login_post "$base" "$password" "$jar")
  if ! echo "$code" | grep -qE '302|200'; then
    rm -f "$jar"
    echo "FAIL not_found_logged_in (login got $code)"
    return 1
  fi
  body=$(curl -s -b "$jar" -w $'\n%{http_code}' --connect-timeout 5 "$base/__smoke_404_probe__" 2>/dev/null || true)
  rm -f "$jar"
  code=$(echo "$body" | tail -1)
  body=$(echo "$body" | sed '$d')
  if [[ "$code" != "404" ]]; then
    echo "FAIL not_found_logged_in (got HTTP $code, want 404)"
    return 1
  fi
  if ! echo "$body" | grep -q '页面不存在'; then
    echo "FAIL not_found_logged_in (missing 页面不存在 in body)"
    return 1
  fi
  if ! echo "$body" | grep -q '返回任务中心'; then
    echo "FAIL not_found_logged_in (missing 返回任务中心 in body)"
    return 1
  fi
  if ! echo "$body" | grep -q '任务中心'; then
    echo "FAIL not_found_logged_in (missing nav 任务中心 in body)"
    return 1
  fi
  echo "PASS not_found (guest + logged-in 404 page OK)"
  return 0
}

smoke_http_suite() {
  local base="$1" password="$2"
  local fail=0 jar code
  smoke_http_check home '200|302' "$base/" || fail=$((fail + 1))
  smoke_http_check docs '200' "$base/docs/" || fail=$((fail + 1))
  smoke_http_check docs_index '200' "$base/docs/index.html" || fail=$((fail + 1))
  smoke_http_check docs_rfc '200' "$base/docs/依赖升级RFC.html" || fail=$((fail + 1))
  smoke_http_check login_page '200' "$base/rbac/login" || fail=$((fail + 1))
  jar=$(mktemp)
  code=$(smoke_http_login_post "$base" "$password" "$jar")
  rm -f "$jar"
  if echo "$code" | grep -qE '302'; then
    echo "PASS login_post ($code)"
  else
    echo "FAIL login_post (got $code, want 302)"
    fail=$((fail + 1))
  fi
  smoke_http_check api_test '200' "$base/api/test" || fail=$((fail + 1))
  smoke_http_cron_list "$base" "$password" || fail=$((fail + 1))
  smoke_http_not_found "$base" "$password" || fail=$((fail + 1))
  return "$fail"
}
