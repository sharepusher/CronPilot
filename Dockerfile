# CronPilot 运行镜像（Ubuntu 22.04 + Python 3.10 + SQLite 试用）
# 构建: docker build -t cronpilot:latest .
# 运行: docker compose up --build -d
FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive
WORKDIR /opt/cronpilot

RUN apt-get update -qq \
  && apt-get install -y -qq curl ca-certificates sudo software-properties-common \
  && rm -rf /var/lib/apt/lists/*

COPY . .

RUN useradd -m -s /bin/bash cronpilot \
  && chown -R cronpilot:cronpilot /opt/cronpilot \
  && add-apt-repository -y ppa:deadsnakes/ppa \
  && apt-get update -qq \
  && apt-get install -y -qq \
    python3.10 python3.10-venv python3.10-dev \
    build-essential libffi-dev libev-dev git \
  && echo 'root ALL=(ALL) NOPASSWD: ALL' > /etc/sudoers.d/docker-root \
  && chmod 440 /etc/sudoers.d/docker-root \
  && rm -rf /var/lib/apt/lists/*

ENV PY=python3.10
RUN SUDO_USER=cronpilot bash scripts/install_ubuntu.sh --production --sqlite

USER cronpilot

# 构建期健康检查（与 scripts/docker/Dockerfile.ubuntu 一致）
RUN bash -euc 'source scripts/lib/python.sh && cronpilot_load_runtime; \
    export FLASK_CONFIG=production; mkdir -p datas/logs datas/prometheus_tmp; chmod 700 datas/prometheus_tmp; \
    export SECRET_KEY="${SECRET_KEY:-$(python3 -c "import secrets; print(secrets.token_hex(32))")}"; \
    "$CRONPILOT_VENV/bin/gunicorn" -b 0.0.0.0:5860 -w 1 -k gevent -c gun.py manage:app & pid=$!; \
    sleep 8; \
    curl -sf http://127.0.0.1:5860/docs/ | head -c 200 | grep -qi html; \
    code=$(curl -sf -o /dev/null -w "%{http_code}" http://127.0.0.1:5860/); \
    echo "HTTP / => $code"; echo "$code" | grep -qE "200|302"; \
    kill $pid; wait $pid 2>/dev/null || true'

EXPOSE 5860
CMD ["bash", "scripts/run_production.sh"]
