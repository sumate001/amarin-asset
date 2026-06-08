#!/bin/bash
# ====================================================
#  Amarin Employee Database — Start Server
# ====================================================

cd "$(dirname "$0")"

# ---- ตรวจสอบ Python ----
if ! command -v python3 &>/dev/null; then
  echo "❌  ไม่พบ python3 กรุณาติดตั้งก่อน"
  exit 1
fi

# ---- ตรวจสอบ / ติดตั้ง dependencies ----
echo "🔍  ตรวจสอบ dependencies..."
python3 -c "import flask, bs4, openpyxl" 2>/dev/null || {
  echo "📦  ติดตั้ง dependencies..."
  pip3 install flask beautifulsoup4 openpyxl requests -q
}

# ---- เลือก port (default 5100, หรือกำหนดเองผ่าน PORT=xxxx) ----
PORT="${PORT:-5100}"

echo ""
echo "✅  เริ่มต้น server..."
echo "🌐  เปิดเบราว์เซอร์ที่:  http://localhost:${PORT}"
echo "🛑  หยุด server: กด  Ctrl + C"
echo ""

# เปิดเบราว์เซอร์หลังจาก 1 วินาที (macOS)
sleep 1 && open "http://localhost:${PORT}" &

# รัน Flask (--debug = auto-reload เมื่อแก้ไข .py)
FLASK_ENV=development python3 -m flask --app app run --host=0.0.0.0 --port="${PORT}" --debug
