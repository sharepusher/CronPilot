#!/usr/bin/env bash
set -euo pipefail
export PATH="/Applications/Docker.app/Contents/Resources/bin:${PATH:-/usr/bin:/bin}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CRONPILOT_ROOT="${CRONPILOT_ROOT:-$(cd "$SCRIPT_DIR/.." && pwd)}"
DOCKERFILE="${DOCKERFILE:-$CRONPILOT_ROOT/Dockerfile}"
IMAGE="${IMAGE:-cronpilot:verify-test}"
CONTAINER="${CONTAINER:-cronpilot-verify}"
BUILD_LOG="${BUILD_LOG:-/tmp/cronpilot-docker-build.log}"
cd "$CRONPILOT_ROOT"
if ! docker info >/dev/null 2>&1; then
  echo "ERROR: Docker daemon not reachable. Start Docker Desktop and retry." >&2
  exit 1
fi
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
cp conf.ini.example conf.ini 2>/dev/null || true
docker rm -f "$CONTAINER" 2>/dev/null || true
echo "=== docker run ==="
docker run -d --name "$CONTAINER" -p 5860:5860 \
  -v "$(pwd)/datas:/opt/cronpilot/datas" \
  -v "$(pwd)/conf.ini:/opt/cronpilot/conf.ini" \
  "$IMAGE"
sleep 10
curl -s -o /dev/null -w "docs:%{http_code}\n" http://127.0.0.1:5860/docs/
curl -s -o /dev/null -w "home:%{http_code}\n" http://127.0.0.1:5860/
echo "--- container logs (last 50) ---"
docker logs "$CONTAINER" 2>&1 | tail -50
docker stop "$CONTAINER" && docker rm "$CONTAINER"
echo "CLEANUP: OK"
