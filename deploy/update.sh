#!/bin/bash
# ====================================================
#  Amarin Employee Database — Update Script
#  ใช้ตอนอัพเดทโค้ดหลังจาก install ครั้งแรกแล้ว
# ====================================================

set -e

APP_DIR="/opt/amarin-employee"
SERVICE="amarin-employee"

echo "=============================="
echo " Amarin Employee DB — Update"
echo "=============================="

SCRIPT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
echo "copy จาก: $SCRIPT_DIR → $APP_DIR"

# copy เฉพาะโค้ด ไม่แตะ database และ json
rsync -a --exclude='.git' --exclude='__pycache__' --exclude='*.pyc' \
      --exclude='deploy' --exclude='.env' \
      --exclude='employees.db' --exclude='edevice_assets.json' \
      "$SCRIPT_DIR/" "$APP_DIR/"

# อัพเดท dependencies (ถ้ามีเพิ่ม)
"$APP_DIR/venv/bin/pip" install -q -r "$APP_DIR/requirements.txt"

# fix สิทธิ์
chown -R www-data:www-data "$APP_DIR/static" "$APP_DIR/templates" "$APP_DIR/app.py"

# restart service
systemctl restart "$SERVICE"
sleep 2
systemctl is-active --quiet "$SERVICE" \
  && echo "✅  อัพเดทเสร็จ — service รันอยู่" \
  || echo "❌  Service มีปัญหา — ดู: journalctl -u $SERVICE -n 50"
