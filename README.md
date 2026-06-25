# Amarin Employee & IT Asset Database

ระบบบริหารข้อมูลพนักงานและทรัพย์สิน IT สำหรับกลุ่มบริษัทอมรินทร์

> **Version 1.4.1** · Python Flask + SQLite + Vanilla JS

---

## Features

### 👥 รายชื่อพนักงาน
- CRUD พนักงาน พร้อม BU / แผนก / ตำแหน่ง / email / โทรศัพท์
- ค้นหาและกรองตาม BU, แผนก, สถานะ, หรือผู้มีทรัพย์สิน IT
- Import / Export Excel
- **Sync จาก Amarin Intranet** — เปรียบเทียบ diff ก่อน apply (preview → confirm)

### 💻 IT Assets
- แสดงเครื่องทั้งหมดจาก **eDevice** + สัญญาเช่าจาก **Google Sheets**
- Summary cards 7 ใบ: เครื่องทั้งหมด · ค่าเช่า/เดือน · 🔴 หมดสัญญาเช่า · ⚠️ eDevice Expire · 🟠 หมดใน 90 วัน · 🟡 หมดใน 180 วัน · 🟢 อยู่ในระยะสัญญา
- กรองตามประเภท, สัญญา (เช่า/ซื้อ), BU, สถานะ, eDevice status, Return, ยังไม่บันทึกใน eDevice
- **Sync eDevice** — background fetch ใน subprocess แยก (ใช้เวลา ~3-5 นาที) พร้อม progress bar แสดง live — ไม่ถูก Gunicorn worker timeout kill
- Export Excel
- โอนทรัพย์สินระหว่างพนักงาน / คืน Stock เมื่อพนักงานออก
- ตรวจจับเครื่อง **"ส่วนกลาง"** จาก eDevice — แสดง badge สีฟ้าแทนชื่อพนักงาน

### 📊 Dashboard (3 แท็บ)

| แท็บ | รายละเอียด |
|---|---|
| **พนักงาน** | สถิติพนักงาน แยก BU + Top 10 แผนก |
| **บริหารสัญญาเช่า** | Summary cards 7 ใบ, Timeline สัญญาหมดรายเดือน, สัญญาวิกฤต |
| **บริหารเครื่อง** | ความผิดปกติ: ไม่ระบุ BU, ไม่บันทึกใน eDevice, ยังไม่ระบุประเภทสัญญา |

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.10+ · Flask |
| Database | SQLite (`employees.db`) |
| Frontend | Vanilla JS · HTML5 · CSS3 (ไม่มี framework) |
| Production | Gunicorn + Nginx + systemd (Linux) |
| Data Sources | eDevice (Intranet), Google Sheets CSV, Amarin Intranet |

---

## Project Structure

```
amarin-asset/
├── app.py                      # Flask app — routes + business logic ทั้งหมด (~1960 บรรทัด)
├── employees.db                # SQLite database (ไม่อยู่ใน git — .gitignore)
├── edevice_assets.json         # Cache ข้อมูล eDevice (สร้างอัตโนมัติ — ไม่อยู่ใน git)
├── edevice_fetch_status.json   # สถานะ background fetch (สร้างอัตโนมัติ)
├── employees_extracted.json    # Seed data พนักงานเริ่มต้น (ใช้ตอน init_db เท่านั้น)
├── requirements.txt
├── setup.sh                    # One-line installer + updater (Linux)
├── start.sh                    # Dev server
├── start-prod.sh               # Production server (Gunicorn)
├── deploy.sh                   # Deploy คำสั่งเดียว (restart Gunicorn + deps + health check)
├── install.py                  # Universal installer (macOS/Linux/Windows)
├── templates/
│   └── index.html              # Single-page HTML
├── static/
│   ├── css/style.css
│   └── js/app.js               # Frontend JS ทั้งหมด (~2000 บรรทัด)
└── deploy/
    ├── amarin-employee.service # systemd unit file
    └── nginx-amarin-employee.conf
```

---

## Quick Start

### ⚡ One-line Install (Linux)

```bash
# ติดตั้งครั้งแรก (สร้าง DB ใหม่ seed จาก employees_extracted.json)
curl -sSL https://raw.githubusercontent.com/sumate001/amarin-asset/main/setup.sh | sudo bash

# ติดตั้งพร้อม database ที่มีอยู่
curl -sSL https://raw.githubusercontent.com/sumate001/amarin-asset/main/setup.sh | sudo bash -s -- --db /path/to/employees.db

# อัพเดทโค้ดโดยไม่แตะ database
curl -sSL https://raw.githubusercontent.com/sumate001/amarin-asset/main/setup.sh | sudo bash -s -- --update
```

