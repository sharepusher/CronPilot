#!/bin/bash
# 兼容入口 → start_local_full.sh
exec bash "$(dirname "$0")/start_local_full.sh" "$@"
