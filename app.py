from flask import Flask, request, jsonify, render_template, send_file
import sqlite3, json, io, os, re, csv, time
from collections import defaultdict, Counter
from datetime import datetime, date
import requests as req_lib
from urllib.parse import quote as _url_quote
from report_pdf import _machine_rank, MACHINE_ORDER, _norm_machine

app = Flask(__name__)
DB = os.path.join(os.path.dirname(__file__), 'employees.db')


# ---------- config / secrets ----------

def _load_dotenv():
    """อ่านไฟล์ .env (ถ้ามี) เข้า os.environ — ไม่พึ่ง lib ภายนอก

    .env อยู่ใน .gitignore แล้ว — credential จึงไม่ติดไปกับ repo
    ค่าที่ตั้งไว้ใน environment อยู่แล้ว (เช่นจาก systemd) จะไม่ถูกทับ
    """
    path = os.path.join(os.path.dirname(__file__), '.env')
    if not os.path.exists(path):
        return
    with open(path, encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            k, v = line.split('=', 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"\''))


_load_dotenv()


def _require_env(key, hint):
    val = os.environ.get(key, '').strip()
    if not val:
        raise RuntimeError(
            f'ไม่พบค่า {key} — ตั้งใน .env หรือ environment ก่อนใช้งาน ({hint})')
    return val

# ---------- DB helpers ----------

def get_db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn

# ชุดตั้งต้นของคลัง Software — ใส่ให้ครั้งเดียวตอนตารางยังว่าง
# ผู้ดูแลแก้/ลบ/เพิ่มได้เองจากหน้า "คลัง Software" ระบบจะไม่เขียนทับอีก
SOFTWARE_SEED = [
    # (ชื่อ, หมวด, ผู้ผลิต, ประเภทลิขสิทธิ์)
    ('Microsoft 365',                  'สำนักงาน',        'Microsoft', 'subscription'),
    ('Microsoft Office 2021',          'สำนักงาน',        'Microsoft', 'perpetual'),
    ('Microsoft Visio',                'สำนักงาน',        'Microsoft', 'perpetual'),
    ('Microsoft Project',              'สำนักงาน',        'Microsoft', 'perpetual'),
    ('Google Workspace',               'สำนักงาน',        'Google',    'subscription'),
    ('Zoom',                           'สำนักงาน',        'Zoom',      'subscription'),

    ('Adobe Creative Cloud (All Apps)','กราฟิก/ออกแบบ',   'Adobe',     'subscription'),
    ('Adobe Photoshop',                'กราฟิก/ออกแบบ',   'Adobe',     'subscription'),
    ('Adobe Illustrator',              'กราฟิก/ออกแบบ',   'Adobe',     'subscription'),
    ('Adobe InDesign',                 'กราฟิก/ออกแบบ',   'Adobe',     'subscription'),
    ('Adobe Acrobat Pro',              'กราฟิก/ออกแบบ',   'Adobe',     'subscription'),
    ('Adobe Lightroom',                'กราฟิก/ออกแบบ',   'Adobe',     'subscription'),
    ('CorelDRAW',                      'กราฟิก/ออกแบบ',   'Corel',     'perpetual'),
    ('Figma',                          'กราฟิก/ออกแบบ',   'Figma',     'subscription'),
    ('Canva Pro',                      'กราฟิก/ออกแบบ',   'Canva',     'subscription'),

    ('Adobe Premiere Pro',             'ตัดต่อวิดีโอ/เสียง','Adobe',    'subscription'),
    ('Adobe After Effects',            'ตัดต่อวิดีโอ/เสียง','Adobe',    'subscription'),
    ('Adobe Audition',                 'ตัดต่อวิดีโอ/เสียง','Adobe',    'subscription'),
    ('Adobe Media Encoder',            'ตัดต่อวิดีโอ/เสียง','Adobe',    'subscription'),
    ('DaVinci Resolve Studio',         'ตัดต่อวิดีโอ/เสียง','Blackmagic','perpetual'),
    ('Final Cut Pro',                  'ตัดต่อวิดีโอ/เสียง','Apple',    'perpetual'),
    ('Avid Media Composer',            'ตัดต่อวิดีโอ/เสียง','Avid',     'subscription'),

    ('Windows 11 Pro',                 'ระบบปฏิบัติการ',  'Microsoft', 'oem'),
    ('Windows 10 Pro',                 'ระบบปฏิบัติการ',  'Microsoft', 'oem'),
    ('Windows Server CAL',             'ระบบปฏิบัติการ',  'Microsoft', 'perpetual'),

    ('ESET Endpoint Security',         'ความปลอดภัย',     'ESET',      'subscription'),
    ('Trend Micro Apex One',           'ความปลอดภัย',     'Trend Micro','subscription'),

    ('AutoCAD',                        'งานเฉพาะทาง',     'Autodesk',  'subscription'),
    ('SketchUp Pro',                   'งานเฉพาะทาง',     'Trimble',   'subscription'),
    ('Enfocus PitStop Pro',            'งานเฉพาะทาง',     'Enfocus',   'perpetual'),

    ('TeamViewer',                     'เครื่องมือทั่วไป', 'TeamViewer','subscription'),
    ('AnyDesk',                        'เครื่องมือทั่วไป', 'AnyDesk',   'subscription'),
    ('WinRAR',                         'เครื่องมือทั่วไป', 'RARLAB',    'perpetual'),
]


def _seed_software_catalog(conn):
    """ใส่ชุดตั้งต้นเฉพาะตอน catalog ว่างสนิท และดึงชื่อที่เคยกรอกอิสระเข้าคลัง"""
    if conn.execute('SELECT COUNT(*) FROM software_catalog').fetchone()[0] == 0:
        conn.executemany(
            '''INSERT INTO software_catalog (name, category, vendor, license_type)
               VALUES (?,?,?,?)''', SOFTWARE_SEED)
        conn.commit()

    # ชื่อที่ถูกกรอกไว้ก่อนมี catalog → เพิ่มเข้าคลังแล้วผูก id ให้
    orphans = conn.execute(
        '''SELECT DISTINCT software FROM software_assignments
           WHERE software_id IS NULL AND software <> "" ''').fetchall()
    for o in orphans:
        name = o['software']
        row = conn.execute(
            'SELECT id FROM software_catalog WHERE name=? COLLATE NOCASE', (name,)).fetchone()
        if not row:
            cur = conn.execute(
                'INSERT INTO software_catalog (name, category) VALUES (?, ?)',
                (name, 'ยังไม่จัดหมวด'))
            sid = cur.lastrowid
        else:
            sid = row['id']
        conn.execute(
            'UPDATE software_assignments SET software_id=? WHERE software=? AND software_id IS NULL',
            (sid, name))
    if orphans:
        conn.commit()


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
    conn.execute('''
        CREATE TABLE IF NOT EXISTS software_catalog (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            name         TEXT NOT NULL UNIQUE,
            category     TEXT,
            vendor       TEXT,
            license_type TEXT,
            note         TEXT,
            is_active    INTEGER DEFAULT 1,
            created_at   TEXT DEFAULT (datetime('now','localtime')),
            updated_at   TEXT DEFAULT (datetime('now','localtime'))
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS software_assignments (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id INTEGER NOT NULL,
            software    TEXT NOT NULL,
            note        TEXT,
            created_at  TEXT DEFAULT (datetime('now','localtime'))
        )
    ''')
    # migration: ผูก assignment เข้ากับ catalog (เดิมเก็บเป็นข้อความอิสระ)
    sw_cols = [r[1] for r in conn.execute("PRAGMA table_info(software_assignments)").fetchall()]
    if 'software_id' not in sw_cols:
        conn.execute("ALTER TABLE software_assignments ADD COLUMN software_id INTEGER")
    conn.execute('''
        CREATE TABLE IF NOT EXISTS machine_specs (
            machine_type TEXT NOT NULL,
            bu_code      TEXT NOT NULL,
            spec         TEXT,
            updated_at   TEXT DEFAULT (datetime('now','localtime')),
            PRIMARY KEY (machine_type, bu_code)
        )
    ''')
    # migration: employees table
    cols = [r[1] for r in conn.execute("PRAGMA table_info(employees)").fetchall()]
    if 'emp_code' not in cols:
        conn.execute("ALTER TABLE employees ADD COLUMN emp_code TEXT")
    conn.execute('''CREATE INDEX IF NOT EXISTS idx_sw_emp
                    ON software_assignments (employee_id)''')
    # migration: จำนวนที่ซื้อจริง + ชุดรวม (bundle)
    cat_cols = [r[1] for r in conn.execute("PRAGMA table_info(software_catalog)").fetchall()]
    for col, decl in [('seats', 'INTEGER'), ('renew_date', 'TEXT'),
                      ('unit_price', 'REAL'), ('is_bundle', 'INTEGER DEFAULT 0')]:
        if col not in cat_cols:
            conn.execute(f'ALTER TABLE software_catalog ADD COLUMN {col} {decl}')
    # ชุดรวมครอบคลุมโปรแกรมอะไรบ้าง — ตั้งครั้งเดียว ไม่ต้องกรอกซ้ำทุกคน
    conn.execute('''
        CREATE TABLE IF NOT EXISTS software_bundle_items (
            bundle_id   INTEGER NOT NULL,
            software_id INTEGER NOT NULL,
            PRIMARY KEY (bundle_id, software_id)
        )
    ''')
    # เครื่องพิมพ์ / เครื่องถ่ายเอกสาร — ข้อมูลสัญญาและค่าสำเนา
    conn.execute('''
        CREATE TABLE IF NOT EXISTS printers (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            brand          TEXT,
            model          TEXT,
            building       TEXT,
            serial_no      TEXT,
            ink_type       TEXT,
            ppm            INTEGER,          -- จำนวนสำเนา/นาที
            purchase_year  INTEGER,          -- เก็บเป็น ค.ศ.
            paper          TEXT,
            price_old      REAL,             -- ค่าสำเนา/แผ่น ราคาเดิม
            price_new      REAL,             -- ค่าสำเนา/แผ่น ราคาใหม่
            contract_start TEXT,
            contract_end   TEXT,
            note           TEXT,
            created_at     TEXT DEFAULT (datetime('now','localtime')),
            updated_at     TEXT DEFAULT (datetime('now','localtime'))
        )
    ''')
    # ประวัติการถอน software คืนคลัง (พนักงาน inactive) — ไว้ตรวจย้อนหลัง/กู้คืน
    conn.execute('''
        CREATE TABLE IF NOT EXISTS software_release_log (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id  INTEGER,
            software_id  INTEGER,
            software     TEXT,
            note         TEXT,
            assigned_at  TEXT,
            released_at  TEXT DEFAULT (datetime('now','localtime')),
            reason       TEXT
        )
    ''')
    conn.commit()
    _seed_software_catalog(conn)
    # จำนวนที่ซื้อแยกตาม BU — software_catalog.seats เป็นยอดรวมทุก BU (คำนวณจากตารางนี้)
    conn.execute('''
        CREATE TABLE IF NOT EXISTS software_bu_seats (
            software_id INTEGER NOT NULL,
            bu_code     TEXT NOT NULL,
            seats       INTEGER,
            renew_date  TEXT,
            unit_price  REAL,
            PRIMARY KEY (software_id, bu_code)
        )
    ''')
    _migrate_bu_seats(conn)
    conn.commit()
    # ตาข่ายกันหลุด: ใครไม่ active แล้วแต่ยังถือ software อยู่ → ถอนคืนคลังตอนเริ่มระบบ
    _release_inactive_software(conn, reason='sweep: พนักงานไม่ active')
    conn.commit()
    # migration: asset_assignments — is_manual แยก manual transfer ออกจาก eDevice sync
    aa_cols = [r[1] for r in conn.execute("PRAGMA table_info(asset_assignments)").fetchall()]
    if 'is_manual' not in aa_cols:
        conn.execute("ALTER TABLE asset_assignments ADD COLUMN is_manual INTEGER DEFAULT 0")
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

import hashlib as _hashlib

def _static_version(*parts):
    try:
        p = os.path.join(os.path.dirname(__file__), 'static', *parts)
        return _hashlib.md5(open(p, 'rb').read()).hexdigest()[:8]
    except Exception:
        return '0'

@app.route('/')
def index():
    return render_template('index.html',
                           js_version=_static_version('js', 'app.js'),
                           css_version=_static_version('css', 'style.css'))

@app.route('/api/employees', methods=['GET'])
def list_employees():
    q         = request.args.get('q', '').strip()
    emp_code  = request.args.get('emp_code', '').strip()
    email     = request.args.get('email', '').strip()
    bu        = request.args.get('bu', '')
    dept      = request.args.get('dept', '')
    position  = request.args.get('position', '').strip()
    status    = request.args.get('status', '')
    software  = request.args.get('software', '').strip()   # catalog id
    page      = max(1, int(request.args.get('page', 1)))
    per_page  = int(request.args.get('per_page', 50))

    where, params = [], []
    if q:
        where.append("(name LIKE ? OR nickname LIKE ? OR position LIKE ? OR department LIKE ? "
                     "OR email LIKE ?)")
        params += [f'%{q}%'] * 5
    if emp_code:
        where.append("UPPER(TRIM(emp_code)) = ?"); params.append(emp_code.upper())
    if email:
        where.append("LOWER(TRIM(email)) = ?"); params.append(email.lower())
    if bu:
        where.append("bu_code = ?"); params.append(bu)
    if dept:
        where.append("department = ?"); params.append(dept)
    if position:
        # ตรงตัว — ผู้ใช้เลือกจาก dropdown ยอดที่ได้ต้องตรงกับตัวเลขข้างตัวเลือก
        # (อยากค้นแบบคร่าว ๆ ใช้ช่องค้นหา ซึ่ง LIKE ตำแหน่งอยู่แล้ว)
        where.append("position = ?"); params.append(position)
    if status:
        where.append("status = ?"); params.append(status)
    if software:
        where.append("""id IN (SELECT employee_id FROM software_assignments
                               WHERE software_id = ?)""")
        params.append(software)

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

@app.route('/api/employees/lookup', methods=['GET'])
def lookup_employee():
    # exact lookup สำหรับ LINE Helpdesk — ต้องส่ง emp_code หรือ email อย่างใดอย่างหนึ่ง
    emp_code = request.args.get('emp_code', '').strip()
    email    = request.args.get('email', '').strip()
    if bool(emp_code) == bool(email):
        return jsonify({'found': False, 'error': 'provide exactly one of: emp_code, email'}), 400

    if emp_code:
        cond, val = "UPPER(TRIM(emp_code)) = ?", emp_code.upper()
    else:
        cond, val = "LOWER(TRIM(email)) = ?", email.lower()

    conn = get_db()
    rows = conn.execute(f'SELECT * FROM employees WHERE {cond} LIMIT 2', (val,)).fetchall()
    conn.close()

    if not rows:
        return jsonify({'found': False, 'employee': None})
    if len(rows) > 1:
        return jsonify({'found': False, 'error': 'ambiguous'})

    r = dict(rows[0])
    return jsonify({'found': True, 'employee': {
        'id': r['id'],
        'emp_code': r.get('emp_code'),
        'name': r.get('name'),
        'nickname': r.get('nickname'),
        'email': r.get('email'),
        'phone': r.get('phone'),
        'position': r.get('position'),
        'department': r.get('department'),
        'bu': r.get('bu'),
        'bu_code': r.get('bu_code'),
        'status': r.get('status'),
        'building': r.get('building'),
        'floor': r.get('floor'),
    }})

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
    # เปลี่ยนเป็น inactive → ถอน software คืนคลังทันที
    released = _release_inactive_software(conn, [eid], reason='แก้สถานะพนักงานเป็น inactive')
    conn.commit()
    row = conn.execute('SELECT * FROM employees WHERE id = ?', (eid,)).fetchone()
    conn.close()
    return jsonify({**dict(row), 'software_released': released})

@app.route('/api/employees/<int:eid>', methods=['DELETE'])
def delete_employee(eid):
    conn = get_db()
    conn.execute('DELETE FROM employees WHERE id = ?', (eid,))
    conn.execute('DELETE FROM software_assignments WHERE employee_id = ?', (eid,))
    conn.commit()
    conn.close()
    return jsonify({'ok': True})

@app.route('/api/filters', methods=['GET'])
def get_filters():
    """ตัวเลือกของ dropdown — แผนก/ตำแหน่ง ไล่ตาม BU และแผนกที่เลือกไว้
    (ตำแหน่งมี 600+ ค่า ถ้าไม่ไล่ตามจะเลือกไม่ไหว)"""
    bu   = request.args.get('bu', '')
    dept = request.args.get('dept', '')
    conn = get_db()
    bus = conn.execute(
        'SELECT DISTINCT bu_code, bu FROM employees WHERE bu_code != "" ORDER BY bu_code'
    ).fetchall()

    dept_where, dept_params = ['department != ""'], []
    if bu:
        dept_where.append('bu_code = ?'); dept_params.append(bu)
    depts = conn.execute(
        f'SELECT DISTINCT department FROM employees WHERE {" AND ".join(dept_where)} '
        f'ORDER BY department', dept_params).fetchall()

    pos_where, pos_params = ['position != ""'], []
    if bu:
        pos_where.append('bu_code = ?');    pos_params.append(bu)
    if dept:
        pos_where.append('department = ?'); pos_params.append(dept)
    positions = conn.execute(
        f'SELECT position, COUNT(*) c FROM employees WHERE {" AND ".join(pos_where)} '
        f'GROUP BY position ORDER BY position COLLATE NOCASE', pos_params).fetchall()

    softwares = conn.execute(
        '''SELECT c.id, c.name, COUNT(a.id) c2 FROM software_catalog c
           JOIN software_assignments a ON a.software_id = c.id
           GROUP BY c.id, c.name ORDER BY c.name COLLATE NOCASE'''
    ).fetchall()
    conn.close()
    return jsonify({
        'bus':       [dict(r) for r in bus],
        'depts':     [r['department'] for r in depts],
        'positions': [{'name': r['position'], 'count': r['c']} for r in positions],
        'softwares': [{'id': r['id'], 'name': r['name'], 'count': r['c2']} for r in softwares],
    })

# ---------- คุณสมบัติเครื่องคอมพิวเตอร์ (spec ต่อ ประเภทเครื่อง × BU) ----------

def _spec_bus():
    """รายการ BU ที่ต้องกรอกคุณสมบัติ — ใช้ชุดเดียวกับตัวกรอง BU ทั้งระบบ"""
    conn = get_db()
    rows = conn.execute(
        'SELECT DISTINCT bu_code, bu FROM employees WHERE bu_code != "" ORDER BY bu_code'
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def _spec_rental_history():
    """รุ่นเครื่องที่เคยเช่ามาในอดีต แยกตาม ประเภทเครื่อง × BU
    → { machine_type: { bu_code: [{model, count, last_end}, ...] } }
    เรียงจำนวนมาก→น้อย เพื่อใช้อ้างอิงตอนกำหนดคุณสมบัติรุ่นใหม่"""
    canon = {_norm_machine(name): name for name, _ in MACHINE_ORDER}
    agg   = {}   # (machine_type, bu_code, model) → {count, last_end, charges, years, holders}

    for r in fetch_assets_raw():
        if r.get('ownership') != 'เช่า':
            continue
        mt = canon.get(_norm_machine((r.get('machine_type') or '').strip()
                                     or _infer_mac_machine(r)))
        bu = (r.get('emp_bu_code') or '').strip()
        md = ' '.join(((r.get('model') or '') or (r.get('brand') or '')).split())
        if not (mt and bu and md):
            continue
        cell = agg.setdefault((mt, bu, md), {'count': 0, 'last_end': '',
                                             'charges': [], 'years': set(), 'holders': []})
        cell['count'] += 1
        end = r.get('end_date') or ''
        if end > cell['last_end']:
            cell['last_end'] = end
        start = r.get('start_date') or ''
        if len(start) >= 4 and start[:4].isdigit():
            cell['years'].add(int(start[:4]))
        # รายละเอียดผู้ถือครอง — กางดูได้จากการคลิกจำนวนในหน้ากำหนดคุณสมบัติ
        cell['holders'].append({
            'name':       r.get('user_name') or '',
            'position':   r.get('emp_position') or '',
            'asset_no':   r.get('asset_no') or '',
            'serial_no':  r.get('serial_no') or '',
            'start_date': start,
            'end_date':   end,
            'monthly':    r.get('monthly_charge') or None,
            'status':     r.get('contract_status') or '',
        })
        # ค่าเช่า/เดือน เป็นราคาต่อเครื่อง และปกติเท่ากันทุกเครื่องในรุ่นเดียวกัน
        # เครื่องที่ Sheets ไม่มีตัวเลข (คืนแล้ว/สัญญาเก่า) = 0 → ไม่นับในค่าเฉลี่ย
        # ไม่งั้นจะฉุดราคาต่อเครื่องให้ต่ำกว่าจริง
        if r.get('monthly_charge'):
            cell['charges'].append(r['monthly_charge'])

    out = {}
    for (mt, bu, md), c in agg.items():
        ch = c['charges']
        yrs = sorted(c['years'])
        # ผู้ถือครอง: สัญญาใหม่สุดขึ้นก่อน แล้วเรียงชื่อ
        c['holders'].sort(key=lambda h: (h['start_date'] or '', h['name']), reverse=True)
        out.setdefault(mt, {}).setdefault(bu, []).append({
            'model':    md,
            'count':    c['count'],
            'last_end': c['last_end'],
            # ปีที่เริ่มเช่า (ค.ศ. จาก start_date) — [] = ไม่มีวันที่เริ่มในระบบ
            'years':      yrs,
            'year_first': yrs[0]  if yrs else None,
            'year_last':  yrs[-1] if yrs else None,
            'holders':    c['holders'],
            # ต่อเครื่อง/เดือน (เฉลี่ยจากเครื่องที่มีตัวเลข) — None = ไม่มีข้อมูลค่าเช่าเลย
            'monthly':       round(sum(ch) / len(ch)) if ch else None,
            'monthly_min':   round(min(ch)) if ch else None,
            'monthly_max':   round(max(ch)) if ch else None,
            'monthly_known': len(ch),          # กี่เครื่องที่รู้ค่าเช่า (จาก count ทั้งหมด)
            'monthly_total': round(sum(ch)) if ch else None,
        })
    # ปีที่เริ่มเช่าใหม่สุดขึ้นก่อน (รุ่นล่าสุดคือรุ่นที่ใช้อ้างอิงตอนกำหนด spec ปีนี้)
    # ไม่มีปี = ไม่มี start_date → ไว้ท้ายสุด, ปีเท่ากันเรียงจำนวนมาก→น้อย
    for by_bu in out.values():
        for lst in by_bu.values():
            lst.sort(key=lambda x: (-(x['year_last'] or 0), -(x['year_first'] or 0),
                                    -x['count'], x['model']))
    return out


def _machine_specs_payload():
    """ข้อมูลตั้งต้นของหน้ากำหนดคุณสมบัติ — ใช้ร่วมกันระหว่าง API และรายงาน PDF"""
    conn = get_db()
    rows = conn.execute('SELECT machine_type, bu_code, spec, updated_at FROM machine_specs').fetchall()
    conn.close()

    specs = {}
    for r in rows:
        specs.setdefault(r['machine_type'], {})[r['bu_code']] = {
            'spec': r['spec'] or '', 'updated_at': r['updated_at']
        }

    # ประวัติรุ่นที่เคยเช่า — ถ้าโหลด asset ไม่ได้ ก็ยังต้องกรอก spec ได้ตามปกติ
    try:
        history = _spec_rental_history()
    except Exception:
        history = {}

    return {
        'types': [{'no': i + 1, 'name': name, 'full_name': full}
                  for i, (name, full) in enumerate(MACHINE_ORDER)],
        'bus':     _spec_bus(),
        'specs':   specs,
        'history': history,
    }


@app.route('/api/machine-specs', methods=['GET'])
def get_machine_specs():
    """คุณสมบัติที่แต่ละ BU กำหนดไว้ ของทุกประเภทเครื่องในแค็ตตาล็อก (1-9)"""
    return jsonify(_machine_specs_payload())


@app.route('/api/machine-specs/report.pdf', methods=['GET'])
def machine_specs_report_pdf():
    """รายงานสรุปคุณสมบัติที่จะเช่า/ซื้อ สำหรับผู้บริหาร — ?bu=XXX กรองเฉพาะ BU เดียว"""
    from report_pdf import build_spec_report

    data = _machine_specs_payload()
    bu   = (request.args.get('bu') or '').strip()
    if bu:
        data['bus'] = [b for b in data['bus'] if b['bu_code'] == bu]

    buf   = build_spec_report(data)
    fname = f"report_machine_specs_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf"
    return send_file(buf, mimetype='application/pdf',
                     as_attachment=True, download_name=fname)


@app.route('/api/machine-specs', methods=['POST'])
def save_machine_specs():
    """บันทึกคุณสมบัติ — body: {"items": [{"machine_type","bu_code","spec"}, ...]}
    spec ว่าง = ลบแถวออก (ไม่เก็บค่าว่างไว้ในตาราง)"""
    items = (request.get_json(silent=True) or {}).get('items') or []
    if not isinstance(items, list):
        return jsonify({'error': 'items ต้องเป็น list'}), 400

    valid_types = {_norm_machine(name): name for name, _ in MACHINE_ORDER}
    valid_bus   = {b['bu_code'] for b in _spec_bus()}

    conn = get_db()
    saved = deleted = 0
    for it in items:
        mt = valid_types.get(_norm_machine(it.get('machine_type')))
        bu = (it.get('bu_code') or '').strip()
        if not mt or bu not in valid_bus:
            conn.close()
            return jsonify({'error': f"ประเภทเครื่องหรือ BU ไม่ถูกต้อง: "
                                     f"{it.get('machine_type')} / {it.get('bu_code')}"}), 400
        spec = (it.get('spec') or '').strip()
        if spec:
            conn.execute('''
                INSERT INTO machine_specs (machine_type, bu_code, spec, updated_at)
                VALUES (?, ?, ?, datetime('now','localtime'))
                ON CONFLICT(machine_type, bu_code)
                DO UPDATE SET spec = excluded.spec, updated_at = excluded.updated_at
            ''', (mt, bu, spec))
            saved += 1
        else:
            cur = conn.execute('DELETE FROM machine_specs WHERE machine_type = ? AND bu_code = ?', (mt, bu))
            deleted += cur.rowcount
    conn.commit()
    conn.close()
    return jsonify({'success': True, 'saved': saved, 'deleted': deleted})


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
        where.append("(name LIKE ? OR nickname LIKE ? OR position LIKE ? OR department LIKE ? "
                     "OR email LIKE ?)")
        params += [f'%{q}%'] * 5
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

SHEETS_ID         = os.environ.get('SHEETS_ID', '***REMOVED-SHEETS_ID***')
SHEETS_URL        = f'https://docs.google.com/spreadsheets/d/{SHEETS_ID}/export?format=csv'
SHEETS_SCRIPT_URL = os.environ.get('SHEETS_SCRIPT_URL', '')
CACHE_TTL  = 1800  # 30 min
ASSET_CACHE_SIGNAL = os.path.join(os.path.dirname(__file__), 'asset_cache_signal.txt')

_asset_cache = {'data': None, 'ts': 0}


def _invalidate_asset_cache():
    """Invalidate asset cache across all Gunicorn workers via file signal."""
    _asset_cache['ts'] = 0
    try:
        with open(ASSET_CACHE_SIGNAL, 'w') as f:
            f.write(str(time.time()))
    except Exception:
        pass

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
    # ตรวจ file signal ว่ามี worker อื่น invalidate cache ไปหรือเปล่า
    try:
        with open(ASSET_CACHE_SIGNAL) as f:
            signal_ts = float(f.read().strip())
        if signal_ts > _asset_cache['ts']:
            _asset_cache['ts'] = 0
    except Exception:
        pass
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
            machine_type = (a_ed.get('machine_type') or '').strip()
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
            # strip HTML tags ออกก่อน (กรณี cache เก่ามี <font>...</font> ติดมา)
            _central_raw = (a_ed.get('central_type') or '').strip()
            _central_type = re.sub(r'<[^>]+>', '', _central_raw).strip()
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
            machine_type = ''
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
            'machine_type':    machine_type,
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


def _infer_mac_machine(r):
    """อนุมานประเภทเครื่อง Macbook/iMac จากช่องรุ่น (เกณฑ์เดียวกับ report_pdf)
    ใช้กับเครื่องที่ eDevice ยังไม่ระบุ machine_type — คืน '' ถ้าไม่ใช่ Mac"""
    text = ('%s %s %s' % (r.get('model') or '', r.get('brand') or '',
                          r.get('asset_type') or '')).lower()
    if 'imac' in text:
        return 'iMac'
    if 'macbook' in text or 'mac book' in text:
        return 'Macbook'
    return ''


def _apply_asset_filters(rows, args):
    """กรอง asset ตาม query params — ใช้ร่วมกันระหว่าง /api/assets และ report PDF
    เพื่อให้รายงานได้ข้อมูลชุดเดียวกับที่แสดงบนหน้าจอเป๊ะ ๆ

    รวมทั้ง filter ฝั่ง server (dropdown) และ filter ที่เดิมทำฝั่ง client
    (checkbox กรองพิเศษ + eDevice status)
    """
    status_f    = args.get('status', '')
    type_f      = args.get('type', '')
    position_f  = args.get('position', '')
    dept_f      = args.get('dept', '')
    customer_f  = args.get('customer', '')
    bu_f        = args.get('bu', '')
    ownership_f = args.get('ownership', '')
    machine_f   = args.get('machine_type', '')
    ed_status_f = args.get('ed_status', '').strip().lower()
    q           = args.get('q', '').strip().lower()

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
        # ต้องกรองตามที่ badge แสดงจริง (ownershipBadge ใน app.js) ไม่ใช่ค่า ownership ดิบ
        # เพราะเครื่องที่ eDevice ไม่ระบุ เช่า/ซื้อ จะถูก infer ownership='เช่า' ไว้
        # แต่หน้าเว็บแสดงเป็น "ไม่ระบุ" เมื่อไม่มี Sheets ยืนยัน
        def _ownership_display(r):
            if r.get('ownership') == 'ซื้อ':
                return 'ซื้อ'
            if r.get('ownership') == 'เช่า' and not r.get('ownership_needs_update'):
                return 'เช่า'
            if r.get('ownership_needs_update') and r.get('sheets_matched'):
                return 'เช่า'
            return '⚠'
        rows = [r for r in rows if _ownership_display(r) == ownership_f]
    if machine_f:
        # '-' = เครื่องที่ eDevice ยังไม่ระบุประเภทเครื่อง (และไม่ใช่ Mac ที่อนุมานได้)
        if machine_f == '-':
            rows = [r for r in rows
                    if not (r.get('machine_type') or '').strip()
                    and not _infer_mac_machine(r)]
        elif machine_f in ('Macbook', 'iMac'):
            # Macbook/iMac กรองจากช่องรุ่น (machine_type ใน eDevice มักว่าง)
            rows = [r for r in rows
                    if ((r.get('machine_type') or '').strip() or _infer_mac_machine(r)) == machine_f]
        else:
            rows = [r for r in rows if (r.get('machine_type') or '').strip() == machine_f]
    if ed_status_f:
        rows = [r for r in rows if (r.get('edevice_status') or '').lower() == ed_status_f]
    # ── checkbox "กรองพิเศษ" (เดิมทำฝั่ง client) ──────────────────
    if args.get('only_resigned') == '1':
        rows = [r for r in rows if r['user_name'] and not r.get('employee_id') and not r.get('is_central')]
    if args.get('only_no_owner') == '1':
        rows = [r for r in rows if not r['user_name'] and not r.get('is_central')]
    if args.get('only_central') == '1':
        rows = [r for r in rows if r.get('is_central')]
    if args.get('only_missing_edevice') == '1':
        rows = [r for r in rows if r.get('ownership_missing_edevice') and r['contract_status'] != 'returned']
    if q:
        rows = [r for r in rows if
                q in r['user_name'].lower() or
                q in r['model'].lower() or
                q in r['serial_no'].lower() or
                q in r['asset_no'].lower() or
                q in r['computer_id'].lower()]
    return rows


@app.route('/api/assets', methods=['GET'])
def list_assets():
    force = request.args.get('refresh') == '1'
    data  = fetch_assets_raw(force)

    # ส่ง returned ด้วย — ให้ frontend เป็นคนตัดสินใจซ่อน/แสดง (checkbox "ซ่อน Return")
    rows = _apply_asset_filters(list(data), request.args)

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


def _asset_active(a):
    """เครื่องที่ถือใช้งานอยู่จริงตอนนี้ = eDevice ระบุสถานะ active
    (expire / spare / return / error ไม่ถือว่าเป็นเครื่องที่ใช้อยู่)
    กฎนี้เป็นตัวตัดสินทั้งป้าย 💻 ในตารางพนักงานและรายการในหน้ารายละเอียด
    ให้ตัวเลขตรงกันเสมอ"""
    return (a.get('edevice_status') or '').strip().lower() == 'active'


@app.route('/api/assets/employee-map', methods=['GET'])
def asset_employee_map():
    """Return {employee_id: count} for employees who have assets.

    ?status=active → นับเฉพาะเครื่องที่ eDevice ระบุ Active (ค่าที่หน้าเว็บใช้)
    ไม่ส่ง = นับทุกเครื่องที่ยังไม่คืน
    """
    active_only = request.args.get('status') == 'active'
    all_assets = fetch_assets_raw()
    count_map = {}
    for a in all_assets:
        if a['contract_status'] == 'returned':
            continue
        if active_only and not _asset_active(a):
            continue
        eid = a.get('employee_id')
        if eid:
            count_map[str(eid)] = count_map.get(str(eid), 0) + 1
    return jsonify(count_map)

@app.route('/api/employees/<int:eid>/assets', methods=['GET'])
def employee_assets(eid):
    """Return all assets currently assigned to this employee.

    ทุกเครื่องจะติดธง is_active_now มาให้ (ใช้กฎเดียวกับป้าย 💻)
    ?status=active → ส่งเฉพาะเครื่อง Active
    ค่าปกติส่งทุกเครื่องที่ยังไม่คืน เพราะหน้าโยกย้ายทรัพย์สินตอนพนักงานลาออก
    ต้องเห็นครบทุกเครื่อง ไม่ใช่แค่ที่ Active
    """
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

    # ติดธงไว้ให้หน้าเว็บกรอง/นับ โดยไม่ต้องรู้กฎเอง (copy ก่อน กัน cache เพี้ยน)
    out = [dict(a, is_active_now=_asset_active(a)) for a in matched]
    if request.args.get('status') == 'active':
        out = [a for a in out if a['is_active_now']]
    return jsonify(out)


# ---------- Software ถือครอง ----------

def _release_inactive_software(conn, emp_ids=None, reason=''):
    """ถอน software ของพนักงานที่ไม่ active คืนคลัง — จดลง software_release_log ก่อนลบ

    emp_ids=None → ตรวจทุกคน, ไม่งั้นเฉพาะรายชื่อที่ให้มา (ข้ามคนที่ยัง active)
    คืนจำนวนรายการที่ถอน (ไม่ commit — ให้ผู้เรียก commit พร้อมงานของตัวเอง)
    """
    sql = '''SELECT a.id, a.employee_id, a.software_id, a.software, a.note, a.created_at
             FROM software_assignments a JOIN employees e ON e.id = a.employee_id
             WHERE COALESCE(e.status, '') <> 'active' '''
    params = []
    if emp_ids is not None:
        emp_ids = [int(e) for e in emp_ids]
        if not emp_ids:
            return 0
        sql += f" AND a.employee_id IN ({','.join('?' * len(emp_ids))})"
        params = emp_ids
    rows = conn.execute(sql, params).fetchall()
    for r in rows:
        conn.execute(
            '''INSERT INTO software_release_log
                 (employee_id, software_id, software, note, assigned_at, reason)
               VALUES (?,?,?,?,?,?)''',
            (r['employee_id'], r['software_id'], r['software'], r['note'],
             r['created_at'], reason))
        conn.execute('DELETE FROM software_assignments WHERE id=?', (r['id'],))
    if rows:
        app.logger.warning('ถอน software คืนคลัง %d รายการ (%d คน) — %s', len(rows),
                           len({r['employee_id'] for r in rows}), reason)
    return len(rows)


@app.route('/api/software/employee-map', methods=['GET'])
def software_employee_map():
    """{employee_id: จำนวน software} สำหรับแสดงคอลัมน์ในตารางพนักงาน

    ชุดรวม (All Apps) นับเป็น 1 — โปรแกรมข้างในชุดที่คนนั้นถืออยู่ไม่นับซ้ำ
    """
    conn  = get_db()
    cover = _emp_covered(conn)
    rows  = conn.execute(
        'SELECT employee_id, software_id FROM software_assignments').fetchall()
    conn.close()
    cnt = Counter(r['employee_id'] for r in rows
                  if r['software_id'] not in cover.get(r['employee_id'], ()))
    return jsonify({str(e): n for e, n in cnt.items()})


# ---------- คลัง Software (master data) ----------

def _int_or_none(v):
    try:
        return int(v) if v not in (None, '', 'null') else None
    except (TypeError, ValueError):
        return None


def _float_or_none(v):
    try:
        return float(v) if v not in (None, '', 'null') else None
    except (TypeError, ValueError):
        return None


def _bundle_map(conn):
    """{bundle_id: [software_id, ...]} — ชุดรวมครอบคลุมโปรแกรมอะไรบ้าง"""
    out = defaultdict(list)
    for r in conn.execute('SELECT bundle_id, software_id FROM software_bundle_items'):
        out[r['bundle_id']].append(r['software_id'])
    return out


def _set_bundle_members(conn, bundle_id, members):
    """ตั้งสมาชิกของชุดรวมใหม่ทั้งชุด (members=None = ไม่แตะ)"""
    if members is None:
        return
    conn.execute('DELETE FROM software_bundle_items WHERE bundle_id=?', (bundle_id,))
    ids = {int(m) for m in members if str(m).strip().isdigit() and int(m) != bundle_id}
    for mid in ids:
        conn.execute(
            'INSERT OR IGNORE INTO software_bundle_items (bundle_id, software_id) VALUES (?,?)',
            (bundle_id, mid))


def _emp_covered(conn, members=None):
    """{employee_id: {software_id, ...}} — โปรแกรมที่แต่ละคนได้ใช้ผ่านชุดรวมที่ถืออยู่

    แถวโปรแกรมที่ตรงกับชุดนี้ยังเก็บไว้เป็นข้อมูล "ใช้จริง" แต่ไม่กิน seat ของตัวแยก
    """
    members = _bundle_map(conn) if members is None else members
    out = defaultdict(set)
    if not members:
        return out
    for r in conn.execute('SELECT employee_id, software_id FROM software_assignments'):
        for m in members.get(r['software_id'], ()):
            out[r['employee_id']].add(m)
    return out


SEAT_MAIN_BU = 'AMTV'   # ตอนแบ่งยอดซื้อเดิมเป็นราย BU ส่วนที่เหลือยกให้ BU นี้


def _seat_usage_by_bu(conn):
    """{(software_id, bu_code): จำนวนที่กิน seat} — ไม่นับโปรแกรมที่ใช้ผ่านชุดรวม"""
    cover = _emp_covered(conn)
    out = Counter()
    for r in conn.execute('SELECT a.employee_id, a.software_id, e.bu_code '
                          'FROM software_assignments a JOIN employees e ON e.id = a.employee_id'):
        if r['software_id'] not in cover.get(r['employee_id'], ()):
            out[(r['software_id'], r['bu_code'] or '')] += 1
    return out


def _migrate_bu_seats(conn):
    """ครั้งแรกที่มีตารางราย BU: แบ่งยอดซื้อรวมเดิมให้แต่ละ BU เท่าที่ใช้จริง
    ส่วนที่เหลือยกให้ SEAT_MAIN_BU (ผู้ใช้แก้ทีหลังได้ในแท็บ BU)"""
    if conn.execute('SELECT 1 FROM software_bu_seats LIMIT 1').fetchone():
        return
    rows = conn.execute('SELECT id, name, seats, renew_date, unit_price FROM software_catalog '
                        'WHERE seats IS NOT NULL').fetchall()
    if not rows:
        return
    usage = _seat_usage_by_bu(conn)
    for c in rows:
        left  = c['seats']
        alloc = {}
        for (sid, bu), n in sorted(usage.items(), key=lambda kv: kv[0][1]):
            if sid == c['id'] and bu and bu != SEAT_MAIN_BU and left > 0:
                alloc[bu] = min(n, left)
                left -= alloc[bu]
        alloc[SEAT_MAIN_BU] = left
        for bu, n in alloc.items():
            if n or len(alloc) == 1:      # ยอดเหลือ 0 ไม่ต้องสร้างแถวให้ BU หลัก
                conn.execute(
                    'INSERT INTO software_bu_seats (software_id, bu_code, seats, renew_date, unit_price) '
                    'VALUES (?,?,?,?,?)', (c['id'], bu, n, c['renew_date'], c['unit_price']))
        app.logger.warning('แบ่งยอดซื้อ "%s" %s → %s', c['name'], c['seats'], alloc)


def _sync_catalog_seats(conn, cid):
    """ยอดรวมในคลัง = ผลรวมทุก BU · วันต่ออายุ = วันที่ใกล้สุด · ราคา = ถ้าทุก BU เท่ากัน"""
    rs = conn.execute('SELECT seats, renew_date, unit_price FROM software_bu_seats '
                      'WHERE software_id=?', (cid,)).fetchall()
    seats  = [r['seats'] for r in rs if r['seats'] is not None]
    renews = [r['renew_date'] for r in rs if r['renew_date']]
    prices = {r['unit_price'] for r in rs}
    conn.execute('UPDATE software_catalog SET seats=?, renew_date=?, unit_price=? WHERE id=?',
                 (sum(seats) if seats else None, min(renews) if renews else None,
                  prices.pop() if len(prices) == 1 else None, cid))   # {None} → None


def _set_bu_seats(conn, cid, bu, d):
    """บันทึกจำนวนซื้อ/วันต่ออายุ/ราคา ของ BU หนึ่ง (ว่างหมด = ลบแถวทิ้ง)"""
    seats = _int_or_none(d.get('seats'))
    renew = (d.get('renew_date') or '').strip() or None
    price = _float_or_none(d.get('unit_price'))
    if seats is None and renew is None and price is None:
        conn.execute('DELETE FROM software_bu_seats WHERE software_id=? AND bu_code=?', (cid, bu))
    else:
        conn.execute(
            'INSERT INTO software_bu_seats (software_id, bu_code, seats, renew_date, unit_price) '
            'VALUES (?,?,?,?,?) ON CONFLICT(software_id, bu_code) DO UPDATE SET '
            'seats=excluded.seats, renew_date=excluded.renew_date, unit_price=excluded.unit_price',
            (cid, bu, seats, renew, price))
    _sync_catalog_seats(conn, cid)


@app.route('/api/software/catalog', methods=['GET'])
def software_catalog_list():
    """รายการใน catalog พร้อมยอดผู้ถือครองแต่ละตัว

    ?all=1 → รวมรายการที่ปิดใช้งานแล้ว (ค่าปกติแสดงเฉพาะที่ยังใช้อยู่)
    ?bu=AMTV → ยอดซื้อ/ใช้/เหลือ ของ BU นั้น (ค่าปกติ = รวมทุก BU)
    """
    show_all = request.args.get('all') == '1'
    bu       = (request.args.get('bu') or '').strip()
    conn = get_db()
    rows = conn.execute(
        f'''SELECT c.*, (SELECT COUNT(*) FROM software_assignments a
                         WHERE a.software_id = c.id) AS holders
            FROM software_catalog c
            {'' if show_all else 'WHERE c.is_active = 1'}
            ORDER BY c.category COLLATE NOCASE, c.name COLLATE NOCASE'''
    ).fetchall()
    members = _bundle_map(conn)
    names   = {r['id']: r['name'] for r in rows}
    # โปรแกรมตัวนี้อยู่ในชุดรวมไหนบ้าง — ใช้เตือนตอนจ่ายซ้ำกับ bundle
    in_bundle = defaultdict(list)
    for bid, mids in members.items():
        for mid in mids:
            in_bundle[mid].append(bid)
    # คนที่ถือชุดรวมอยู่แล้ว ใช้โปรแกรมข้างในได้โดยไม่กิน seat ของตัวแยก
    cover   = _emp_covered(conn, members)
    asg = conn.execute('''SELECT a.employee_id, a.software_id, e.bu_code
                          FROM software_assignments a
                          LEFT JOIN employees e ON e.id = a.employee_id''').fetchall()
    if bu:
        asg = [r for r in asg if (r['bu_code'] or '') == bu]
    holders = Counter(r['software_id'] for r in asg)
    covered = Counter(r['software_id'] for r in asg
                      if r['software_id'] in cover.get(r['employee_id'], ()))
    # ยอดซื้อราย BU — แท็บ BU ใช้ของ BU นั้น, แท็บรวมแสดงแยกให้ดูว่ามาจาก BU ไหน
    bu_seats = defaultdict(dict)
    for r in conn.execute('SELECT * FROM software_bu_seats'):
        bu_seats[r['software_id']][r['bu_code']] = dict(r)
    conn.close()

    out = []
    for r in rows:
        d = dict(r)
        d['members'] = sorted(({'id': m, 'name': names.get(m, '?')}
                               for m in members.get(r['id'], [])),
                              key=lambda x: x['name'].lower())
        d['in_bundles'] = [{'id': b, 'name': names.get(b, '?')} for b in in_bundle.get(r['id'], [])]
        d['seats_by_bu'] = {b: x['seats'] for b, x in sorted(bu_seats[r['id']].items())
                            if x['seats'] is not None}
        if bu:
            mine = bu_seats[r['id']].get(bu, {})
            d['seats']      = mine.get('seats')
            d['renew_date'] = mine.get('renew_date')
            d['unit_price'] = mine.get('unit_price')
        d['holders'] = holders.get(r['id'], 0)
        d['covered'] = covered.get(r['id'], 0)
        d['used']    = d['holders'] - d['covered']      # จำนวนที่กิน seat จริง
        # seats = จำนวนที่ซื้อ (None = ยังไม่ระบุ) → คำนวณเหลือ/เกินให้เลย
        d['available'] = (d['seats'] - d['used']) if d['seats'] is not None else None
        d['over'] = max(0, d['used'] - d['seats']) if d['seats'] is not None else 0
        out.append(d)
    return jsonify(out)


@app.route('/api/software/catalog', methods=['POST'])
def software_catalog_add():
    d    = request.json or {}
    name = (d.get('name') or '').strip()
    if not name:
        return jsonify({'error': 'ต้องระบุชื่อ Software'}), 400

    conn = get_db()
    if conn.execute('SELECT id FROM software_catalog WHERE name=? COLLATE NOCASE',
                    (name,)).fetchone():
        conn.close()
        return jsonify({'error': f'"{name}" มีอยู่ในคลังแล้ว'}), 409
    cur = conn.execute(
        '''INSERT INTO software_catalog
             (name, category, vendor, license_type, note, is_bundle)
           VALUES (?,?,?,?,?,?)''',
        (name, (d.get('category') or '').strip(), (d.get('vendor') or '').strip(),
         (d.get('license_type') or '').strip(), (d.get('note') or '').strip(),
         1 if d.get('is_bundle') else 0))
    new_id = cur.lastrowid
    _set_bundle_members(conn, new_id, d.get('members'))
    # จำนวนซื้อเก็บราย BU — เพิ่มจากแท็บไหนก็เป็นของ BU นั้น
    bu = (d.get('bu') or '').strip()
    if bu:
        _set_bu_seats(conn, new_id, bu, d)
    conn.commit()
    conn.close()
    return jsonify({'ok': True, 'id': new_id, 'name': name})


@app.route('/api/software/catalog/<int:cid>', methods=['PUT'])
def software_catalog_update(cid):
    d    = request.json or {}
    name = (d.get('name') or '').strip()
    if not name:
        return jsonify({'error': 'ต้องระบุชื่อ Software'}), 400

    conn = get_db()
    if conn.execute('SELECT id FROM software_catalog WHERE name=? COLLATE NOCASE AND id<>?',
                    (name, cid)).fetchone():
        conn.close()
        return jsonify({'error': f'"{name}" มีอยู่ในคลังแล้ว'}), 409

    cur = conn.execute(
        '''UPDATE software_catalog
           SET name=?, category=?, vendor=?, license_type=?, note=?, is_active=?,
               is_bundle=?, updated_at=datetime('now','localtime')
           WHERE id=?''',
        (name, (d.get('category') or '').strip(), (d.get('vendor') or '').strip(),
         (d.get('license_type') or '').strip(), (d.get('note') or '').strip(),
         1 if d.get('is_active', 1) else 0, 1 if d.get('is_bundle') else 0, cid))
    if not cur.rowcount:
        conn.close()
        return jsonify({'error': 'ไม่พบรายการในคลัง'}), 404
    # จำนวนซื้อ/วันต่ออายุ/ราคา แก้ได้เฉพาะในแท็บ BU (แท็บรวมเป็นผลรวม แก้ตรงไม่ได้)
    bu = (d.get('bu') or '').strip()
    if bu:
        _set_bu_seats(conn, cid, bu, d)
    if 'members' in d:
        _set_bundle_members(conn, cid, d.get('members'))
    # ชื่อที่บันทึกไว้กับพนักงานเป็นสำเนา — เปลี่ยนชื่อในคลังต้องตามไปแก้ด้วย
    conn.execute('UPDATE software_assignments SET software=? WHERE software_id=?', (name, cid))
    conn.commit()
    conn.close()
    return jsonify({'ok': True})


@app.route('/api/software/catalog/<int:cid>', methods=['DELETE'])
def software_catalog_delete(cid):
    """ลบรายการออกจากคลัง

    ปกติลบได้เฉพาะที่ยังไม่มีใครถือครอง (ที่มีคนถือให้ปิดใช้งานแทน)
    ?with_assignments=1 → ลบ license ของทุกคนที่ถือตัวนี้ออกด้วย
    ใช้ตอนเลิกใช้โปรแกรมนั้นจริง ๆ กู้คืนไม่ได้ ฝั่ง UI จึงบังคับพิมพ์ยืนยันจำนวนก่อน
    """
    force = request.args.get('with_assignments') == '1'
    conn  = get_db()
    row   = conn.execute('SELECT name FROM software_catalog WHERE id=?', (cid,)).fetchone()
    if not row:
        conn.close()
        return jsonify({'error': 'ไม่พบรายการในคลัง'}), 404

    holders = conn.execute(
        'SELECT COUNT(*) c FROM software_assignments WHERE software_id=?', (cid,)
    ).fetchone()['c']
    if holders and not force:
        conn.close()
        return jsonify({
            'error': f'ลบไม่ได้ — มีพนักงาน {holders} คนถือครองอยู่ '
                     f'(ถ้าเลิกใช้แล้วให้เลือก "ปิดใช้งาน" แทน)',
            'holders': holders,
        }), 409

    removed = 0
    if force and holders:
        removed = conn.execute(
            'DELETE FROM software_assignments WHERE software_id=?', (cid,)).rowcount
    conn.execute('DELETE FROM software_catalog WHERE id=?', (cid,))
    conn.execute('DELETE FROM software_bundle_items WHERE bundle_id=? OR software_id=?',
                 (cid, cid))
    conn.execute('DELETE FROM software_bu_seats WHERE software_id=?', (cid,))
    conn.commit()
    conn.close()
    app.logger.warning('ลบ software จากคลัง: "%s" (id=%s) พร้อม license %d ใบ',
                       row['name'], cid, removed)
    return jsonify({'ok': True, 'name': row['name'], 'removed_assignments': removed})


# ---------- Software ที่พนักงานถือครอง ----------

@app.route('/api/employees/<int:eid>/software', methods=['GET'])
def list_employee_software(eid):
    conn = get_db()
    rows = conn.execute(
        '''SELECT a.id, a.software, a.software_id, a.note, a.created_at,
                  c.category, c.vendor, c.license_type, c.is_active, c.is_bundle
           FROM software_assignments a
           LEFT JOIN software_catalog c ON c.id = a.software_id
           WHERE a.employee_id=? ORDER BY a.software COLLATE NOCASE''', (eid,)
    ).fetchall()
    members = _bundle_map(conn)
    names   = {r['id']: r['name'] for r in
               conn.execute('SELECT id, name FROM software_catalog')}
    conn.close()
    held = {r['software_id'] for r in rows}
    out = []
    for r in rows:
        d = dict(r)
        # ชุดรวมไม่ต้องกรอกตัวข้างใน — ส่งรายชื่อที่ครอบคลุมไปแสดงใต้ชื่อ
        d['covers'] = sorted((names.get(m, '?') for m in members.get(r['software_id'], [])),
                             key=str.lower)
        # โปรแกรมที่คนนี้ได้ใช้ผ่านชุดรวมที่ถืออยู่ → ไม่ต้องซื้อแยก
        d['covered_by'] = sorted(names.get(b, '?') for b, ms in members.items()
                                 if b in held and r['software_id'] in ms)
        out.append(d)
    return jsonify(out)


def _resolve_catalog(conn, d):
    """หา (id, ชื่อ) จาก catalog โดยรับได้ทั้ง software_id และชื่อ
    คืน (None, ข้อความ error) ถ้าไม่พบ — บันทึกได้เฉพาะของที่มีในคลัง"""
    cid  = d.get('software_id')
    name = (d.get('software') or '').strip()
    row  = None
    if cid:
        row = conn.execute('SELECT id, name FROM software_catalog WHERE id=?', (cid,)).fetchone()
        if not row:
            return None, 'ไม่พบ Software นี้ในคลัง'
    elif name:
        row = conn.execute('SELECT id, name FROM software_catalog WHERE name=? COLLATE NOCASE',
                           (name,)).fetchone()
        if not row:
            return None, f'"{name}" ยังไม่มีในคลัง — เพิ่มเข้าคลังก่อนจึงจะบันทึกได้'
    else:
        return None, 'ต้องเลือก Software จากคลัง'
    return row, None


@app.route('/api/employees/<int:eid>/software', methods=['POST'])
def add_employee_software(eid):
    d    = request.json or {}
    note = (d.get('note') or '').strip()

    conn = get_db()
    emp  = conn.execute('SELECT status FROM employees WHERE id=?', (eid,)).fetchone()
    if not emp:
        conn.close()
        return jsonify({'error': 'ไม่พบพนักงาน'}), 404
    if emp['status'] != 'active':
        conn.close()
        return jsonify({'error': 'พนักงานคนนี้ Inactive แล้ว — เพิ่ม Software ไม่ได้'}), 409

    row, err = _resolve_catalog(conn, d)
    if err:
        conn.close()
        return jsonify({'error': err}), 400

    dup = conn.execute(
        'SELECT id FROM software_assignments WHERE employee_id=? AND software_id=?',
        (eid, row['id'])).fetchone()
    if dup:
        conn.close()
        return jsonify({'error': f'มี "{row["name"]}" อยู่แล้ว'}), 409

    cur = conn.execute(
        '''INSERT INTO software_assignments (employee_id, software, software_id, note)
           VALUES (?,?,?,?)''', (eid, row['name'], row['id'], note))
    conn.commit()
    new_id = cur.lastrowid
    conn.close()
    return jsonify({'ok': True, 'id': new_id})


@app.route('/api/employees/<int:eid>/software/<int:sid>', methods=['PUT'])
def update_employee_software(eid, sid):
    d    = request.json or {}
    note = (d.get('note') or '').strip()

    conn = get_db()
    row, err = _resolve_catalog(conn, d)
    if err:
        conn.close()
        return jsonify({'error': err}), 400

    dup = conn.execute(
        'SELECT id FROM software_assignments WHERE employee_id=? AND software_id=? AND id<>?',
        (eid, row['id'], sid)).fetchone()
    if dup:
        conn.close()
        return jsonify({'error': f'มี "{row["name"]}" อยู่แล้ว'}), 409

    cur = conn.execute(
        '''UPDATE software_assignments SET software=?, software_id=?, note=?
           WHERE id=? AND employee_id=?''', (row['name'], row['id'], note, sid, eid))
    conn.commit()
    changed = cur.rowcount
    conn.close()
    if not changed:
        return jsonify({'error': 'ไม่พบรายการ'}), 404
    return jsonify({'ok': True})


@app.route('/api/employees/<int:eid>/software/batch', methods=['POST'])
def batch_employee_software(eid):
    """บันทึกการเปลี่ยนแปลงทั้งชุดในครั้งเดียว — ผู้ใช้เลือกหลายตัวแล้วกดยืนยันทีเดียว
    body: { add: [{software_id, note}], update: [{id, note}], remove: [id, ...] }
    ตรวจให้ผ่านทั้งหมดก่อนจึงเขียน ถ้ามีอันใดผิดจะไม่เขียนอะไรเลย
    """
    d       = request.json or {}
    adds    = d.get('add')    or []
    updates = d.get('update') or []
    removes = d.get('remove') or []

    conn = get_db()
    emp  = conn.execute('SELECT status FROM employees WHERE id=?', (eid,)).fetchone()
    if not emp:
        conn.close()
        return jsonify({'error': 'ไม่พบพนักงาน'}), 404
    # คน inactive ถูกถอน software คืนคลังแล้ว — ห้ามเพิ่มกลับเข้าไป
    if adds and emp['status'] != 'active':
        conn.close()
        return jsonify({'error': 'พนักงานคนนี้ Inactive แล้ว — เพิ่ม Software ไม่ได้'}), 409

    current = {r['id']: r['software_id'] for r in conn.execute(
        'SELECT id, software_id FROM software_assignments WHERE employee_id=?', (eid,))}

    unknown = [i for i in list(removes) + [u.get('id') for u in updates] if i not in current]
    if unknown:
        conn.close()
        return jsonify({'error': 'มีรายการที่ไม่ใช่ของพนักงานคนนี้ หรือถูกลบไปแล้ว'}), 409

    # ชุดที่จะเหลือหลังลบ ใช้กันเพิ่มซ้ำ
    remaining = {sid for rid, sid in current.items() if rid not in removes}
    resolved  = []
    for a in adds:
        row, err = _resolve_catalog(conn, a)
        if err:
            conn.close()
            return jsonify({'error': err}), 400
        if row['id'] in remaining:
            conn.close()
            return jsonify({'error': f'มี "{row["name"]}" อยู่แล้ว'}), 409
        remaining.add(row['id'])
        resolved.append((row, (a.get('note') or '').strip()))

    for rid in removes:
        conn.execute('DELETE FROM software_assignments WHERE id=? AND employee_id=?', (rid, eid))
    for u in updates:
        conn.execute('UPDATE software_assignments SET note=? WHERE id=? AND employee_id=?',
                     ((u.get('note') or '').strip(), u['id'], eid))
    for row, note in resolved:
        conn.execute(
            '''INSERT INTO software_assignments (employee_id, software, software_id, note)
               VALUES (?,?,?,?)''', (eid, row['name'], row['id'], note))
    conn.commit()
    total = conn.execute('SELECT COUNT(*) c FROM software_assignments WHERE employee_id=?',
                         (eid,)).fetchone()['c']
    conn.close()
    return jsonify({'ok': True, 'added': len(resolved), 'updated': len(updates),
                    'removed': len(removes), 'total': total})


@app.route('/api/employees/<int:eid>/software/<int:sid>', methods=['DELETE'])
def delete_employee_software(eid, sid):
    conn = get_db()
    cur  = conn.execute(
        'DELETE FROM software_assignments WHERE id=? AND employee_id=?', (sid, eid))
    conn.commit()
    changed = cur.rowcount
    conn.close()
    if not changed:
        return jsonify({'error': 'ไม่พบรายการ'}), 404
    return jsonify({'ok': True})


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

        # upsert assignment (is_manual=1 กันไม่ให้ eDevice sync ทับ)
        conn.execute(
            '''INSERT INTO asset_assignments (asset_no, employee_id, note, is_manual, created_at)
               VALUES (?, ?, ?, 1, datetime('now','localtime'))
               ON CONFLICT(asset_no) DO UPDATE SET
                 employee_id=excluded.employee_id,
                 note=excluded.note,
                 is_manual=1,
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
    _invalidate_asset_cache()
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
    _invalidate_asset_cache()
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

    # no_timeline_by_bu: เครื่องเช่าที่ไม่มีวันหมดสัญญา (ไม่อยู่ใน timeline) แยกตาม BU
    # เฉพาะ eDevice = Active/Spare (spare ไม่อยู่ใน rentals จึงต้องวนจาก data ตรงๆ)
    no_tl_bu = defaultdict(list)
    for r in data:
        if (is_rental(r)
                and r['contract_status'] != 'returned'
                and r.get('resolution', 'pending') not in RESOLVED
                and (r.get('edevice_status') or '').lower() in ('active', 'spare')
                and not r['end_date']):
            no_tl_bu[r['emp_bu_code'] or '—'].append({
                'asset_no':       r['asset_no'],
                'computer_id':    r['computer_id'],
                'serial_no':      r['serial_no'],
                'model':          r['model'],
                'edevice_status': r.get('edevice_status', ''),
                'user_name':      r['user_name'],
            })
    no_timeline_by_bu = sorted(
        [{'bu_code': k, 'count': len(v), 'items': v} for k, v in no_tl_bu.items()],
        key=lambda x: -x['count']
    )

    # urgent: expired + critical เฉพาะเครื่องที่ eDevice = Active (เรียงวันหมดก่อน)
    urgent = sorted(
        [r for r in rentals
         if r['contract_status'] in ('expired', 'critical')
         and (r.get('edevice_status') or '').lower() == 'active'],
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
    # เฉพาะเครื่องที่ eDevice = Active
    needs_update = [_mini(r) for r in all_assets
                    if r.get('ownership_needs_update')
                    and (r.get('edevice_status') or '').lower() == 'active']
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
        'no_timeline_by_bu': no_timeline_by_bu,
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
    machines  = set()
    positions = set()
    depts     = set()
    for r in active:
        customers[r['customer_code']] = r['customer_name']
        t = r['asset_type']
        if t:
            types.add(_TYPE_NORM.get(t.lower(), t))
        m = (r.get('machine_type') or '').strip() or _infer_mac_machine(r)
        if m:
            machines.add(m)
        p = r.get('emp_position', '')
        if p:
            positions.add(p)
        d = r.get('emp_dept', '')
        if d:
            depts.add(d)
    return jsonify({
        'customers':  [{'code': k, 'name': v} for k, v in customers.items()],
        'types':      sorted(types),
        # แสดงครบทุกลำดับแค็ตตาล็อก (1-9) เสมอแม้ไม่มีเครื่อง เหมือนข้อ 1 ในรายงาน
        # เรียงตามลำดับเดียวกับรายงาน PDF — Macbook #8, iMac #9; นอกลิสต์ต่อท้าย
        'machine_types': sorted(machines | {k for k, _ in MACHINE_ORDER},
                                key=lambda m: (_machine_rank(m), m)),
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

        # ชีตคอลัมน์ ชื่อ-สกุล เก็บเฉพาะชื่อคนจริง — placeholder ของระบบห้ามเขียนกลับ
        if name in ('ส่วนกลาง', 'IT Stock'):
            name = ''

        # ส่งเฉพาะ field ที่มีค่า — ค่าว่างต้องไม่ไปลบข้อมูลเดิมในชีต
        u = {'serial': sn}
        if name:     u['name'] = name
        if dept:     u['dept'] = dept
        if division: u['division'] = division
        if len(u) == 1:
            skipped.append(sn)
            continue

        updates.append(u)

    if not updates:
        return jsonify({'ok': False, 'error': 'ไม่มีข้อมูลที่จะอัพเดท', 'skipped': len(skipped)})

    if not SHEETS_SCRIPT_URL:
        return jsonify({'ok': False,
                        'error': 'ยังไม่ได้ตั้งค่า SHEETS_SCRIPT_URL ใน .env'}), 500

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



def _rental_rows(data):
    """เครื่องเช่าที่ยัง active — ใช้เกณฑ์ชุดเดียวกับ /api/dashboard/rental
    เพื่อให้ยอดใน export ตรงกับตัวเลขบนหน้าจอ (ไม่งั้นคนใช้จะงงว่าทำไมไม่เท่ากัน)"""
    RESOLVED = {'returned', 'bought', 'renewed', 'extended'}
    ED_SKIP  = {'spare'}
    return [r for r in data
            if r.get('ownership') == 'เช่า'
            and r['contract_status'] != 'returned'
            and r.get('resolution', 'pending') not in RESOLVED
            and (r.get('edevice_status') or '').lower() not in ED_SKIP]


@app.route('/api/rental/export-options', methods=['GET'])
def rental_export_options():
    """ตัวเลือกที่มีจริงในข้อมูล สำหรับ dropdown หน้า export
    ส่งจำนวนไปด้วยเพื่อให้เห็นก่อนกดว่าจะได้กี่เครื่อง"""
    from collections import Counter
    rows = _rental_rows(fetch_assets_raw())

    years = Counter(r['end_date'][:4] for r in rows if r.get('end_date'))
    types = Counter(r.get('machine_type') or '' for r in rows)
    bus   = Counter(r.get('emp_bu_code') or '' for r in rows)

    # ประเภทเครื่องเรียงตามลำดับแค็ตตาล็อกมาตรฐาน ไม่ใช่ตามจำนวน
    type_list = sorted(((t, n) for t, n in types.items() if t),
                       key=lambda x: (_machine_rank(x[0]), x[0]))
    return jsonify({
        'total':      len(rows),
        'years':      [{'year': y, 'count': n} for y, n in sorted(years.items())],
        'no_year':    sum(1 for r in rows if not r.get('end_date')),
        'types':      [{'name': t, 'count': n} for t, n in type_list],
        'no_type':    types.get('', 0),
        'bus':        [{'bu_code': b, 'count': n}
                       for b, n in sorted(bus.items()) if b],
        'no_bu':      bus.get('', 0),
    })


@app.route('/api/rental/export', methods=['GET'])
def rental_export():
    """Export เครื่องเช่าเป็น Excel สำหรับทำรายงานขอเช่าปีถัดไป

    ตัวกรอง (ว่าง = ไม่กรอง): bu, year, machine_type — คั่นหลายค่าด้วย ,
    year = ปีที่หมดสัญญา (ค.ศ.) เพราะเครื่องที่หมดปีไหน คือชุดที่ต้องขอเช่าใหม่ปีนั้น
    include_no_year / include_no_type = 1 → รวมเครื่องที่ไม่มีข้อมูลด้านนั้นเข้ามาด้วย
    (ข้อมูลจริงมีเครื่องเช่าที่ไม่มีวันหมดสัญญา ~60% ถ้าไม่รวมยอดจะหายไปเยอะ)
    """
    from collections import defaultdict
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.utils import get_column_letter

    a = request.args
    split = lambda k: [x.strip() for x in (a.get(k) or '').split(',') if x.strip()]
    bu_f, year_f, type_f = split('bu'), split('year'), split('machine_type')
    inc_no_year = a.get('include_no_year') == '1'
    inc_no_type = a.get('include_no_type') == '1'

    rows = _rental_rows(fetch_assets_raw())
    if bu_f:
        rows = [r for r in rows if (r.get('emp_bu_code') or '') in bu_f]
    def keep_year(r):
        # ไม่มีวันหมดสัญญา = ตัดสินด้วย include_no_year ไม่ใช่ตัดทิ้งเงียบๆ
        return r['end_date'][:4] in year_f if r.get('end_date') else inc_no_year

    def keep_type(r):
        return r['machine_type'] in type_f if r.get('machine_type') else inc_no_type

    if year_f:
        rows = [r for r in rows if keep_year(r)]
    if type_f:
        rows = [r for r in rows if keep_type(r)]

    UNSPEC = 'ยังไม่ระบุประเภท'
    mt_of  = lambda r: r.get('machine_type') or UNSPEC
    bu_of  = lambda r: r.get('emp_bu_code') or 'ไม่ระบุ BU'
    rows.sort(key=lambda r: (_machine_rank(mt_of(r)), mt_of(r), bu_of(r),
                             r.get('end_date') or '9999', r.get('asset_no') or ''))

    wb = Workbook()
    HFILL  = PatternFill('solid', fgColor='1E3A5F')
    SUBFIL = PatternFill('solid', fgColor='F1F5F9')
    THIN   = Side(style='thin', color='D8DEE7')
    BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)

    def style_header(ws, ncols, row=1):
        for c in range(1, ncols + 1):
            cell = ws.cell(row=row, column=c)
            cell.font = Font(color='FFFFFF', bold=True, size=10)
            cell.fill = HFILL
            cell.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)

    def autosize(ws, minw=9, maxw=42):
        for col in ws.columns:
            width = max((len(str(c.value or '')) for c in col), default=0)
            ws.column_dimensions[get_column_letter(col[0].column)].width = \
                min(max(width + 2, minw), maxw)

    # ── ชีท 1: สรุป — ประเภทเครื่อง × BU (เอาไปแปะรายงานขอเช่าได้เลย) ──
    ws = wb.active
    ws.title = 'สรุป'

    bu_cols = sorted({bu_of(r) for r in rows})
    mt_keys = sorted({mt_of(r) for r in rows}, key=lambda m: (_machine_rank(m), m))
    cnt   = defaultdict(int)
    money = defaultdict(float)
    for r in rows:
        cnt[(mt_of(r), bu_of(r))]  += 1
        money[(mt_of(r), bu_of(r))] += r.get('monthly_charge') or 0

    filters_txt = ' · '.join(filter(None, [
        'BU: ' + ', '.join(bu_f) if bu_f else 'ทุก BU',
        'ปีหมดสัญญา: ' + ', '.join(year_f) if year_f else 'ทุกปี',
        'ประเภทเครื่อง: ' + ', '.join(type_f) if type_f else 'ทุกประเภท',
        'รวมเครื่องที่ไม่มีวันหมดสัญญา' if inc_no_year and year_f else None,
        'รวมเครื่องที่ยังไม่ระบุประเภท' if inc_no_type and type_f else None,
    ]))
    ws.append(['สรุปเครื่องเช่า เพื่อจัดทำรายงานขอเช่า'])
    ws['A1'].font = Font(bold=True, size=13)
    ws.append(['ตัวกรอง: ' + filters_txt])
    ws['A2'].font = Font(size=9, color='64748B')
    ws.append(['ออกรายงานเมื่อ ' + datetime.now().strftime('%d/%m/%Y %H:%M น.') +
               '  ·  รวม %d เครื่อง' % len(rows)])
    ws['A3'].font = Font(size=9, color='64748B')
    ws.append([])

    head_row = ws.max_row + 1
    ws.append(['ประเภทเครื่อง'] + bu_cols + ['รวม', 'ค่าเช่ารวม/เดือน (฿)'])
    style_header(ws, 2 + len(bu_cols), head_row)

    for mt in mt_keys:
        line = [mt] + [cnt[(mt, b)] or '' for b in bu_cols]
        line += [sum(cnt[(mt, b)] for b in bu_cols),
                 round(sum(money[(mt, b)] for b in bu_cols))]
        ws.append(line)
    total_row = ws.max_row + 1
    ws.append(['รวมทุกประเภท'] +
              [sum(cnt[(m, b)] for m in mt_keys) for b in bu_cols] +
              [len(rows), round(sum(money.values()))])
    for c in range(1, 3 + len(bu_cols)):
        ws.cell(row=total_row, column=c).font = Font(bold=True)
        ws.cell(row=total_row, column=c).fill = SUBFIL
    for row in ws.iter_rows(min_row=head_row, max_row=total_row,
                            max_col=2 + len(bu_cols)):
        for cell in row:
            cell.border = BORDER
            if cell.column > 1:
                cell.alignment = Alignment(horizontal='right')
    for r_ in range(head_row + 1, total_row + 1):
        ws.cell(row=r_, column=2 + len(bu_cols)).number_format = '#,##0'
    ws.freeze_panes = ws.cell(row=head_row + 1, column=2)
    autosize(ws)

    # ── ชีท 2: รายการเครื่อง — ไว้ตรวจสอบรายตัว ─────────────────────
    ws2 = wb.create_sheet('รายการเครื่อง')
    headers = ['ประเภทเครื่อง', 'BU', 'Asset No.', 'รหัสเครื่อง', 'S/N',
               'ประเภท (eDevice)', 'รุ่น', 'ผู้ถือครอง', 'ตำแหน่ง', 'แผนก',
               'วันเริ่มเช่า', 'วันหมดสัญญา', 'ปีหมดสัญญา', 'เหลือ (วัน)',
               'สถานะสัญญา', 'สถานะ eDevice', 'ค่าเช่า/เดือน (฿)', 'PO']
    ws2.append(headers)
    style_header(ws2, len(headers))
    ST = {'ok': 'อยู่ในระยะสัญญา', 'warning': 'ใกล้หมด (180 วัน)',
          'critical': 'วิกฤต (90 วัน)', 'expired': 'หมดสัญญาแล้ว',
          'unknown': 'ไม่มีข้อมูลสัญญา'}
    for r in rows:
        ws2.append([
            mt_of(r), bu_of(r), r.get('asset_no', ''), r.get('computer_id', ''),
            r.get('serial_no', ''), r.get('asset_type', ''),
            r.get('brand') or r.get('model') or '',
            r.get('user_name', ''), r.get('emp_position', ''),
            r.get('emp_dept') or r.get('dept_sheet') or '',
            r.get('start_date', ''), r.get('end_date', ''),
            (r['end_date'][:4] if r.get('end_date') else ''),
            r.get('days_remaining'), ST.get(r.get('contract_status'), ''),
            r.get('edevice_status', ''), r.get('monthly_charge') or 0,
            r.get('po_no', ''),
        ])
    for row in ws2.iter_rows(min_row=2, max_row=ws2.max_row):
        row[16].number_format = '#,##0.00'
    ws2.auto_filter.ref = ws2.dimensions
    ws2.freeze_panes = 'A2'
    autosize(ws2)

    buf = io.BytesIO()
    wb.save(buf); buf.seek(0)
    tag = '_'.join(filter(None, ['-'.join(bu_f), '-'.join(year_f)])) or 'all'
    fname = f"rental_plan_{tag}_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
    return send_file(buf, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                     as_attachment=True, download_name=fname)


# ---------- Dashboard: บริหาร Software ----------

def _software_rows(conn):
    """license ทุกใบ พร้อมข้อมูลผู้ถือครอง — ฐานของทุกตัวเลขในหน้านี้"""
    return conn.execute('''
        SELECT a.id, a.software_id, a.note, a.created_at,
               COALESCE(c.name, a.software) AS name,
               c.category, c.vendor, c.license_type, c.is_active,
               COALESCE(c.is_bundle, 0) AS is_bundle,
               e.id AS emp_id, e.emp_code, e.name AS emp_name, e.bu_code,
               e.department, e.position, e.status
        FROM software_assignments a
        LEFT JOIN software_catalog c ON c.id = a.software_id
        LEFT JOIN employees e        ON e.id = a.employee_id
        ORDER BY name COLLATE NOCASE, e.bu_code, e.name
    ''').fetchall()


@app.route('/api/dashboard/software', methods=['GET'])
def dashboard_software():
    from collections import defaultdict

    conn = get_db()
    rows = _software_rows(conn)
    catalog = conn.execute(
        'SELECT id, name, category, vendor, license_type, is_active FROM software_catalog'
    ).fetchall()
    members = _bundle_map(conn)
    cover   = _emp_covered(conn, members)
    names   = {c['id']: c['name'] for c in catalog}
    emp_active = conn.execute(
        "SELECT COUNT(*) c FROM employees WHERE status='active'").fetchone()['c']
    bus = [r['bu_code'] for r in conn.execute(
        'SELECT DISTINCT bu_code FROM employees WHERE bu_code != "" ORDER BY bu_code')]
    emp_by_bu = {r['bu_code']: r['c'] for r in conn.execute(
        "SELECT bu_code, COUNT(*) c FROM employees WHERE status='active' AND bu_code != '' "
        "GROUP BY bu_code")}
    conn.close()

    NO_BU = 'ไม่ระบุ BU'
    bu_of = lambda r: (r['bu_code'] or NO_BU)

    per_sw   = defaultdict(lambda: {'total': 0, 'by_bu': defaultdict(int), 'inactive': 0,
                                    'covered': 0})
    per_bu   = defaultdict(lambda: {'licenses': 0, 'emps': set()})
    holders  = set()
    orphan   = 0      # license ที่หาเจ้าของใน HR ไม่เจอแล้ว
    inactive = []     # license ค้างที่พนักงานที่ไม่ active
    n_lic    = 0
    n_cov    = 0

    for r in rows:
        key = r['software_id'] or ('name:' + (r['name'] or ''))
        s = per_sw[key]
        s.setdefault('meta', {'id': r['software_id'], 'name': r['name'],
                              'category': r['category'], 'vendor': r['vendor'],
                              'license_type': r['license_type'],
                              'is_active': r['is_active'], 'is_bundle': r['is_bundle']})
        if r['emp_id'] is not None:
            holders.add(r['emp_id'])
            per_bu[bu_of(r)]['emps'].add(r['emp_id'])
        # ชุดรวม (All Apps) นับเป็น 1 — โปรแกรมข้างในชุดที่คนนั้นถืออยู่ไม่นับเป็น license
        if r['software_id'] in cover.get(r['emp_id'], ()):
            s['covered'] += 1
            n_cov += 1
            continue
        n_lic += 1
        s['total'] += 1
        s['by_bu'][bu_of(r)] += 1
        if r['emp_id'] is None:
            orphan += 1
        else:
            per_bu[bu_of(r)]['licenses'] += 1
        if r['status'] and r['status'] != 'active':
            s['inactive'] += 1
            inactive.append({
                'assignment_id': r['id'], 'software': r['name'],
                'emp_id': r['emp_id'], 'emp_name': r['emp_name'],
                'emp_code': r['emp_code'], 'bu_code': r['bu_code'],
                'department': r['department'], 'note': r['note'],
                # ชุดรวม: บอกด้วยว่ารวมโปรแกรมอะไรของคนนี้อยู่ (ตอนเคลียร์ต้องลบด้วย)
                'covers': sorted(names.get(m, '?') for m in members.get(r['software_id'], ())),
            })

    by_software = sorted(
        [{**v['meta'], 'total': v['total'], 'inactive': v['inactive'],
          'covered': v['covered'], 'by_bu': dict(v['by_bu'])} for v in per_sw.values()],
        key=lambda s: (-s['total'], -s['covered'], (s['name'] or '').lower()))

    used = {s['id'] for s in by_software if s['id']}
    unused = sorted(
        [dict(c) for c in catalog if c['id'] not in used],
        key=lambda c: ((c['category'] or 'ยังไม่จัดหมวด'), c['name'].lower()))

    by_bu = sorted(
        [{'bu_code': b, 'licenses': v['licenses'], 'employees': len(v['emps']),
          'emp_total': emp_by_bu.get(b, 0)} for b, v in per_bu.items()],
        key=lambda x: -x['licenses'])

    return jsonify({
        'summary': {
            'licenses':          n_lic,     # ชุดรวมนับ 1 ไม่นับโปรแกรมข้างใน
            'covered':           n_cov,     # โปรแกรมที่ใช้ผ่านชุดรวม (ไม่นับเป็น license)
            'employees_with':    len(holders),
            'employees_active':  emp_active,
            'catalog_total':     len(catalog),
            'catalog_used':      len(used),
            'catalog_unused':    len(unused),
            'inactive_licenses': len(inactive),
            'orphan_licenses':   orphan,
        },
        'bus':         bus + [NO_BU],
        'by_software': by_software,
        'by_bu':       by_bu,
        'unused':      unused,
        'inactive':    sorted(inactive, key=lambda x: ((x['bu_code'] or ''),
                                                       (x['emp_name'] or ''))),
    })


# เกณฑ์ชี้ว่าใครควรใช้ Adobe Creative Cloud (All Apps) แทนการซื้อแยกตัว
# ถือ Adobe ตั้งแต่ 3 ตัวขึ้นไปถือว่าคุ้มกว่า — ไม่นับ Media Encoder เพราะแถมมากับ Premiere
CC_RULE = {
    'label':   'Creative Cloud (All Apps)',
    'min':     3,
    'exclude': ['Adobe Media Encoder'],
}


def _vendor_of(r):
    """ผู้ผลิตของ license หนึ่งใบ — ถ้าช่อง vendor ว่าง เดาจากคำแรกของชื่อ"""
    v = (r['vendor'] or '').strip()
    if v:
        return v
    name = (r['name'] or '').strip()
    return name.split()[0] if name else 'ไม่ระบุผู้ผลิต'


@app.route('/api/dashboard/software/vendor', methods=['GET'])
def dashboard_software_vendor():
    """ไล่ดูทีละผู้ผลิต (ตั้งต้น Adobe): BU → ฝ่าย/แผนก → รายคน ว่าใครถือตัวไหน

    ฐานข้อมูลพนักงานมีชั้นหน่วยงานเดียวคือ department จึงใช้ช่องนั้นเป็น "ฝ่าย"
    """
    from collections import defaultdict

    want = (request.args.get('name') or 'Adobe').strip()
    conn = get_db()
    rows = _software_rows(conn)
    catalog = conn.execute(
        'SELECT id, name, category, vendor, license_type, is_active, is_bundle, seats '
        'FROM software_catalog'
    ).fetchall()
    members = _bundle_map(conn)
    conn.close()

    # รายชื่อผู้ผลิตให้เลือก — เรียงจากที่มี license มากไปน้อย
    v_lic, v_prod = defaultdict(int), defaultdict(set)
    for r in rows:
        v = _vendor_of(r)
        v_lic[v] += 1
        v_prod[v].add(r['name'])
    vendors = sorted(
        [{'name': v, 'licenses': n, 'products': len(v_prod[v])} for v, n in v_lic.items()],
        key=lambda x: (-x['licenses'], x['name'].lower()))

    mine = [r for r in rows if _vendor_of(r).lower() == want.lower()]

    NO_BU, NO_DEPT = 'ไม่ระบุ BU', 'ไม่ระบุฝ่าย'
    prod_total = defaultdict(int)
    tree       = {}   # bu → dept → emp_id → ข้อมูลคน
    people     = set()

    for r in mine:
        bu   = r['bu_code'] or NO_BU
        dept = r['department'] or NO_DEPT
        eid  = r['emp_id']
        d = tree.setdefault(bu, {}).setdefault(dept, {})
        p = d.setdefault(eid, {
            'emp_id': eid, 'emp_code': r['emp_code'],
            'name': r['emp_name'] or '(ไม่พบใน HR)',
            'position': r['position'], 'status': r['status'],
            'items': [], 'bundles': [], 'covered_ids': set(),
        })
        # ชุดรวม (All Apps) ไม่ใช่โปรแกรม — แยกเก็บ ไม่ปนกับรายการที่ใช้จริง
        if r['is_bundle']:
            p['bundles'].append(r['name'])
            p['covered_ids'].update(members.get(r['software_id'], ()))
        else:
            prod_total[r['name']] += 1
            p['items'].append({'product': r['name'], 'note': r['note'] or '',
                               'sid': r['software_id']})
        if eid is not None:
            people.add(eid)

    products = sorted(prod_total.items(), key=lambda kv: (-kv[1], kv[0].lower()))

    # เกณฑ์ All Apps ใช้กับ Adobe เท่านั้น ผู้ผลิตอื่นไม่มีชุดรวมแบบนี้
    rule = CC_RULE if want.lower() == 'adobe' else None
    skip = {x.lower() for x in (rule['exclude'] if rule else [])}

    def pack_people(d):
        out = []
        for p in d.values():
            p['items'].sort(key=lambda i: i['product'].lower())
            p['products'] = [i['product'] for i in p['items']]
            # จำนวน license: ชุดรวมนับ 1 + ตัวที่ซื้อแยก (โปรแกรมที่อยู่ในชุดไม่นับซ้ำ)
            cov = p.pop('covered_ids')
            for i in p['items']:
                i['in_bundle'] = i.pop('sid') in cov
            p['licenses'] = len(p['bundles']) + sum(1 for i in p['items'] if not i['in_bundle'])
            if rule:
                p['counted'] = [i['product'] for i in p['items']
                                if i['product'].lower() not in skip]
                # ถือชุดรวมอยู่แล้ว = All Apps จริง / ถึงเกณฑ์แต่ยังไม่ได้บันทึกชุด = ควรได้
                p['has_bundle'] = bool(p['bundles'])
                p['cc_pending'] = not p['bundles'] and len(p['counted']) >= rule['min']
                p['cc'] = p['has_bundle'] or p['cc_pending']
            out.append(p)
        out.sort(key=lambda p: (-len(p['items']), (p['name'] or '').lower()))
        return out

    def count_products(items_src):
        c = defaultdict(int)
        for p in items_src:
            for i in p['items']:
                c[i['product']] += 1
        return dict(c)

    by_bu = []
    for bu, depts in tree.items():
        dept_list = []
        for dept, emps in depts.items():
            plist = pack_people(emps)
            dept_list.append({
                'department': dept,
                'licenses':   sum(p['licenses'] for p in plist),
                'people':     len(plist),
                'products':   count_products(plist),
                'cc':         sum(1 for p in plist if p.get('cc')),
                'few':        sum(1 for p in plist if rule and not p.get('cc')),
                'lic_cc':     sum(len(p['items']) for p in plist if p.get('cc')),
                'lic_few':    sum(len(p['items']) for p in plist
                                  if rule and not p.get('cc')),
                'people_list': plist,
            })
        dept_list.sort(key=lambda d: (-d['licenses'], d['department'].lower()))
        by_bu.append({
            'bu_code':  bu,
            'licenses': sum(d['licenses'] for d in dept_list),
            'people':   sum(d['people'] for d in dept_list),
            'products': count_products([p for d in dept_list for p in d['people_list']]),
            'cc':       sum(d['cc'] for d in dept_list),
            'few':      sum(d['few'] for d in dept_list),
            'lic_cc':   sum(d['lic_cc'] for d in dept_list),
            'lic_few':  sum(d['lic_few'] for d in dept_list),
            'depts':    dept_list,
        })
    by_bu.sort(key=lambda b: (-b['licenses'], b['bu_code']))

    held = {r['name'] for r in mine}
    unused = sorted([c['name'] for c in catalog
                     if _vendor_of(c).lower() == want.lower() and c['name'] not in held
                     and not c['is_bundle']],
                    key=str.lower)

    # สรุปแยก 2 กลุ่ม: คนที่ควรใช้ All Apps (ถือ ≥ min) กับคนที่ใช้ไม่ถึงเกณฑ์
    groups = None
    if rule:
        everyone = [p for b in by_bu for d in b['depts'] for p in d['people_list']]

        def summarize(ppl):
            prod = defaultdict(int)
            dist = defaultdict(int)
            for p in ppl:
                for i in p['items']:
                    prod[i['product']] += 1
                dist[len(p['counted'])] += 1
            return {
                'people':   len(ppl),
                'licenses': sum(len(p['items']) for p in ppl),
                'products': dict(sorted(prod.items(), key=lambda kv: (-kv[1], kv[0].lower()))),
                # กระจายตามจำนวนโปรแกรมที่นับได้ เช่น {1: 20, 2: 27}
                'dist':     {str(k): v for k, v in sorted(dist.items())},
            }

        cc_people  = [p for p in everyone if p['cc']]
        few_people = [p for p in everyone if not p['cc']]

        # แผนต่ออายุ = All Apps เท่าจำนวนคนที่เข้าเกณฑ์
        #            + ตัวแยกเท่าจำนวนคนในกลุ่มไม่ถึงเกณฑ์ที่ถือตัวนั้น
        few_prod = defaultdict(int)
        for p in few_people:
            for i in p['items']:
                few_prod[i['product']] += 1
        n_has     = sum(1 for p in cc_people if p['has_bundle'])
        n_pending = len(cc_people) - n_has
        plan = [{'item': rule['label'], 'qty': len(cc_people), 'kind': 'bundle',
                 'note': (f'ถือชุด All Apps อยู่ {n_has} คน' if n_has else
                          f'สำหรับคนที่ใช้ตั้งแต่ {rule["min"]} ตัวขึ้นไป')
                         + (f' + ใช้ถึง {rule["min"]} ตัวแต่ยังไม่ได้บันทึกชุด {n_pending} คน'
                            if n_has and n_pending else '')}]
        plan += [{'item': n, 'qty': q, 'kind': 'single',
                  'note': 'ซื้อแยกให้คนที่ใช้ไม่ถึงเกณฑ์'}
                 for n, q in sorted(few_prod.items(), key=lambda kv: (-kv[1], kv[0].lower()))]
        # จำนวนที่ซื้อไว้จริงตามคลัง (None = ยังไม่ได้ระบุ) ไว้เทียบกับที่ต้องใช้
        mine_cat = [c for c in catalog if _vendor_of(c).lower() == want.lower()]
        b_seats  = [c['seats'] for c in mine_cat if c['is_bundle']]
        s_seats  = {c['name']: c['seats'] for c in mine_cat if not c['is_bundle']}
        plan[0]['seats'] = (sum(x for x in b_seats if x is not None)
                            if any(x is not None for x in b_seats) else None)
        plan[0]['catalog_name'] = next((c['name'] for c in mine_cat if c['is_bundle']), None)
        for p_ in plan[1:]:
            p_['seats'] = s_seats.get(p_['item'])
        # ตัวที่ซื้อไว้แต่ไม่มีใครต้องใช้แยก (อยู่ใน All Apps หมด) — โชว์ไว้ ยอดซื้อจะได้ครบ
        in_plan = {p_['item'] for p_ in plan}
        plan += [{'item': n, 'qty': 0, 'kind': 'single', 'seats': st,
                  'note': 'ไม่มีคนต้องใช้แยก'}
                 for n, st in sorted(s_seats.items(), key=lambda kv: kv[0].lower())
                 if st and n not in in_plan]

        # แผนเดียวกันแต่แยกตาม BU/ฝ่าย เพราะงบและใบขอซื้อแยกตาม BU
        def plan_of(ppl):
            d = defaultdict(int)
            for p in ppl:
                if not p['cc']:
                    for i in p['items']:
                        d[i['product']] += 1
            return {'allapps': sum(1 for p in ppl if p['cc']), 'items': dict(d)}

        plan_by_bu = []
        for b in by_bu:
            ppl_bu = [p for d in b['depts'] for p in d['people_list']]
            plan_by_bu.append({
                'bu_code': b['bu_code'], **plan_of(ppl_bu),
                'depts': [{'department': d['department'], **plan_of(d['people_list'])}
                          for d in b['depts']],
            })

        groups = {
            'rule': rule,
            'plan': plan,
            'plan_by_bu': plan_by_bu,
            'current_singles': sum(prod_total.values()),   # แถวโปรแกรมที่ใช้อยู่ทั้งหมด
            'has_bundle': sum(1 for p in everyone if p.get('has_bundle')),
            'cc_pending': sum(1 for p in everyone if p.get('cc_pending')),
            'cc':   summarize(cc_people),
            'few':  summarize(few_people),
            'by_bu': [{
                'bu_code': b['bu_code'],
                'people': b['people'], 'cc': b['cc'], 'few': b['few'],
                'lic_cc': b['lic_cc'], 'lic_few': b['lic_few'],
                'depts': [{
                    'department': d['department'], 'people': d['people'],
                    'cc': d['cc'], 'few': d['few'],
                    'lic_cc': d['lic_cc'], 'lic_few': d['lic_few'],
                } for d in b['depts']],
            } for b in by_bu],
        }

    return jsonify({
        'vendor':   want,
        'vendors':  vendors,
        'products': [{'name': n, 'total': t} for n, t in products],
        'unused':   unused,
        'rule':     rule,
        'groups':   groups,
        'summary': {
            'licenses': sum(d['licenses'] for b in by_bu for d in b['depts']),
            'usage':    sum(prod_total.values()),   # จำนวนโปรแกรมที่บันทึกว่าใช้ (นับทุกตัว)
            'bundles':  sum(1 for r in mine if r['is_bundle']),
            'people':   len(people),
            'bus':      len(by_bu),
            'depts':    sum(len(b['depts']) for b in by_bu),
            'products': len(products),
            'cc':       sum(b['cc'] for b in by_bu) if rule else 0,
        },
        'by_bu': by_bu,
    })


@app.route('/api/software/catalog/<int:cid>/holders', methods=['GET'])
def software_holders(cid):
    """ใครถือ software ตัวนี้บ้าง — ใช้ตอนคลิกดูรายชื่อจากหน้า dashboard"""
    conn = get_db()
    rows = conn.execute('''
        SELECT a.id, a.note, a.created_at,
               e.id AS emp_id, e.emp_code, e.name AS emp_name, e.nickname,
               e.bu_code, e.department, e.position, e.status
        FROM software_assignments a
        LEFT JOIN employees e ON e.id = a.employee_id
        WHERE a.software_id = ?
        ORDER BY e.bu_code, e.name COLLATE NOCASE''', (cid,)).fetchall()
    cover = _emp_covered(conn)
    conn.close()
    # via_bundle = ใช้ผ่านชุดรวมที่ถืออยู่ ไม่กิน seat ของตัวแยก
    return jsonify([{**dict(r), 'via_bundle': cid in cover.get(r['emp_id'], ())}
                    for r in rows])


@app.route('/api/software/export', methods=['GET'])
def software_export():
    """Export ข้อมูล Software ถือครองเป็น Excel — สรุป (Software × BU) + รายการรายใบ

    ?bu=AMTV,APUB → กรองเฉพาะ BU ที่ต้องการ (ว่าง = ทุก BU)
    ?vendor=Adobe → เฉพาะผู้ผลิตนั้น แล้วเพิ่มชีท ฝ่าย × Software และ รายคน × Software
                    (ตารางติ๊กว่าใครถือตัวไหน ใช้ทำรายงานต่อสัญญารายปี)
    """
    from collections import defaultdict
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.utils import get_column_letter

    bu_f   = [x.strip() for x in (request.args.get('bu') or '').split(',') if x.strip()]
    vendor = (request.args.get('vendor') or '').strip()

    conn = get_db()
    rows = [dict(r) for r in _software_rows(conn)]
    # โปรแกรมที่อยู่ในชุดรวมที่คนนั้นถือ → ไม่นับเป็น license (ชุดรวมนับ 1)
    cover = _emp_covered(conn)
    for r in rows:
        r['in_bundle'] = r['software_id'] in cover.get(r['emp_id'], ())
    unused = [dict(r) for r in conn.execute('''
        SELECT c.name, c.category, c.vendor, c.license_type, c.is_active, c.seats
        FROM software_catalog c
        WHERE c.id NOT IN (SELECT software_id FROM software_assignments
                           WHERE software_id IS NOT NULL)
        ORDER BY c.category COLLATE NOCASE, c.name COLLATE NOCASE''').fetchall()]
    conn.close()

    NO_BU, NO_DEPT = 'ไม่ระบุ BU', 'ไม่ระบุฝ่าย'
    bu_of   = lambda r: (r['bu_code'] or NO_BU)
    dept_of = lambda r: (r['department'] or NO_DEPT)
    if bu_f:
        rows = [r for r in rows if bu_of(r) in bu_f]
    if vendor:
        rows   = [r for r in rows if _vendor_of(r).lower() == vendor.lower()]
        unused = [c for c in unused if _vendor_of(c).lower() == vendor.lower()]

    LIC = {'subscription': 'รายปี', 'perpetual': 'ซื้อขาด',
           'oem': 'ติดมากับเครื่อง', 'free': 'ฟรี'}

    wb = Workbook()
    HFILL  = PatternFill('solid', fgColor='1E3A5F')
    SUBFIL = PatternFill('solid', fgColor='F1F5F9')
    THIN   = Side(style='thin', color='D8DEE7')
    BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)

    def style_header(ws, ncols, row=1):
        for c in range(1, ncols + 1):
            cell = ws.cell(row=row, column=c)
            cell.font = Font(color='FFFFFF', bold=True, size=10)
            cell.fill = HFILL
            cell.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)

    def autosize(ws, minw=9, maxw=42):
        for col in ws.columns:
            width = max((len(str(c.value or '')) for c in col), default=0)
            ws.column_dimensions[get_column_letter(col[0].column)].width = \
                min(max(width + 2, minw), maxw)

    # ── ชีท 1: สรุป Software × BU ──────────────────────────────────
    ws = wb.active
    ws.title = 'สรุป'
    bu_cols = sorted({bu_of(r) for r in rows})
    cnt = defaultdict(int)
    cov = defaultdict(int)
    for r in rows:
        if r['in_bundle']:
            cov[r['name']] += 1
        else:
            cnt[(r['name'], bu_of(r))] += 1
    n_lic = sum(1 for r in rows if not r['in_bundle'])
    sw_keys = sorted({r['name'] for r in rows},
                     key=lambda n: (-sum(cnt[(n, b)] for b in bu_cols), -cov[n], n.lower()))
    meta = {r['name']: r for r in rows}

    ws.append([('สรุป Software ที่พนักงานถือครอง' if not vendor
                else f'สรุป Software ของ {vendor} ที่พนักงานถือครอง')])
    ws['A1'].font = Font(bold=True, size=13)
    ws.append(['ตัวกรอง: ' + ' · '.join(filter(None, [
        'BU: ' + ', '.join(bu_f) if bu_f else 'ทุก BU',
        'ผู้ผลิต: ' + vendor if vendor else None]))])
    ws['A2'].font = Font(size=9, color='64748B')
    ws.append(['ออกรายงานเมื่อ ' + datetime.now().strftime('%d/%m/%Y %H:%M น.') +
               '  ·  รวม %d license (ชุดรวม All Apps นับ 1 ไม่นับโปรแกรมข้างใน)' % n_lic])
    ws['A3'].font = Font(size=9, color='64748B')
    ws.append([])

    # จำนวนที่ซื้อไว้ตามคลัง (ว่าง = ยังไม่ได้ระบุ) — กรอง BU = ใช้ยอดซื้อของ BU นั้น
    conn = get_db()
    if bu_f:
        seats_of = {}
        for r in conn.execute(
                f'''SELECT c.name, SUM(s.seats) seats FROM software_bu_seats s
                    JOIN software_catalog c ON c.id = s.software_id
                    WHERE s.bu_code IN ({','.join('?' * len(bu_f))}) AND s.seats IS NOT NULL
                    GROUP BY c.name''', bu_f):
            seats_of[r['name']] = r['seats']
    else:
        seats_of = {r['name']: r['seats'] for r in
                    conn.execute('SELECT name, seats FROM software_catalog')}
    conn.close()

    def seat_diff(seats, used):
        if seats is None:
            return ''
        return f'เกิน {used - seats}' if used > seats else (
               f'เหลือ {seats - used}' if seats > used else 'พอดี')

    head_row = ws.max_row + 1
    ncol = 7 + len(bu_cols)
    ws.append(['Software', 'หมวด', 'ลิขสิทธิ์'] + bu_cols +
              ['รวม (ใช้)', 'ซื้อไว้', 'เหลือ / เกิน', 'ใช้ในชุดรวม (ไม่นับ)'])
    style_header(ws, ncol, head_row)
    for n in sw_keys:
        m = meta[n]
        used  = sum(cnt[(n, b)] for b in bu_cols)
        seats = seats_of.get(n)
        ws.append([n + (' [ชุดรวม]' if m['is_bundle'] else ''), m['category'] or '',
                   LIC.get(m['license_type'], m['license_type'] or '')] +
                  [cnt[(n, b)] or '' for b in bu_cols] +
                  [used, '' if seats is None else seats, seat_diff(seats, used), cov[n] or ''])
        if str(ws.cell(row=ws.max_row, column=ncol - 1).value).startswith('เกิน'):
            ws.cell(row=ws.max_row, column=ncol - 1).font = Font(bold=True, color='DC2626')
    total_row = ws.max_row + 1
    seat_known = [seats_of[n] for n in sw_keys if seats_of.get(n) is not None]
    ws.append(['รวมทุก Software', '', ''] +
              [sum(cnt[(n, b)] for n in sw_keys) for b in bu_cols] +
              [n_lic, sum(seat_known) if seat_known else '',
               f'ระบุจำนวนซื้อแล้ว {len(seat_known)}/{len(sw_keys)} รายการ',
               sum(cov.values()) or ''])
    for c in range(1, ncol + 1):
        ws.cell(row=total_row, column=c).font = Font(bold=True)
        ws.cell(row=total_row, column=c).fill = SUBFIL
    for row in ws.iter_rows(min_row=head_row, max_row=total_row, max_col=ncol):
        for cell in row:
            cell.border = BORDER
            if cell.column > 3:
                cell.alignment = Alignment(horizontal='right')
    ws.freeze_panes = ws.cell(row=head_row + 1, column=4)
    autosize(ws)

    # ── ชีท 2: รายการรายใบ ────────────────────────────────────────
    ws2 = wb.create_sheet('รายการ license')
    headers = ['Software', 'หมวด', 'ผู้ผลิต', 'ลิขสิทธิ์', 'รหัสพนักงาน', 'ชื่อ-สกุล',
               'BU', 'แผนก', 'ตำแหน่ง', 'สถานะพนักงาน', 'หมายเหตุ', 'วันที่บันทึก',
               'ชุดรวม']
    ws2.append(headers)
    style_header(ws2, len(headers))
    for r in rows:
        ws2.append([
            r['name'], r['category'] or '', r['vendor'] or '',
            LIC.get(r['license_type'], r['license_type'] or ''),
            r['emp_code'] or '', r['emp_name'] or '(ไม่พบใน HR)',
            r['bu_code'] or '', r['department'] or '', r['position'] or '',
            'Active' if r['status'] == 'active' else ('Inactive' if r['status'] else '—'),
            r['note'] or '', (r['created_at'] or '')[:10],
            'ชุดรวม' if r['is_bundle'] else ('ใช้ผ่านชุดรวม' if r['in_bundle'] else ''),
        ])
    ws2.auto_filter.ref = ws2.dimensions
    ws2.freeze_panes = 'A2'
    autosize(ws2)

    # ── ชีทเพิ่มเมื่อดูเป็นผู้ผลิต: ฝ่าย × Software และ รายคน × Software ──
    rule = None
    if vendor and rows:
        # ชุดรวม (All Apps) ไม่ใช่โปรแกรม — ตารางติ๊กนับเฉพาะโปรแกรมที่ใช้จริง
        # ส่วนคนที่ถือชุดรวมอยู่ถือว่าเป็นกลุ่ม All Apps แน่นอน
        # people_rows = ใช้หาว่ามีใครบ้าง (รวมคนที่ถือแต่ชุดรวม ยังไม่ได้ระบุโปรแกรม)
        # rows        = ใช้นับจำนวนโปรแกรม
        bundle_emp = {r['emp_id'] for r in rows if r['is_bundle'] and r['emp_id'] is not None}
        prog_emp   = {r['emp_id'] for r in rows if not r['is_bundle']}
        people_rows = [r for r in rows if not r['is_bundle'] or r['emp_id'] not in prog_emp]
        rows = [r for r in rows if not r['is_bundle']]
    else:
        people_rows = rows
    if vendor and people_rows:
        prods = sorted({r['name'] for r in rows},
                       key=lambda n: (-sum(1 for r in rows if r['name'] == n), n.lower()))

        # เกณฑ์ All Apps: ถือ Adobe ≥ 3 ตัว (ไม่นับ Media Encoder)
        rule = CC_RULE if vendor.lower() == 'adobe' else None
        skip = {x.lower() for x in (rule['exclude'] if rule else [])}
        per_emp = defaultdict(set)
        for r in people_rows:
            if r['emp_id'] is not None:
                per_emp[r['emp_id']]
                if not r['is_bundle']:
                    per_emp[r['emp_id']].add(r['name'])
        cc_emp = {e for e, ps in per_emp.items()
                  if rule and (e in bundle_emp or
                               len([p for p in ps if p.lower() not in skip]) >= rule['min'])}

        wsd = wb.create_sheet(f'ฝ่าย × {vendor}'[:31])
        wsd.append(['BU', 'ฝ่าย / แผนก', 'จำนวนคน'] + prods +
                   ['รวม license'] + (['All Apps (คน)'] if rule else []))
        style_header(wsd, 4 + len(prods) + (1 if rule else 0))
        dcnt = defaultdict(int)
        dpeople = defaultdict(set)
        for r in rows:
            dcnt[(bu_of(r), dept_of(r), r['name'])] += 1
        for r in people_rows:
            if r['emp_id'] is not None:
                dpeople[(bu_of(r), dept_of(r))].add(r['emp_id'])
        keys = sorted({(bu_of(r), dept_of(r)) for r in people_rows},
                      key=lambda k: (k[0], -sum(dcnt[(k[0], k[1], p)] for p in prods), k[1]))
        for bu, dept in keys:
            line = [bu, dept, len(dpeople[(bu, dept)])]
            line += [dcnt[(bu, dept, p)] or '' for p in prods]
            line += [sum(dcnt[(bu, dept, p)] for p in prods)]
            if rule:
                line += [len(dpeople[(bu, dept)] & cc_emp) or '']
            wsd.append(line)
        trow = wsd.max_row + 1
        wsd.append(['รวมทุกฝ่าย', '', len(per_emp)] +
                   [sum(dcnt[(b, d, p)] for b, d in keys) for p in prods] + [len(rows)] +
                   ([len(cc_emp)] if rule else []))
        for c in range(1, 5 + len(prods) + (1 if rule else 0)):
            wsd.cell(row=trow, column=c).font = Font(bold=True)
            wsd.cell(row=trow, column=c).fill = SUBFIL
        for row in wsd.iter_rows(min_row=1, max_row=trow,
                                 max_col=4 + len(prods) + (1 if rule else 0)):
            for cell in row:
                cell.border = BORDER
                if cell.column > 2:
                    cell.alignment = Alignment(horizontal='right')
        wsd.freeze_panes = 'C2'
        autosize(wsd)

        wsp = wb.create_sheet(f'รายคน × {vendor}'[:31])
        wsp.append(['BU', 'ฝ่าย / แผนก', 'รหัส', 'ชื่อ-สกุล', 'ตำแหน่ง', 'สถานะ'] +
                   prods + ['รวม'] +
                   ([f"{rule['label']} (ถือชุด หรือใช้ ≥{rule['min']} ตัว)"] if rule else []))
        style_header(wsp, 7 + len(prods) + (1 if rule else 0))
        held = defaultdict(set)
        info = {}
        for r in people_rows:
            k = (bu_of(r), dept_of(r), r['emp_id'], r['emp_name'] or '(ไม่พบใน HR)')
            held[k]
            if not r['is_bundle']:
                held[k].add(r['name'])
            info[k] = r
        for k in sorted(held, key=lambda k: (k[0], k[1], -len(held[k]), (k[3] or '').lower())):
            r = info[k]
            wsp.append([k[0], k[1], r['emp_code'] or '', k[3], r['position'] or '',
                        'Active' if r['status'] == 'active'
                        else ('Inactive' if r['status'] else '—')] +
                       ['✓' if p in held[k] else '' for p in prods] + [len(held[k])] +
                       ((['✓'] if k[2] in cc_emp else ['']) if rule else []))
        for row in wsp.iter_rows(min_row=1, max_row=wsp.max_row,
                                 max_col=7 + len(prods) + (1 if rule else 0)):
            for cell in row:
                cell.border = BORDER
                if cell.column > 6:
                    cell.alignment = Alignment(horizontal='center')
        if rule:   # คอลัมน์ All Apps ให้เป็นเครื่องหมายถูกสีแดง เหมือนบนหน้าจอ
            ccol = 7 + len(prods) + 1
            for r_ in range(2, wsp.max_row + 1):
                wsp.cell(row=r_, column=ccol).font = Font(color='DC2626', bold=True)
        wsp.auto_filter.ref = wsp.dimensions
        wsp.freeze_panes = 'E2'
        autosize(wsp)

    # ── ชีทแผนต่ออายุ (เฉพาะผู้ผลิตที่มีเกณฑ์ All Apps) ───────────
    if vendor and people_rows and rule:
        emp_prods = dict(per_emp)
        few_emp   = {e for e in emp_prods if e not in cc_emp}
        # ตัวแยกที่ต้องซื้อ = นับคนในกลุ่มไม่ถึงเกณฑ์ที่ถือโปรแกรมนั้น
        few_prod = {p: sum(1 for e in few_emp if p in emp_prods[e]) for p in prods}
        few_prod = {p: q for p, q in sorted(few_prod.items(), key=lambda kv: (-kv[1], kv[0].lower())) if q}

        wsg = wb.create_sheet('แผนต่ออายุ')
        wsg.append([f'แผนต่ออายุ license {vendor}' + (f' — {", ".join(bu_f)}' if bu_f else '')])
        wsg['A1'].font = Font(bold=True, size=13)
        wsg.append([f'All Apps = คนที่ถือชุด All Apps อยู่ หรือใช้ตั้งแต่ {rule["min"]} ตัวขึ้นไป'
                    + (f' (ไม่นับ {", ".join(rule["exclude"])})' if rule['exclude'] else '')
                    + f'  ·  ออกรายงาน {datetime.now().strftime("%d/%m/%Y %H:%M น.")}'])
        wsg['A2'].font = Font(size=9, color='64748B')
        wsg.append([])

        # จำนวนที่ซื้อไว้ตามคลัง — เทียบกับที่ต้องใช้ (ว่าง = ยังไม่ได้ระบุในคลัง)
        conn = get_db()
        vcat = [dict(c) for c in conn.execute(
            'SELECT id, name, vendor, is_bundle, seats FROM software_catalog').fetchall()
            if _vendor_of(c).lower() == vendor.lower()]
        if bu_f:   # เลือก BU → ใช้จำนวนซื้อของ BU นั้น
            per = defaultdict(list)
            for r in conn.execute(
                    f"SELECT software_id, seats FROM software_bu_seats WHERE seats IS NOT NULL "
                    f"AND bu_code IN ({','.join('?' * len(bu_f))})", bu_f):
                per[r['software_id']].append(r['seats'])
            for c in vcat:
                c['seats'] = sum(per[c['id']]) if per[c['id']] else None
        conn.close()
        b_cat   = [c for c in vcat if c['is_bundle']]
        b_seats = (sum(c['seats'] for c in b_cat if c['seats'] is not None)
                   if any(c['seats'] is not None for c in b_cat) else None)
        s_seats = {c['name']: c['seats'] for c in vcat if not c['is_bundle']}
        # ตัวที่ซื้อไว้แต่ตอนนี้ไม่ต้องใช้แยกเลย (เช่นทุกคนอยู่ใน All Apps) ก็ต้องโชว์ ยอดซื้อจะได้ครบ
        plan_items = dict(few_prod)
        for n, st in sorted(s_seats.items(), key=lambda kv: kv[0].lower()):
            if st and n not in plan_items:
                plan_items[n] = 0

        def diff(seats, need):
            if seats is None:
                return ''
            return f'ขาด {need - seats}' if seats < need else (
                   f'เหลือ {seats - need}' if seats > need else 'พอดี')

        head = wsg.max_row + 1
        wsg.append(['รายการ', 'ต้องใช้', 'ซื้อไว้', 'ขาด / เหลือ', 'ไว้ให้ใคร'])
        style_header(wsg, 5, head)
        n_has = len(cc_emp & bundle_emp)
        wsg.append([b_cat[0]['name'] if b_cat else rule['label'], len(cc_emp),
                    '' if b_seats is None else b_seats, diff(b_seats, len(cc_emp)),
                    f'ถือชุดอยู่ {n_has} คน' + (f' + ใช้ ≥ {rule["min"]} ตัวแต่ยังไม่บันทึกชุด '
                                               f'{len(cc_emp) - n_has} คน'
                                               if len(cc_emp) > n_has else '')])
        wsg.cell(row=wsg.max_row, column=1).font = Font(bold=True)
        wsg.cell(row=wsg.max_row, column=2).font = Font(bold=True, color='DC2626')
        for p, q in plan_items.items():
            st = s_seats.get(p)
            wsg.append([p, q, '' if st is None else st, diff(st, q),
                        f'{q} คน' if q else 'ไม่มีคนต้องใช้แยก'])
        for r_ in range(head + 1, wsg.max_row + 1):
            if str(wsg.cell(row=r_, column=4).value or '').startswith('ขาด'):
                wsg.cell(row=r_, column=4).font = Font(bold=True, color='DC2626')
        # ยอดรวมซื้อไว้ — ถ้ายังมีรายการที่ไม่ได้ระบุจำนวนซื้อ จะไม่สรุปขาด/เหลือ (ตัวเลขไม่ครบ)
        def total(items):
            # ไม่มีคนต้องใช้และไม่ได้ซื้อ (เช่น BU ที่ไม่มี All Apps) ไม่ต้องนับว่า "ยังไม่ระบุ"
            items = [(q, st) for q, st in items if q or st is not None]
            known = [st for _, st in items if st is not None]
            need  = sum(q for q, _ in items)
            if not known:
                return '', 'ยังไม่ได้ระบุจำนวนซื้อ'
            if len(known) < len(items):
                return sum(known), f'ระบุจำนวนซื้อแล้ว {len(known)}/{len(items)} รายการ'
            return sum(known), diff(sum(known), need)
        singles = [(q, s_seats.get(p)) for p, q in plan_items.items()]
        s_tot, s_diff = total(singles)
        a_tot, a_diff = total([(len(cc_emp), b_seats)] + singles)

        srow = wsg.max_row + 1
        wsg.append(['รวมตัวแยก', sum(few_prod.values()), s_tot, s_diff,
                    f'{len(few_emp)} คนที่ใช้ไม่ถึง {rule["min"]} ตัว'])
        wsg.append(['รวมทั้งหมด', len(cc_emp) + sum(few_prod.values()), a_tot, a_diff,
                    f'{len(cc_emp)} All Apps + {sum(few_prod.values())} ตัวแยก'])
        for r_ in (srow, srow + 1):
            for c_ in range(1, 6):
                wsg.cell(row=r_, column=c_).font = Font(bold=True)
                wsg.cell(row=r_, column=c_).fill = SUBFIL
            if str(wsg.cell(row=r_, column=4).value or '').startswith('ขาด'):
                wsg.cell(row=r_, column=4).font = Font(bold=True, color='DC2626')
        for row in wsg.iter_rows(min_row=head, max_row=srow + 1, max_col=5):
            for cell in row:
                cell.border = BORDER
                if 2 <= cell.column <= 4:
                    cell.alignment = Alignment(horizontal='right')
        wsg.append([])
        wsg.append([f'ปัจจุบันบันทึกการใช้โปรแกรมไว้ {len(rows)} รายการ — '
                    f'ต้องซื้อ {len(cc_emp)} All Apps + {sum(few_prod.values())} ตัวแยก'])
        wsg.cell(row=wsg.max_row, column=1).font = Font(size=9, color='64748B')
        wsg.append([])

        # แยกตาม BU / ฝ่าย — คอลัมน์เดียวกับรายการในแผน
        cols = list(few_prod)
        drow = wsg.max_row + 1
        wsg.append(['BU', 'ฝ่าย / แผนก', rule['label']] + cols + ['รวม'])
        style_header(wsg, 4 + len(cols), drow)
        dep_emp = defaultdict(set)
        for r in people_rows:
            if r['emp_id'] is not None:
                dep_emp[(bu_of(r), dept_of(r))].add(r['emp_id'])
        for bu, dept in keys:
            es   = dep_emp[(bu, dept)]
            ccn  = len(es & cc_emp)
            line = [bu, dept, ccn or '']
            per  = [sum(1 for e in es - cc_emp if p in emp_prods[e]) for p in cols]
            line += [v or '' for v in per]
            line += [ccn + sum(per)]
            wsg.append(line)
        trow = wsg.max_row + 1
        wsg.append(['รวมทุก BU', '', len(cc_emp)] + [few_prod[p] for p in cols] +
                   [len(cc_emp) + sum(few_prod.values())])
        for c_ in range(1, 5 + len(cols)):
            wsg.cell(row=trow, column=c_).font = Font(bold=True)
            wsg.cell(row=trow, column=c_).fill = SUBFIL
        for row in wsg.iter_rows(min_row=drow, max_row=trow, max_col=4 + len(cols)):
            for cell in row:
                cell.border = BORDER
                if cell.column > 2:
                    cell.alignment = Alignment(horizontal='right')
        autosize(wsg)

    # ── ชีท 3: ในคลังแต่ยังไม่มีใครถือ ─────────────────────────────
    ws3 = wb.create_sheet('ยังไม่มีผู้ถือครอง')
    ws3.append(['Software', 'หมวด', 'ผู้ผลิต', 'ลิขสิทธิ์', 'สถานะในคลัง', 'ซื้อไว้'])
    style_header(ws3, 6)
    for c in unused:
        ws3.append([c['name'], c['category'] or '', c['vendor'] or '',
                    LIC.get(c['license_type'], c['license_type'] or ''),
                    'เปิดใช้งาน' if c['is_active'] else 'ปิดใช้งาน',
                    '' if c['seats'] is None else c['seats']])
    ws3.freeze_panes = 'A2'
    autosize(ws3)

    buf = io.BytesIO()
    wb.save(buf); buf.seek(0)
    tag = '-'.join(bu_f) or 'all'
    fname = f"software_{tag}_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
    return send_file(buf, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                     as_attachment=True, download_name=fname)


# ---------- Presentation สำหรับผู้บริหาร (Software) ----------

def _call_json(view, url):
    """เรียก view เดิมในโปรเซสเดียวกัน เพื่อใช้ตัวเลขชุดเดียวกับหน้าจอ"""
    with app.test_request_context(url):
        return view().get_json()


def _software_deck_data(bu):
    dash = _call_json(dashboard_software, '/api/dashboard/software')
    ven  = _call_json(dashboard_software_vendor, '/api/dashboard/software/vendor?name=Adobe')
    cat  = _call_json(software_catalog_list,
                      '/api/software/catalog' + (f'?bu={_url_quote(bu)}' if bu else ''))
    seats = {c['name']: c for c in cat}

    # Software ที่ใช้ (ชุดรวมนับ 1) — กรอง BU ใช้ยอดของ BU นั้น
    sw = []
    for x in dash['by_software']:
        used = x['by_bu'].get(bu, 0) if bu else x['total']
        if used:
            c = seats.get(x['name'], {})
            sw.append({'name': x['name'], 'used': used, 'seats': c.get('seats')})
    sw.sort(key=lambda t: (-t['used'], t['name'].lower()))

    if bu:
        b = next((r for r in dash['by_bu'] if r['bu_code'] == bu), None) or {}
        emps, emp_total = b.get('employees', 0), b.get('emp_total')
    else:
        emps, emp_total = dash['summary']['employees_with'], dash['summary']['employees_active']
    over = [t for t in sw if t['seats'] is not None and t['used'] > t['seats']]
    known = [t for t in sw if t['seats'] is not None]

    # Adobe: All Apps + ตัวแยก (ยอดของ BU ที่เลือก หรือรวม)
    adobe = None
    g = ven.get('groups')
    if g:
        if bu:
            pb = next((r for r in g['plan_by_bu'] if r['bu_code'] == bu), None)
            allapps = pb['allapps'] if pb else 0
            need = dict(pb['items']) if pb else {}
        else:
            allapps = g['plan'][0]['qty']
            need = {p['item']: p['qty'] for p in g['plan'][1:]}
        bundle = next((c for c in cat if c.get('is_bundle') and (c.get('vendor') or '') == 'Adobe'), None)
        for c in cat:   # ตัวที่ซื้อไว้แต่ไม่มีใครต้องใช้แยก ก็ต้องโชว์ ยอดซื้อจะได้ครบ
            if (c.get('vendor') == 'Adobe' and not c.get('is_bundle') and c.get('seats')
                    and c['name'] not in need):
                need[c['name']] = 0
        singles = [{'item': n, 'qty': q, 'seats': (seats.get(n) or {}).get('seats')}
                   for n, q in sorted(need.items(), key=lambda kv: (-kv[1], kv[0].lower()))]
        adobe = {'allapps': allapps, 'allapps_seats': bundle.get('seats') if bundle else None,
                 'singles': singles, 'min': g['rule']['min']}

    # BU ทั้งหมด + All Apps ต่อ BU (เฉพาะรายงานรวม)
    by_bu = []
    if not bu:
        aa = {r['bu_code']: r['allapps'] for r in (g['plan_by_bu'] if g else [])}
        by_bu = [{**r, 'allapps': aa.get(r['bu_code'], 0)} for r in dash['by_bu']
                 if r['bu_code'] != 'ไม่ระบุ BU']

    # สิ่งที่ต้องดำเนินการ
    today = date.today()
    actions = []
    if over:
        actions.append(('!', f'ใช้เกินจำนวนซื้อ {len(over)} รายการ',
                        ' · '.join(f'{t["name"]} เกิน {t["used"] - t["seats"]}' for t in over[:4]) +
                        ' — ซื้อเพิ่ม หรือเรียกคืนจากคนที่ไม่ได้ใช้'))
    soon = sorted([c for c in cat if c.get('renew_date') and
                   0 <= (date.fromisoformat(c['renew_date']) - today).days <= 90],
                  key=lambda c: c['renew_date'])
    if soon:
        from report_pptx import th_date
        actions.append(('⏰', f'ต่ออายุภายใน 90 วัน {len(soon)} รายการ',
                        ' · '.join(f'{c["name"]} ({th_date(c["renew_date"])})' for c in soon[:4])))
    if adobe:
        lack = [x for x in [{'item': 'All Apps', 'qty': adobe['allapps'],
                             'seats': adobe['allapps_seats']}] + adobe['singles']
                if x['seats'] is not None and x['qty'] > x['seats']]
        if lack:
            actions.append(('A', 'Adobe ต้องซื้อเพิ่ม',
                            ' · '.join(f'{x["item"].replace("Adobe ", "")} ขาด {x["qty"] - x["seats"]}'
                                       for x in lack[:4])))
    no_seat = [t['name'] for t in sw if t['seats'] is None]
    if no_seat:
        actions.append(('?', f'ยังไม่ระบุจำนวนซื้อ {len(no_seat)} รายการ',
                        'กรอกในคลัง Software เพื่อให้เทียบใช้/ซื้อได้ครบ เช่น ' +
                        ', '.join(no_seat[:4])))

    highlights = [f'ใช้งาน {sum(t["used"] for t in sw):,} license จาก {len(sw)} รายการ '
                  f'โดยพนักงาน {emps:,} คน']
    if adobe:
        hi = f'Adobe: All Apps {adobe["allapps"]:,} ชุด + ซื้อแยก {sum(x["qty"] for x in adobe["singles"]):,} license'
        highlights.append(hi)
    highlights.append(f'ใช้เกินจำนวนซื้อ {len(over)} รายการ' if over else
                      'ไม่มี Software ที่ใช้เกินจำนวนที่ซื้อ')

    return {
        'scope': bu or 'ทุก BU', 'today': today,
        'kpi': {'licenses': sum(t['used'] for t in sw), 'products': len(sw),
                'employees': emps, 'emp_active': emp_total,
                'seats_total': sum(t['seats'] for t in known) if known else None,
                'seats_known': len(known), 'over': len(over)},
        'top': sw, 'adobe': adobe, 'by_bu': by_bu, 'actions': actions,
        'highlights': highlights,
    }


@app.route('/api/software/presentation', methods=['GET'])
def software_presentation():
    """Presentation (.pptx) สรุปบริหาร Software สำหรับผู้บริหาร · ?bu=AMTV เฉพาะ BU"""
    from report_pptx import build_software_deck
    bu  = (request.args.get('bu') or '').strip()
    buf = build_software_deck(_software_deck_data(bu))
    fname = f"software_presentation_{bu or 'all'}_{datetime.now().strftime('%Y%m%d_%H%M')}.pptx"
    return send_file(buf, as_attachment=True, download_name=fname,
                     mimetype='application/vnd.openxmlformats-officedocument.presentationml.presentation')


def _vendor_deck_data(vendor, bu):
    """ข้อมูลสำหรับ Presentation รายผู้ผลิต — ตัวเลขชุดเดียวกับ "ไล่ดูรายคน" และแผนต่ออายุ"""
    ven = _call_json(dashboard_software_vendor,
                     f'/api/dashboard/software/vendor?name={_url_quote(vendor)}')
    cat = _call_json(software_catalog_list,
                     '/api/software/catalog' + (f'?bu={_url_quote(bu)}' if bu else ''))
    vendor = ven['vendor']
    vcat = [c for c in cat if _vendor_of(c).lower() == vendor.lower()]
    seats = {c['name']: c.get('seats') for c in vcat}

    bus = [b for b in ven['by_bu'] if not bu or b['bu_code'] == bu]
    g = ven.get('groups')
    pbu = {r['bu_code']: r for r in (g['plan_by_bu'] if g else [])}

    usage = Counter()
    for b in bus:
        usage.update(b['products'])
    people = [p for b in bus for d in b['depts'] for p in d['people_list']]

    # ตัวแยกที่ต้องซื้อในขอบเขตนี้
    singles = Counter()
    allapps = 0
    for b in bus:
        r = pbu.get(b['bu_code'])
        if r:
            allapps += r['allapps']
            singles.update(r['items'])

    products = sorted([{'name': n, 'total': t, 'single': singles.get(n, 0)}
                       for n, t in usage.items()], key=lambda x: (-x['total'], x['name'].lower()))

    # รายฝ่าย
    depts = []
    for b in bus:
        pd = {x['department']: x for x in (pbu.get(b['bu_code']) or {}).get('depts', [])}
        for dd in b['depts']:
            pr = pd.get(dd['department'], {})
            depts.append({'bu_code': b['bu_code'], 'department': dd['department'],
                          'people': dd['people'], 'licenses': dd['licenses'],
                          'allapps': pr.get('allapps', 0),
                          'singles': sum((pr.get('items') or {}).values())})
    depts.sort(key=lambda x: (-x['people'], x['department'].lower()))

    plan = None
    if g:
        bundle = next((c for c in vcat if c.get('is_bundle')), None)
        need = dict(singles)
        for c in vcat:   # ซื้อไว้แต่ไม่มีใครต้องใช้แยก — โชว์ให้ยอดซื้อครบ
            if not c.get('is_bundle') and c.get('seats') and c['name'] not in need:
                need[c['name']] = 0
        items = [{'item': bundle['name'] if bundle else g['rule']['label'], 'qty': allapps,
                  'seats': bundle.get('seats') if bundle else None,
                  'who': f'{allapps:,} คนที่ใช้ All Apps' if allapps else 'ไม่มีคนใช้'}]
        items += [{'item': n, 'qty': q, 'seats': seats.get(n),
                   'who': f'{q:,} คน' if q else 'ไม่มีคนต้องใช้แยก'}
                  for n, q in sorted(need.items(), key=lambda kv: (-kv[1], kv[0].lower()))]
        counted = [it for it in items if it['qty'] or it['seats'] is not None]
        known = [it['seats'] for it in counted if it['seats'] is not None]
        plan = {'min': g['rule']['min'], 'allapps': allapps, 'items': items,
                'single_total': sum(singles.values()),
                'few_people': sum(1 for p in people if not p.get('cc')),
                'need_total': sum(it['qty'] for it in items),
                'seats_total': sum(known) if known else None,
                'seats_known': len(known), 'items_n': len(counted),
                'seats_complete': bool(counted) and len(known) == len(counted)}

    # สิ่งที่ต้องดำเนินการ
    from report_pptx import th_date
    today, actions = date.today(), []
    if plan:
        lack = [it for it in plan['items'] if it['seats'] is not None and it['qty'] > it['seats']]
        if lack:
            actions.append(('', f'ซื้อเพิ่ม {len(lack)} รายการ',
                            ' · '.join(f'{it["item"].replace(vendor + " ", "")} ขาด {it["qty"] - it["seats"]:,}'
                                       for it in lack[:4])))
        spare = [it for it in plan['items'] if it['seats'] is not None and it['seats'] > it['qty']]
        if spare:
            n_sp = sum(it['seats'] - it['qty'] for it in spare)
            actions.append(('', f'License ว่าง {n_sp:,} ใบ',
                            ' · '.join(f'{it["item"].replace(vendor + " ", "")} {it["seats"] - it["qty"]:,}'
                                       for it in spare[:4]) +
                            ' — แจกให้คนที่รอ หรือลดจำนวนตอนต่ออายุ'))
        pending = sum(1 for p in people if p.get('cc_pending'))
        if pending:
            actions.append(('', f'ควรย้ายไป All Apps {pending:,} คน',
                            f'ใช้ตั้งแต่ {plan["min"]} โปรแกรมแต่ยังไม่ได้บันทึกชุด All Apps — '
                            f'ถ้าย้ายจะลดการซื้อแยก'))
    soon = sorted([c for c in vcat if c.get('renew_date') and
                   0 <= (date.fromisoformat(c['renew_date']) - today).days <= 90],
                  key=lambda c: c['renew_date'])
    if soon:
        actions.append(('', f'ต่ออายุภายใน 90 วัน {len(soon)} รายการ',
                        ' · '.join(f'{c["name"].replace(vendor + " ", "")} ({th_date(c["renew_date"])})'
                                   for c in soon[:4])))
    if plan and not plan['seats_complete']:
        miss = [it['item'].replace(vendor + ' ', '') for it in plan['items']
                if it['seats'] is None and it['qty']]
        if miss:
            actions.append(('', f'ยังไม่ระบุจำนวนซื้อ {len(miss)} รายการ',
                            'กรอกในคลัง Software (แท็บ BU) — ' + ', '.join(miss[:4])))

    highlights = [f'คนใช้ {vendor} {len(people):,} คน ใน {len(depts)} ฝ่าย '
                  f'ใช้ {len(products)} โปรแกรม']
    if plan:
        highlights.append(f'ต้องมี All Apps {allapps:,} ชุด + ซื้อแยก {plan["single_total"]:,} license '
                          f'(รวม {plan["need_total"]:,})')
        if plan['seats_complete']:
            gap = plan['seats_total'] - plan['need_total']
            highlights.append(f'ซื้อไว้ {plan["seats_total"]:,} — ' +
                              (f'เหลือ {gap:,}' if gap > 0 else f'ขาด {-gap:,}' if gap < 0 else 'พอดี'))
    if depts:
        highlights.append(f'ฝ่ายที่ใช้มากที่สุด: {depts[0]["department"]} ({depts[0]["people"]:,} คน)')

    return {'vendor': vendor, 'scope': bu or 'ทุก BU', 'today': today,
            'kpi': {'people': len(people), 'depts': len(depts), 'products': len(products),
                    'licenses': sum(x['licenses'] for x in depts),
                    # ผู้ผลิตที่ไม่มีชุดรวม: เทียบใช้กับซื้อรายโปรแกรม
                    'seats': sum(seats[p['name']] for p in products if seats.get(p['name']) is not None)
                             if any(seats.get(p['name']) is not None for p in products) else None,
                    'seats_known': sum(1 for p in products if seats.get(p['name']) is not None),
                    'over': sum(1 for p in products if seats.get(p['name']) is not None
                                and p['total'] > seats[p['name']])},
            'products': products, 'plan': plan, 'depts': depts,
            'actions': actions, 'highlights': highlights}


@app.route('/api/software/vendor-presentation', methods=['GET'])
def vendor_presentation():
    """Presentation (.pptx) รายผู้ผลิต · ?name=Adobe&bu=AMTV"""
    from report_pptx import build_vendor_deck
    vendor = (request.args.get('name') or 'Adobe').strip()
    bu     = (request.args.get('bu') or '').strip()
    buf = build_vendor_deck(_vendor_deck_data(vendor, bu))
    safe = re.sub(r'[^A-Za-z0-9_-]+', '_', vendor)
    fname = f"{safe}_presentation_{bu or 'all'}_{datetime.now().strftime('%Y%m%d_%H%M')}.pptx"
    return send_file(buf, as_attachment=True, download_name=fname,
                     mimetype='application/vnd.openxmlformats-officedocument.presentationml.presentation')


# ---------- บริหาร Printer ----------

PRINTER_FIELDS = ['brand', 'model', 'building', 'serial_no', 'ink_type', 'ppm',
                  'purchase_year', 'paper', 'price_old', 'price_new',
                  'contract_start', 'contract_end', 'note']
PRINTER_SOON_DAYS = 90     # สัญญาเหลือไม่เกินกี่วันถือว่า "ใกล้หมด"


def _printer_clean(d):
    """แปลงค่าจากฟอร์มให้พร้อมบันทึก — คืน (dict, error)"""
    out = {}
    for f in ['brand', 'model', 'building', 'serial_no', 'ink_type', 'paper', 'note']:
        out[f] = re.sub(r'\s+', ' ', str(d.get(f) or '')).strip()
    out['ppm'] = _int_or_none(d.get('ppm'))
    y = _int_or_none(d.get('purchase_year'))
    if y is not None and y > 2400:          # กรอกเป็น พ.ศ. → เก็บเป็น ค.ศ.
        y -= 543
    if y is not None and not (1980 <= y <= date.today().year + 1):
        return None, 'ปีที่ซื้อไม่ถูกต้อง (กรอกเป็น พ.ศ. หรือ ค.ศ. ก็ได้)'
    out['purchase_year'] = y
    for f in ['price_old', 'price_new']:
        v = _float_or_none(d.get(f))
        if v is not None and v < 0:
            return None, 'ค่าสำเนาต้องไม่ติดลบ'
        out[f] = v
    for f in ['contract_start', 'contract_end']:
        v = (d.get(f) or '').strip()
        if v and not re.fullmatch(r'\d{4}-\d{2}-\d{2}', v):
            return None, 'วันที่สัญญาไม่ถูกต้อง'
        out[f] = v or None
    if out['contract_start'] and out['contract_end'] and out['contract_end'] < out['contract_start']:
        return None, 'วันสิ้นสุดสัญญาต้องไม่ก่อนวันเริ่มต้น'
    if not (out['brand'] or out['model'] or out['serial_no']):
        return None, 'กรอกอย่างน้อย ยี่ห้อ รุ่น หรือเลขเครื่อง'
    return out, None


def _printer_row(r):
    """เติมค่าที่คำนวณได้: อายุการใช้งาน, % ราคาเปลี่ยน, สถานะสัญญา"""
    d = dict(r)
    today = date.today()
    d['age_years'] = (today.year - d['purchase_year']) if d['purchase_year'] else None
    po, pn = d['price_old'], d['price_new']
    d['change_pct'] = round((pn - po) / po * 100, 2) if po and pn is not None else None
    status, days = 'none', None
    if d['contract_end']:
        days = (date.fromisoformat(d['contract_end']) - today).days
        status = 'expired' if days < 0 else ('soon' if days <= PRINTER_SOON_DAYS else 'active')
    d['contract_status'], d['days_left'] = status, days
    return d


def _printer_dup(conn, serial, pid=None):
    if not serial:
        return None
    return conn.execute(
        'SELECT id FROM printers WHERE serial_no=? COLLATE NOCASE AND id<>?',
        (serial, pid or 0)).fetchone()


@app.route('/api/printers', methods=['GET'])
def printers_list():
    """รายการเครื่องทั้งหมด + ตัวเลขสรุปสำหรับหน้า dashboard"""
    conn = get_db()
    rows = [_printer_row(r) for r in conn.execute(
        'SELECT * FROM printers ORDER BY building COLLATE NOCASE, brand COLLATE NOCASE, '
        'model COLLATE NOCASE')]
    conn.close()

    ages = [r['age_years'] for r in rows if r['age_years'] is not None]
    pcts = [r['change_pct'] for r in rows if r['change_pct'] is not None]
    by_building = Counter(r['building'] or 'ไม่ระบุอาคาร' for r in rows)
    return jsonify({
        'rows': rows,
        'summary': {
            'total':       len(rows),
            'avg_age':     round(sum(ages) / len(ages), 1) if ages else None,
            'old_5y':      sum(1 for a in ages if a >= 5),
            'expired':     sum(1 for r in rows if r['contract_status'] == 'expired'),
            'soon':        sum(1 for r in rows if r['contract_status'] == 'soon'),
            'no_contract': sum(1 for r in rows if r['contract_status'] == 'none'),
            'avg_change':  round(sum(pcts) / len(pcts), 2) if pcts else None,
            'up':          sum(1 for p in pcts if p > 0),
            'down':        sum(1 for p in pcts if p < 0),
            'soon_days':   PRINTER_SOON_DAYS,
        },
        'by_building': sorted(by_building.items(), key=lambda kv: (-kv[1], kv[0])),
    })


@app.route('/api/printers', methods=['POST'])
def printers_add():
    d, err = _printer_clean(request.json or {})
    if err:
        return jsonify({'error': err}), 400
    conn = get_db()
    if _printer_dup(conn, d['serial_no']):
        conn.close()
        return jsonify({'error': f'เลขเครื่อง "{d["serial_no"]}" มีอยู่แล้ว'}), 409
    cur = conn.execute(
        f'INSERT INTO printers ({", ".join(PRINTER_FIELDS)}) '
        f'VALUES ({", ".join("?" * len(PRINTER_FIELDS))})',
        [d[f] for f in PRINTER_FIELDS])
    conn.commit()
    new_id = cur.lastrowid
    conn.close()
    return jsonify({'ok': True, 'id': new_id})


@app.route('/api/printers/<int:pid>', methods=['PUT'])
def printers_update(pid):
    d, err = _printer_clean(request.json or {})
    if err:
        return jsonify({'error': err}), 400
    conn = get_db()
    if _printer_dup(conn, d['serial_no'], pid):
        conn.close()
        return jsonify({'error': f'เลขเครื่อง "{d["serial_no"]}" มีอยู่แล้ว'}), 409
    cur = conn.execute(
        f'UPDATE printers SET {", ".join(f + "=?" for f in PRINTER_FIELDS)}, '
        f"updated_at=datetime('now','localtime') WHERE id=?",
        [d[f] for f in PRINTER_FIELDS] + [pid])
    conn.commit()
    changed = cur.rowcount
    conn.close()
    if not changed:
        return jsonify({'error': 'ไม่พบเครื่องนี้'}), 404
    return jsonify({'ok': True})


@app.route('/api/printers/<int:pid>', methods=['DELETE'])
def printers_delete(pid):
    conn = get_db()
    row = conn.execute('SELECT * FROM printers WHERE id=?', (pid,)).fetchone()
    if not row:
        conn.close()
        return jsonify({'error': 'ไม่พบเครื่องนี้'}), 404
    conn.execute('DELETE FROM printers WHERE id=?', (pid,))
    conn.commit()
    conn.close()
    app.logger.warning('ลบ printer id=%s: %s', pid, json.dumps(dict(row), ensure_ascii=False))
    return jsonify({'ok': True})


@app.route('/api/printers/export', methods=['GET'])
def printers_export():
    """Export รายการ Printer เป็น Excel — คอลัมน์ตามที่หน้าจอแสดง"""
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.utils import get_column_letter

    conn = get_db()
    rows = [_printer_row(r) for r in conn.execute(
        'SELECT * FROM printers ORDER BY building COLLATE NOCASE, brand COLLATE NOCASE, '
        'model COLLATE NOCASE')]
    conn.close()

    ST = {'expired': 'หมดสัญญาแล้ว', 'soon': 'ใกล้หมดสัญญา', 'active': 'อยู่ในสัญญา',
          'none': 'ไม่ระบุสัญญา'}
    th = lambda s: (f'{s[8:10]}/{s[5:7]}/{int(s[:4]) + 543}' if s else '')

    wb = Workbook()
    ws = wb.active
    ws.title = 'Printer'
    ws.append(['รายการ Printer / เครื่องถ่ายเอกสาร'])
    ws['A1'].font = Font(bold=True, size=13)
    ws.append([f'ออกรายงานเมื่อ {datetime.now().strftime("%d/%m/%Y %H:%M น.")}  ·  รวม {len(rows)} เครื่อง'])
    ws['A2'].font = Font(size=9, color='64748B')
    ws.append([])
    headers = ['ยี่ห้อ', 'รุ่น', 'อาคารที่ตั้ง', 'เลขเครื่อง', 'ชนิดหมึก', 'สำเนา/นาที',
               'ปีที่ซื้อ (พ.ศ.)', 'อายุการใช้งาน (ปี)', 'กระดาษที่ใช้',
               'ค่าสำเนาราคาเดิม (บาท)', 'ค่าสำเนาราคาใหม่ (บาท)', 'เพิ่ม/ลด (%)',
               'สัญญาเริ่มต้น', 'สัญญาสิ้นสุด', 'สถานะสัญญา', 'เหลือ (วัน)', 'หมายเหตุ']
    head = ws.max_row + 1
    ws.append(headers)
    HFILL = PatternFill('solid', fgColor='1E3A5F')
    THIN = Side(style='thin', color='D8DEE7')
    BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)
    for c in range(1, len(headers) + 1):
        cell = ws.cell(row=head, column=c)
        cell.font = Font(color='FFFFFF', bold=True, size=10)
        cell.fill = HFILL
        cell.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
    for r in rows:
        ws.append([
            r['brand'], r['model'], r['building'], r['serial_no'], r['ink_type'], r['ppm'],
            r['purchase_year'] + 543 if r['purchase_year'] else None, r['age_years'], r['paper'],
            r['price_old'], r['price_new'], r['change_pct'],
            th(r['contract_start']), th(r['contract_end']), ST[r['contract_status']],
            r['days_left'] if r['contract_status'] in ('soon', 'active') else None, r['note'],
        ])
        n = ws.max_row
        if r['change_pct'] is not None:
            ws.cell(row=n, column=12).font = Font(
                bold=True, color='DC2626' if r['change_pct'] > 0 else '15803D')
        if r['contract_status'] in ('expired', 'soon'):
            ws.cell(row=n, column=15).font = Font(
                bold=True, color='DC2626' if r['contract_status'] == 'expired' else 'B45309')
    for row in ws.iter_rows(min_row=head, max_row=ws.max_row, max_col=len(headers)):
        for cell in row:
            cell.border = BORDER
            if cell.row > head and cell.column in (10, 11):
                cell.number_format = '#,##0.00'
    ws.freeze_panes = ws.cell(row=head + 1, column=3)
    ws.auto_filter.ref = f'A{head}:{get_column_letter(len(headers))}{ws.max_row}'
    for i, h in enumerate(headers, 1):
        width = max([len(h)] + [len(str(ws.cell(row=r_, column=i).value or ''))
                                for r_ in range(head + 1, ws.max_row + 1)])
        ws.column_dimensions[get_column_letter(i)].width = min(max(width + 2, 9), 36)

    buf = io.BytesIO()
    wb.save(buf); buf.seek(0)
    return send_file(buf, as_attachment=True,
                     download_name=f"printers_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
                     mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')


@app.route('/api/assets/report.pdf', methods=['GET'])
def asset_report_pdf():
    """รายงาน PDF — ประเภทเครื่อง × ตำแหน่งงาน ตาม filter ที่หน้าจอเลือกไว้"""
    from report_pdf import build_asset_report

    rows = _apply_asset_filters(list(fetch_assets_raw()), request.args)

    # สรุป filter ที่ใช้ ไปแสดงหัวรายงาน ให้รู้ว่าตัวเลขมาจากชุดข้อมูลไหน
    _ST = {'expired': 'หมดสัญญาแล้ว', 'critical': 'เหลือ < 90 วัน',
           'warning': 'เหลือ < 180 วัน', 'ok': 'อยู่ในระยะสัญญา', 'returned': 'คืนแล้ว'}
    a = request.args
    labels = []
    for key, prefix, mapper in [
        ('q',            'ค้นหา',          lambda v: '"%s"' % v),
        ('bu',           'BU',             str),
        ('type',         'ประเภท',         str),
        ('ownership',    'ประเภทสัญญา',    str),
        ('machine_type', 'ประเภทเครื่อง',  lambda v: 'ยังไม่ระบุ' if v == '-' else v),
        ('status',       'สถานะสัญญา',     lambda v: _ST.get(v, v)),
        ('ed_status',    'eDevice status', str),
        ('position',     'ตำแหน่ง',        str),
        ('dept',         'แผนก',           str),
    ]:
        v = (a.get(key) or '').strip()
        if v:
            labels.append('%s: %s' % (prefix, mapper(v)))
    for key, text in [
        ('only_resigned',        'เฉพาะไม่พบใน HR'),
        ('only_no_owner',        'เฉพาะไม่มีผู้ถือครอง'),
        ('only_central',         'เฉพาะส่วนกลาง'),
        ('only_missing_edevice', 'เฉพาะยังไม่บันทึกใน eDevice'),
    ]:
        if a.get(key) == '1':
            labels.append(text)

    buf = build_asset_report(rows, labels)
    fname = f"report_asset_by_position_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf"
    return send_file(buf, mimetype='application/pdf',
                     as_attachment=True, download_name=fname)


# ---------- eDevice Sync ----------

EDEVICE_JSON        = os.path.join(os.path.dirname(__file__), 'edevice_assets.json')
EDEVICE_STATUS_JSON = os.path.join(os.path.dirname(__file__), 'edevice_fetch_status.json')
# สรุปเครื่องที่ fetch ไม่สำเร็จในรอบล่าสุด (เพื่อ debug — ดูผ่าน /api/sync/edevice/skipped)
EDEVICE_SKIPPED_JSON = os.path.join(os.path.dirname(__file__), 'edevice_fetch_skipped.json')

import threading as _threading
_edevice_fetch_lock = _threading.Lock()

def _ed_write_status(state: dict):
    try:
        with open(EDEVICE_STATUS_JSON, 'w', encoding='utf-8') as f:
            json.dump(state, f)
    except Exception:
        pass

def _ed_read_status() -> dict:
    try:
        with open(EDEVICE_STATUS_JSON, encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {'running': False, 'done': False, 'error': None, 'count': 0, 'total': 0}

EDEVICE_LOGIN_URL  = 'http://amarin.intra/webappl/acorporate/index.aspx?s=out'
EDEVICE_CORP_URL   = 'http://www.amarin.intra/webappl/eDevice_ATV/***REMOVED-EDEVICE_INIT_PATH***'
EDEVICE_DETAIL_URL     = 'http://www.amarin.intra/webappl/eDevice_ATV/ComputerDetail.asp?id={}'
EDEVICE_MAC_DETAIL_URL = 'http://www.amarin.intra/webappl/eDevice_ATV/MacintoshDetail.asp?id={}'
EDEVICE_LIST_URL       = 'http://www.amarin.intra/webappl/eDevice_ATV/Computer1.asp'
EDEVICE_MAC_URL        = 'http://www.amarin.intra/webappl/eDevice_ATV/Macintosh.asp'

# eDevice มี 2 ระบบแยกกัน — เครื่องบางส่วน (เช่น APC67xxxx/APC68xxxx) อยู่เฉพาะตัวหลัก
# ทั้งสองใช้ layout หน้า detail เหมือนกัน → parser เดิมใช้ได้ทั้งคู่
EDEVICE_BASES = [
    'http://www.amarin.intra/webappl/eDevice_ATV/',
    'http://www.amarin.intra/webappl/eDevice/',
]
EDEVICE_INIT_PATH = '***REMOVED-EDEVICE_INIT_PATH***'

BU_TH_MAP = {
    'อมรินทร์ทีวี': 'AMTV', 'ออมนิเวิร์ส': 'AOMNI', 'สำนักพิมพ์': 'APUB',
    'อมรินทร์ บุ๊ค': 'ABOOK', 'โรงพิมพ์': 'APRINT', 'ACS': 'ACS',
    'มีเดีย': 'AME', 'เอเอ็มอี': 'AME', 'อมรินทร์ คอร์': 'ACS',
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
        'ctl00$ContentPlaceHolder1$loginauth1$txtlogin': _require_env('EDEVICE_USER', 'username ที่ใช้ล็อกอิน eDevice'),
        'ctl00$ContentPlaceHolder1$loginauth1$txtpass': _require_env('EDEVICE_PASS', 'password ที่ใช้ล็อกอิน eDevice'),
        'ctl00$ContentPlaceHolder1$loginauth1$btnlogin': 'เข้าสู่ระบบ',
    }, timeout=15, allow_redirects=True)
    # init session ของแต่ละระบบ eDevice (ไม่ init จะได้หน้าเปล่า ~1.2KB)
    for base in EDEVICE_BASES:
        try:
            sess.get(base + EDEVICE_INIT_PATH, timeout=15)
        except Exception:
            pass
    return dict(sess.cookies)


def _norm_label(s):
    """normalize label ก่อนเทียบ — eDevice แต่ละระบบเขียน label ไม่เหมือนกัน
    เช่น 'Serial No.*:' (ATV) vs 'Serial No. :' (ตัวหลัก) → 'serialno.:' ทั้งคู่"""
    return re.sub(r'[\s *]+', '', s or '').lower()


def _parse_label_value(soup, label_map):
    """Helper: วน <tr> แล้ว match label → value จาก adjacent <td> cells"""
    norm_map   = [(_norm_label(lbl), key) for lbl, key in label_map.items()]
    all_labels = {_norm_label(lbl) for lbl in label_map}
    data = {}
    for row in soup.find_all('tr'):
        cells = [td.get_text(strip=True).replace('\xa0', ' ') for td in row.find_all('td')]
        for i in range(len(cells) - 1):
            val = cells[i + 1].strip()
            if not val or val.endswith(':') or _norm_label(val) in all_labels:
                continue
            lbl_norm = _norm_label(cells[i])
            for lbl, key in norm_map:
                if lbl not in lbl_norm or key in data:
                    continue
                # กัน 'ทรัพย์สินฝ่าย*:' (dept_asset) ไปติด key 'ฝ่าย :' (section)
                if 'ทรัพย์สิน' in lbl_norm and 'ทรัพย์สิน' not in lbl:
                    continue
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
    # ── ประเภทเครื่อง (dropdown ตัวที่ 2) เช่น 'NB สำนักงานทั่วไป' ────
    # หน้า ComputerDetail มี label 'ประเภท*:' 2 จุด:
    #   จุดแรก = device_type + ownership ('NoteBook  เช่า')
    #   จุดที่สอง = ประเภทเครื่องตาม spec (ค่า '-' ถ้ายังไม่ระบุ)
    for row in soup.find_all('tr'):
        tds = row.find_all('td')
        for i in range(len(tds) - 1):
            if 'ประเภท' not in tds[i].get_text(strip=True):
                continue
            val = tds[i + 1].get_text(' ', strip=True).replace('\xa0', ' ').strip()
            val = re.sub(r'\s+', ' ', val)
            if not val or val == '-' or 'เช่า' in val or 'ซื้อ' in val:
                continue
            if val == re.sub(r'\s+', ' ', (data.get('device_type') or '').strip()):
                continue   # ค่าซ้ำกับ device_type (เครื่องที่ไม่ระบุ เช่า/ซื้อ)
            data['machine_type'] = val
            break
        if 'machine_type' in data:
            break
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
                            # อาจเป็น NavigableString หรือ Tag (<font>ส่วนกลาง</font>)
                            t = sibling.get_text(strip=True) if hasattr(sibling, 'get_text') else str(sibling).strip()
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
            label  = _norm_label(td.get_text(strip=True))
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
                if _norm_label(lbl) in label and key not in data:
                    values = _get_cell_value(val_td)
                    if values:
                        data[key] = values[0]

            # ── text fields ทั่วไป ──
            for lbl, key in label_map.items():
                if _norm_label(lbl) in label and key not in data:
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
                            # อาจเป็น NavigableString หรือ Tag (<font>ส่วนกลาง</font>)
                            t = sibling.get_text(strip=True) if hasattr(sibling, 'get_text') else str(sibling).strip()
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
                data = json.load(f)
                if data:
                    return data
        except Exception:
            pass  # JSON เสีย / ว่าง — fall through ไป live fetch

    # live fetch — ดึง ID จากทั้ง PC (Computer1.asp) และ Mac (Macintosh.asp)
    cookies = _edevice_login()

    def get_ids(url, select_name):
        """ดึงรหัสเครื่องจาก <select name="FullComId"/"FullMacId"> เท่านั้น

        หน้า Computer1.asp/Macintosh.asp มี <select> อีกหลายตัวบนหน้าเดียวกัน
        (ID_EmpNameAPU/ID_EmpNameAPUO = รหัสพนักงาน, SectionAPU/DepartAPU = ชื่อฝ่าย/แผนก,
        PublicOwner) ถ้ากวาด <OPTION> ทั้งหน้าเหมือนเดิม จะได้รหัสพนักงานปนมาเป็น
        'รหัสเครื่อง' ~5,800 ตัว แล้วยิง ComputerDetail ไม่เจอ → HTTP 500 ทุกตัว
        ทำให้ยอด skipped บวมจนดูเหมือน sync พังทั้งที่ของจริงครบ"""
        try:
            r = req_lib.get(url, cookies=cookies, timeout=15)
            html = r.content.decode('tis-620', errors='replace')
            m = re.search(r'<select\s+name="%s">(.*?)</select>' % select_name,
                          html, re.S | re.I)
            if not m:
                return []
            return [o for o in re.findall(r"<option value='([^']*)'>", m.group(1), re.I)
                    if o and o != 'All']
        except Exception:
            return []

    def _detail_url(base, cid, mac=False):
        # id ที่มีอักษรไทย/ช่องว่าง ('TCC ยืม 1') ต้อง encode เป็น tis-620
        # ไม่ใช่ utf-8 ที่ requests ใส่ให้เอง ไม่งั้น ASP ตัวเก่าตอบ 500
        page = 'MacintoshDetail.asp' if mac else 'ComputerDetail.asp'
        return base + page + '?id=' + _url_quote(cid.encode('tis-620', 'replace'))

    # cid → [detail_url ตามลำดับที่จะลอง]
    # เดิมใช้ setdefault = ระบบแรกใน EDEVICE_BASES ชนะแล้วไม่ลองระบบอื่นอีก
    # แต่มีเครื่องที่อยู่ในลิสต์ของทั้งสองระบบและเปิดได้เฉพาะระบบหลัง (เช่น APC63006)
    cid_urls = {}
    for base in EDEVICE_BASES:
        tag = base.rstrip('/').split('/')[-1]
        for page, sel, mac in (('Computer1.asp', 'FullComId', False),
                               ('Macintosh.asp', 'FullMacId', True)):
            _ed_write_status({'running': True, 'done': False, 'error': None,
                              'count': 0, 'total': 0, 'heartbeat': time.time(),
                              'phase': f'กำลังโหลดรายการ {"Mac" if mac else "PC"} ({tag})...'})
            for cid in get_ids(base + page, sel):
                urls = cid_urls.setdefault(cid, [])
                u = (_detail_url(base, cid, mac), mac)
                if u not in urls:
                    urls.append(u)

    # เครื่องที่อยู่ในลิสต์เดียวไม่มีตัวสำรอง — เติม endpoint อีกแบบไว้ให้ลองต่อ
    for cid, urls in cid_urls.items():
        for base in EDEVICE_BASES:
            for mac in (False, True):
                u = (_detail_url(base, cid, mac), mac)
                if u not in urls:
                    urls.append(u)

    total_ids = len(cid_urls)
    _ed_write_status({'running': True, 'done': False, 'error': None, 'count': 0, 'total': total_ids})

    def fetch_one(cid):
        """คืน (record, skip_reason) — skip_reason=None แปลว่าสำเร็จ
        ลอง endpoint ตามลำดับใน cid_urls จนกว่าจะได้หน้าจริง (ดู _detail_url)"""
        reason = 'no_endpoint'
        for url, mac in cid_urls[cid]:
            try:
                r2 = req_lib.get(url, cookies=cookies, timeout=12)
            except Exception as e:
                reason = f'request_error:{type(e).__name__}'
                continue
            if r2.status_code != 200:
                reason = f'http_{r2.status_code}'
                continue
            if len(r2.content) <= 3000:
                reason = 'empty_page'   # หน้าเปล่า/redirect — มักแปลว่า session หมดอายุ
                continue
            try:
                text = r2.content.decode('tis-620', errors='replace')
                rec = _parse_mac_detail(text, cid) if mac else _parse_computer_detail(text, cid)
            except Exception as e:
                reason = f'parse_error:{type(e).__name__}'
                continue
            return rec, None
        return None, reason

    assets = []
    # skipped: reason → { count, cids (เก็บตัวอย่างไม่เกิน 20) }
    skipped = {}
    _last_hb = time.time()
    _ed_write_status({'running': True, 'done': False, 'error': None,
                      'count': 0, 'total': total_ids, 'heartbeat': _last_hb,
                      'phase': 'กำลังดึงข้อมูลรายเครื่อง...'})
    # max_workers=10 — มากกว่านี้ GIL อิ่มตัว แต่ตอนนี้รันใน subprocess แยกแล้ว ไม่กระทบ Gunicorn worker
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as ex:
        fut_map = {ex.submit(fetch_one, cid): cid for cid in cid_urls}
        for fut in concurrent.futures.as_completed(fut_map):
            rec, reason = fut.result()
            if rec:
                assets.append(rec)
            else:
                # aggregate ใน thread หลัก (as_completed) — ไม่ต้องใช้ lock
                s = skipped.setdefault(reason, {'count': 0, 'cids': []})
                s['count'] += 1
                if len(s['cids']) < 20:
                    s['cids'].append(fut_map[fut])
            # heartbeat ทุก ~2s — ให้ progress bar ไหลลื่นขึ้น
            now = time.time()
            if now - _last_hb >= 2:
                _last_hb = now
                _ed_write_status({'running': True, 'done': False, 'error': None,
                                  'count': len(assets), 'total': total_ids,
                                  'heartbeat': now,
                                  'phase': 'กำลังดึงข้อมูลรายเครื่อง...'})

    with open(EDEVICE_JSON, 'w', encoding='utf-8') as f:
        json.dump(assets, f, ensure_ascii=False, indent=2)

    skipped_summary = {
        'fetched_at':  datetime.now().isoformat(timespec='seconds'),
        'total_ids':   total_ids,
        'ok':          len(assets),
        'skipped':     total_ids - len(assets),
        'by_reason':   dict(sorted(skipped.items(), key=lambda kv: -kv[1]['count'])),
    }
    try:
        with open(EDEVICE_SKIPPED_JSON, 'w', encoding='utf-8') as f:
            json.dump(skipped_summary, f, ensure_ascii=False, indent=2)
    except Exception:
        pass
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


@app.route('/api/sync/edevice/skipped', methods=['GET'])
def edevice_skipped():
    """สรุปเครื่องที่ fetch ไม่สำเร็จในรอบล่าสุด (แยกตามสาเหตุ)"""
    try:
        with open(EDEVICE_SKIPPED_JSON, encoding='utf-8') as f:
            return jsonify(json.load(f))
    except Exception:
        return jsonify({'error': 'ยังไม่มีข้อมูล — ต้อง fetch อย่างน้อย 1 รอบก่อน'}), 404


@app.route('/api/sync/edevice/fetch-start', methods=['POST'])
def edevice_fetch_start():
    """เริ่ม background fetch จาก eDevice (non-blocking)."""
    st = _ed_read_status()
    if st.get('running'):
        return jsonify({'status': 'already_running', **st})
    _ed_write_status({'running': True, 'done': False, 'error': None,
                      'count': 0, 'total': 0, 'heartbeat': time.time()})
    # รัน fetch เป็น subprocess แยก — อิสระจาก Gunicorn worker
    # (worker จะถูก recycle/kill ก็ไม่กระทบ fetch อีกต่อไป)
    import subprocess, sys as _sys
    subprocess.Popen(
        [_sys.executable, os.path.abspath(__file__), '--edevice-fetch'],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        start_new_session=True,   # detach จาก process group ของ Gunicorn
    )
    return jsonify({'status': 'started'})


@app.route('/api/sync/edevice/fetch-status', methods=['GET'])
def edevice_fetch_status():
    """สถานะ background fetch."""
    state = _ed_read_status()
    # ตรวจ heartbeat — ถ้า running=True แต่ไม่มี heartbeat นาน >120s แสดงว่า worker ถูก kill กลางคัน
    if state.get('running') and not state.get('done'):
        hb = state.get('heartbeat', 0)
        if hb and time.time() - hb > 120:
            state['running'] = False
            state['error'] = 'Worker ถูก kill กลางคัน (WORKER TIMEOUT) กรุณาลองใหม่'
            _ed_write_status(state)
        elif not hb and state.get('count', 0) == 0:
            pass  # เพิ่งเริ่ม ยังไม่มี heartbeat ครั้งแรก — ปล่อยผ่าน
    try:
        state['cache_ready'] = os.path.exists(EDEVICE_JSON) and os.path.getsize(EDEVICE_JSON) > 0
    except Exception:
        state['cache_ready'] = False
    return jsonify(state)


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

    # เฉพาะที่ transfer ด้วยมือ (is_manual=1) เท่านั้นที่ห้ามทับ
    manual_nos = {r[0] for r in conn.execute(
        'SELECT asset_no FROM asset_assignments WHERE is_manual=1').fetchall()}

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
    _invalidate_asset_cache()
    return jsonify({'ok': True, 'assigned': assigned, 'protected': protected,
                    'skipped': skipped, 'code_updated': code_updated})


# ---------- Intranet Sync ----------

INTRANET_URL    = 'http://amarin.intra/webappl/Contact/displays_all.asp'
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
    import socket
    try:
        sess = req_lib.Session()
        # GET ก่อนเพื่อรับ ASPSESSION cookie
        sess.get(INTRANET_URL, timeout=15)
        resp = sess.post(INTRANET_URL, data=INTRANET_PARAMS,
                         headers={'Content-Type': 'application/x-www-form-urlencoded'},
                         timeout=30)
        resp.raise_for_status()
        if len(resp.content) == 0:
            raise RuntimeError('Intranet ตอบกลับ 200 OK แต่ข้อมูลว่างเปล่า — อาจต้องการ authentication เพิ่มเติม')
    except req_lib.exceptions.ConnectionError as e:
        host = INTRANET_URL.split('/')[2]
        try:
            ip = socket.gethostbyname(host)
            raise RuntimeError(f'เชื่อมต่อ {host} ({ip}) ไม่สำเร็จ — เซิร์ฟเวอร์ปฏิเสธ connection: {e}')
        except socket.gaierror:
            raise RuntimeError(
                f'DNS resolve "{host}" ไม่ได้ — เซิร์ฟเวอร์อาจต้องการ DNS/hosts ของ Intranet\n'
                f'แก้ด้วย: sudo echo "<IP> {host}" >> /etc/hosts'
            )
    except req_lib.exceptions.Timeout:
        raise RuntimeError(f'Timeout เชื่อมต่อ Intranet ({INTRANET_URL}) — ตรวจสอบ network และ firewall')
    except req_lib.exceptions.HTTPError as e:
        raise RuntimeError(f'HTTP Error จาก Intranet: {e}')
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
    try:
        intranet_employees = fetch_intranet_employees()
    except RuntimeError as e:
        return jsonify({'error': str(e)}), 503
    except Exception as e:
        return jsonify({'error': f'ไม่สามารถดึงข้อมูลจาก Intranet: {e}'}), 500
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
    try:
        intranet_employees = fetch_intranet_employees()
    except RuntimeError as e:
        return jsonify({'error': str(e)}), 503
    except Exception as e:
        return jsonify({'error': f'ไม่สามารถดึงข้อมูลจาก Intranet: {e}'}), 500
    intranet_map = { _norm(e['name']): e for e in intranet_employees }

    conn = get_db()
    db_employees = conn.execute(
        'SELECT id, name, status, bu, bu_code, department, position, email, phone FROM employees'
    ).fetchall()
    db_map = { _norm(emp['name']): dict(emp) for emp in db_employees }

    inactivated, added, updated = 0, 0, 0
    gone = []

    # 1. active in DB but not in intranet → inactive
    for emp in db_employees:
        key = _norm(emp['name'])
        if emp['status'] == 'active' and key not in intranet_map:
            conn.execute(
                "UPDATE employees SET status='inactive', updated_at=datetime('now','localtime') WHERE id=?",
                (emp['id'],)
            )
            inactivated += 1
            gone.append(emp['id'])
    # คนที่ออกแล้ว → ถอน software คืนคลัง
    sw_released = _release_inactive_software(conn, gone, reason='Sync Intranet: ไม่พบในระบบ HR')

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
    return jsonify({'ok': True, 'inactivated': inactivated, 'added': added, 'updated': updated,
                    'software_released': sw_released})


init_db()

if __name__ == '__main__':
    import sys
    # subprocess entry point — เรียกจาก /api/sync/edevice/fetch-start
    if '--edevice-fetch' in sys.argv:
        try:
            assets = fetch_edevice_assets(force_live=True)
            # total = จำนวนรหัสเครื่องที่เจอในลิสต์จริง ไม่ใช่จำนวนที่ดึงสำเร็จ
            # (เดิมใส่ len(assets) ทั้งสองช่อง หน้าจอเลยขึ้น 100% เสมอ ต่อให้ดึงไม่ครบ)
            try:
                with open(EDEVICE_SKIPPED_JSON, encoding='utf-8') as f:
                    _sum = json.load(f)
            except Exception:
                _sum = {}
            _ed_write_status({'running': False, 'done': True, 'error': None,
                              'count': len(assets),
                              'total': _sum.get('total_ids') or len(assets),
                              'skipped': _sum.get('skipped', 0)})
            # บอกให้ทุก Gunicorn worker ล้าง in-memory asset cache ทันที
            _invalidate_asset_cache()
        except Exception as e:
            _ed_write_status({'running': False, 'done': False, 'error': str(e),
                              'count': 0, 'total': 0})
        sys.exit(0)

    app.run(debug=True, port=5050)
