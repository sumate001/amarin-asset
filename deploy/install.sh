#!/bin/bash
# ====================================================
#  Amarin Employee Database — Linux Install Script
#  รัน script นี้บน Ubuntu Server ด้วย sudo
#  ใช้ครั้งเดียวตอน deploy ครั้งแรก
# ====================================================

set -e   # หยุดทันทีถ้ามี error

APP_DIR="/opt/amarin-employee"
LOG_DIR="/var/log/amarin-employee"
SERVICE="amarin-employee"

echo "=============================="
echo " Amarin Employee DB — Install"
echo "=============================="

# ---- 1. System packages ----
echo "[1/6] ติดตั้ง system packages..."
apt-get update -q
apt-get install -y -q python3 python3-pip python3-venv nginx

# ---- 2. สร้าง app directory ----
echo "[2/6] เตรียม app directory: $APP_DIR"
mkdir -p "$APP_DIR"
mkdir -p "$LOG_DIR"

# copy ไฟล์จาก directory ปัจจุบัน (รัน script จาก project folder)
SCRIPT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
echo "     copy จาก: $SCRIPT_DIR"
rsync -a --exclude='.git' --exclude='__pycache__' --exclude='*.pyc' \
      --exclude='deploy' --exclude='.env' \
      "$SCRIPT_DIR/" "$APP_DIR/"

# ---- 3. Python venv + dependencies ----
echo "[3/6] สร้าง Python virtual environment..."
python3 -m venv "$APP_DIR/venv"
"$APP_DIR/venv/bin/pip" install -q --upgrade pip
"$APP_DIR/venv/bin/pip" install -q -r "$APP_DIR/requirements.txt"

# ---- 4. สิทธิ์ file ----
echo "[4/6] กำหนดสิทธิ์..."
chown -R www-data:www-data "$APP_DIR"
chown -R www-data:www-data "$LOG_DIR"
chmod -R 755 "$APP_DIR"
chmod 664 "$APP_DIR/employees.db" 2>/dev/null || true
chmod 664 "$APP_DIR/edevice_assets.json" 2>/dev/null || true

# ---- 5. systemd service ----
echo "[5/6] ติดตั้ง systemd service..."
cp "$SCRIPT_DIR/deploy/amarin-employee.service" /etc/systemd/system/
systemctl daemon-reload
systemctl enable "$SERVICE"
systemctl restart "$SERVICE"
sleep 2
systemctl is-active --quiet "$SERVICE" && echo "     ✅ Service รันอยู่" || echo "     ❌ Service มีปัญหา — ดู: journalctl -u $SERVICE"

# ---- 6. Nginx ----
echo "[6/6] ตั้งค่า Nginx..."
cp "$SCRIPT_DIR/deploy/nginx-amarin-employee.conf" /etc/nginx/sites-available/amarin-employee
ln -sf /etc/nginx/sites-available/amarin-employee /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default    # เอา default ออก
nginx -t && systemctl restart nginx

echo ""
echo "=============================="
echo " ✅  Install เสร็จแล้ว!"
SERVER_IP=$(hostname -I | awk '{print $1}')
echo " 🌐  เปิดได้ที่:  http://${SERVER_IP}"
echo "=============================="
