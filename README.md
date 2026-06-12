# Amarin Employee Database

ระบบบริหารข้อมูลพนักงานและทรัพย์สิน IT สำหรับกลุ่มบริษัทอมรินทร์

> **Version 1.3.2** · Python Flask + SQLite + Vanilla JS

---

## Features

### 👥 รายชื่อพนักงาน
- CRUD พนักงาน พร้อม BU / แผนก / ตำแหน่ง / email / โทรศัพท์
- ค้นหาและกรองตาม BU, แผนก, สถานะ, หรือผู้มีทรัพย์สิน IT
- Import / Export Excel
- Sync ข้อมูลจาก Amarin Intranet (เปรียบเทียบ diff ก่อน apply)

### 💻 IT Assets
- แสดงเครื่องทั้งหมดจาก **eDevice** + สัญญาเช่าจาก **Google Sheets**
- Summary cards 7 ใบ: เครื่องทั้งหมด · ค่าเช่า/เดือน · 🔴 หมดสัญญาเช่า · ⚠️ eDevice Expire · 🟠 หมดใน 90 วัน · 🟡 หมดใน 180 วัน · 🟢 อยู่ในระยะสัญญา
- **แยก "หมดสัญญาเช่า" ออกจาก "eDevice Expire"** — eDevice Expire นับทุกเครื่อง (ซื้อ+เช่า) ที่ eDevice ระบุ Expire
- กรองตามประเภท, ประเภทสัญญา (เช่า/ซื้อ), BU, สถานะสัญญา, eDevice status, เครื่อง Return, เครื่องที่ยังไม่บันทึกใน eDevice
- Sync eDevice: ดึงรายละเอียดเครื่องและ match รหัสพนักงาน
- Export Excel
- โอนทรัพย์สินระหว่างพนักงาน / คืน Stock เมื่อพนักงานออก
- Popup ทรัพย์สิน IT: แสดงรายละเอียดครบในรูปแบบ card พร้อมสีกรอบตามสถานะ
- ตรวจจับเครื่อง **"ส่วนกลาง"** จาก eDevice — แสดง badge สีฟ้าแทนชื่อพนักงาน

### 📊 Dashboard
แบ่งเป็น 3 แท็บ:

| แท็บ | รายละเอียด |
|---|---|
| **พนักงาน** | สถิติพนักงาน แยก BU + Top 10 แผนก |
| **บริหารสัญญาเช่า** | Summary cards 7 ใบ (รวม eDevice Expire), Timeline สัญญาหมดรายเดือน (คลิก expand ดูรายละเอียดครบ), สัญญาวิกฤต/เกินกำหนด |
| **บริหารเครื่อง** | ความผิดปกติ: ไม่ระบุ BU, ไม่บันทึกใน eDevice, ยังไม่ระบุประเภทสัญญา |

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.10+ · Flask |
| Database | SQLite (`employees.db`) |
| Frontend | Vanilla JS · HTML5 · CSS3 (ไม่มี framework) |
| Production | Gunicorn + Nginx + systemd (Linux) |
| Data Sources | eDevice (Intranet), Google Sheets, Amarin Intranet |

---

## Project Structure

```
employee/
├── app.py                    # Flask app — routes + business logic ทั้งหมด
├── employees.db              # SQLite database (ไม่อยู่ใน git)
├── edevice_assets.json       # Cache ข้อมูล eDevice (สร้างอัตโนมัติ)
├── requirements.txt
├── start.sh                  # Dev server
├── start-prod.sh             # Production (Gunicorn)
├── install.py                # Universal installer (macOS/Linux/Windows)
├── templates/
│   └── index.html            # Single-page HTML
├── static/
│   ├── css/style.css
│   └── js/app.js
└── deploy/
    ├── install.sh            # Linux first-time setup
    ├── update.sh             # Update code (ไม่แตะ .db)
    ├── amarin-employee.service
    └── nginx-amarin-employee.conf
```

---

## IT Asset Data Flow

```
eDevice Intranet (แหล่งหลัก — 900+ เครื่อง)
  computer_id, serial_no, emp_name, device_type, brand, dept, bu
        │
        │  join ด้วย Serial No.
        ▼
Google Sheets (สัญญาเช่า)
  asset_no, end_date, monthly_charge, customer, PO_no, model
        │
        │  + Sheets-only (S/N ไม่มีใน eDevice)
        ▼
fetch_assets_raw()  →  merge กับ SQLite (asset_assignments, asset_notes)
        │
        ▼
/api/assets  →  browser
```