Script ทำทุกอย่างอัตโนมัติ: clone → venv → pip install → init DB → systemd → nginx → print URL

### 🖥 Local Development

```bash
git clone https://github.com/sumate001/amarin-asset.git
cd amarin-asset
pip install -r requirements.txt
python app.py
# เปิด http://localhost:5050
```

> ถ้าไม่มี `employees.db` จะสร้างและ seed จาก `employees_extracted.json` อัตโนมัติ

---

## Deployment (Production)

### 🚀 Deploy คำสั่งเดียว

รัน `deploy.sh` บนเครื่อง server (รัน Gunicorn ตรง ไม่ผ่าน systemd):

```bash
./deploy.sh           # deploy โค้ดใน working tree ปัจจุบัน (restart Gunicorn + ติดตั้ง deps + health check)
./deploy.sh --pull    # git pull origin main ก่อน แล้วค่อย deploy
```

ปรับค่าได้ผ่าน env: `PORT` (5100) · `WORKERS` (2) · `TIMEOUT` (300)
สำหรับ setup ที่ใช้ **systemd** ให้ใช้ `sudo bash setup.sh --update` แทน (ดูด้านล่าง)

### Services ที่ติดตั้ง

| Service | รายละเอียด |
|---|---|
| **Gunicorn** | 3 workers · timeout 300s · bind `127.0.0.1:5100` |
| **Nginx** | reverse proxy port 80 → 5100 · gzip · static files cache 7d |
| **systemd** | `amarin-employee.service` · auto-restart |

### Commands

```bash
# ดูสถานะ
systemctl status amarin-employee

# ดู logs realtime
journalctl -u amarin-employee -f

# Restart
sudo systemctl restart amarin-employee

# อัพเดทโค้ด
sudo bash /path/to/setup.sh --update
```

### Backup Database

```bash
# สำรอง
cp /opt/amarin-employee/employees.db employees_backup_$(date +%Y%m%d).db

# Restore
sudo cp employees_backup_20260622.db /opt/amarin-employee/employees.db
sudo systemctl restart amarin-employee
```

---

## Configuration

ค่า config อยู่ต้นไฟล์ `app.py`:

```python
DB        = 'employees.db'    # path ของ SQLite
CACHE_TTL = 1800              # cache assets (วินาที, default 30 นาที)

# Google Sheets (สัญญาเช่า)
SHEETS_ID  = '1AVJbcZq-...'  # Spreadsheet ID
SHEETS_URL = f'https://docs.google.com/spreadsheets/d/{SHEETS_ID}/export?format=csv'

# eDevice Intranet
EDEVICE_LOGIN_URL = 'http://amarin.intra/webappl/acorporate/index.aspx?s=out'
EDEVICE_LIST_URL  = 'http://www.amarin.intra/webappl/eDevice_ATV/Computer1.asp'
```

> **ข้อจำกัด:** Sync eDevice และ Sync Intranet ต้องรันบนเครื่องที่เชื่อมต่อ **Intranet อมรินทร์** เท่านั้น

---

## Database Schema

### `employees`

| คอลัมน์ | ชนิด | คำอธิบาย |
|---|---|---|
| id | INTEGER PK | รหัสในระบบ |
| emp_code | TEXT | รหัสพนักงาน (จาก eDevice) |
| name | TEXT NOT NULL | ชื่อ-นามสกุล |
| nickname | TEXT | ชื่อเล่น |
| bu / bu_code | TEXT | Business Unit |
| department | TEXT | แผนก |
| position | TEXT | ตำแหน่ง |
| email / phone | TEXT | ช่องทางติดต่อ |
| start_date | TEXT | วันเริ่มงาน (YYYY-MM-DD) |
| status | TEXT | `active` / `inactive` |

### `asset_assignments`
เก็บว่า asset_no ไหนกับพนักงาน id ไหน — **override** ข้อมูลจาก eDevice

### `asset_notes`
สถานะดำเนินการของ asset: `pending` / `returned` / `renewed` / `bought`

### `asset_transfer_log`
ประวัติการโอน asset ระหว่างพนักงาน (from_id, to_id, transfer_type)

---

## API Reference

### Employees

