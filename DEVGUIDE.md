# Developer Guide — Amarin Employee Database

คู่มือสำหรับนักพัฒนาที่ต้องการต่อยอดหรือแก้ไขโปรเจ็คนี้

---

## สารบัญ

1. [Architecture Overview](#1-architecture-overview)
2. [Backend — app.py](#2-backend--apppy)
3. [Frontend — app.js](#3-frontend--appjs)
4. [Data Flow: IT Assets](#4-data-flow-it-assets)
5. [Data Flow: Sync Intranet](#5-data-flow-sync-intranet)
6. [Data Flow: eDevice Sync](#6-data-flow-edevice-sync)
7. [การเพิ่ม Feature ใหม่](#7-การเพิ่ม-feature-ใหม่)
8. [Pitfalls และข้อควรระวัง](#8-pitfalls-และข้อควรระวัง)

---

## 1. Architecture Overview

```
Browser (SPA)
  └── fetch() → Flask routes (app.py)
                  ├── SQLite (employees.db)           ← ข้อมูลหลัก + manual overrides
                  ├── eDevice (TIS-620 + BS4)         ← primary asset source
                  ├── Google Sheets CSV               ← contract info (end_date, PO, ฯลฯ)
                  └── Amarin Intranet (TIS-620 + BS4) ← ข้อมูลพนักงาน
```

ทุกอย่างอยู่ในไฟล์เดียวไม่กี่ไฟล์ ไม่มี ORM ไม่มี frontend build step

---

## 2. Backend — `app.py`

### โครงสร้างไฟล์

```
init_db()                ← สร้าง schema + migration + seed
get_db()                 ← sqlite3.connect() พร้อม row_factory

_load_edevice_list()     ← อ่าน edevice_assets.json แบบ lenient
fetch_assets_raw()       ← core: merge eDevice + Sheets + SQLite → cache

fetch_edevice_assets()   ← อ่าน cache JSON หรือ live scrape
_edevice_login()         ← POST login + scrape VIEWSTATE
_parse_computer_detail() ← BeautifulSoup → dict สำหรับแต่ละเครื่อง

fetch_intranet_employees() ← scrape Intranet contact page
_norm(s)                 ← normalize string สำหรับ name matching

Routes: /api/employees, /api/assets, /api/sync, ...
```

---

## 3. Frontend — `app.js`

### State หลัก

```javascript
let currentPage  = 1;
let filters      = { q, bu, dept, status, hasAsset };
let buMap        = {};   // bu_code → bu name

let assetLoaded  = false;   // lazy load เมื่อเปิด tab
let assetFilters = { q, customer, type, bu, status, ownership };
let assetEmpMap  = {};      // { employee_id: count }

let transferAssets   = [];  // inline asset transfer ใน modal
let empSearchCache   = [];  // active employees สำหรับ datalist
let edSyncData       = null;
let syncData         = null;
```

### Pattern: Modal

```javascript
// เปิด-ปิดด้วย classList
element.classList.add('open');
element.classList.remove('open');

// ทุก modal ต้องมี 3 ฟังก์ชัน
openXxxModal()
closeXxxModal()
closeXxxOnOverlay(e)   // ← e.target === overlay element
```

### `esc(s)` — บังคับใช้ทุกครั้งที่ interpolate ใน innerHTML

```javascript
tbody.innerHTML = `<td>${esc(emp.name)}</td>`;  // ✅
tbody.innerHTML = `<td>${emp.name}</td>`;        // ❌ XSS
```

### `api(url, method, body)` — wrapper fetch

```javascript
const data = await api('/api/employees');
await api('/api/employees/1', 'PUT', payload);
```

---

## 4. Data Flow: IT Assets

### แหล่งข้อมูลและลำดับ priority

```
eDevice JSON cache (primary)
  └── computer_id, serial_no, emp_name, emp_code,
      device_type → แยกเป็น asset_type + ownership
      brand, section/department, bu, monthly_rent

      │ join ด้วย serial_no.upper()
      ▼

Google Sheets CSV (secondary — contract info เท่านั้น)
  └── asset_no, end_date, start_date, monthly_charge,
      customer_code, customer_name, PO_no, model, returned

      │ + Sheets-only records (S/N ไม่มีใน eDevice)
      ▼

asset_notes (SQLite)   → resolution, resolution_note
asset_assignments (SQLite) → override employee_id + user_name
```

### `fetch_assets_raw()` — สองรอบ (Pass 1 + Pass 2)

**Pass 1:** loop eDevice ทั้งหมด → join Sheets ถ้า S/N ตรง

```python
for a in edevice_list:
    sh = sheets_sn_map.get(serial_no.upper())
    results.append(make_record(computer_id, serial_no, a, sh))
```

**Pass 2:** Sheets records ที่ S/N ไม่มีใน eDevice เลย → เพิ่มเข้า results ด้วย เพื่อไม่ให้ข้อมูลสัญญาหาย (สำคัญมากสำหรับเครื่องที่หมดสัญญาและถูกถอดออกจาก eDevice แล้ว)

```python
for sn_upper, sh in sheets_sn_map.items():
    if sn_upper not in ed_sn_set:
        results.append(make_record('', sn, None, sh))
```

### `make_record()` — helper สร้าง record

รับ `(computer_id, serial_no, a_ed, sh)` โดย `a_ed` หรือ `sh` เป็น `None` ได้:
- `a_ed=None` → Sheets-only record (ไม่มีใน eDevice)
- `sh=None` → eDevice-only record (ไม่มีในสัญญา Sheets) → `contract_status = 'unknown'`

### Cache Invalidation

```python
_asset_cache['ts'] = 0   # บังคับ reload รอบหน้า
```

ทุก route ที่แก้ไข `asset_assignments` หรือ `asset_notes` จะ invalidate cache อัตโนมัติ

### Contract Status

| สถานะ | เงื่อนไข |
|---|---|
| `returned` | มีข้อมูลในคอลัมน์ Returned ของ Sheets |
| `expired` | end_date < today |
| `critical` | เหลือ ≤ 90 วัน |
| `warning` | เหลือ ≤ 180 วัน |
| `ok` | เหลือ > 180 วัน |
| `unknown` | ไม่มี end_date (eDevice-only) |

### Ownership Detection

```python
# แยกจาก device_type ของ eDevice เช่น "NoteBook เช่า" → ("NoteBook", "เช่า")
for kw in ('เช่า', 'ซื้อ'):
    if kw in raw_device_type:
        ownership = kw
        device_type_clean = raw_device_type.replace(kw, '').strip()
        break

# computer_id ขึ้นต้น R = เครื่องเช่า (เช่น RNB65001, RPC63001)
is_rental = computer_id.upper().startswith('R')
```

---

## 5. Data Flow: Sync Intranet

```
POST http://www.amarin.intra/webappl/Contact/displays_all.asp
  └── fetch_intranet_employees() — BeautifulSoup, TIS-620

parse BU header (class=fTbHead) → current_bu_code
parse employee rows (td[width=190]) → name, nickname, dept, position, email, phone

/api/sync/preview:
  to_inactive  = active ใน DB แต่ไม่มีใน Intranet → mark inactive
  to_add       = มีใน Intranet แต่ไม่มีใน DB → INSERT
  to_update:
    structural  = bu/dept/position เปลี่ยน
    enrich      = email/phone เปลี่ยน
```

**Key function:** `_norm(s)` — ใช้ normalize ชื่อก่อน match เสมอ

```python
def _norm(s):
    return re.sub(r'\s+', ' ', (s or '').strip().lower())
```

---

## 6. Data Flow: eDevice Sync

```
fetch_edevice_assets(force_live=False)
  ├── มี edevice_assets.json → _load_edevice_list() (lenient JSON parser)
  └── ไม่มี / force_live=True → live fetch:
        _edevice_login()         ← scrape VIEWSTATE → POST login
        GET Computer1.asp        ← รายการ computer_id ทั้งหมด
        ThreadPoolExecutor(15)   ← fetch ComputerDetail.asp แบบ parallel
        _parse_computer_detail() ← BS4 → dict
        → เขียนทับ edevice_assets.json

/api/sync/edevice/preview:
  match by emp_code → match by name → unmatched
  code_updates = ชื่อ match แต่ยังไม่มี emp_code ใน DB

/api/sync/edevice/apply:
  INSERT/UPDATE asset_assignments (ข้าม record ที่มี manual assignment อยู่แล้ว)
  UPDATE emp_code เฉพาะที่ยังว่าง
```

### `_load_edevice_list()` — Lenient JSON Parser

ไฟล์ `edevice_assets.json` อาจมี encoding เสียจาก TIS-620 scraping ใช้ fallback regex parser:

```python
try:
    assets = json.load(f)   # ลองปกติก่อน
except:
    # parse ทีละ object ด้วย regex
    for obj in re.findall(r'\{[^{}]+\}', raw, re.DOTALL):
        try: assets.append(json.loads(obj))
        except: pass
```

---

## 7. การเพิ่ม Feature ใหม่

### เพิ่ม column ในตารางพนักงาน

1. เพิ่มใน `init_db()` (CREATE TABLE + migration block)
2. เพิ่มใน INSERT/UPDATE routes
3. เพิ่ม input ใน `index.html` modal และ `saveEmployee()` payload

### เพิ่ม filter asset ใหม่

**Backend** — `list_assets()`:
```python
new_f = request.args.get('new_filter', '')
if new_f:
    rows = [r for r in rows if r.get('field') == new_f]
```

**Frontend** — เพิ่ม state, select element, event listener, URLSearchParams

### เพิ่ม field ใน asset record

แก้ `make_record()` ใน `fetch_assets_raw()` เพิ่ม key ใหม่ในทั้ง branch `a_ed` และ `else`

### เปลี่ยน Google Sheets

แก้ `SHEETS_ID` ใน `app.py` แล้วตรวจ column name:
- `row.get('Asset number')`, `row.get('Serial Number')`, `row.get('End date')` ฯลฯ

---

## 8. Pitfalls และข้อควรระวัง

### Encoding TIS-620

Intranet และ eDevice ใช้ TIS-620 — ต้อง decode ก่อนทุกครั้ง:

```python
text = resp.content.decode('tis-620', errors='replace')
```

อ่านไฟล์ JSON ที่ eDevice เขียนทับ:

```python
open(EDEVICE_JSON, encoding='utf-8', errors='replace')
```

### eDevice JSON อาจเสีย

`edevice_assets.json` อาจมี record เสียถ้า scraping ดึงข้อมูลไม่สมบูรณ์ — ใช้ `_load_edevice_list()` ที่มี fallback regex เสมอ อย่าเปิดไฟล์ตรง ๆ ใน code ใหม่

### ชื่อซ้ำ / name collision

`_norm()` match แบบ exact string — ถ้ามีพนักงานชื่อซ้ำกัน match ได้คนเดียว แนะนำ fill `emp_code` ให้ครบ (ผ่าน eDevice Sync) เพื่อใช้ code match แทน

### asset_no vs computer_id

- `asset_no` = Sheets asset_no ถ้า S/N match, ไม่งั้น = `computer_id`
- `computer_id` = รหัสจาก eDevice (`RNB65001`, `RPC63001`, ฯลฯ)
- สองระบบนี้ **ไม่ใช่ key เดียวกัน** — อย่า join โดยตรง ใช้ S/N เป็นตัวเชื่อมเท่านั้น

### Manual Assignments ห้ามถูกทับ

`edevice_apply()` จะ skip record ที่มีอยู่ใน `asset_assignments` แล้ว:

```python
manual_nos = {r[0] for r in conn.execute('SELECT asset_no FROM asset_assignments')}
if cid in manual_nos:
    protected += 1   # ข้าม — ไม่ทับ
```

### SQLite Concurrency

Flask รัน single-threaded (`debug=True`) — ไม่มีปัญหา  
ถ้า deploy แบบ multi-worker ต้องเพิ่ม connection pool หรือเปลี่ยนเป็น PostgreSQL

### Cache TTL = 30 นาที

`_asset_cache` อยู่ใน memory — restart server = cache หาย โหลดใหม่อัตโนมัติรอบถัดไป  
force reload ได้ด้วยปุ่ม **Refresh** (ส่ง `?refresh=1`)
