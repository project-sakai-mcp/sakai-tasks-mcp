#!/usr/bin/env bash
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# 自分自身のフォルダから隔離属性 (Quarantine) をサイレントに全解除
xattr -cr "$SCRIPT_DIR" 2>/dev/null || true

export PYTHONPATH="$SCRIPT_DIR:${PYTHONPATH:-}"
exec "$SCRIPT_DIR/python/bin/python3" "$SCRIPT_DIR/src/server.py" "$@"

