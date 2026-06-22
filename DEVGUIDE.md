# Developer Guide — Amarin Employee & IT Asset Database

คู่มือสำหรับนักพัฒนาที่จะต่อยอดหรือแก้ไขโปรเจกต์นี้

---

## สารบัญ

1. [Architecture Overview](#1-architecture-overview)
2. [Environment Setup](#2-environment-setup)
3. [Backend — app.py](#3-backend--apppy)
4. [Frontend — app.js](#4-frontend--appjs)
5. [Data Flow: IT Assets](#5-data-flow-it-assets)
6. [Data Flow: Sync Intranet (พนักงาน)](#6-data-flow-sync-intranet-พนักงาน)
7. [Data Flow: eDevice Sync](#7-data-flow-edevice-sync)
8. [Background Fetch System](#8-background-fetch-system)
9. [Production Architecture](#9-production-architecture)
10. [การเพิ่ม Feature ใหม่](#10-การเพิ่ม-feature-ใหม่)
11. [Pitfalls และข้อควรระวัง](#11-pitfalls-และข้อควรระวัง)

---

## 1. Architecture Overview

```
Browser (SPA — Single Page App)
  └── fetch() / polling ──→ Nginx (port 80)
                                └── proxy_pass ──→ Gunicorn (port 5100, 3 workers)
                                                        └── Flask app.py
                                                              ├── SQLite employees.db
                                                              ├── eDevice Intranet (HTTP scraping)
                                                              ├── Google Sheets CSV (HTTP)
                                                              └── Amarin Intranet (HTTP scraping)
```

**ไม่มี:** ORM, frontend build step (webpack/vite), database migration tool, task queue (Celery/Redis)  
**มี:** raw SQL, BeautifulSoup scraping, vanilla JS, file-based background task state

---

## 2. Environment Setup

### Dev

```bash
git clone https://github.com/sumate001/amarin-asset.git
cd amarin-asset

# สร้าง virtual environment (แนะนำ)
python3 -m venv venv
source venv/bin/activate   # หรือ venv\Scripts\activate บน Windows

pip install -r requirements.txt

# รัน dev server (auto-reload)
python app.py
# หรือ
bash start.sh
```

Dev server รันที่ port **5050** พร้อม Flask debug mode

### Production Path

```
/opt/amarin-employee/        ← app directory (git clone)
/opt/amarin-employee/venv/   ← Python virtualenv
/var/log/amarin-employee/    ← access.log, error.log
/etc/systemd/system/amarin-employee.service
/etc/nginx/sites-available/amarin-employee
```

### Dependencies (requirements.txt)

```
flask
requests
beautifulsoup4
openpyxl
gunicorn
```

---

## 3. Backend — `app.py`

### โครงสร้างไฟล์ (ตามลำดับ)

```
# imports + constants (DB, CACHE_TTL, SHEETS_ID, EDEVICE_URLs)

init_db()          ← สร้าง schema + auto-migration + seed จาก JSON
get_db()           ← sqlite3.connect() พร้อม row_factory=sqlite3.Row

_js_version()      ← md5 hash ของ app.js (ใช้ cache-bust URL param)

# ─── Routes: Employees ────────────────────────────────
/                  ← render index.html พร้อม js_version
/api/employees     ← CRUD + pagination + filter
/api/filters       ← BU list, department list
/api/stats         ← สถิติ total/by_bu/by_dept
/api/export/excel  ← openpyxl export
/api/import/excel  ← openpyxl import

# ─── Routes: IT Assets ────────────────────────────────
_asset_cache = {}  ← in-memory cache dict {ts, data}
fetch_assets_raw() ← merge eDevice + Sheets + SQLite (core function)
/api/assets        ← รายการ asset พร้อม filter
/api/assets/meta   ← ประเภท + BU list
/api/assets/employee-map ← employee_id → asset count
/api/employees/<id>/assets
/api/assets/transfer-bulk
/api/assets/<no>/resolution
/api/assets/export
/api/dashboard/rental
/api/sheets/update-info

# ─── eDevice Sync ─────────────────────────────────────
EDEVICE_JSON, EDEVICE_STATUS_JSON
_ed_write_status(), _ed_read_status()   ← file-based state
_edevice_fetch_bg()                     ← background thread function
_edevice_login()                        ← scrape VIEWSTATE → POST login
_parse_computer_detail()                ← BS4 → dict (PC)
_parse_mac_detail()                     ← BS4 → dict (Mac)
_parse_label_value()                    ← shared table parser
_clean_serial()                         ← ตัด placeholder serial
fetch_edevice_assets()                  ← cache หรือ live fetch (parallel)
/api/sync/edevice/fetch-start   POST   ← เริ่ม background thread
/api/sync/edevice/fetch-status  GET    ← poll state จากไฟล์
/api/sync/edevice/preview       GET    ← match stats (ใช้ cache)
/api/sync/edevice/apply         POST   ← upsert asset_assignments

# ─── Intranet Sync (พนักงาน) ──────────────────────────
fetch_intranet_employees()
/api/sync/preview   GET
/api/sync/apply     POST

init_db()   ← เรียกที่ module level (ไม่ใช่ใน if __name__)
```

### `init_db()` — ทำไมต้องอยู่ที่ module level

```python
# ✅ ถูก — อยู่นอก if __name__
init_db()

if __name__ == '__main__':
    app.run(debug=True, port=5050)
```

เมื่อ Gunicorn import `app:app` จะไม่ผ่าน `if __name__ == '__main__'` เลย ถ้า `init_db()` อยู่ในนั้น DB จะไม่มี table → 500 error ทุก request

### Asset Cache

```python
_asset_cache = {'ts': 0, 'data': None}

# invalidate ทันที (หลัง sync หรือ transfer)
_asset_cache['ts'] = 0

# auto-reload ถ้า cache หมดอายุ (CACHE_TTL = 1800 วินาที)
if time.time() - _asset_cache['ts'] > CACHE_TTL:
    _asset_cache['data'] = fetch_assets_raw()
    _asset_cache['ts']   = time.time()
```

⚠️ Cache อยู่ใน memory ของแต่ละ Gunicorn worker — 3 workers = 3 caches แยกกัน  
กด Sync หรือ transfer จะ invalidate เฉพาะ worker ที่รับ request นั้น  
Worker อื่นจะ reload เมื่อ cache หมดอายุตามปกติ (ภายใน 30 นาที)

---

## 4. Frontend — `app.js`

### State หลัก

```javascript
// Employees tab
let currentPage  = 1;
let filters      = {};
let buMap        = {};        // bu_code → bu name

// Assets tab
let assetLoaded  = false;     // lazy load เมื่อเปิด tab ครั้งแรก
let allAssets    = [];        // raw asset array จาก API
let assetFilters = {};
let assetEmpMap  = {};        // employee_id → asset count

// Modals
let transferAssets = [];      // asset ที่เลือกสำหรับ transfer
let edSyncData     = null;    // eDevice preview data
let syncData       = null;    // Intranet preview data
let _edPollTimer   = null;    // setTimeout ref สำหรับ eDevice status polling
```

### Pattern: Modal

```javascript
function openXxxModal()        { element.classList.add('open'); ... }
function closeXxxModal()       { element.classList.remove('open'); ... }
function closeXxxOnOverlay(e)  { if (e.target === overlay) closeXxxModal(); }
```

### `api(url, method, body)` — wrapper fetch

```javascript
const data = await api('/api/employees');
await api('/api/employees/1', 'PUT', payload);
// throw ถ้า HTTP error → ให้ catch ที่ caller
```

### `esc(s)` — XSS prevention

```javascript
// บังคับใช้ทุกครั้งที่ interpolate user data ใน innerHTML
tbody.innerHTML = `<td>${esc(emp.name)}</td>`;   // ✅
tbody.innerHTML = `<td>${emp.name}</td>`;         // ❌
```

### eDevice Polling Pattern

```javascript
// เปิด modal
openEdeviceSyncModal()
  → fetch-status (running? cache_ready?)
  → ถ้า cache_ready → preview (fast, จาก cache)
  → ถ้าไม่มี cache → startEdeviceFetch() → เริ่ม poll

// poll loop (ทุก 3 วินาที)
_pollEdeviceFetch()
  → fetch-status → อัพเดท progress bar
  → ถ้า running → setTimeout(_pollEdeviceFetch, 3000)
  → ถ้า done    → fetch preview → _edShowPreview(data)
  → ถ้า error   → แสดง error message

// ปิด modal = cancel poll timer
closeEdeviceSyncModal()
  → clearTimeout(_edPollTimer)
```

### Cache-Busting app.js

HTML template (`index.html`) ใช้ Jinja2 variable:

```html
<script src="/static/js/app.js?v={{ js_version }}"></script>
```

`js_version` = md5 hash 8 ตัวของไฟล์ คำนวณใน `_js_version()` ใน `app.py`  
ทุกครั้งที่ `app.js` เปลี่ยน hash จะเปลี่ยน → browser โหลดใหม่อัตโนมัติ

---

## 5. Data Flow: IT Assets

### แหล่งข้อมูล (3 แหล่ง ลำดับ priority)

```
① eDevice JSON cache  (primary — รายการเครื่องทั้งหมด)
    computer_id, serial_no, emp_name, emp_code,
    device_type → asset_type + ownership
    brand, section/department, bu_th, monthly_rent

        │  join ด้วย serial_no.upper()
        ▼

② Google Sheets CSV  (secondary — ข้อมูลสัญญาเท่านั้น)
    asset_no, end_date, start_date, monthly_charge,
    customer_code, customer_name, PO_no, model, returned

        │  + Sheets-only (S/N ไม่มีใน eDevice เลย)
        ▼

③ SQLite  (override)
    asset_notes     → resolution, note
    asset_assignments → employee_id, user_name (ทับ eDevice)
```

### `fetch_assets_raw()` — 2 passes

**Pass 1:** loop eDevice ทั้งหมด → join Sheets ด้วย S/N
```python
for a in edevice_list:
    sh = sheets_sn_map.get(serial_no.upper())
    results.append(make_record(computer_id, serial_no, a, sh))
```

**Pass 2:** Sheets records ที่ S/N ไม่มีใน eDevice → เพิ่มด้วย (อย่าให้หาย)
```python
for sn_upper, sh in sheets_sn_map.items():
    if sn_upper not in ed_sn_set:
        results.append(make_record('', sn, None, sh))
```

Pass 2 สำคัญมากสำหรับเครื่องที่หมดสัญญาและถูกถอดออกจาก eDevice แล้ว

### Ownership Detection

```python
# 1. ดู device_type จาก eDevice เช่น "NoteBook เช่า" → ownership = "เช่า"
for kw in ('เช่า', 'ซื้อ'):
    if kw in raw_device_type:
        ownership = kw; break

# 2. computer_id ขึ้นต้น R = เครื่องเช่า (R = Rent)
is_rental = computer_id.upper().startswith('R')
```

### asset_no vs computer_id

- `computer_id` = รหัสจาก eDevice เช่น `RNB65001`, `RPC63001`, `1212-0028`
- `asset_no` = Sheets asset_no ถ้า S/N match, ไม่งั้น fallback เป็น computer_id
- **สองระบบนี้ไม่ใช่ key เดียวกัน** — ใช้ serial_no เป็นตัวเชื่อมเท่านั้น

---

## 6. Data Flow: Sync Intranet (พนักงาน)

```
fetch_intranet_employees()
  POST http://www.amarin.intra/webappl/Contact/displays_all.asp
  decode TIS-620
  BS4 parse:
    td.class=fTbHead → BU header (regex: "- AMTV" → bu_code)
    tr → td[width=190] → name/nickname, dept, position, email, phone

/api/sync/preview:
  to_inactive  = active ใน DB แต่ไม่มีใน Intranet
  to_add       = มีใน Intranet แต่ยังไม่มีใน DB
  to_update:
    structural  = bu/dept/position เปลี่ยน
    enrich      = email/phone/nickname เปลี่ยน

/api/sync/apply:
  apply to_inactive → UPDATE status='inactive'
  apply to_add      → INSERT
  apply to_update   → UPDATE fields
```

**Key:** `_norm(s)` ใช้ normalize ชื่อก่อน match เสมอ

```python
def _norm(s):
    return re.sub(r'\s+', ' ', (s or '').strip().lower())
```

---

## 7. Data Flow: eDevice Sync

### Login Flow

```
GET  http://amarin.intra/webappl/acorporate/index.aspx?s=out
     ← scrape __VIEWSTATE, __EVENTVALIDATION (ASP.NET hidden fields)

POST same URL + credentials (username=90004)
     ← ระบบ redirect → session cookie ถูก set

GET  http://www.amarin.intra/webappl/eDevice_ATV/default.asp?ID_Emp=...
     ← activate corporate session
```

### Fetch Flow

```
GET Computer1.asp    → regex ดึง <OPTION value='...'> → pc_ids[]
GET Macintosh.asp    → เหมือนกัน                      → mac_ids[]

ThreadPoolExecutor(max_workers=50):
  fetch ComputerDetail.asp?id={cid}    ← PC
  fetch MacintoshDetail.asp?id={cid}   ← Mac
  _parse_computer_detail(text, cid)    ← BS4 → dict
  _parse_mac_detail(text, cid)

เขียนทับ edevice_assets.json (UTF-8)
```

### Match Logic (`edevice_preview` / `edevice_apply`)

```
matched_code:  emp_code ตรงกับ employees.emp_code
matched_name:  _norm(emp_name) ตรงกับ _norm(employees.name)
unmatched:     ไม่พบเลย — ต้องตรวจสอบด้วยมือ
```

```python
# apply: ข้าม asset ที่มี manual assignment อยู่แล้ว
manual_nos = {r[0] for r in conn.execute('SELECT asset_no FROM asset_assignments')}
if cid in manual_nos:
    protected += 1   # ไม่ทับ manual assignment
```

---

## 8. Background Fetch System

### ปัญหาที่แก้

eDevice มี ~4,757 devices (PC + Mac) การ scrape แบบ sync ใช้เวลา 3-5 นาที ซึ่งเกิน Nginx `proxy_read_timeout 120s` และ Gunicorn `--timeout 300s`

### วิธีแก้: Background Thread + File-Based State

```
Browser                     Gunicorn Worker A       Gunicorn Worker B/C
   │                              │                         │
   ├─ POST /fetch-start ──────────►                         │
   │                         spawn thread                   │
   │                         write status.json: running=True│
   │◄─ {status: "started"} ───────┤                         │
   │                              │                         │
   ├─ GET /fetch-status ──────────┼────────────────────────►│
   │◄─ {running:T, count:350} ────┼──────── read status.json┤
   │         (3s)                 │                         │
   ├─ GET /fetch-status ──────────┼────────────────────────►│
   │         (3s)                 │ thread still running    │
   │         ...                  │ write status.json: c=650│
   │                              │                         │
   │                      thread done                       │
   │                      write status.json: done=True      │
   ├─ GET /fetch-status ──────────┼────────────────────────►│
   │◄─ {done:T, cache_ready:T} ───┤                         │
   │                              │                         │
   ├─ GET /preview ───────────────┼────────────────────────►│
   │◄─ {stats, unmatched...} ─────┼──── read cache file ────┤
```

### ทำไมต้อง File-Based (ไม่ใช่ Global Variable)

Gunicorn รัน 3 worker processes แยกกัน — แต่ละ worker มี memory ของตัวเอง  
ถ้าใช้ `global _state = {}` Worker A set `running=True` แต่ Worker B/C ยังเห็น `running=False`

**Solution:** เขียน/อ่านผ่าน `edevice_fetch_status.json` ซึ่งทุก worker เห็นตรงกัน

```python
def _ed_write_status(state: dict):
    with open(EDEVICE_STATUS_JSON, 'w', encoding='utf-8') as f:
        json.dump(state, f)

def _ed_read_status() -> dict:
    try:
        with open(EDEVICE_STATUS_JSON, encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {'running': False, 'done': False, 'error': None, 'count': 0, 'total': 0}
```

### Files ที่สร้างอัตโนมัติ

| ไฟล์ | สร้างเมื่อ | ลบได้? |
|---|---|---|
| `edevice_assets.json` | หลัง fetch สำเร็จ | ได้ — จะ fetch ใหม่ครั้งหน้า |
| `edevice_fetch_status.json` | ระหว่าง/หลัง fetch | ได้ — จะสร้างใหม่ |

---

## 9. Production Architecture

### Nginx Config (`deploy/nginx-amarin-employee.conf`)

```nginx
server {
    listen 80;
    client_max_body_size 20M;
    gzip on;

    location /static/ {
        alias /opt/amarin-employee/static/;
        expires 7d;                          # browser cache 7 วัน
        add_header Cache-Control "public";   # แต่ app.js ใช้ ?v=hash cache-bust
    }

    location / {
        proxy_pass         http://127.0.0.1:5100;
        proxy_read_timeout 120s;             # ⚠️ เพิ่มถ้ามี endpoint ที่ใช้เวลานาน
    }
}
```

### Gunicorn (`deploy/amarin-employee.service`)

```
--workers  3       # 3 processes
--timeout  300     # 5 นาที (สำหรับ live eDevice fetch ฉุกเฉิน)
--preload         # โหลด app ก่อน fork workers (init_db() ทำงานที่นี่)
```

⚠️ `--preload` + background threads: thread ที่ spawn หลัง fork จะทำงานได้ปกติ  
แต่ Python GIL อาจทำให้ CPU-bound work ช้าลง (I/O bound เช่น HTTP ไม่มีปัญหา)

### Deployment Pipeline

```bash
# Developer
git commit + git push → GitHub

# Server (รัน setup.sh --update)
git pull                   # จาก GitHub
pip install -r requirements.txt
systemctl restart amarin-employee

# Nginx/systemd service file เปลี่ยน → ต้อง copy + reload ด้วยตัวเอง
sudo cp deploy/amarin-employee.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl restart amarin-employee
```

`setup.sh --update` ไม่ copy service/nginx file อัตโนมัติ ต้องทำเองถ้าแก้ไข

---

## 10. การเพิ่ม Feature ใหม่

### เพิ่ม column ในตารางพนักงาน

1. เพิ่มใน `CREATE TABLE` ใน `init_db()`
2. เพิ่ม migration block (ตรวจก่อน ALTER TABLE):
   ```python
   cols = [r[1] for r in conn.execute("PRAGMA table_info(employees)").fetchall()]
   if 'new_col' not in cols:
       conn.execute("ALTER TABLE employees ADD COLUMN new_col TEXT")
   ```
3. เพิ่มใน INSERT/UPDATE routes
4. เพิ่ม input ใน modal (`index.html`) และ payload (`app.js`)

### เพิ่ม filter asset ใหม่

**Backend** — ใน `fetch_assets_raw()` หรือ `/api/assets`:
```python
new_f = request.args.get('new_filter', '')
if new_f:
    rows = [r for r in rows if r.get('field') == new_f]
```

**Frontend** — เพิ่ม:
1. State variable ใน `assetFilters`
2. `<select>` element ใน filter bar
3. Event listener → call `renderAssets()`
4. URLSearchParams ใน `loadAssets()`

### เพิ่ม endpoint ใหม่

```python
@app.route('/api/new-endpoint', methods=['GET'])
def new_endpoint():
    conn = get_db()
    # ... logic
    conn.close()
    return jsonify(result)
```

อย่าลืม `conn.close()` เสมอ — SQLite ไม่มี connection pool

### เปลี่ยน Google Sheets source

แก้ `SHEETS_ID` ใน `app.py` แล้วตรวจ column name ใน Sheets:
```python
row.get('Asset number')    # asset_no
row.get('Serial Number')   # serial_no
row.get('End date')        # end_date
row.get('monthly charge')  # monthly_charge
```
Column name case-sensitive — ต้องตรงกับ header ใน Sheets

---

## 11. Pitfalls และข้อควรระวัง

### TIS-620 Encoding

Intranet และ eDevice ใช้ TIS-620 — ต้อง decode ก่อนเสมอ:
```python
text = resp.content.decode('tis-620', errors='replace')
```

อย่าใช้ `resp.text` โดยตรง (requests จะ guess encoding ผิด)

### edevice_assets.json อาจเสีย

การ scrape อาจถูก interrupt → ไฟล์เสียกลางทาง ใช้ `_load_edevice_list()` ที่มี fallback regex parser:
```python
try:
    assets = json.load(f)
except:
    for obj in re.findall(r'\{[^{}]+\}', raw, re.DOTALL):
        try: assets.append(json.loads(obj))
        except: pass
```
อย่าเปิดไฟล์ตรงๆ ใน code ใหม่ — ใช้ `fetch_edevice_assets()` หรือ `_load_edevice_list()` เสมอ

### ชื่อซ้ำ / Name Collision

`_norm()` match exact string — ถ้ามีพนักงานชื่อซ้ำ match ได้แค่คนแรก  
แก้ได้โดย fill `emp_code` ให้ครบ (ผ่าน eDevice Sync apply) เพื่อใช้ code match แทน name match

### Gunicorn Multi-Process Cache

3 workers = 3 in-memory caches แยกกัน  
กด "Sync" จะ invalidate cache เฉพาะ worker ที่รับ request นั้น  
ใช้ file-based state สำหรับ data ที่ต้องแชร์ข้าม workers (เหมือน edevice_fetch_status.json)

### Nginx proxy_read_timeout = 120s

Endpoint ที่ใช้เวลานาน (> 2 นาที) จะถูก Nginx ตัดก่อน แม้ Gunicorn ยัง process อยู่  
**แนวทาง:** ใช้ pattern background fetch + polling เหมือน eDevice

### init_db() ต้องอยู่ที่ module level

```python
# ✅ ถูก
init_db()
if __name__ == '__main__':
    app.run(...)

# ❌ ผิด — Gunicorn ไม่เรียก init_db() เลย
if __name__ == '__main__':
    init_db()
    app.run(...)
```

### Manual Assignments ห้ามถูก eDevice ทับ

```python
# edevice_apply() skip record ที่มี manual assignment อยู่แล้ว
manual_nos = {r[0] for r in conn.execute('SELECT asset_no FROM asset_assignments')}
if cid in manual_nos:
    protected += 1   # skip — ไม่ทับ
```

เมื่อ sync eDevice ซ้ำ manual assignment ที่ทำไว้จะไม่ถูกลบทิ้ง

### Browser Cache app.js

Nginx cache static files 7 วัน — ถ้า deploy `app.js` ใหม่โดยไม่มี cache-bust  
browser จะใช้ของเก่าต่อไปอีก 7 วัน  
ระบบนี้แก้ด้วย `?v={{ js_version }}` (md5 hash) ใน template แล้ว — ไม่ต้องแก้อะไรเพิ่ม

### SQLite WAL Mode

ไม่ได้เปิด WAL mode — ถ้ามี write load สูงขึ้น (หลาย user sync พร้อมกัน) อาจ lock  
แก้ได้ด้วย `conn.execute("PRAGMA journal_mode=WAL")` ใน `get_db()`
