#!/bin/bash
# ====================================================
#  Amarin Employee Database — Production Server
#  ใช้ Gunicorn (multi-process, stable)
# ====================================================

cd "$(dirname "$0")"

# ---- ตรวจสอบ Python ----
if ! command -v python3 &>/dev/null; then
  echo "❌  ไม่พบ python3"
  exit 1
fi

# ---- ติดตั้ง dependencies (ถ้ายังไม่มี) ----
echo "🔍  ตรวจสอบ dependencies..."
python3 -c "import flask, bs4, openpyxl, gunicorn" 2>/dev/null || {
  echo "📦  ติดตั้ง dependencies..."
  pip3 install flask beautifulsoup4 openpyxl requests gunicorn -q
}

# ---- Config ----
PORT="${PORT:-5100}"
WORKERS="${WORKERS:-2}"        # จำนวน worker process (แนะนำ: CPU*2+1)
TIMEOUT="${TIMEOUT:-120}"      # วินาที (สำหรับ request ที่ใช้เวลานาน เช่น sync)
LOG_LEVEL="${LOG_LEVEL:-info}"

echo ""
echo "🚀  Production server เริ่มต้นแล้ว"
echo "🌐  URL:      http://0.0.0.0:${PORT}"
echo "👷  Workers:  ${WORKERS}"
echo "🛑  หยุด:     Ctrl+C"
echo ""

# ---- รัน Gunicorn ----
exec gunicorn app:app \
  --bind "0.0.0.0:${PORT}" \
  --workers "${WORKERS}" \
  --timeout "${TIMEOUT}" \
  --log-level "${LOG_LEVEL}" \
  --access-logfile "-" \
  --error-logfile "-" \
  --preload
