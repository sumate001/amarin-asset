#!/bin/bash
# ====================================================
#  Amarin Employee Database — Deploy (คำสั่งเดียว)
# ----------------------------------------------------
#  รันผ่าน systemd user service: amarin-asset
#  (~/.config/systemd/user/amarin-asset.service — auto-start ตอน boot,
#   auto-restart ถ้า process ตาย)
#
#  ใช้งาน:
#    ./deploy.sh           deploy โค้ดใน working tree ปัจจุบัน
#    ./deploy.sh --pull    git pull origin main ก่อน แล้วค่อย deploy
#
#  ปรับ PORT/WORKERS/TIMEOUT: แก้ใน service file แล้ว
#  systemctl --user daemon-reload
# ====================================================
set -euo pipefail

cd "$(dirname "$0")"

PORT="${PORT:-5100}"
SERVICE="amarin-asset"

# ---- 0. git pull (เฉพาะเมื่อใส่ --pull) ----
if [[ "${1:-}" == "--pull" ]]; then
  echo "📥  git pull origin main..."
  git pull --ff-only origin main
fi

# ---- 1. dependencies ----
echo "📦  ตรวจสอบ/ติดตั้ง dependencies..."
pip3 install --user --break-system-packages -q -r requirements.txt

# ---- 2. เก็บกวาด gunicorn เก่าที่รันนอก systemd (ถ้ามี) ----
if [[ -f gunicorn.pid ]]; then
  kill "$(cat gunicorn.pid)" 2>/dev/null || true
  rm -f gunicorn.pid
fi

# ---- 3. restart service ----
echo "🔄  restart systemd service ($SERVICE)..."
systemctl --user restart "$SERVICE"

# ---- 4. health check ----
echo "🔍  health check..."
for i in $(seq 1 10); do
  if curl -fsS -o /dev/null "http://localhost:${PORT}/" 2>/dev/null; then
    echo "✅  deploy สำเร็จ — http://localhost:${PORT}"
    systemctl --user status "$SERVICE" --no-pager | head -5
    # ---- 5. MCP server (AI) เรียก API นี้อยู่ — แค่ตรวจว่ายังตอบ ไม่ fail deploy ----
    if systemctl --user is-enabled mcp-amarin-asset >/dev/null 2>&1; then
      if curl -fsS -o /dev/null "http://127.0.0.1:${MCP_PORT:-5201}/health" 2>/dev/null; then
        echo "🤖  MCP (mcp-amarin-asset) ตอบปกติ"
      else
        echo "⚠️   MCP (mcp-amarin-asset) ไม่ตอบ — รัน ~/mcp-servers/deploy.sh amarin-asset"
      fi
      echo "    ถ้าแก้/เพิ่ม API ที่ AI ใช้ อย่าลืมอัปเดต ~/mcp-servers/amarin-asset/server.py"
    fi
    exit 0
  fi
  sleep 1
done

echo "❌  server ไม่ตอบหลัง deploy — สถานะ service และ 20 บรรทัดท้ายของ error log:"
systemctl --user status "$SERVICE" --no-pager | head -15 || true
tail -20 gunicorn-error.log
exit 1