| Method | Endpoint | คำอธิบาย |
|---|---|---|
| GET | `/api/employees` | รายชื่อ (pagination + filter: q, bu, dept, status) |
| GET | `/api/employees/<id>` | พนักงานรายคน |
| POST | `/api/employees` | เพิ่มพนักงาน |
| PUT | `/api/employees/<id>` | แก้ไขพนักงาน |
| DELETE | `/api/employees/<id>` | ลบพนักงาน |
| GET | `/api/employees/<id>/assets` | ทรัพย์สิน IT ของพนักงาน |
| GET | `/api/filters` | BU list + department list |
| GET | `/api/stats` | สถิติ (total, by_bu, by_dept) |
| GET | `/api/export/excel` | Export Excel |
| POST | `/api/import/excel` | Import Excel |

### IT Assets

| Method | Endpoint | คำอธิบาย |
|---|---|---|
| GET | `/api/assets` | รายการ asset (cache 30 นาที) |
| GET | `/api/assets/meta` | ประเภทและ BU list สำหรับ filter |
| GET | `/api/assets/employee-map` | map employee_id → count |
| GET | `/api/assets/export` | Export Excel |
| PUT | `/api/assets/<asset_no>/resolution` | อัพเดทสถานะดำเนินการ |
| POST | `/api/assets/transfer-bulk` | โอน asset หลายรายการ |

**Query params `/api/assets`:**

| Param | ค่า | คำอธิบาย |
|---|---|---|
| `q` | text | ค้นหา S/N, รหัสเครื่อง, ชื่อพนักงาน |
| `status` | `expired/critical/warning/ok/unknown` | สถานะสัญญา |
| `ownership` | `เช่า` / `ซื้อ` | ประเภทสัญญา |
| `type` | text | ประเภทเครื่อง |
| `bu` | bu_code | Business Unit |

### Sync

| Method | Endpoint | คำอธิบาย |
|---|---|---|
| GET | `/api/sync/preview` | Preview diff จาก Intranet (พนักงาน) |
| POST | `/api/sync/apply` | Apply sync พนักงาน |
| POST | `/api/sync/edevice/fetch-start` | เริ่ม background fetch จาก eDevice |
| GET | `/api/sync/edevice/fetch-status` | สถานะ background fetch (running/done/count/total) |
| GET | `/api/sync/edevice/preview` | Preview match eDevice ↔ พนักงาน (ใช้ cache) |
| POST | `/api/sync/edevice/apply` | Apply sync eDevice → asset_assignments |

### Dashboard

| Method | Endpoint | คำอธิบาย |
|---|---|---|
| GET | `/api/dashboard/rental` | ข้อมูลแท็บบริหารสัญญา + timeline รายเดือน |

---

## Contract Status

| สถานะ | เงื่อนไข |
|---|---|
| 🔴 หมดสัญญาเช่า | end_date < วันนี้ และ eDevice ≠ Expire |
| ⚠️ eDevice Expire | eDevice status = Expire (ทุกเครื่อง ทั้งซื้อและเช่า) |
| 🟠 `critical` | เหลือ ≤ 90 วัน |
| 🟡 `warning` | เหลือ ≤ 180 วัน |
| 🟢 `ok` | เหลือ > 180 วัน |
| ⚪ `unknown` | ไม่มี end_date (eDevice-only) |
| 🗑 ตัดจำหน่าย | เครื่องซื้อ + eDevice = Expire |
| 🏢 ส่วนกลาง | eDevice ระบุ "ทรัพย์สินของ: ส่วนกลาง" |

---

## BU Codes

| Code | บริษัท |
|---|---|
| APUB | Amarin Publishing |
| APRINT | Amarin Printing & Packaging |
| ACS | Amarin Corporate Support |
| ABOOK | Amarin Book Center |
| AMTV | Amarin Television |
| AOMNI | Amarin Omniverse |
| AME | Amarin Media & Event / AME Imaginative |

---

## Notes

- `edevice_assets.json` — cache ข้อมูลเครื่องจาก eDevice สร้างอัตโนมัติ ไม่ต้อง commit
- `edevice_fetch_status.json` — state ของ background fetch สร้างอัตโนมัติ ไม่ต้อง commit
- `employees.db` — ห้าม commit เด็ดขาด (อยู่ใน `.gitignore`)
- Cache assets หมดอายุทุก 30 นาที หรือหลัง sync eDevice apply ทันที
- `app.js` ใช้ cache-bust ด้วย md5 hash ใน URL (`?v=xxxxxxxx`) — browser จะโหลดใหม่ทุกครั้งที่ไฟล์เปลี่ยน
