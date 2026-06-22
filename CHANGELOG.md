# Changelog

---

## [1.4.0] — 2026-06-22

### Fixed
- **DB ไม่ถูก initialize เมื่อรันด้วย Gunicorn** — `init_db()` ย้ายออกมา module level (ไม่อยู่ใน `if __name__ == '__main__'`) เพราะ Gunicorn import module โดยไม่ผ่าน block นั้น ทำให้ `employees.db` ว่างเปล่าและทุก request ได้ 500 error
- **eDevice sync ค้าง / 504 timeout** — live fetch ดึง 4,757 devices ใช้เวลา 3-5 นาที เกิน Nginx `proxy_read_timeout 120s` และ Gunicorn `--timeout` เดิม
- **edevice_assets.json ว่างเปล่าทำให้ live fetch ทุกครั้ง** — เพิ่ม `if data:` check ก่อน return cache

### Added
- **Background fetch system สำหรับ eDevice** — `POST /api/sync/edevice/fetch-start` เริ่ม thread background, `GET /api/sync/edevice/fetch-status` ให้ frontend poll ทุก 3 วินาที พร้อม progress bar แสดง X/4757 รายการ
- **File-based fetch state** — state เขียน/อ่านผ่าน `edevice_fetch_status.json` ทำให้ทุก Gunicorn worker เห็นสถานะเดียวกัน (global variable ไม่ทำงานกับ multi-process)
- **Cache-busting สำหรับ app.js** — `?v=<md5-hash>` ใน script tag คำนวณจาก content ของไฟล์ browser โหลดใหม่อัตโนมัติทุกครั้งที่ deploy
- **Progress bar ใน Sync eDevice modal** — แสดง count/total และ % ขณะ fetch

### Changed
- Gunicorn `--timeout` เพิ่มจาก 120s → 300s
- `ThreadPoolExecutor max_workers` เพิ่มจาก 15 → 50 (เพื่อเร่ง fetch)
- ปุ่ม "ดึงข้อมูลใหม่จาก eDevice" เปลี่ยนจาก checkbox เป็น button ที่ trigger background fetch

---

## [1.3.2] — 2026-06

### Fixed
- `central_type` มี HTML tag `<font>` ติดมาจาก eDevice ทำให้ `is_central=False` เสมอ

### Changed
- ย้ายปุ่ม "ล้าง Filter" ไปอยู่หลัง checkbox สุดท้าย

---

## [1.3.1] — 2026-06

### Added
- `setup.sh` รองรับ `--db` flag สำหรับระบุ path ของ `employees.db` ที่มีอยู่
- `setup.sh` auto-detect `employees.db` ใน current directory

### Changed
- `setup.sh` กลายเป็น one-line installer ที่รองรับทั้ง install และ update mode

---

## [1.3.0] — 2026-05

### Added
- ปุ่ม "ล้าง Filter ทั้งหมด" และกด × บน tag เพื่อยกเลิกทีละตัว
- Dashboard แท็บ "บริหารเครื่อง" — anomaly panels

### Fixed
- eDevice Expire นับแยกจากสัญญาเช่าหมดอายุ (เครื่องซื้อ + Expire = ตัดจำหน่าย ไม่นับเป็น "หมดสัญญา")
