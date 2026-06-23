#!/usr/bin/env bash
# 在 Docker 中验证根目录 Dockerfile（隔离 conf，不覆盖宿主机 conf.ini）。
# 注意：通过本脚本 ≠ docker compose 可用；compose 黄金路径须 scripts/verify_docker_compose.sh
set -euo pipefail
export PATH="/Applications/Docker.app/Contents/Resources/bin:${PATH:-/usr/bin:/bin}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CRONPILOT_ROOT="${CRONPILOT_ROOT:-$(cd "$SCRIPT_DIR/.." && pwd)}"
DOCKERFILE="${DOCKERFILE:-$CRONPILOT_ROOT/Dockerfile}"
IMAGE="${IMAGE:-cronpilot:verify-test}"
CONTAINER="${CONTAINER:-cronpilot-verify}"
BUILD_LOG="${BUILD_LOG:-/tmp/cronpilot-docker-build.log}"
VERIFY_CONF="${VERIFY_CONF:-$(mktemp /tmp/cronpilot-docker-verify.XXXXXX.ini)}"
WAIT_SECS="${WAIT_SECS:-60}"
cd "$CRONPILOT_ROOT"

cleanup() {
  rm -f "$VERIFY_CONF" 2>/dev/null || true
}
trap cleanup EXIT

if ! docker info >/dev/null 2>&1; then
  echo "ERROR: Docker daemon not reachable. Start Docker Desktop and retry." >&2
  exit 1
fi

echo "=== prepare SQLite conf for container ==="
mkdir -p datas/logs
CRONPILOT_ROOT="$CRONPILOT_ROOT" VERIFY_CONF="$VERIFY_CONF" python3 - <<'PY'
from configparser import ConfigParser
import os
from pathlib import Path

root = Path(os.environ["CRONPILOT_ROOT"])
out = Path(os.environ["VERIFY_CONF"])
cp = ConfigParser()
cp.read(root / "conf.ini.example", encoding="utf-8")
cp.set("default", "is_single", "1")
cp.set("default", "cron_db_url", "sqlite:////opt/cronpilot/datas/cron.sqlite")
cp.set("default", "cron_job_log_db_url", "sqlite:////opt/cronpilot/datas/job_log.sqlite")
cp.set("default", "login_pwd", "changeme")
with open(out, "w", encoding="utf-8") as f:
    cp.write(f)
print("VERIFY_CONF:", out)
PY

echo "=== docker build ==="
set +e
docker build -f "$DOCKERFILE" -t "$IMAGE" . 2>&1 | tee "$BUILD_LOG"
BUILD_EXIT=${PIPESTATUS[0]}
set -e
if [[ "$BUILD_EXIT" -ne 0 ]]; then
  echo "BUILD: FAIL (exit $BUILD_EXIT)"
  echo "--- last 50 lines of build log ---"
  tail -50 "$BUILD_LOG"
  exit "$BUILD_EXIT"
fi
echo "BUILD: OK"

docker rm -f "$CONTAINER" 2>/dev/null || true
echo "=== docker run ==="
docker run -d --name "$CONTAINER" -p 5860:5860 \
  -v "$(pwd)/datas:/opt/cronpilot/datas" \
  -v "$VERIFY_CONF:/opt/cronpilot/conf.ini:ro" \
  "$IMAGE"

echo "=== wait for HTTP (up to ${WAIT_SECS}s) ==="
deadline=$((SECONDS + WAIT_SECS))
docs_code="000"
home_code="000"
while (( SECONDS < deadline )); do
  docs_code=$(curl -sf -o /dev/null -w "%{http_code}" --connect-timeout 3 http://127.0.0.1:5860/docs/ 2>/dev/null || echo "000")
  home_code=$(curl -sf -o /dev/null -w "%{http_code}" --connect-timeout 3 http://127.0.0.1:5860/ 2>/dev/null || echo "000")
  if [[ "$docs_code" == "200" && "$home_code" =~ ^(200|302)$ ]]; then
    break
  fi
  sleep 2
done

echo "docs:${docs_code}"
echo "home:${home_code}"

echo "--- container logs (last 50) ---"
docker logs "$CONTAINER" 2>&1 | tail -50

if [[ "$docs_code" != "200" || ! "$home_code" =~ ^(200|302)$ ]]; then
  echo "HTTP: FAIL (docs=${docs_code}, home=${home_code})" >&2
  docker stop "$CONTAINER" && docker rm "$CONTAINER"
  exit 1
fi
echo "HTTP: OK"

if [[ "${SMOKE_LEVEL:-basic}" == "full" ]]; then
  echo "=== extended HTTP smoke ==="
  # shellcheck source=smoke_http.sh
  source "$SCRIPT_DIR/smoke_http.sh"
  ext_fail=0
  smoke_http_suite "http://127.0.0.1:5860" "changeme" || ext_fail=$?
  if [[ "$ext_fail" -ne 0 ]]; then
    echo "EXTENDED_HTTP: FAIL ($ext_fail checks)" >&2
    docker stop "$CONTAINER" && docker rm "$CONTAINER"
    exit 1
  fi
  echo "=== flask db CLI (container) ==="
  docker exec "$CONTAINER" bash -c 'cd /opt/cronpilot && export FLASK_APP=manage:app FLASK_CONFIG=production && .venv-py39/bin/flask db --help | head -1' || {
    echo "EXTENDED: flask db FAIL" >&2
    docker stop "$CONTAINER" && docker rm "$CONTAINER"
    exit 1
  }
  echo "=== gevent / gunicorn (container) ==="
  docker exec "$CONTAINER" bash -c '.venv-py39/bin/python -c "import gevent, gunicorn; print(gevent.__version__, gunicorn.__version__)"' || {
    echo "EXTENDED: gevent FAIL" >&2
    docker stop "$CONTAINER" && docker rm "$CONTAINER"
    exit 1
  }
  echo "EXTENDED: OK"
fi

docker stop "$CONTAINER" && docker rm "$CONTAINER"
echo "CLEANUP: OK"
