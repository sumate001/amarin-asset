# Amarin Employee Database

ระบบบริหารข้อมูลพนักงานและทรัพย์สิน IT สำหรับกลุ่มบริษัทอมรินทร์

---

## Features

| โมดูล | รายละเอียด |
|---|---|
| **รายชื่อพนักงาน** | CRUD พนักงาน, ค้นหา, กรองตาม BU / แผนก / สถานะ / มีทรัพย์สิน IT, Export/Import Excel |
| **IT Assets** | แสดงเครื่องทั้งหมดจาก eDevice + ข้อมูลสัญญาจาก Google Sheets, กรองตามประเภท / การถือครอง / BU / สถานะสัญญา |
| **Dashboard** | สถิติพนักงานแยก BU และ Top 10 แผนก |
| **Sync Intranet** | เปรียบเทียบและอัพเดทข้อมูลพนักงานจาก Amarin Intranet |
| **Sync eDevice** | ดึง asset assignment จากระบบ eDevice ภายใน และอัพเดทรหัสพนักงาน |

---

## Tech Stack

- **Backend:** Python 3 · Flask
- **Database:** SQLite (`employees.db`)
- **Frontend:** Vanilla JS · HTML/CSS (ไม่มี framework)
- **Data Sources:**
  - **eDevice** (primary) — ข้อมูลเครื่องคอมพิวเตอร์ทั้งหมด + ผู้ถือครอง
  - **Google Sheets** (secondary) — วันหมดสัญญาเช่า, asset_no, PO, บริษัทผู้ให้เช่า
  - **Amarin Intranet** — ข้อมูลพนักงานปัจจุบัน

---

## Quick Start

```bash
pip install flask openpyxl requests beautifulsoup4
python app.py
# เปิด http://localhost:5050
```

---

## Project Structure

```
employee/
├── app.py                    # Flask app — routes + business logic ทั้งหมด
├── employees.db              # SQLite database
├── employees_extracted.json  # ข้อมูล seed พนักงานเริ่มต้น
├── edevice_assets.json       # Cache ข้อมูล eDevice (สร้างอัตโนมัติ)
├── templates/
│   └── index.html            # Single-page HTML
└── static/
    ├── css/style.css
    └── js/app.js             # Frontend logic ทั้งหมด
```

---

## Database Schema

### `employees`
| คอลัมน์ | ชนิด | คำอธิบาย |
|---|---|---|
| id | INTEGER PK | รหัสในระบบ |
| emp_code | TEXT | รหัสพนักงาน (HR / eDevice) |
| bu / bu_code | TEXT | Business Unit |
| department | TEXT | แผนก |
| name | TEXT NOT NULL | ชื่อ-นามสกุล |
| nickname | TEXT | ชื่อเล่น |
| position | TEXT | ตำแหน่ง |
| email / phone | TEXT | ช่องทางติดต่อ |
| start_date | TEXT | วันเริ่มงาน (YYYY-MM-DD) |
| status | TEXT | `active` / `inactive` |
| note | TEXT | หมายเหตุ |
| created_at / updated_at | TEXT | timestamp localtime |

### `asset_assignments`
เก็บว่า asset ไหนอยู่กับพนักงานคนไหน — override ข้อมูลจาก eDevice/Sheets

### `asset_notes`
บันทึกสถานะการดำเนินการของ asset ที่หมดสัญญา (`pending`, `returned`, `bought`, `renewed`, ...)

### `asset_transfer_log`
ประวัติการโอน asset ระหว่างพนักงาน

---

## IT Asset Data Flow

```
eDevice (primary — 900+ เครื่อง)
  └── computer_id, serial_no, emp_name, emp_code,
      device_type, brand, department, bu, monthly_rent
         │
         │ join ด้วย Serial No.
         ▼
Google Sheets (secondary — สัญญาเช่า)
  └── asset_no, end_date, monthly_charge,
      customer, PO_no, model
         │
         │ + Sheets-only records (S/N ไม่มีใน eDevice)
         ▼
fetch_assets_raw() → merge asset_notes + asset_assignments (SQLite)
         │
         ▼
/api/assets → browser
```

**กฎการ merge:**
1. eDevice records ทั้งหมด → join Sheets ด้วย S/N ถ้าตรงกัน
2. Sheets records ที่ S/N ไม่มีใน eDevice → เพิ่มเข้าไปด้วย (ไม่ให้สัญญาหาย)
3. `asset_assignments` ใน SQLite → override ผู้ถือครองทั้งหมด

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
| GET | `/api/filters` | BU list + dept list สำหรับ filter |
| GET | `/api/stats` | สถิติรวม |
| GET | `/api/export/excel` | Export Excel |
| POST | `/api/import/excel` | Import Excel |

### IT Assets

| Method | Endpoint | คำอธิบาย |
|---|---|---|
| GET | `/api/assets` | รายการ asset (cache 30 นาที) |
| GET | `/api/assets/meta` | บริษัทและประเภท asset สำหรับ filter |
| GET | `/api/assets/employee-map` | `{employee_id: จำนวน asset}` |
| GET | `/api/assets/export` | Export Excel |
| PUT | `/api/assets/<asset_no>/resolution` | อัพเดทสถานะดำเนินการ |
| POST | `/api/assets/transfer-bulk` | โอน asset หลายรายการพร้อมกัน |

**Query params สำหรับ `/api/assets`:**

| Param | ค่าที่รับ | คำอธิบาย |
|---|---|---|
| `q` | text | ค้นหาชื่อ, รุ่น, S/N, รหัสเครื่อง |
| `status` | `expired` / `critical` / `warning` / `ok` | สถานะสัญญา |
| `ownership` | `เช่า` / `ซื้อ` | การถือครอง |
| `type` | text | ประเภทเครื่อง (NoteBook, Desktop, ...) |
| `bu` | bu_code | Business Unit |
| `customer` | customer_code | บริษัทผู้ให้เช่า |
| `refresh` | `1` | force reload จาก eDevice + Sheets |

### Sync

| Method | Endpoint | คำอธิบาย |
|---|---|---|
| GET | `/api/sync/preview` | Preview diff จาก Intranet |
| POST | `/api/sync/apply` | Apply sync จาก Intranet |
| GET | `/api/sync/edevice/preview` | Preview การ match asset กับพนักงาน |
| POST | `/api/sync/edevice/apply` | Apply eDevice sync |

---

## Contract Status

| สถานะ | เงื่อนไข | สี |
|---|---|---|
| `expired` | end_date < วันนี้ | 🔴 แดง |
| `critical` | เหลือ ≤ 90 วัน | 🟠 ส้ม |
| `warning` | เหลือ ≤ 180 วัน | 🟡 เหลือง |
| `ok` | เหลือ > 180 วัน | 🟢 เขียว |
| `unknown` | ไม่มี end_date (เครื่องที่ไม่อยู่ในสัญญา Sheets) | — |

## รหัสเครื่อง (computer_id)

| Prefix | ความหมาย |
|---|---|
| `R...` | เครื่องเช่า (เช่น `RNB65001`, `RPC63001`) |
| อื่น ๆ | เครื่องซื้อขาด หรือไม่ได้ระบุ |

---

## BU Codes

| Code | ชื่อบริษัท |
|---|---|
| APUB | Amarin Publishing |
| APRINT | Amarin Printing & Packaging |
| ACS | Amarin Corporate Support |
| ABOOK | Amarin Book Center |
| AMTV | Amarin Television |
| AOMNI | Amarin Omniverse |
| AME | Amarin Media & Event |
