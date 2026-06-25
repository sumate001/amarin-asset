#!/bin/bash
# ====================================================
#  Amarin Employee Database — Deploy (คำสั่งเดียว)
# ----------------------------------------------------
#  สำหรับเครื่อง server ที่รัน Gunicorn ตรง (ไม่ผ่าน systemd)
#
#  ใช้งาน:
#    ./deploy.sh           deploy โค้ดใน working tree ปัจจุบัน
#    ./deploy.sh --pull    git pull origin main ก่อน แล้วค่อย deploy
#
#  ปรับค่าได้ผ่าน env:  PORT (5100) · WORKERS (2) · TIMEOUT (300)
# ====================================================
set -euo pipefail

cd "$(dirname "$0")"

PORT="${PORT:-5100}"
WORKERS="${WORKERS:-2}"
TIMEOUT="${TIMEOUT:-300}"
PIDFILE="gunicorn.pid"

# ---- 0. git pull (เฉพาะเมื่อใส่ --pull) ----
if [[ "${1:-}" == "--pull" ]]; then
  echo "📥  git pull origin main..."
  git pull --ff-only origin main
fi

# ---- 1. dependencies ----
echo "📦  ตรวจสอบ/ติดตั้ง dependencies..."
pip3 install --user --break-system-packages -q -r requirements.txt

# ---- 2. หา gunicorn ----
if command -v gunicorn &>/dev/null; then
  GUNICORN="gunicorn"
else
  GUNICORN="python3 -m gunicorn"   # fallback กรณี ~/.local/bin ไม่อยู่ใน PATH
fi

# ---- 3. หยุด server เดิม ----
echo "🛑  หยุด Gunicorn เดิม (ถ้ามี)..."
if [[ -f "$PIDFILE" ]]; then
  kill "$(cat "$PIDFILE")" 2>/dev/null || true
  sleep 2
fi
pkill -f "[g]unicorn app:app" 2>/dev/null || true   # [g] = เลี่ยง pkill จับ process ตัวเอง
sleep 1

# ---- 4. start server ใหม่ (daemon) ----
echo "🚀  start Gunicorn (workers=$WORKERS, timeout=${TIMEOUT}s, port=$PORT)..."
$GUNICORN app:app \
  --bind "0.0.0.0:${PORT}" \
  --workers "${WORKERS}" \
  --timeout "${TIMEOUT}" \
  --pid "$PIDFILE" \
  --access-logfile gunicorn-access.log \
  --error-logfile  gunicorn-error.log \
  --log-level info \
  --daemon \
  --preload

# ---- 5. health check ----
echo "🔍  health check..."
for i in $(seq 1 10); do
  if curl -fsS -o /dev/null "http://localhost:${PORT}/" 2>/dev/null; then
    echo "✅  deploy สำเร็จ — http://localhost:${PORT}  (PID $(cat "$PIDFILE"))"
    exit 0
  fi
  sleep 1
done

echo "❌  server ไม่ตอบหลัง deploy — 20 บรรทัดท้ายของ error log:"
tail -20 gunicorn-error.log
exit 1