**กฎการ merge:**
1. eDevice records ทั้งหมด → join Sheets ด้วย S/N ถ้าตรงกัน
2. Sheets records ที่ S/N ไม่มีใน eDevice → เพิ่มเข้าไปด้วย
3. `asset_assignments` (SQLite) → override ผู้ถือครองจาก eDevice

---

## Database Schema

### `employees`
| คอลัมน์ | ชนิด | คำอธิบาย |
|---|---|---|
| id | INTEGER PK | รหัสในระบบ |
| emp_code | TEXT | รหัสพนักงาน |
| name | TEXT | ชื่อ-นามสกุล |
| nickname | TEXT | ชื่อเล่น |
| bu / bu_code | TEXT | Business Unit |
| department | TEXT | แผนก |
| position | TEXT | ตำแหน่ง |
| email / phone | TEXT | ช่องทางติดต่อ |
| start_date | TEXT | วันเริ่มงาน (YYYY-MM-DD) |
| status | TEXT | `active` / `inactive` |

### `asset_assignments`
เก็บว่า asset ไหนกับพนักงานคนไหน — override ข้อมูล eDevice/Sheets

### `asset_notes`
สถานะดำเนินการของ asset ที่หมดสัญญา (`pending` / `returned` / `renewed` / `bought`)

### `asset_transfer_log`
ประวัติการโอน asset ระหว่างพนักงาน

---

## API Reference

### Employees

| Method | Endpoint | คำอธิบาย |
|---|---|---|
| GET | `/api/employees` | รายชื่อพนักงาน (pagination + filter) |
| GET | `/api/employees/<id>` | ข้อมูลพนักงานรายคน |
| POST | `/api/employees` | เพิ่มพนักงาน |
| PUT | `/api/employees/<id>` | แก้ไขพนักงาน |
| DELETE | `/api/employees/<id>` | ลบพนักงาน |
| GET | `/api/employees/<id>/assets` | ทรัพย์สิน IT ของพนักงาน |
| GET | `/api/export/excel` | Export Excel |
| POST | `/api/import/excel` | Import Excel |

### IT Assets

| Method | Endpoint | คำอธิบาย |
|---|---|---|
| GET | `/api/assets` | รายการ asset (cache 30 นาที) |
| GET | `/api/assets/meta` | ประเภทและบริษัทสำหรับ filter |
| GET | `/api/assets/export` | Export Excel |
| PUT | `/api/assets/<asset_no>/resolution` | อัพเดทสถานะดำเนินการ |
| POST | `/api/assets/transfer-bulk` | โอน asset หลายรายการ |

**Query params `/api/assets`:**

| Param | ค่า | คำอธิบาย |
|---|---|---|
| `q` | text | ค้นหาชื่อ, รุ่น, S/N, รหัสเครื่อง |
| `status` | `expired` / `critical` / `warning` / `ok` | สถานะสัญญา |
| `ownership` | `เช่า` / `ซื้อ` | ประเภทสัญญา |
| `type` | text | ประเภทเครื่อง |
| `bu` | bu_code | Business Unit |
| `refresh` | `1` | force reload จาก eDevice + Sheets |

### Dashboard & Sync

| Method | Endpoint | คำอธิบาย |
|---|---|---|
| GET | `/api/dashboard/rental` | ข้อมูลแท็บบริหารสัญญา + timeline |
| GET | `/api/sync/preview` | Preview diff จาก Intranet |
| POST | `/api/sync/apply` | Apply sync Intranet |
| POST | `/api/sync-edevice` | Sync ข้อมูล eDevice |

---

## Contract Status

| สถานะ | เงื่อนไข | หมายเหตุ |
|---|---|---|
| 🔴 หมดสัญญาเช่า | end_date < วันนี้ และ eDevice ≠ Expire | สัญญาเช่าหมดอายุจริง |
| ⚠️ eDevice Expire | eDevice status = Expire (ทุกเครื่อง) | ทั้งซื้อและเช่า — ควรตรวจสอบ |
| 🟠 `critical` | เหลือ ≤ 90 วัน | |
| 🟡 `warning` | เหลือ ≤ 180 วัน | |
| 🟢 `ok` | เหลือ > 180 วัน | |
| ⚪ `unknown` | ไม่มี end_date | เครื่องที่ไม่อยู่ในสัญญา Sheets |
| 🗑 ตัดจำหน่าย | เครื่องซื้อ + eDevice = Expire | แสดงในคอลัม สถานะสัญญา |
| ↩ คืนแล้ว | eDevice = Return หรือ Sheets Returned | |
| 🏢 ส่วนกลาง | eDevice ระบุ "ทรัพย์สินของ: ส่วนกลาง" | แสดง badge สีฟ้าในคอลัมน์ผู้ถือครอง |

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
| AME | Amarin Media & Event |

