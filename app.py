from flask import Flask, request, jsonify, render_template, send_file
import sqlite3, json, io, os, re, csv, time
from datetime import datetime, date
import requests as req_lib

app = Flask(__name__)
DB = os.path.join(os.path.dirname(__file__), 'employees.db')

# ---------- DB helpers ----------

def get_db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS employees (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            emp_code    TEXT,
            bu          TEXT,
            bu_code     TEXT,
            department  TEXT,
            name        TEXT NOT NULL,
            nickname    TEXT,
            position    TEXT,
            email       TEXT,
            phone       TEXT,
            start_date  TEXT,
            status      TEXT DEFAULT 'active',
            note        TEXT,
            created_at  TEXT DEFAULT (datetime('now','localtime')),
            updated_at  TEXT DEFAULT (datetime('now','localtime'))
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS asset_notes (
            asset_no    TEXT PRIMARY KEY,
            resolution  TEXT DEFAULT 'pending',
            note        TEXT,
            updated_at  TEXT DEFAULT (datetime('now','localtime'))
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS asset_assignments (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            asset_no    TEXT NOT NULL UNIQUE,
            employee_id INTEGER,
            note        TEXT,
            created_at  TEXT DEFAULT (datetime('now','localtime'))
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS asset_transfer_log (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            asset_no            TEXT NOT NULL,
            from_employee_id    INTEGER,
            to_employee_id      INTEGER,
            transfer_type       TEXT,
            note                TEXT,
            created_at          TEXT DEFAULT (datetime('now','localtime'))
        )
    ''')
    # migration: add emp_code if not exists
    cols = [r[1] for r in conn.execute("PRAGMA table_info(employees)").fetchall()]
    if 'emp_code' not in cols:
        conn.execute("ALTER TABLE employees ADD COLUMN emp_code TEXT")
    conn.commit()
    # Seed from JSON if empty
    count = conn.execute('SELECT COUNT(*) FROM employees').fetchone()[0]
    if count == 0:
        json_path = os.path.join(os.path.dirname(__file__), 'employees_extracted.json')
        if os.path.exists(json_path):
            with open(json_path) as f:
                data = json.load(f)
            conn.executemany(
                'INSERT INTO employees (bu, bu_code, department, name, nickname, position) VALUES (?,?,?,?,?,?)',
                [(e['bu'], e['bu_code'], e['department'], e['name'], e['nickname'], e['position']) for e in data]
            )
            conn.commit()
    conn.close()

# ---------- Routes ----------

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/employees', methods=['GET'])
def list_employees():
    q         = request.args.get('q', '').strip()
    bu        = request.args.get('bu', '')
    dept      = request.args.get('dept', '')
    status    = request.args.get('status', '')
    page      = max(1, int(request.args.get('page', 1)))
    per_page  = int(request.args.get('per_page', 50))

    where, params = [], []
    if q:
        where.append("(name LIKE ? OR nickname LIKE ? OR position LIKE ? OR department LIKE ?)")
        params += [f'%{q}%'] * 4
    if bu:
        where.append("bu_code = ?"); params.append(bu)
    if dept:
        where.append("department = ?"); params.append(dept)
    if status:
        where.append("status = ?"); params.append(status)

    sql_where = ('WHERE ' + ' AND '.join(where)) if where else ''

    conn = get_db()
    total = conn.execute(f'SELECT COUNT(*) FROM employees {sql_where}', params).fetchone()[0]
    rows  = conn.execute(
        f'SELECT * FROM employees {sql_where} ORDER BY bu_code, department, name LIMIT ? OFFSET ?',
        params + [per_page, (page - 1) * per_page]
    ).fetchall()
    conn.close()

    return jsonify({
        'total': total,
        'page': page,
        'per_page': per_page,
        'pages': (total + per_page - 1) // per_page,
        'employees': [dict(r) for r in rows]
    })

@app.route('/api/employees/<int:eid>', methods=['GET'])
def get_employee(eid):
    conn = get_db()
    row = conn.execute('SELECT * FROM employees WHERE id = ?', (eid,)).fetchone()
    conn.close()
    if not row:
        return jsonify({'error': 'Not found'}), 404
    return jsonify(dict(row))

@app.route('/api/employees', methods=['POST'])
def create_employee():
    d = request.json
    conn = get_db()
    cur = conn.execute(
        '''INSERT INTO employees (emp_code, bu, bu_code, department, name, nickname, position, email, phone, start_date, status, note)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?)''',
        (d.get('emp_code'), d.get('bu'), d.get('bu_code'), d.get('department'), d['name'],
         d.get('nickname'), d.get('position'), d.get('email'), d.get('phone'),
         d.get('start_date'), d.get('status', 'active'), d.get('note'))
    )
    conn.commit()
    row = conn.execute('SELECT * FROM employees WHERE id = ?', (cur.lastrowid,)).fetchone()
    conn.close()
    return jsonify(dict(row)), 201

@app.route('/api/employees/<int:eid>', methods=['PUT'])
def update_employee(eid):
    d = request.json
    conn = get_db()
    conn.execute(
        '''UPDATE employees SET emp_code=?, bu=?, bu_code=?, department=?, name=?, nickname=?, position=?,
           email=?, phone=?, start_date=?, status=?, note=?, updated_at=datetime('now','localtime')
           WHERE id=?''',
        (d.get('emp_code'), d.get('bu'), d.get('bu_code'), d.get('department'), d['name'],
         d.get('nickname'), d.get('position'), d.get('email'), d.get('phone'),
         d.get('start_date'), d.get('status', 'active'), d.get('note'), eid)
    )
    conn.commit()
    row = conn.execute('SELECT * FROM employees WHERE id = ?', (eid,)).fetchone()
    conn.close()
    return jsonify(dict(row))

@app.route('/api/employees/<int:eid>', methods=['DELETE'])
def delete_employee(eid):
    conn = get_db()
    conn.execute('DELETE FROM employees WHERE id = ?', (eid,))
    conn.commit()
    conn.close()
    return jsonify({'ok': True})

@app.route('/api/filters', methods=['GET'])
def get_filters():
    bu = request.args.get('bu', '')
    conn = get_db()
    bus   = conn.execute('SELECT DISTINCT bu_code, bu FROM employees WHERE bu_code != "" ORDER BY bu_code').fetchall()
    if bu:
        depts = conn.execute('SELECT DISTINCT department FROM employees WHERE department != "" AND bu_code = ? ORDER BY department', (bu,)).fetchall()
    else:
        depts = conn.execute('SELECT DISTINCT department FROM employees WHERE department != "" ORDER BY department').fetchall()
    conn.close()
    return jsonify({
        'bus':   [dict(r) for r in bus],
        'depts': [r['department'] for r in depts]
    })

@app.route('/api/stats', methods=['GET'])
def get_stats():
    conn = get_db()
    total    = conn.execute("SELECT COUNT(*) FROM employees").fetchone()[0]
    active   = conn.execute("SELECT COUNT(*) FROM employees WHERE status='active'").fetchone()[0]
    by_bu    = conn.execute("SELECT bu_code, bu, COUNT(*) as cnt FROM employees GROUP BY bu_code ORDER BY cnt DESC").fetchall()
    by_dept  = conn.execute("SELECT department, COUNT(*) as cnt FROM employees GROUP BY department ORDER BY cnt DESC LIMIT 10").fetchall()
    conn.close()
    return jsonify({
        'total': total,
        'active': active,
        'by_bu':   [dict(r) for r in by_bu],
        'by_dept': [dict(r) for r in by_dept]
    })

@app.route('/api/export/excel', methods=['GET'])
def export_excel():
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment

    q    = request.args.get('q', '').strip()
    bu   = request.args.get('bu', '')
    dept = request.args.get('dept', '')

    where, params = [], []
    if q:
        where.append("(name LIKE ? OR nickname LIKE ? OR position LIKE ? OR department LIKE ?)")
        params += [f'%{q}%'] * 4
    if bu:
        where.append("bu_code = ?"); params.append(bu)
    if dept:
        where.append("department = ?"); params.append(dept)

    sql_where = ('WHERE ' + ' AND '.join(where)) if where else ''
    conn = get_db()
    rows = conn.execute(
        f'SELECT * FROM employees {sql_where} ORDER BY bu_code, department, name', params
    ).fetchall()
    conn.close()

    wb = Workbook()
    ws = wb.active
    ws.title = "รายชื่อพนักงาน"

    headers = ['ID', 'BU Code', 'Business Unit', 'แผนก', 'ชื่อ-นามสกุล', 'ชื่อเล่น',
               'ตำแหน่ง', 'Email', 'เบอร์โทร', 'วันเริ่มงาน', 'สถานะ', 'หมายเหตุ']
    ws.append(headers)
    hdr_fill = PatternFill('solid', fgColor='1E3A5F')
    for cell in ws[1]:
        cell.font = Font(color='FFFFFF', bold=True)
        cell.fill = hdr_fill
        cell.alignment = Alignment(horizontal='center')

    for r in rows:
        ws.append([r['id'], r['bu_code'], r['bu'], r['department'], r['name'],
                   r['nickname'], r['position'], r['email'], r['phone'],
                   r['start_date'], r['status'], r['note']])

    for col in ws.columns:
        ws.column_dimensions[col[0].column_letter].width = max(len(str(col[0].value or '')), 12)

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    filename = f"employees_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    return send_file(buf, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                     as_attachment=True, download_name=filename)

@app.route('/api/import/excel', methods=['POST'])
def import_excel():
    from openpyxl import load_workbook
    f = request.files.get('file')
    if not f:
        return jsonify({'error': 'No file'}), 400

    wb = load_workbook(f)
    ws = wb.active
    headers = [str(c.value or '').strip() for c in ws[1]]

    col_map = {
        'ชื่อ-นามสกุล': 'name', 'ชื่อเล่น': 'nickname', 'ตำแหน่ง': 'position',
        'แผนก': 'department', 'Business Unit': 'bu', 'BU Code': 'bu_code',
        'Email': 'email', 'เบอร์โทร': 'phone', 'วันเริ่มงาน': 'start_date',
        'สถานะ': 'status', 'หมายเหตุ': 'note'
    }

    added, skipped = 0, 0
    conn = get_db()
    for row in ws.iter_rows(min_row=2, values_only=True):
        d = {col_map.get(headers[i]): (str(v).strip() if v is not None else '') for i, v in enumerate(row) if headers[i] in col_map}
        if not d.get('name'):
            skipped += 1; continue
        conn.execute(
            '''INSERT INTO employees (bu, bu_code, department, name, nickname, position, email, phone, start_date, status, note)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)''',
            (d.get('bu'), d.get('bu_code'), d.get('department'), d['name'],
             d.get('nickname'), d.get('position'), d.get('email'), d.get('phone'),
             d.get('start_date'), d.get('status', 'active'), d.get('note'))
        )
        added += 1
    conn.commit()
    conn.close()
    return jsonify({'added': added, 'skipped': skipped})

# ---------- IT Assets (Google Sheets) ----------

SHEETS_ID         = '***REMOVED-SHEETS_ID***'
SHEETS_URL        = f'https://docs.google.com/spreadsheets/d/{SHEETS_ID}/export?format=csv'
SHEETS_SCRIPT_URL = 'https://script.google.com/macros/s/AKfycbwRYfZAOADCUx9ClgcmsKZgNQCd4Ym12quCO-fiMboQnmwpzEl_641wKKuRJHqy7lXU/exec'
CACHE_TTL  = 1800  # 30 min

_asset_cache = {'data': None, 'ts': 0}

def _load_edevice_list():
    """โหลด edevice_assets.json แบบ lenient — คืน list of dicts."""
    if not os.path.exists(EDEVICE_JSON):
        return []
    try:
        with open(EDEVICE_JSON, encoding='utf-8', errors='replace') as f:
            return json.load(f)
    except Exception:
        raw = open(EDEVICE_JSON, encoding='utf-8', errors='replace').read()
        assets = []
        for obj in re.findall(r'\{[^{}]+\}', raw, re.DOTALL):
            try:
                assets.append(json.loads(obj))
            except Exception:
                pass
        return assets


def fetch_assets_raw(force=False):
    now = time.time()
    if not force and _asset_cache['data'] and now - _asset_cache['ts'] < CACHE_TTL:
        return _asset_cache['data']

    today = date.today()

    # --- Step 1: eDevice เป็น base ---
    edevice_list = _load_edevice_list()

    # --- Step 2: Google Sheets → lookup by S/N เพื่อเอาข้อมูลสัญญา ---
    sheets_sn_map = {}   # serial_no.upper() → row dict
    try:
        resp = req_lib.get(SHEETS_URL, allow_redirects=True, timeout=15)
        resp.raise_for_status()
        resp.encoding = 'utf-8'
        for row in csv.DictReader(io.StringIO(resp.text)):
            sn = (row.get('Serial Number') or '').strip().upper()
            an = (row.get('Asset number') or '').strip()
            if sn and an:
                sheets_sn_map[sn] = row
    except Exception:
        pass

    # --- Step 3: Employee lookup from DB ---
    conn = get_db()
    emp_rows = conn.execute('SELECT id, emp_code, name, bu, bu_code, department, position FROM employees').fetchall()
    conn.close()
    emp_code_lookup    = {}
    emp_name_lookup    = {}   # full name → emp
    emp_fname_lookup   = {}   # ชื่อจริง (word 0) → list of emp
    emp_lname_lookup   = {}   # นามสกุล (word -1) → list of emp
    for e in emp_rows:
        if e['emp_code']:
            emp_code_lookup[str(e['emp_code']).strip()] = dict(e)
        key = re.sub(r'\s+', ' ', (e['name'] or '').strip().lower())
        emp_name_lookup[key] = dict(e)
        parts = key.split()
        if parts:
            emp_fname_lookup.setdefault(parts[0], []).append(dict(e))
        if len(parts) > 1:
            emp_lname_lookup.setdefault(parts[-1], []).append(dict(e))

    def match_employee(raw_name, emp_code=None):
        # 1) match by emp_code (reliable)
        if emp_code and str(emp_code).strip():
            hit = emp_code_lookup.get(str(emp_code).strip())
            if hit:
                return hit
        if not raw_name or raw_name.strip().upper() in ('N/A', ''):
            return None

        # ทำความสะอาดชื่อ: ตัด (xxx) ออก, normalize spaces, lower
        clean = re.sub(r'\([^)]*\)', '', raw_name).strip()
        key   = re.sub(r'\s+', ' ', clean.lower())

        # 2) exact full-name match
        hit = emp_name_lookup.get(key)
        if hit:
            return hit

        # 3) fallback: ตรงทั้งชื่อจริง + นามสกุล (ช่วย edge case เว้นวรรคต่าง)
        parts = key.split()
        if len(parts) >= 2:
            fname, lname = parts[0], parts[-1]
            # หาคนที่มีชื่อจริงตรง แล้วกรองนามสกุล
            candidates = emp_fname_lookup.get(fname, [])
            for c in candidates:
                c_parts = re.sub(r'\s+', ' ', (c['name'] or '').lower()).split()
                if c_parts and c_parts[-1] == lname:
                    return c
            # หาคนที่มีนามสกุลตรง แล้วกรองชื่อจริง
            candidates = emp_lname_lookup.get(lname, [])
            for c in candidates:
                c_parts = re.sub(r'\s+', ' ', (c['name'] or '').lower()).split()
                if c_parts and c_parts[0] == fname:
                    return c

        return None

    def parse_date(s):
        if not s or not s.strip():
            return None
        for fmt in ('%m/%d/%Y', '%d/%m/%Y', '%Y-%m-%d'):
            try:
                return datetime.strptime(s.strip(), fmt).date()
            except ValueError:
                pass
        return None

    def parse_money(s):
        if not s:
            return 0.0
        return float(re.sub(r'[^0-9.]', '', s) or 0)

    def contract_status(end_dt):
        if not end_dt:
            return 'unknown'
        delta = (end_dt - today).days
        if delta < 0:    return 'expired'
        if delta <= 90:  return 'critical'
        if delta <= 180: return 'warning'
        return 'ok'

    # S/N ที่มีใน eDevice — ใช้ตรวจว่า Sheets record ถูก cover แล้วหรือยัง
    ed_sn_set = {(a.get('serial_no') or '').strip().upper() for a in edevice_list if (a.get('serial_no') or '').strip()}

    def make_record(computer_id, serial_no, a_ed, sh):
        """สร้าง record จาก eDevice (a_ed) + Sheets (sh) — ฝั่งใดไม่มีใส่ None"""
        is_rental = computer_id.upper().startswith('R') if computer_id else False
        asset_no  = (sh.get('Asset number') or '').strip() if sh else computer_id

        end_dt      = parse_date(sh.get('End date', ''))      if sh else None
        start_dt    = parse_date(sh.get('Start date', ''))    if sh else None
        returned    = (sh.get('Returned') or '').strip()      if sh else ''
        is_returned = bool(returned)
        monthly     = parse_money(sh.get('Monthly Charge', '')) if sh else parse_money((a_ed or {}).get('monthly_rent', ''))
        days_remaining = (end_dt - today).days if end_dt else None

        if a_ed:
            ed_emp_code  = (a_ed.get('emp_code') or '').strip()
            ed_emp_name  = (a_ed.get('emp_name') or '').strip()
            emp          = match_employee(ed_emp_name, ed_emp_code)
            raw_device_type = (a_ed.get('device_type') or '').strip()
            _DEVICE_NORM = {
                'desktop,pc': 'Desktop', 'desktop': 'Desktop',
                'notebook':   'Notebook',
            }
            if a_ed.get('is_mac'):
                # Mac: ownership มาจาก radio button (mac_ownership) ที่ parser แยกไว้
                ownership = (a_ed.get('mac_ownership') or '').strip()
                device_type_clean = _DEVICE_NORM.get(raw_device_type.lower(), raw_device_type)
            else:
                # PC: ownership ฝังอยู่ใน device_type เช่น 'NoteBook เช่า'
                ownership = ''
                device_type_clean = raw_device_type
                for kw in ('เช่า', 'ซื้อ'):
                    if kw in raw_device_type:
                        ownership = kw
                        device_type_clean = raw_device_type.replace(kw, '').strip()
                        break
                device_type_clean = _DEVICE_NORM.get(device_type_clean.lower(), device_type_clean)
            brand      = (a_ed.get('brand') or '').strip()
            # dept จาก eDevice (ฝ่าย/แผนก ที่บันทึกใน eDevice โดยตรง)
            ed_dept    = (a_ed.get('section') or a_ed.get('department') or '').strip()
            user_name  = ed_emp_name
            ed_status  = (a_ed.get('status') or '').strip()
            # BU จาก eDevice (ทรัพย์สิน BU) — ใช้เป็น fallback เมื่อ HR lookup ไม่เจอ
            ed_bu_code = (a_ed.get('bu_code') or '').strip()
            ed_bu      = ''   # ชื่อเต็มไม่จำเป็น
            # ── ส่วนกลาง detection ───────────────────────────────────
            # 1) central_type จาก radio button (หลัง re-sync)
            # 2) fallback: eDevice มีข้อมูลแต่ไม่มีชื่อพนักงานและรหัสพนักงาน → ส่วนกลาง
            _central_type = (a_ed.get('central_type') or '').strip()
            is_central = (
                _central_type == 'ส่วนกลาง'
                or (not _central_type and not ed_emp_name and not ed_emp_code)
            )
            if is_central:
                user_name = 'ส่วนกลาง'
                emp = None   # ไม่มีพนักงานเป็นเจ้าของ
        else:
            # Sheets-only: ไม่มีข้อมูล eDevice
            emp        = match_employee(sh.get('ชื่อ-สกุล', '') if sh else '')
            _sh_dt = (sh.get('Group description') or '').strip() if sh else ''
            _DEVICE_NORM = {'desktop,pc': 'Desktop', 'desktop': 'Desktop', 'notebook': 'Notebook'}
            device_type_clean = _DEVICE_NORM.get(_sh_dt.lower(), _sh_dt)
            ownership  = 'เช่า'   # Sheets-only = เครื่องเช่าทั้งหมด
            brand      = (sh.get('Brand') or '').strip() if sh else ''
            ed_dept    = (sh.get('Department') or sh.get('แผนก') or '').strip() if sh else ''
            user_name  = (sh.get('ชื่อ-สกุล') or '').strip() if sh else ''
            ed_status  = ''
            ed_bu_code = ''
            ed_bu      = ''
            is_central = False

        # ── Ownership fallback + flag ─────────────────────────────────
        # ownership_needs_update: eDevice มีข้อมูลแต่ไม่ได้ระบุ เช่า/ซื้อ → ควรไปแก้ใน eDevice
        # ownership_missing_edevice: ไม่มีข้อมูลใน eDevice เลย (Sheets-only) → ควรไปเพิ่มใน eDevice
        ownership_needs_update    = False   # case 1: eDevice ไม่ระบุ ownership
        ownership_missing_edevice = False   # case 2: Sheets-only ไม่มีใน eDevice

        if a_ed and not ownership:
            ownership = 'เช่า'   # infer จาก Sheets หรือ naming convention
            ownership_needs_update = True   # แจ้งเตือนให้ไประบุใน eDevice
        elif not a_ed and sh:
            ownership_missing_edevice = True  # ไม่มีใน eDevice เลย

        # ── BU / Dept resolution ────────────────────────────────────
        # Priority: HR lookup → eDevice bu_code → ว่าง
        final_bu_code = (emp['bu_code']    if emp else '') or ed_bu_code
        final_bu      = (emp['bu']         if emp else '') or ed_bu
        final_dept    = (emp['department'] if emp else '') or ed_dept
        final_position= (emp['position']   if emp else '') or ''

        # ── eDevice status → ผล logic ──────────────────────────────
        # Return  → คืนเครื่องแล้ว (override contract_status เป็น returned)
        # Expire  → หมดสัญญาแล้ว (ยืนยัน expired แม้ Sheets ไม่มีวันที่)
        # Spare   → เครื่องสำรอง (ไม่มีผู้ใช้ — แยกแสดงได้)

        # Sheets-only + Monthly Charge = 0 → ถือว่าคืนแล้ว (ไม่เคยบันทึกใน eDevice)
        if ownership_missing_edevice and monthly == 0:
            ed_status = 'Return'

        ed_status_norm = ed_status.lower()
        if ed_status_norm == 'return':
            _contract_status = 'returned'
        elif ed_status_norm == 'expire' and not end_dt:
            # eDevice บอก expire แต่ Sheets ไม่มีวันที่ → ถือว่า expired
            _contract_status = 'expired'
        else:
            _contract_status = 'returned' if is_returned else contract_status(end_dt)

        return {
            'asset_no':        asset_no,
            'computer_id':     computer_id,
            'is_rental':       is_rental,
            'serial_no':       serial_no,
            'asset_type':      device_type_clean,
            'ownership':       ownership,
            'brand':           brand,
            'model':           (sh.get('Model') or '').strip() if sh else brand,
            'user_name':       user_name,
            'dept_sheet':      ed_dept,
            'monthly_charge':  monthly,
            'start_date':      start_dt.isoformat() if start_dt else '',
            'end_date':        end_dt.isoformat()   if end_dt   else '',
            'days_remaining':  days_remaining,
            'contract_status': _contract_status,
            'edevice_status':  ed_status,          # Active/Expire/Return/Spare/Error
            'po_no':           (sh.get('Purchase Order No.') or '').strip() if sh else '',
            'returned':        returned,
            'customer_code':   (sh.get('Customer') or '').strip()      if sh else '',
            'customer_name':   (sh.get('Customer Name') or '').strip() if sh else '',
            'sub_asset':       '',
            'sheets_matched':           bool(sh),
            'edevice_matched':          bool(a_ed),
            'ownership_needs_update':   ownership_needs_update,     # มีใน eDevice แต่ไม่ระบุ เช่า/ซื้อ
            'ownership_missing_edevice':ownership_missing_edevice,  # ไม่มีใน eDevice เลย
            'is_central':      is_central,     # เครื่องที่เป็น "ส่วนกลาง" ใน eDevice
            'employee_id':     emp['id']   if emp else None,
            'emp_bu':          final_bu,
            'emp_bu_code':     final_bu_code,
            'emp_dept':        final_dept,
            'emp_position':    final_position,
            # flag ว่า BU/dept มาจากแหล่งไหน (เพื่อ debug / anomaly panel)
            'bu_source':       'hr' if (emp and emp['bu_code']) else ('edevice' if ed_bu_code else ''),
            'dept_source':     'hr' if (emp and emp['department']) else ('edevice' if ed_dept else 'sheets'),
        }

    results = []

    # --- Pass 1: eDevice records (join Sheets ถ้า S/N ตรง) ---
    for a in edevice_list:
        computer_id = (a.get('computer_id') or '').strip()
        if not computer_id:
            continue
        serial_no = (a.get('serial_no') or '').strip()
        sh = sheets_sn_map.get(serial_no.upper()) if serial_no else None
        results.append(make_record(computer_id, serial_no, a, sh))

    # --- Pass 2: Sheets records ที่ S/N ไม่มีใน eDevice เลย (ไม่ให้หาย) ---
    seen_asset_nos = {r['asset_no'] for r in results}
    for sn_upper, sh in sheets_sn_map.items():
        if sn_upper not in ed_sn_set:
            an = (sh.get('Asset number') or '').strip()
            if an and an not in seen_asset_nos:
                sn = (sh.get('Serial Number') or '').strip()
                results.append(make_record('', sn, None, sh))

    # --- Step 4: merge asset_notes + asset_assignments จาก SQLite ---
    conn = get_db()
    note_rows   = conn.execute('SELECT asset_no, resolution, note FROM asset_notes').fetchall()
    assign_rows = conn.execute(
        '''SELECT aa.asset_no, aa.employee_id, aa.note as assign_note,
                  e.name, e.bu, e.bu_code, e.department
           FROM asset_assignments aa
           LEFT JOIN employees e ON e.id = aa.employee_id'''
    ).fetchall()
    conn.close()

    notes_map  = {r['asset_no']: dict(r) for r in note_rows}
    assign_map = {r['asset_no']: dict(r) for r in assign_rows}

    for r in results:
        n = notes_map.get(r['asset_no'], {})
        r['resolution']      = n.get('resolution', 'pending')
        r['resolution_note'] = n.get('note', '')

        a_db = assign_map.get(r['asset_no'])
        if a_db:
            r['employee_id'] = a_db['employee_id']
            r['user_name']   = a_db['name'] or 'IT Stock' if a_db['employee_id'] else 'IT Stock'
            r['emp_bu']      = a_db['bu']         or ''
            r['emp_bu_code'] = a_db['bu_code']    or ''
            r['emp_dept']    = a_db['department'] or ''
            r['assigned_from'] = 'db'
        else:
            r['assigned_from'] = 'edevice'

    _asset_cache['data'] = results
    _asset_cache['ts']   = now
    return results


@app.route('/api/assets', methods=['GET'])
def list_assets():
    force       = request.args.get('refresh') == '1'
    status_f    = request.args.get('status', '')
    type_f      = request.args.get('type', '')
    position_f  = request.args.get('position', '')
    dept_f      = request.args.get('dept', '')
    customer_f  = request.args.get('customer', '')
    bu_f        = request.args.get('bu', '')
    ownership_f = request.args.get('ownership', '')
    q           = request.args.get('q', '').strip().lower()

    data = fetch_assets_raw(force)

    # ส่ง returned ด้วย — ให้ frontend เป็นคนตัดสินใจซ่อน/แสดง (checkbox "ซ่อน Return")
    rows = list(data)

    if status_f:
        rows = [r for r in rows if r['contract_status'] == status_f]
    if type_f:
        _TYPE_NORM = {'desktop,pc': 'Desktop', 'desktop': 'Desktop', 'notebook': 'Notebook'}
        type_norm = _TYPE_NORM.get(type_f.lower(), type_f)
        rows = [r for r in rows if _TYPE_NORM.get(r['asset_type'].lower(), r['asset_type']) == type_norm]
    if position_f:
        rows = [r for r in rows if r.get('emp_position') == position_f]
    if dept_f:
        rows = [r for r in rows if r.get('emp_dept') == dept_f]
    if customer_f:
        rows = [r for r in rows if r['customer_code'] == customer_f]
    if bu_f:
        rows = [r for r in rows if r['emp_bu_code'] == bu_f]
    if ownership_f:
        rows = [r for r in rows if r.get('ownership') == ownership_f]
    if q:
        rows = [r for r in rows if
                q in r['user_name'].lower() or
                q in r['model'].lower() or
                q in r['serial_no'].lower() or
                q in r['asset_no'].lower() or
                q in r['computer_id'].lower()]

    rows.sort(key=lambda r: (r['days_remaining'] is None, r['days_remaining'] or 0))

    total_monthly = sum(r['monthly_charge'] for r in rows)
    status_counts = {}
    for r in rows:
        status_counts[r['contract_status']] = status_counts.get(r['contract_status'], 0) + 1

    cached_at = datetime.fromtimestamp(_asset_cache['ts']).strftime('%d/%m/%Y %H:%M') if _asset_cache['ts'] else ''

    return jsonify({
        'total': len(rows),
        'total_monthly': total_monthly,
        'status_counts': status_counts,
        'cached_at': cached_at,
        'assets': rows
    })


@app.route('/api/assets/employee-map', methods=['GET'])
def asset_employee_map():
    """Return {employee_id: count} for employees who have assets."""
    all_assets = fetch_assets_raw()
    count_map = {}
    for a in all_assets:
        if a['contract_status'] == 'returned':
            continue
        eid = a.get('employee_id')
        if eid:
            count_map[str(eid)] = count_map.get(str(eid), 0) + 1
    return jsonify(count_map)

@app.route('/api/employees/<int:eid>/assets', methods=['GET'])
def employee_assets(eid):
    """Return all assets currently assigned to this employee."""
    conn = get_db()
    emp = conn.execute('SELECT name FROM employees WHERE id=?', (eid,)).fetchone()
    db_assets = conn.execute(
        'SELECT asset_no FROM asset_assignments WHERE employee_id=?', (eid,)
    ).fetchall()
    conn.close()

    db_asset_nos = {r['asset_no'] for r in db_assets}
    all_assets   = fetch_assets_raw()

    emp_name = re.sub(r'\s+', ' ', (emp['name'] if emp else '').strip().lower())

    matched = []
    seen    = set()
    for a in all_assets:
        if a['contract_status'] == 'returned':
            continue
        key = a['asset_no'] or a['computer_id'] or a['serial_no']

        # 1) match จาก asset_assignments (manual assign)
        if a['asset_no'] in db_asset_nos:
            if key not in seen:
                matched.append(a); seen.add(key)
            continue

        # 2) match จาก employee_id (eDevice emp_code → HR lookup)
        if a.get('employee_id') == eid:
            if key not in seen:
                matched.append(a); seen.add(key)
            continue

        # 3) fallback: match ชื่อจาก Sheets
        if a.get('assigned_from') == 'sheets' and emp_name:
            sheet_name = re.sub(r'\s+', ' ', re.sub(r'\([^)]*\)', '', a['user_name']).strip().lower())
            if sheet_name == emp_name and key not in seen:
                matched.append(a); seen.add(key)

    return jsonify(matched)


@app.route('/api/assets/transfer-bulk', methods=['POST'])
def transfer_bulk():
    """
    Bulk transfer assets when employee goes inactive.
    Body: { from_employee_id, transfers: [{asset_no, to_type: 'stock'|'employee', to_employee_id}] }
    """
    d             = request.json
    from_emp_id   = d.get('from_employee_id')
    transfers     = d.get('transfers', [])

    conn = get_db()
    for t in transfers:
        asset_no      = t['asset_no']
        to_type       = t['to_type']          # 'stock' or 'employee'
        to_emp_id     = t.get('to_employee_id')  # None if stock
        note          = t.get('note', '')

        # upsert assignment
        conn.execute(
            '''INSERT INTO asset_assignments (asset_no, employee_id, note, created_at)
               VALUES (?, ?, ?, datetime('now','localtime'))
               ON CONFLICT(asset_no) DO UPDATE SET
                 employee_id=excluded.employee_id,
                 note=excluded.note,
                 created_at=excluded.created_at''',
            (asset_no, to_emp_id, note)
        )
        # log history
        conn.execute(
            '''INSERT INTO asset_transfer_log
               (asset_no, from_employee_id, to_employee_id, transfer_type, note)
               VALUES (?, ?, ?, ?, ?)''',
            (asset_no, from_emp_id, to_emp_id,
             'to_stock' if to_type == 'stock' else 'to_employee', note)
        )

    conn.commit()
    conn.close()
    _asset_cache['ts'] = 0   # invalidate cache
    return jsonify({'ok': True, 'transferred': len(transfers)})


@app.route('/api/assets/<asset_no>/resolution', methods=['PUT'])
def update_asset_resolution(asset_no):
    d = request.json
    resolution = d.get('resolution', 'pending')
    note       = d.get('note', '')
    conn = get_db()
    conn.execute(
        '''INSERT INTO asset_notes (asset_no, resolution, note, updated_at)
           VALUES (?, ?, ?, datetime('now','localtime'))
           ON CONFLICT(asset_no) DO UPDATE SET
             resolution=excluded.resolution,
             note=excluded.note,
             updated_at=excluded.updated_at''',
        (asset_no, resolution, note)
    )
    conn.commit()
    conn.close()
    # invalidate cache so next load reflects change
    _asset_cache['ts'] = 0
    return jsonify({'ok': True, 'asset_no': asset_no, 'resolution': resolution})

@app.route('/api/dashboard/rental', methods=['GET'])
def dashboard_rental():
    """สถิติเครื่องเช่าสำหรับ Dashboard."""
    from collections import defaultdict

    data = fetch_assets_raw()

    def is_rental(r):
        # ownership = 'เช่า' ครอบทั้ง eDevice และ Sheets-only แล้ว
        return r.get('ownership') == 'เช่า'

    # resolution ที่ถือว่า "ดำเนินการแล้ว" → ซ่อนจาก dashboard
    RESOLVED = {'returned', 'bought', 'renewed', 'extended'}

    # eDevice status ที่ซ่อนจาก dashboard rental
    # - Return  → contract_status = 'returned' แล้ว (กรองออกโดย condition ด้านล่าง)
    # - Spare   → เครื่องสำรอง ไม่มีผู้ใช้งาน ไม่นับในสถิติเช่า
    ED_SKIP = {'spare'}

    rentals = [r for r in data
               if is_rental(r)
               and r['contract_status'] != 'returned'
               and r.get('resolution', 'pending') not in RESOLVED
               and (r.get('edevice_status') or '').lower() not in ED_SKIP]

    today = date.today()

    # summary — นับจาก all_assets (raw) เพื่อให้ card แสดงยอดรวมจริง
    by_status = defaultdict(int)
    # ed_expire: ทุกเครื่อง (ซื้อ+เช่า) ที่ eDevice = Expire
    ed_expire_count = sum(
        1 for r in data
        if (r.get('edevice_status') or '').lower() == 'expire'
        and r['contract_status'] != 'returned'
    )
    by_status['ed_expire'] = ed_expire_count
    # สถานะสัญญาเช่า (ไม่นับเครื่องที่ eDevice = Expire แล้ว)
    # unknown: ยกเว้น ownership_needs_update เพราะอยู่ใน panel "ยังไม่ระบุ เช่า/ซื้อ" แทน
    for r in rentals:
        if (r.get('edevice_status') or '').lower() == 'expire':
            continue   # นับใน ed_expire แล้ว
        cs = r['contract_status']
        if cs == 'unknown' and r.get('ownership_needs_update'):
            continue   # ไม่นับใน card ไม่มีข้อมูลสัญญา
        if cs == 'unknown' and r.get('is_central'):
            continue   # ส่วนกลาง = stock ปกติ ไม่นับเป็น anomaly
        by_status[cs] += 1

    total_monthly = sum(r['monthly_charge'] for r in rentals)

    # แยก BU
    bu_map = defaultdict(lambda: {'count': 0, 'monthly': 0.0})
    for r in rentals:
        code = r['emp_bu_code'] or '—'
        bu_map[code]['count']   += 1
        bu_map[code]['monthly'] += r['monthly_charge']
    by_bu = sorted(
        [{'bu_code': k, 'count': v['count'], 'monthly': v['monthly']} for k, v in bu_map.items()],
        key=lambda x: -x['count']
    )

    # แผนกทั้งหมด เรียงตามจำนวนเครื่อง
    dept_map = defaultdict(int)
    for r in rentals:
        dept = r['emp_dept'] or r['dept_sheet'] or '—'
        dept_map[dept] += 1
    by_dept = sorted(
        [{'dept': k, 'count': v} for k, v in dept_map.items()],
        key=lambda x: -x['count']
    )

    # timeline: สัญญาหมดรายเดือน แยก BU
    # timeline_by_bu = { bu_code: { ym: count } }
    all_months = set()
    bu_month_map = defaultdict(lambda: defaultdict(int))
    timeline_map  = defaultdict(lambda: {'count': 0, 'monthly': 0.0})
    for r in rentals:
        if not r['end_date']:
            continue
        ym   = r['end_date'][:7]
        bu   = r['emp_bu_code'] or '—'
        all_months.add(ym)
        bu_month_map[bu][ym]        += 1
        timeline_map[ym]['count']   += 1
        timeline_map[ym]['monthly'] += r['monthly_charge']

    sorted_months = sorted(all_months)
    # รายการ BU ที่มีใน timeline (เรียงตาม total มาก→น้อย)
    bu_totals = {bu: sum(m.values()) for bu, m in bu_month_map.items()}
    timeline_bus = sorted(bu_totals, key=lambda b: -bu_totals[b])
    # สร้าง timeline_by_bu: list of { bu_code, months: [{month, count}] }
    timeline_by_bu = [
        {
            'bu_code': bu,
            'months': [{'month': ym, 'count': bu_month_map[bu].get(ym, 0)} for ym in sorted_months]
        }
        for bu in timeline_bus
    ]
    timeline = sorted(
        [{'month': k, 'count': v['count'], 'monthly': v['monthly']} for k, v in timeline_map.items()],
        key=lambda x: x['month']
    )

    # urgent: expired + critical (เรียงวันหมดก่อน)
    urgent = sorted(
        [r for r in rentals if r['contract_status'] in ('expired', 'critical')],
        key=lambda x: (x['days_remaining'] is None, x['days_remaining'] or 0)
    )
    urgent_out = [{
        'asset_no':       r['asset_no'],
        'computer_id':    r['computer_id'],
        'serial_no':      r['serial_no'],
        'asset_type':     r.get('asset_type', ''),
        'model':          r['model'],
        'brand':          r['brand'],
        'ownership':      r.get('ownership', ''),
        'ownership_needs_update':    r.get('ownership_needs_update', False),
        'ownership_missing_edevice': r.get('ownership_missing_edevice', False),
        'user_name':      r['user_name'],
        'emp_bu_code':    r['emp_bu_code'],
        'emp_dept':       r['emp_dept'] or r['dept_sheet'],
        'start_date':     r['start_date'],
        'end_date':       r['end_date'],
        'days_remaining': r['days_remaining'],
        'contract_status':   r['contract_status'],
        'monthly_charge':    r['monthly_charge'],
        'resolution':        r.get('resolution', 'pending'),
        'edevice_status':    r.get('edevice_status', ''),
        'sheets_matched':    r.get('sheets_matched', False),
    } for r in urgent]

    # ---- anomaly: เครื่องเช่าที่ไม่มีข้อมูลสัญญา (status=unknown) ----
    def _mini(r):
        return {
            'asset_no':       r['asset_no'],
            'computer_id':    r['computer_id'],
            'serial_no':      r['serial_no'],
            'brand':          r['brand'],
            'model':          r['model'],
            'asset_type':     r.get('asset_type', ''),
            'ownership':      r.get('ownership', ''),
            'user_name':      r['user_name'],
            'employee_id':    r.get('employee_id'),
            'emp_bu_code':    r['emp_bu_code'],
            'emp_dept':       r['emp_dept'],
            'monthly_charge': r['monthly_charge'],
            'start_date':     r['start_date'],
            'end_date':       r['end_date'],
            'days_remaining': r['days_remaining'],
            'contract_status':r['contract_status'],
            'edevice_status': r.get('edevice_status', ''),
            'sheets_matched':  r.get('sheets_matched', False),
            'edevice_matched': r.get('edevice_matched', False),
            'ownership_needs_update':    r.get('ownership_needs_update', False),
            'ownership_missing_edevice': r.get('ownership_missing_edevice', False),
            'is_central':                r.get('is_central', False),
        }

    # no_contract = เช่าที่ไม่มีข้อมูลสัญญา แต่ยกเว้น ownership_needs_update
    # (กลุ่มนั้นมีปัญหา ownership ก่อน ควรแก้ใน eDevice ก่อน → อยู่ใน panel needs_update แทน)
    no_contract = [_mini(r) for r in rentals
                   if r['contract_status'] == 'unknown'
                   and not r.get('ownership_needs_update')
                   and not r.get('is_central')]   # ส่วนกลาง = stock ไม่มีสัญญาเป็นเรื่องปกติ
    no_contract.sort(key=lambda x: (x['emp_bu_code'] or '่', x['emp_dept'] or '่'))

    # ---- anomaly: เครื่องเช่าที่ไม่มี BU (จากทั้ง HR + eDevice) ----
    # หลังจากปรับ logic ให้ eDevice bu_code เป็น fallback แล้ว
    # no_bu = เครื่องที่ยังหา BU ไม่เจอจากทั้งสองแหล่ง
    no_bu_list = [r for r in rentals if not r['emp_bu_code']]
    no_bu = []
    for r in sorted(no_bu_list, key=lambda x: x['computer_id'] or ''):
        m = _mini(r)
        m['has_dept']   = bool(r['emp_dept'])
        m['bu_source']  = r.get('bu_source', '')
        m['dept_source']= r.get('dept_source', '')
        no_bu.append(m)

    # rental_index: { "YYYY-MM|bu_code": [mini records] } — สำหรับ expand แท่ง timeline
    rental_index = defaultdict(list)
    for r in rentals:
        if not r['end_date']:
            continue
        ym  = r['end_date'][:7]
        bu  = r['emp_bu_code'] or '—'
        rental_index[f'{ym}|{bu}'].append({
            'computer_id':    r['computer_id'],
            'asset_no':       r['asset_no'],
            'asset_type':     r.get('asset_type', ''),
            'brand':          r['brand'],
            'model':          r['model'],
            'serial_no':      r['serial_no'],
            'ownership':      r.get('ownership', ''),
            'user_name':      r['user_name'],
            'employee_id':    r.get('employee_id'),
            'emp_bu_code':    r['emp_bu_code'],
            'emp_dept':       r['emp_dept'] or r.get('dept_sheet', ''),
            'end_date':       r['end_date'],
            'days_remaining': r['days_remaining'],
            'contract_status': r['contract_status'],
            'monthly_charge': r['monthly_charge'],
            'edevice_status': r.get('edevice_status', ''),
            'sheets_matched':  r.get('sheets_matched', False),
            'edevice_matched': r.get('edevice_matched', False),
            'ownership_needs_update':    r.get('ownership_needs_update', False),
            'ownership_missing_edevice': r.get('ownership_missing_edevice', False),
            'is_central':                r.get('is_central', False),
        })
        rental_index[f'{ym}|ALL'].append(rental_index[f'{ym}|{bu}'][-1])

    # ---- anomaly: ยังไม่บันทึกใน eDevice (Sheets-only, ownership_missing_edevice) ----
    all_assets = fetch_assets_raw()
    missing_edevice = [_mini(r) for r in all_assets
                       if r.get('ownership_missing_edevice')
                       and r['contract_status'] != 'returned']
    missing_edevice.sort(key=lambda x: (x['emp_bu_code'] or '่', x['emp_dept'] or '่'))

    # ---- anomaly: eDevice ไม่ระบุการถือครอง (ownership_needs_update) ----
    needs_update = [_mini(r) for r in all_assets if r.get('ownership_needs_update')]
    needs_update.sort(key=lambda x: (x['emp_bu_code'] or '่', x['emp_dept'] or '่'))

    return jsonify({
        'total_rental':   len(rentals),
        'total_monthly':  total_monthly,
        'by_status':      dict(by_status),
        'by_bu':          by_bu,
        'by_dept':        by_dept,
        'timeline':       timeline,
        'timeline_by_bu': timeline_by_bu,
        'rental_index':   dict(rental_index),
        'urgent':         urgent_out,
        'no_contract':    no_contract,
        'no_bu':          no_bu,
        'missing_edevice': missing_edevice,
        'needs_update':    needs_update,
    })


@app.route('/api/assets/meta', methods=['GET'])
def asset_meta():
    data = fetch_assets_raw()
    active = [r for r in data if r['contract_status'] != 'returned']
    _TYPE_NORM = {
        'desktop,pc': 'Desktop', 'desktop': 'Desktop',
        'notebook':   'Notebook',
    }
    customers = {}
    types     = set()
    positions = set()
    depts     = set()
    for r in active:
        customers[r['customer_code']] = r['customer_name']
        t = r['asset_type']
        if t:
            types.add(_TYPE_NORM.get(t.lower(), t))
        p = r.get('emp_position', '')
        if p:
            positions.add(p)
        d = r.get('emp_dept', '')
        if d:
            depts.add(d)
    return jsonify({
        'customers':  [{'code': k, 'name': v} for k, v in customers.items()],
        'types':      sorted(types),
        'positions':  sorted(positions),
        'depts':      sorted(depts),
    })


@app.route('/api/sheets/update-info', methods=['POST'])
def sheets_update_info():
    """อัพเดท ชื่อ-สกุล / ฝ่าย / แผนก กลับไปใน Google Sheets ผ่าน Apps Script"""
    try:
        data = fetch_assets_raw()
    except Exception as e:
        return jsonify({'ok': False, 'error': f'โหลด asset ไม่ได้: {e}'}), 500

    # โหลด eDevice เพื่อดึง section (ฝ่าย) ซึ่งไม่ได้ expose ใน asset record ปกติ
    ed_section_map = {}   # serial_no.upper() → section
    try:
        for a in fetch_edevice_assets():
            sn_ed = (a.get('serial_no') or '').strip().upper()
            sec   = (a.get('section') or '').strip()
            if sn_ed and sec:
                ed_section_map[sn_ed] = sec
    except Exception:
        pass

    updates = []
    skipped = []
    for r in data:
        sn = (r.get('serial_no') or '').strip()
        if not sn or not r.get('sheets_matched'):
            continue   # เฉพาะ record ที่มีใน Sheets เท่านั้น

        name     = (r.get('user_name') or '').strip()
        dept     = (r.get('emp_dept') or '').strip()          # แผนก จาก HR
        division = ed_section_map.get(sn.upper(), '')         # ฝ่าย จาก eDevice section
        if not division:
            division = (r.get('dept_sheet') or '').strip()    # fallback: จาก eDevice dept

        if not name and not dept and not division:
            skipped.append(sn)
            continue

        updates.append({
            'serial':   sn,
            'name':     name,
            'dept':     dept,
            'division': division,
        })

    if not updates:
        return jsonify({'ok': False, 'error': 'ไม่มีข้อมูลที่จะอัพเดท', 'skipped': len(skipped)})

    try:
        import requests as _req
        payload = json.dumps({'updates': updates}).encode('utf-8')
        headers = {'Content-Type': 'application/json'}

        # Google Apps Script doPost flow:
        # Step 1: POST → script รัน → ได้ 302 redirect ไปที่ echo URL
        r1 = _req.post(SHEETS_SCRIPT_URL, data=payload, headers=headers,
                       allow_redirects=False, timeout=30)

        # Step 2: GET echo URL → ดึง response ที่ script return กลับมา
        if r1.status_code in (301, 302, 303) and 'Location' in r1.headers:
            r2 = _req.get(r1.headers['Location'], timeout=30)
            resp_text = r2.text
        else:
            resp_text = r1.text

        result = json.loads(resp_text)
        result['sent']    = len(updates)
        result['skipped'] = len(skipped)
        return jsonify(result)
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e), 'sent': len(updates)}), 500


@app.route('/api/assets/export', methods=['GET'])
def export_assets():
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment, PatternFill
    from openpyxl.utils import get_column_letter

    status_f   = request.args.get('status', '')
    type_f     = request.args.get('type', '')
    customer_f = request.args.get('customer', '')
    bu_f       = request.args.get('bu', '')

    data = fetch_assets_raw()
    rows = [r for r in data if r['contract_status'] != 'returned']
    if status_f:   rows = [r for r in rows if r['contract_status'] == status_f]
    if type_f:     rows = [r for r in rows if r['asset_type'].lower() == type_f.lower()]
    if customer_f: rows = [r for r in rows if r['customer_code'] == customer_f]
    if bu_f:       rows = [r for r in rows if r['emp_bu_code'] == bu_f]
    rows.sort(key=lambda r: (r['days_remaining'] is None, r['days_remaining'] or 0))

    wb = Workbook()
    ws = wb.active
    ws.title = 'IT Assets'

    headers = ['Asset No.', 'S/N', 'ประเภท', 'รุ่น', 'ผู้ถือครอง', 'BU', 'แผนก',
               'บริษัท', 'วันเริ่ม', 'วันหมดสัญญา', 'เหลือ (วัน)', 'สถานะ', 'ค่าเช่า/เดือน', 'PO']
    ws.append(headers)
    hfill = PatternFill('solid', fgColor='1E3A5F')
    for cell in ws[1]:
        cell.font = Font(color='FFFFFF', bold=True)
        cell.fill = hfill
        cell.alignment = Alignment(horizontal='center')

    status_thai = {'ok': 'ปกติ', 'warning': 'ใกล้หมด (180วัน)', 'critical': 'วิกฤต (90วัน)', 'expired': 'หมดแล้ว', 'unknown': 'ไม่ระบุ'}
    for r in rows:
        ws.append([
            r['asset_no'], r['serial_no'], r['asset_type'], r['model'],
            r['user_name'], r['emp_bu_code'] or '', r['emp_dept'] or r['dept_sheet'],
            r['customer_name'], r['start_date'], r['end_date'],
            r['days_remaining'], status_thai.get(r['contract_status'], ''),
            r['monthly_charge'], r['po_no']
        ])

    for col in ws.columns:
        ws.column_dimensions[get_column_letter(col[0].column)].width = max(
            len(str(col[0].value or '')), 10)

    buf = io.BytesIO()
    wb.save(buf); buf.seek(0)
    fname = f"it_assets_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    return send_file(buf, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                     as_attachment=True, download_name=fname)


# ---------- eDevice Sync ----------

EDEVICE_JSON = os.path.join(os.path.dirname(__file__), 'edevice_assets.json')
EDEVICE_LOGIN_URL  = 'http://amarin.intra/webappl/acorporate/index.aspx?s=out'
EDEVICE_CORP_URL   = 'http://www.amarin.intra/webappl/eDevice_ATV/***REMOVED-EDEVICE_INIT_PATH***'
EDEVICE_DETAIL_URL     = 'http://www.amarin.intra/webappl/eDevice_ATV/ComputerDetail.asp?id={}'
EDEVICE_MAC_DETAIL_URL = 'http://www.amarin.intra/webappl/eDevice_ATV/MacintoshDetail.asp?id={}'
EDEVICE_LIST_URL       = 'http://www.amarin.intra/webappl/eDevice_ATV/Computer1.asp'
EDEVICE_MAC_URL        = 'http://www.amarin.intra/webappl/eDevice_ATV/Macintosh.asp'

BU_TH_MAP = {
    'อมรินทร์ทีวี': 'AMTV', 'ออมนิเวิร์ส': 'AOMNI', 'สำนักพิมพ์': 'APUB',
    'อมรินทร์ บุ๊ค': 'ABOOK', 'โรงพิมพ์': 'APRINT', 'ACS': 'ACS',
    'มีเดีย': 'AME', 'อมรินทร์ คอร์': 'ACS',
}

def bu_th_to_code(bu_th):
    for k, v in BU_TH_MAP.items():
        if k in (bu_th or ''):
            return v
    return ''


def _edevice_login():
    """Login and return session + cookies."""
    sess = req_lib.Session()
    r = sess.get(EDEVICE_LOGIN_URL, timeout=15)
    vs = re.search(r'name="__VIEWSTATE" id="__VIEWSTATE" value="([^"]+)"', r.text).group(1)
    ev = re.search(r'name="__EVENTVALIDATION" id="__EVENTVALIDATION" value="([^"]+)"', r.text).group(1)
    sess.post(EDEVICE_LOGIN_URL, data={
        '__VIEWSTATE': vs, '__EVENTVALIDATION': ev,
        'ctl00_ToolkitScriptManager1_HiddenField': '',
        'ctl00$ContentPlaceHolder1$loginauth1$txtlogin': '90004',
        'ctl00$ContentPlaceHolder1$loginauth1$txtpass': '12QWaszx@',
        'ctl00$ContentPlaceHolder1$loginauth1$btnlogin': 'เข้าสู่ระบบ',
    }, timeout=15, allow_redirects=True)
    sess.get(EDEVICE_CORP_URL, timeout=15)
    return dict(sess.cookies)


def _parse_label_value(soup, label_map):
    """Helper: วน <tr> แล้ว match label → value จาก adjacent <td> cells"""
    all_labels = set(label_map.keys())
    data = {}
    for row in soup.find_all('tr'):
        cells = [td.get_text(strip=True).replace('\xa0', ' ') for td in row.find_all('td')]
        for i in range(len(cells) - 1):
            val = cells[i + 1].strip()
            if not val or val.endswith(':') or val in all_labels:
                continue
            for lbl, key in label_map.items():
                if lbl in cells[i] and key not in data:
                    data[key] = val
    return data


def _parse_computer_detail(text, cid):
    """Parse PC detail page (ComputerDetail.asp)"""
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(text, 'html.parser')
    label_map = {
        'รหัสพนักงาน*:':         'emp_code',
        'ชื่อพนักงาน*:':         'emp_name',
        'ฝ่าย :':                'section',
        'แผนก :':                'department',
        'ทรัพย์สิน BU*:':        'bu_th',
        'Serial No.(ผู้ผลิต)*:': 'serial_no',
        'ชื่อคอมพิวเตอร์:':      'computer_name',
        'IP Address:':            'ip',
        'Mac Address:':           'mac',
        'Status:':                'status',
        'ยี่ห้อ:':                'brand',
        'ประเภท*:':               'device_type',
        'วันที่รับสินค้า*:':     'received_date',
        'ราคาเช่าต่อเดือน:':    'monthly_rent',
    }
    data = {'computer_id': cid}
    data.update(_parse_label_value(soup, label_map))
    data['bu_code'] = bu_th_to_code(data.get('bu_th', ''))
    _clean_serial(data)
    # ── Radio button: ทรัพย์สินของ*: (ส่วนบุคคล / ส่วนกลาง) ─────────
    for row in soup.find_all('tr'):
        tds = row.find_all('td')
        for i in range(len(tds) - 1):
            lbl = tds[i].get_text(strip=True).replace('\xa0', ' ')
            if 'ทรัพย์สินของ' in lbl:
                val_td = tds[i + 1]
                for radio in val_td.find_all('input', {'type': 'radio'}):
                    if radio.has_attr('checked'):
                        sibling = radio.next_sibling
                        if sibling:
                            t = str(sibling).strip()
                            if t:
                                data['central_type'] = t
                                break
                        v = radio.get('value', '').strip()
                        if v:
                            data['central_type'] = v
                            break
                break
    return data


def _get_cell_value(td):
    """ดึงค่าจาก <td> — ถ้ามี <select> ให้ดู <option selected>, ถ้ามี <input> ดู value attr"""
    # กรณี select dropdown
    selects = td.find_all('select')
    if selects:
        values = []
        for sel in selects:
            opt = sel.find('option', selected=True)
            if not opt:
                # บางหน้าใช้ selected="" หรือ selected="selected"
                opt = sel.find('option', attrs={'selected': True})
            if not opt and sel.find('option'):
                opt = sel.find_all('option')[0]  # fallback: option แรก
            if opt:
                v = opt.get_text(strip=True).replace('\xa0', ' ')
                if v:
                    values.append(v)
        return values  # คืน list เพราะอาจมีหลาย select
    # กรณี text input
    inp = td.find('input', {'type': ['text', 'hidden']})
    if inp and inp.get('value'):
        return [inp['value'].strip()]
    # กรณี plain text
    txt = td.get_text(strip=True).replace('\xa0', ' ')
    return [txt] if txt else []


def _parse_mac_detail(text, cid):
    """Parse Mac detail page (MacintoshDetail.asp)

    Mac page ใช้ <select> dropdown สำหรับหลาย field
    โดยเฉพาะ row 'ประเภท*:' มี 2 selects: [device_type] [ownership(เช่า/ซื้อ)]
    ต่างจาก PC ที่ ownership ฝังเป็น text ใน device_type
    """
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(text, 'html.parser')

    # label → field mapping (ใช้สำหรับ text fields ปกติ)
    label_map = {
        'รหัสพนักงาน*:':    'emp_code',
        'ชื่อพนักงาน*:':    'emp_name',
        'ฝ่าย :':           'section',
        'แผนก :':           'department',
        'ทรัพย์สิน BU*:':   'bu_th',
        'ทรัพย์สินฝ่าย*:':  'dept_asset',
        'Serial No.*:':      'serial_no',
        'ชื่อเครื่อง :':    'computer_name',
        'ชื่อคอมพิวเตอร์ :':'computer_name',
        'Mac Address :':     'mac',
        'รหัสทรัพย์สิน AMS':'asset_ams',
    }

    # fields ที่มาจาก <select> (single select → ค่าเดียว)
    select_label_map = {
        'Status :':  'status',
        'รุ่น :':    'brand',       # Mac model: MacBookPro, iMac, etc.
    }

    data = {'computer_id': cid, 'is_mac': True}

    for row in soup.find_all('tr'):
        tds = row.find_all('td')
        if len(tds) < 2:
            continue
        for i, td in enumerate(tds[:-1]):
            label = td.get_text(strip=True).replace('\xa0', ' ')
            val_td = tds[i + 1]

            # ── ประเภท / ประเภท*: — device_type + ownership ──
            # Mac detail page แสดงเป็น plain text เช่น "Macbook    ซื้อ"
            # (เหมือน PC ที่ ownership ฝังอยู่ใน device_type text)
            if 'ประเภท' in label and 'device_type' not in data:
                values = _get_cell_value(val_td)
                raw_str = values[0] if values else ''
                _DEVICE_NORM_MAC = {
                    'desktop': 'Desktop', 'notebook': 'Notebook',
                    'macbook': 'MacBook', 'imac': 'iMac', 'mac mini': 'Mac Mini',
                    'macbook pro': 'MacBook', 'macbook air': 'MacBook',
                }
                # แยก ownership ออกจาก device_type (เช่น "Macbook    ซื้อ")
                raw_dt = raw_str
                for kw in ('เช่า', 'ซื้อ'):
                    if kw in raw_str:
                        data['mac_ownership'] = kw
                        raw_dt = raw_str.replace(kw, '').strip()
                        break
                data['device_type'] = _DEVICE_NORM_MAC.get(raw_dt.lower(), raw_dt) or raw_dt
                continue

            # ── select fields ทั่วไป ──
            for lbl, key in select_label_map.items():
                if lbl in label and key not in data:
                    values = _get_cell_value(val_td)
                    if values:
                        data[key] = values[0]

            # ── text fields ทั่วไป ──
            for lbl, key in label_map.items():
                if lbl in label and key not in data:
                    values = _get_cell_value(val_td)
                    if values:
                        # เลือกค่าที่ไม่ใช่ label ตัวเอง
                        for v in values:
                            if v and not v.endswith(':'):
                                data[key] = v
                                break

    data['bu_code'] = bu_th_to_code(data.get('bu_th', ''))
    _clean_serial(data)
    # ── Radio button: ทรัพย์สินของ*: (ส่วนบุคคล / ส่วนกลาง) ─────────
    for row in soup.find_all('tr'):
        tds = row.find_all('td')
        for i in range(len(tds) - 1):
            lbl = tds[i].get_text(strip=True).replace('\xa0', ' ')
            if 'ทรัพย์สินของ' in lbl:
                val_td = tds[i + 1]
                for radio in val_td.find_all('input', {'type': 'radio'}):
                    if radio.has_attr('checked'):
                        sibling = radio.next_sibling
                        if sibling:
                            t = str(sibling).strip()
                            if t:
                                data['central_type'] = t
                                break
                        v = radio.get('value', '').strip()
                        if v:
                            data['central_type'] = v
                            break
                break
    return data


def _clean_serial(data):
    """กรอง serial_no ที่เป็น placeholder หรือ garbage"""
    sn = data.get('serial_no', '')
    if sn and sn.lower() in ('serial', 'serial no', 'serial no.', '-', 'n/a', 'na'):
        data['serial_no'] = ''


def fetch_edevice_assets(force_live=False):
    """Return list of assets from eDevice (cached JSON or live fetch)."""
    import concurrent.futures

    if not force_live and os.path.exists(EDEVICE_JSON):
        try:
            with open(EDEVICE_JSON, encoding='utf-8', errors='replace') as f:
                return json.load(f)
        except Exception:
            pass  # JSON เสีย — fall through ไป live fetch

    # live fetch — ดึง ID จากทั้ง PC (Computer1.asp) และ Mac (Macintosh.asp)
    cookies = _edevice_login()

    def get_ids(url):
        try:
            r = req_lib.get(url, cookies=cookies, timeout=15)
            return re.findall(r"<OPTION value='([^']+)'>[^<]+</Option>",
                              r.content.decode('tis-620', errors='replace'))
        except Exception:
            return []

    pc_ids  = get_ids(EDEVICE_LIST_URL)
    mac_ids = get_ids(EDEVICE_MAC_URL)

    # map: cid → detail_url (PC และ Mac ใช้ endpoint ต่างกัน)
    cid_url_map = {}
    for cid in pc_ids:
        cid_url_map[cid] = EDEVICE_DETAIL_URL.format(cid)
    for cid in mac_ids:
        # Mac ใช้ MacintoshDetail.asp (ไม่ทับกับ PC)
        cid_url_map[cid] = EDEVICE_MAC_DETAIL_URL.format(cid)

    def fetch_one(cid):
        try:
            url  = cid_url_map[cid]
            r2   = req_lib.get(url, cookies=cookies, timeout=12)
            if r2.status_code == 200 and len(r2.content) > 3000:
                text = r2.content.decode('tis-620', errors='replace')
                if cid in mac_ids:
                    rec = _parse_mac_detail(text, cid)   # Mac parser
                else:
                    rec = _parse_computer_detail(text, cid)  # PC parser
                return rec
        except: pass
        return None

    assets = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=15) as ex:
        for result in concurrent.futures.as_completed(
                {ex.submit(fetch_one, cid): cid for cid in cid_url_map}):
            r2 = result.result()
            if r2:
                assets.append(r2)

    with open(EDEVICE_JSON, 'w', encoding='utf-8') as f:
        json.dump(assets, f, ensure_ascii=False, indent=2)
    return assets


@app.route('/api/debug/mac-detail', methods=['GET'])
def debug_mac_detail():
    """Debug: ดู raw label-value pairs จาก MacintoshDetail.asp ของ Mac เครื่องแรก"""
    import json as _json
    try:
        cid = request.args.get('cid', '')
        cookies = _edevice_login()
        if not cid:
            # หา Mac ID แรกจาก Macintosh.asp
            r = req_lib.get(EDEVICE_MAC_URL, cookies=cookies, timeout=15)
            ids = re.findall(r"<OPTION value='([^']+)'>[^<]+</Option>",
                             r.content.decode('tis-620', errors='replace'))
            if not ids:
                return jsonify({'error': 'ไม่พบ Mac ID ใน Macintosh.asp'})
            cid = ids[0]
        url = EDEVICE_MAC_DETAIL_URL.format(cid)
        r2  = req_lib.get(url, cookies=cookies, timeout=12)
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(r2.content.decode('tis-620', errors='replace'), 'html.parser')
        rows_out = []
        for row in soup.find_all('tr'):
            cells = [td.get_text(strip=True).replace('\xa0', ' ') for td in row.find_all('td')]
            if cells:
                rows_out.append(cells)
        return jsonify({'cid': cid, 'url': url, 'rows': rows_out})
    except Exception as e:
        return jsonify({'error': str(e)})


@app.route('/api/sync/edevice/preview', methods=['GET'])
def edevice_preview():
    force = request.args.get('refresh') == '1'
    assets = fetch_edevice_assets(force_live=force)

    conn = get_db()
    emp_rows = conn.execute('SELECT id, emp_code, name, bu_code, department, status FROM employees').fetchall()
    conn.close()

    code_map = {str(e['emp_code']).strip(): dict(e) for e in emp_rows if e['emp_code']}
    name_map = {_norm(e['name']): dict(e) for e in emp_rows}

    stats = {'total': len(assets), 'matched_code': 0, 'matched_name': 0,
             'unmatched': 0, 'inactive_has_asset': 0}
    unmatched, code_updates = [], []

    for a in assets:
        ec = str(a.get('emp_code', '') or '').strip()
        nm = _norm(re.sub(r'\([^)]*\)', '', a.get('emp_name', '') or ''))
        emp = code_map.get(ec) or name_map.get(nm)
        if ec and ec in code_map:
            stats['matched_code'] += 1
        elif nm and nm in name_map:
            stats['matched_name'] += 1
            # found by name but emp_code not set yet → can update emp_code
            db_emp = name_map[nm]
            if not db_emp.get('emp_code') and ec:
                code_updates.append({'id': db_emp['id'], 'name': db_emp['name'],
                                     'emp_code': ec})
        else:
            stats['unmatched'] += 1
            unmatched.append({'computer_id': a['computer_id'], 'emp_name': a.get('emp_name', ''),
                               'emp_code': ec, 'bu_th': a.get('bu_th', '')})
        if emp and emp.get('status') == 'inactive':
            stats['inactive_has_asset'] += 1

    return jsonify({
        'stats': stats,
        'code_updates': code_updates[:50],
        'unmatched': unmatched[:50],
        'cached_file': os.path.exists(EDEVICE_JSON),
    })


@app.route('/api/sync/edevice/apply', methods=['POST'])
def edevice_apply():
    """Sync eDevice assets → asset_assignments + update emp_codes."""
    force = request.json.get('force_live', False) if request.json else False
    assets = fetch_edevice_assets(force_live=force)

    conn = get_db()
    emp_rows = conn.execute('SELECT id, emp_code, name FROM employees').fetchall()
    code_map = {str(e['emp_code']).strip(): e['id'] for e in emp_rows if e['emp_code']}
    name_map = {_norm(re.sub(r'\([^)]*\)', '', e['name'] or '')): e['id'] for e in emp_rows}

    assigned, skipped, protected, code_updated = 0, 0, 0, 0

    # รายการที่ถูก assign ด้วยมือ (transfer) — ห้ามทับ
    manual_nos = {r[0] for r in conn.execute('SELECT asset_no FROM asset_assignments').fetchall()}

    for a in assets:
        ec = str(a.get('emp_code', '') or '').strip()
        nm = _norm(re.sub(r'\([^)]*\)', '', a.get('emp_name', '') or ''))
        emp_id = code_map.get(ec) or name_map.get(nm)

        cid = a['computer_id']
        note = f"{a.get('device_type','')} {a.get('brand','')} {a.get('serial_no','')}".strip()

        if emp_id:
            if cid in manual_nos:
                # มีการ assign ด้วยมือไว้แล้ว — ข้ามเพื่อไม่ให้ทับ
                protected += 1
            else:
                conn.execute(
                    '''INSERT INTO asset_assignments (asset_no, employee_id, note, created_at)
                       VALUES (?,?,?,datetime('now','localtime'))
                       ON CONFLICT(asset_no) DO UPDATE SET
                         employee_id=excluded.employee_id, note=excluded.note,
                         created_at=excluded.created_at''',
                    (cid, emp_id, note)
                )
            assigned += 1
            # update emp_code if missing
            if nm and nm in name_map and ec and ec not in code_map:
                conn.execute(
                    "UPDATE employees SET emp_code=? WHERE id=? AND (emp_code IS NULL OR emp_code='')",
                    (ec, emp_id)
                )
                code_map[ec] = emp_id
                code_updated += 1
        else:
            skipped += 1

    conn.commit()
    conn.close()
    _asset_cache['ts'] = 0
    return jsonify({'ok': True, 'assigned': assigned, 'protected': protected,
                    'skipped': skipped, 'code_updated': code_updated})


# ---------- Intranet Sync ----------

INTRANET_URL    = 'http://www.amarin.intra/webappl/Contact/displays_all.asp'
INTRANET_PARAMS = 'Division=All&Section=All&sname='

# BU code from section header
BU_MAP = {
    'APUB':   'Amarin Publishing',
    'APRINT': 'Amarin Printing & Packaging',
    'ACS':    'Amarin Corporate Support',
    'ABOOK':  'Amarin Book Center',
    'AMTV':   'Amarin Television',
    'AOMNI':  'Amarin Omniverse',
    'AME':    'Amarin Media & Event / AME Imaginative',
}

def fetch_intranet_employees():
    from bs4 import BeautifulSoup
    resp = req_lib.post(INTRANET_URL, data=INTRANET_PARAMS,
                        headers={'Content-Type': 'application/x-www-form-urlencoded'},
                        timeout=30)
    text = resp.content.decode('tis-620', errors='replace')
    soup = BeautifulSoup(text, 'html.parser')

    employees = []
    current_bu_code = ''
    current_bu_name = ''

    for tag in soup.find_all(['td', 'tr']):
        # BU section header
        if tag.name == 'td' and 'fTbHead' in (tag.get('class') or []):
            header = tag.get_text(strip=True)
            m = re.search(r'-\s*([A-Z]+)\s*$', header)
            if m:
                current_bu_code = m.group(1).strip()
                current_bu_name = BU_MAP.get(current_bu_code, '')

        # employee row — parse all 6 cells
        if tag.name == 'tr':
            cells = tag.find_all('td')
            if len(cells) >= 6 and cells[1].get('width') == '190':
                raw_name = cells[1].get_text(separator=' ', strip=True)
                if not raw_name or raw_name == 'ชื่อ-สกุล':
                    continue

                # parse name + nickname
                nm = re.match(r'^(.*?)\(([^)]+)\)\s*$', raw_name)
                if nm:
                    name     = re.sub(r'\s+', ' ', nm.group(1)).strip()
                    nickname = nm.group(2).strip()
                else:
                    name     = re.sub(r'\s+', ' ', raw_name).strip()
                    nickname = ''

                dept     = cells[2].get_text(strip=True)
                position = cells[3].get_text(strip=True)
                # email from <a href=mailto:...>
                a = cells[4].find('a')
                email = ''
                if a and 'mailto:' in (a.get('href') or ''):
                    email = a['href'].replace('mailto:', '').strip()
                phone = cells[5].get_text(strip=True)

                employees.append({
                    'name': name, 'nickname': nickname,
                    'bu_code': current_bu_code, 'bu': current_bu_name,
                    'department': dept, 'position': position,
                    'email': email, 'phone': phone,
                })
    return employees


def _norm(s):
    return re.sub(r'\s+', ' ', (s or '').strip().lower())

SYNC_FIELDS = [
    ('bu_code',    'BU'),
    ('bu',         'ชื่อบริษัท'),
    ('department', 'แผนก/ฝ่าย'),
    ('position',   'ตำแหน่ง'),
    ('email',      'Email'),
    ('phone',      'เบอร์ต่อ'),
]

@app.route('/api/sync/preview', methods=['GET'])
def sync_preview():
    """Fetch intranet and return full diff (inactive / add / update)."""
    intranet_employees = fetch_intranet_employees()
    intranet_map = { _norm(e['name']): e for e in intranet_employees }

    conn = get_db()
    db_employees = conn.execute(
        'SELECT id, name, status, bu, bu_code, department, position, email, phone FROM employees'
    ).fetchall()
    conn.close()

    to_inactive, to_add, to_update = [], [], []

    db_map = {}
    for emp in db_employees:
        db_map[_norm(emp['name'])] = dict(emp)

    # active in DB but not in intranet → inactive
    for emp in db_employees:
        key = _norm(emp['name'])
        if emp['status'] == 'active' and key not in intranet_map:
            to_inactive.append(dict(emp))

    # in intranet but not in DB → add
    for e in intranet_employees:
        key = _norm(e['name'])
        if key not in db_map:
            to_add.append(e)

    # in both → check for field changes
    for e in intranet_employees:
        key = _norm(e['name'])
        db = db_map.get(key)
        if not db:
            continue
        changes = []
        for field, label in SYNC_FIELDS:
            old_val = re.sub(r'\s+', ' ', (db.get(field) or '')).strip()
            new_val = re.sub(r'\s+', ' ', (e.get(field) or '')).strip()
            if new_val and old_val != new_val:
                changes.append({
                    'field': field, 'label': label,
                    'old': old_val, 'new': new_val
                })
        if changes:
            structural = [c for c in changes if c['field'] in ('bu_code', 'bu', 'department', 'position')]
            to_update.append({
                'id':         db['id'],
                'name':       db['name'],
                'bu_code':    db['bu_code'],
                'department': db['department'],
                'changes':    changes,
                'has_structural': bool(structural),
                'structural_changes': structural,
            })

    # enrich to_inactive with asset info
    all_assets = fetch_assets_raw()
    asset_by_emp = {}
    for a in all_assets:
        eid = a.get('employee_id')
        if eid:
            asset_by_emp.setdefault(eid, []).append(a)
    for emp in to_inactive:
        emp['asset_count'] = len(asset_by_emp.get(emp['id'], []))

    return jsonify({
        'intranet_total': len(intranet_employees),
        'db_total':       len(db_employees),
        'to_inactive':    to_inactive,
        'to_add':         to_add,
        'to_update':      to_update,
    })


@app.route('/api/sync/apply', methods=['POST'])
def sync_apply():
    """Apply the sync: inactive / add / update."""
    intranet_employees = fetch_intranet_employees()
    intranet_map = { _norm(e['name']): e for e in intranet_employees }

    conn = get_db()
    db_employees = conn.execute(
        'SELECT id, name, status, bu, bu_code, department, position, email, phone FROM employees'
    ).fetchall()
    db_map = { _norm(emp['name']): dict(emp) for emp in db_employees }

    inactivated, added, updated = 0, 0, 0

    # 1. active in DB but not in intranet → inactive
    for emp in db_employees:
        key = _norm(emp['name'])
        if emp['status'] == 'active' and key not in intranet_map:
            conn.execute(
                "UPDATE employees SET status='inactive', updated_at=datetime('now','localtime') WHERE id=?",
                (emp['id'],)
            )
            inactivated += 1

    # 2. in intranet but not in DB → add
    for e in intranet_employees:
        key = _norm(e['name'])
        if key not in db_map:
            conn.execute(
                '''INSERT INTO employees (bu, bu_code, department, name, nickname, position, email, phone, status)
                   VALUES (?,?,?,?,?,?,?,?,?)''',
                (e['bu'], e['bu_code'], e['department'], e['name'],
                 e['nickname'], e['position'], e['email'], e['phone'], 'active')
            )
            added += 1

    # 3. in both → update changed fields
    for e in intranet_employees:
        key = _norm(e['name'])
        db = db_map.get(key)
        if not db:
            continue
        updates = {}
        for field, _ in SYNC_FIELDS:
            old_val = (db.get(field) or '').strip()
            new_val = (e.get(field) or '').strip()
            if new_val and old_val != new_val:
                updates[field] = new_val
        if updates:
            # normalize whitespace before saving
            updates = {k: re.sub(r'\s+', ' ', v).strip() for k, v in updates.items()}
            set_clause = ', '.join(f'{f}=?' for f in updates)
            vals = list(updates.values()) + [db['id']]
            conn.execute(
                f"UPDATE employees SET {set_clause}, updated_at=datetime('now','localtime') WHERE id=?",
                vals
            )
            updated += 1

    conn.commit()
    conn.close()
    return jsonify({'ok': True, 'inactivated': inactivated, 'added': added, 'updated': updated})


if __name__ == '__main__':
    init_db()
    app.run(debug=True, port=5050)
