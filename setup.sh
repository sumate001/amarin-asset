#!/bin/bash
# ============================================================
#  Amarin Employee Database — One-line Installer
#
#  ติดตั้งครั้งแรก (ไม่มี database):
#    curl -sSL https://raw.githubusercontent.com/sumate001/amarin-asset/main/setup.sh | sudo bash
#
#  ติดตั้งพร้อม database ที่มีอยู่แล้ว:
#    curl -sSL https://raw.githubusercontent.com/sumate001/amarin-asset/main/setup.sh | sudo bash -s -- --db /path/to/employees.db
#
#  อัพเดทโค้ด (ไม่แตะ database):
#    curl -sSL https://raw.githubusercontent.com/sumate001/amarin-asset/main/setup.sh | sudo bash -s -- --update
# ============================================================

set -e

# ── Config ──────────────────────────────────────────────────
REPO="https://github.com/sumate001/amarin-asset.git"
APP_DIR="/opt/amarin-employee"
LOG_DIR="/var/log/amarin-employee"
SERVICE="amarin-employee"
NGINX_CONF="amarin-employee"

# ── Parse args ──────────────────────────────────────────────
MODE="install"
DB_SRC=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --update) MODE="update"; shift ;;
    --db)     DB_SRC="$2"; shift 2 ;;
    *)        shift ;;
  esac
done

# ── Root check ──────────────────────────────────────────────
if [ "$EUID" -ne 0 ]; then
  echo "❌  กรุณารันด้วย sudo"
  exit 1
fi

# ── Banner ──────────────────────────────────────────────────
echo ""
echo "╔══════════════════════════════════════════╗"
if [ "$MODE" = "update" ]; then
  echo "║   Amarin Employee DB  —  อัพเดทโค้ด     ║"
else
  echo "║   Amarin Employee DB  —  ติดตั้งใหม่    ║"
fi
echo "╚══════════════════════════════════════════╝"
echo ""

# ════════════════════════════════════════════
#   MODE: UPDATE
# ════════════════════════════════════════════
if [ "$MODE" = "update" ]; then
  echo "▶ ดึงโค้ดล่าสุดจาก GitHub..."
  git config --global --add safe.directory "$APP_DIR" 2>/dev/null || true
  if [ -d "$APP_DIR/.git" ]; then
    git -C "$APP_DIR" pull --ff-only
  else
    echo "❌  ไม่พบ repo ที่ $APP_DIR — รัน install ก่อน"
    exit 1
  fi

  echo "▶ อัพเดท dependencies..."
  "$APP_DIR/venv/bin/pip" install -q -r "$APP_DIR/requirements.txt"

  echo "▶ Restart service..."
  systemctl restart "$SERVICE"
  sleep 2

  if systemctl is-active --quiet "$SERVICE"; then
    SERVER_IP=$(hostname -I | awk '{print $1}')
    echo ""
    echo "╔══════════════════════════════════════════╗"
    echo "║         ✅  อัพเดทเสร็จแล้ว!             ║"
    printf "║  🌐  http://%-29s║\n" "${SERVER_IP}"
    echo "╚══════════════════════════════════════════╝"
  else
    echo "❌  Service มีปัญหา:"
    journalctl -u "$SERVICE" -n 20 --no-pager
    exit 1
  fi
  exit 0
fi

# ════════════════════════════════════════════
#   MODE: INSTALL
# ════════════════════════════════════════════

# ── Step 1: System packages ──────────────────
echo "[1/5] ติดตั้ง packages..."
apt-get update -qq
apt-get install -y -qq git python3 python3-pip python3-venv nginx curl

# ── Step 2: Clone / pull repo ────────────────
echo "[2/5] ดึงโค้ดจาก GitHub..."
git config --global --add safe.directory "$APP_DIR" 2>/dev/null || true
if [ -d "$APP_DIR/.git" ]; then
  echo "      พบ repo เดิม — git pull..."
  git -C "$APP_DIR" pull --ff-only
else
  git clone "$REPO" "$APP_DIR"
fi
mkdir -p "$LOG_DIR"

# ── Step 3: Python venv + deps ───────────────
echo "[3/5] สร้าง Python virtual environment..."
python3 -m venv "$APP_DIR/venv"
"$APP_DIR/venv/bin/pip" install -q --upgrade pip
"$APP_DIR/venv/bin/pip" install -q -r "$APP_DIR/requirements.txt"

# ── Step 4: Database ──────────────────────────
echo "[4/5] เตรียม database..."

if [ -n "$DB_SRC" ]; then
  # ระบุ path ชัดเจนด้วย --db
  if [ -f "$DB_SRC" ]; then
    cp "$DB_SRC" "$APP_DIR/employees.db"
    echo "      ✅ copy database จาก $DB_SRC"
  else
    echo "      ❌ ไม่พบไฟล์ $DB_SRC"
    exit 1
  fi
elif [ -f "$(pwd)/employees.db" ] && [ "$(pwd)/employees.db" != "$APP_DIR/employees.db" ]; then
  # auto-detect: มี employees.db ใน directory ปัจจุบัน
  cp "$(pwd)/employees.db" "$APP_DIR/employees.db"
  echo "      ✅ พบ employees.db ใน $(pwd) — copy อัตโนมัติ"
elif [ ! -s "$APP_DIR/employees.db" ]; then
  # ไม่มี db เลย — สร้าง empty (app จะ init schema เอง)
  touch "$APP_DIR/employees.db"
  echo "      ⚠  ไม่พบ database — สร้างใหม่ (ข้อมูลว่าง)"
else
  echo "      ✅ ใช้ database เดิมที่ $APP_DIR/employees.db"
fi

# permissions
touch "$APP_DIR/edevice_assets.json" 2>/dev/null || true
chown -R www-data:www-data "$APP_DIR" "$LOG_DIR"
chmod -R 755 "$APP_DIR"
chmod 664 "$APP_DIR/employees.db" "$APP_DIR/edevice_assets.json"

# ── Step 5: systemd + Nginx ───────────────────
echo "[5/5] ตั้งค่า systemd + Nginx..."

cp "$APP_DIR/deploy/amarin-employee.service" /etc/systemd/system/
systemctl daemon-reload
systemctl enable "$SERVICE" --quiet
systemctl restart "$SERVICE"
sleep 2

if systemctl is-active --quiet "$SERVICE"; then
  echo "      ✅ Service รันอยู่"
else
  echo "      ❌ Service มีปัญหา:"
  journalctl -u "$SERVICE" -n 15 --no-pager
  exit 1
fi

cp "$APP_DIR/deploy/nginx-amarin-employee.conf" "/etc/nginx/sites-available/$NGINX_CONF"
ln -sf "/etc/nginx/sites-available/$NGINX_CONF" "/etc/nginx/sites-enabled/$NGINX_CONF"
rm -f /etc/nginx/sites-enabled/default 2>/dev/null || true
nginx -t -q && systemctl restart nginx

# ── Done ─────────────────────────────────────
SERVER_IP=$(hostname -I | awk '{print $1}')
echo ""
echo "╔══════════════════════════════════════════╗"
echo "║           ✅  ติดตั้งเสร็จแล้ว!          ║"
echo "╠══════════════════════════════════════════╣"
printf "║  🌐  http://%-29s║\n" "${SERVER_IP}"
echo "║                                          ║"
echo "║  ดู log:                                 ║"
echo "║    journalctl -u amarin-employee -f      ║"
echo "╚══════════════════════════════════════════╝"
echo ""