---

## Deployment

### ⚡ One-line Install (Linux)

```bash
# ติดตั้งครั้งแรก
curl -sSL https://raw.githubusercontent.com/sumate001/amarin-asset/main/setup.sh | sudo bash

# อัพเดทโค้ด (ไม่แตะ database)
curl -sSL https://raw.githubusercontent.com/sumate001/amarin-asset/main/setup.sh | sudo bash -s -- --update
```

> **หมายเหตุ:** หลัง install ถ้ามีไฟล์ `employees.db` อยู่แล้ว ให้ copy เข้าไปด้วย:
> ```bash
> sudo cp employees.db /opt/amarin-employee/
> sudo chown www-data /opt/amarin-employee/employees.db
> sudo systemctl restart amarin-employee
> ```

---

### 🖥 Local / Development

```bash
# 1. Clone
git clone https://github.com/sumate001/amarin-asset.git
cd amarin-asset

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run
python app.py
# หรือ
bash start.sh

# เปิด http://localhost:5050
```

> **หมายเหตุ:** ต้องมีไฟล์ `employees.db` อยู่ในโฟลเดอร์ก่อน  
> ถ้าไม่มี app จะสร้าง database ใหม่โดยอัตโนมัติ (ข้อมูลพนักงานว่างเปล่า)

---

### 🐧 Linux (Ubuntu/Debian) — Production

#### ติดตั้งครั้งแรก

```bash
# 1. Clone repo
cd /opt
sudo git clone https://github.com/sumate001/amarin-asset.git
sudo chown -R $USER:$USER /opt/amarin-asset
cd /opt/amarin-asset

# 2. สร้าง virtual environment
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 3. คัดลอก employees.db เข้ามา
cp /path/to/employees.db .

# 4. ติดตั้ง systemd service
sudo cp deploy/amarin-employee.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable amarin-employee
sudo systemctl start amarin-employee

# 5. ติดตั้ง Nginx
sudo cp deploy/nginx-amarin-employee.conf /etc/nginx/sites-available/amarin-employee
sudo ln -s /etc/nginx/sites-available/amarin-employee /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

#### อัพเดท code (ไม่กระทบ database)

```bash
cd /opt/amarin-asset
bash deploy/update.sh
```

หรือทำเอง:

```bash
git pull origin main
sudo systemctl restart amarin-employee
```

#### ดู logs

```bash
sudo journalctl -u amarin-employee -f
```

---

### 🍎 macOS — Production (launchd)

```bash
# 1. Clone และติดตั้ง
cd ~/Desktop/project
git clone https://github.com/sumate001/amarin-asset.git employee
cd employee
pip3 install -r requirements.txt

# 2. รันด้วย Gunicorn
bash start-prod.sh

# หรือใช้ installer อัตโนมัติ
python3 install.py
```

---

### 🪟 Windows — Production (NSSM)

```powershell
# 1. Clone
git clone https://github.com/sumate001/amarin-asset.git
cd amarin-asset

# 2. ติดตั้ง dependencies
pip install -r requirements.txt

# 3. ใช้ installer
python install.py

# หรือรัน dev server
python app.py
```

---

### ⚙️ Environment / Config

ค่า config อยู่ในส่วนบนของ `app.py`:

```python
PORT      = 5050          # port ที่ใช้รัน
CACHE_TTL = 1800          # cache assets (วินาที, default 30 นาที)
DB_PATH   = 'employees.db'

# Google Sheets (ข้อมูลสัญญาเช่า)
SHEET_ID  = '...'         # Google Sheets ID
SHEET_GID = '...'         # Sheet tab GID

# eDevice (Intranet)
EDEVICE_BASE = 'http://amarin.intra/webappl/eDevice_ATV/'
```

> **ข้อจำกัด:** การ Sync eDevice และ Sync Intranet ต้องรันบนเครื่องที่เชื่อมต่อ **Intranet อมรินทร์** เท่านั้น

---

### 🔄 Backup Database

```bash
# สำรอง
cp employees.db employees_backup_$(date +%Y%m%d).db

# Restore
cp employees_backup_20260612.db employees.db
sudo systemctl restart amarin-employee
```

---

## Notes

- `edevice_assets.json` — cache ข้อมูลเครื่องจาก eDevice สร้างอัตโนมัติหลัง Sync ไม่ต้อง commit
- `employees.db` — ห้าม commit เด็ดขาด (อยู่ใน `.gitignore`)
- Cache assets หมดอายุทุก 30 นาที หรือกด Sync eDevice เพื่อ invalidate ทันที
