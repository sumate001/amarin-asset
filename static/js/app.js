// ---- Ownership badge (ใช้ทุกหน้า) ----
function ownershipBadge(a) {
  if (a.ownership === 'ซื้อ') {
    return '<span class="pill-bought">ซื้อ</span>';
  }
  if (a.ownership === 'เช่า' && !a.ownership_needs_update) {
    return '<span class="pill-rented">เช่า</span>';
  }
  if (a.ownership_needs_update && a.sheets_matched) {
    return '<span class="pill-rented">เช่า</span> <span title="ยืนยันจาก Sheets แต่ eDevice ยังไม่ระบุ" style="font-size:.68rem;color:#f59e0b;cursor:help">✎</span>';
  }
  if (a.ownership_missing_edevice || a.ownership_needs_update) {
    return '<span style="font-size:.72rem;padding:2px 7px;border-radius:4px;background:#f1f5f9;color:#94a3b8;font-weight:600">ไม่ระบุ</span>';
  }
  return '<span style="color:#cbd5e1">—</span>';
}

// ---- Shared dashboard/anomaly helpers (global) ----
const _TH = 'padding:7px 10px;text-align:left;font-size:.78rem;font-weight:600;color:#374151;white-space:nowrap';

function _dateFmt(d) {
  return d ? new Date(d).toLocaleDateString('th-TH', {day:'numeric', month:'short', year:'2-digit'}) : '—';
}

function _srcBadge(a) {
  if (a.sheets_matched && a.edevice_matched) return `<span class="src-badge src-both">eDevice+Sheets</span>`;
  if (a.sheets_matched)  return `<span class="src-badge src-sheets">Sheets</span>`;
  if (a.edevice_matched) return `<span class="src-badge src-edevice">eDevice</span>`;
  return `<span class="src-badge src-sheets">Sheets</span>`;
}

function _edBadge(s) {
  if (!s) return '—';
  const m = { active:{bg:'#dcfce7',color:'#15803d',label:'● Active'}, expire:{bg:'#fef9c3',color:'#854d0e',label:'⚠ Expire'},
              return:{bg:'#f1f5f9',color:'#475569',label:'↩ Return'}, spare:{bg:'#ede9fe',color:'#6d28d9',label:'◎ Spare'},
              error:{bg:'#fee2e2',color:'#b91c1c',label:'✕ Error'} };
  const c = m[s.toLowerCase()] || {bg:'#f1f5f9',color:'#475569',label:s};
  return `<span style="font-size:.72rem;padding:2px 7px;border-radius:5px;font-weight:600;background:${c.bg};color:${c.color}">${c.label}</span>`;
}

function _contractPill(a) {
  // เครื่องซื้อ + eDevice = Expire → ตัดจำหน่ายแล้ว ไม่ใช่สัญญาหมด
  if (a.ownership === 'ซื้อ' && (a.edevice_status||'').toLowerCase() === 'expire') {
    return `<span class="status-pill" style="background:#f1f5f9;color:#475569">🗑 ตัดจำหน่าย</span>`;
  }
  const cls = {expired:'pill-expired',critical:'pill-critical',warning:'pill-warning',ok:'pill-ok',returned:'pill-returned'};
  const lbl = {
    expired:  `🔴 เกิน ${Math.abs(a.days_remaining||0)} วัน`,
    critical: `🟠 เหลือ ${a.days_remaining} วัน`,
    warning:  `🟡 เหลือ ${a.days_remaining} วัน`,
    ok:       `🟢 อยู่ในสัญญา`,
    returned: `↩ คืนแล้ว`,
    unknown:  `⚪ ไม่มีข้อมูล`,
  };
  const s = a.contract_status || 'unknown';
  return `<span class="status-pill ${cls[s]||''}">${lbl[s]||s}</span>`;
}

function _anomalyHead(showEdStatus = true) {
  return `
    <th style="${_TH}">Asset No.</th>
    <th style="${_TH}">รหัสเครื่อง</th>
    <th style="${_TH}">Serial No.</th>
    <th style="${_TH};text-align:center">แหล่งข้อมูล</th>
    <th style="${_TH}">ประเภท</th>
    <th style="${_TH}">ประเภทสัญญา</th>
    <th style="${_TH}">รุ่น</th>
    <th style="${_TH}">ผู้ถือครอง</th>
    <th style="${_TH}">BU</th>
    <th style="${_TH}">แผนก</th>
    <th style="${_TH}">วันหมดสัญญา</th>
    <th style="${_TH};text-align:center">สถานะสัญญา</th>
    ${showEdStatus ? `<th style="${_TH};text-align:center">สถานะ eDevice</th>` : ''}
    <th style="${_TH};text-align:right">฿/เดือน</th>`;
}

function _anomalyRow(a, opts = {}) {
  const showEdStatus = opts.showEdStatus !== false;
  const rowBg = a.contract_status === 'expired'  ? 'background:#fff5f5'
              : a.contract_status === 'returned' ? 'background:#f8fafc'
              : !a.emp_bu_code                   ? 'background:#fffbeb' : '';
  const userCell = a.is_central
    ? '<span class="badge-central">🏢 ส่วนกลาง</span>'
    : a.user_name
      ? `<strong>${esc(a.user_name)}</strong>${!a.employee_id ? ' <span style="font-size:.68rem;color:#ef4444">(ไม่พบใน HR)</span>' : ''}`
      : '<em style="color:#cbd5e1">ไม่ระบุ</em>';

  const cols = `
    <td style="padding:6px 10px;font-size:.75rem;color:#64748b;font-family:monospace;white-space:nowrap">${esc(a.asset_no)||'—'}</td>
    <td style="padding:6px 10px"><code style="font-size:.78rem;color:#334155">${esc(a.computer_id)||'—'}</code></td>
    <td style="padding:6px 10px;font-size:.75rem;color:#64748b;font-family:monospace;white-space:nowrap">${esc(a.serial_no)||'—'}</td>
    <td style="padding:6px 10px;text-align:center;white-space:nowrap">${_srcBadge(a)}</td>
    <td style="padding:6px 10px;font-size:.78rem">${esc(a.asset_type)||'—'}</td>
    <td style="padding:6px 10px;white-space:nowrap">${ownershipBadge(a)}</td>
    <td style="padding:6px 10px;font-size:.78rem;max-width:150px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="${esc(a.model)||''}">${esc(a.model)||esc(a.brand)||'—'}</td>
    <td style="padding:6px 10px;font-size:.82rem;max-width:160px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="${esc(a.user_name)||''}">${userCell}</td>
    <td style="padding:6px 10px;white-space:nowrap"><span class="bu-badge bu-${esc(a.emp_bu_code)}">${esc(a.emp_bu_code)||'—'}</span></td>
    <td style="padding:6px 10px;font-size:.78rem;color:#64748b;max-width:140px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="${esc(a.emp_dept)||''}">${esc(a.emp_dept)||'—'}</td>
    <td style="padding:6px 10px;white-space:nowrap;font-size:.8rem">${_dateFmt(a.end_date)}</td>
    <td style="padding:6px 10px;text-align:center;white-space:nowrap">${_contractPill(a)}</td>
    ${showEdStatus ? `<td style="padding:6px 10px;text-align:center">${_edBadge(a.edevice_status)}</td>` : ''}
    <td style="padding:6px 10px;text-align:right;font-size:.8rem;font-weight:600">${a.monthly_charge ? '฿'+a.monthly_charge.toLocaleString() : '฿0'}</td>`;

  return `<tr style="border-bottom:1px solid #f1f5f9;${rowBg}">${cols}</tr>`;
}

// toggle รายการเครื่องใต้แท่ง BU ในการ์ด "ไม่มีข้อมูลวันหมดสัญญา"
function toggleNoTimelineDetail(buCode, safeId) {
  const el = document.getElementById(`ntl-detail-${safeId}`);
  if (!el) return;
  if (el.style.display !== 'none') { el.style.display = 'none'; return; }
  const items = (window._ntlByBu || {})[buCode] || [];
  const th = 'padding:4px 8px;text-align:left;color:#94a3b8;font-size:.7rem;font-weight:600';
  const td = 'padding:4px 8px;font-size:.75rem';
  el.innerHTML = `
    <div style="border:1px solid #e2e8f0;border-radius:8px;background:#fafafa;max-height:260px;overflow:auto">
      <table style="width:100%;border-collapse:collapse">
        <thead><tr style="border-bottom:1px solid #e2e8f0">
          <th style="${th}">รหัสเครื่อง</th>
          <th style="${th}">Serial No.</th>
          <th style="${th}">รุ่น</th>
          <th style="${th}">ผู้ถือครอง</th>
          <th style="${th};text-align:center">eDevice</th>
        </tr></thead>
        <tbody>${items.map(a => `<tr style="border-bottom:1px solid #f1f5f9">
          <td style="${td}"><code style="font-size:.75rem;color:#334155">${esc(a.computer_id) || esc(a.asset_no) || '—'}</code></td>
          <td style="${td};font-family:monospace;color:#64748b">${esc(a.serial_no) || '—'}</td>
          <td style="${td};max-width:150px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="${esc(a.model)||''}">${esc(a.model) || '—'}</td>
          <td style="${td};max-width:150px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="${esc(a.user_name)||''}">${esc(a.user_name) || '—'}</td>
          <td style="${td};text-align:center">${_edBadge(a.edevice_status)}</td>
        </tr>`).join('')}</tbody>
      </table>
    </div>`;
  el.style.display = '';
}

// ---- State ----
let currentPage = 1;
let totalPages  = 1;
let filters     = { q: '', bu: '', dept: '', position: '', status: '', software: '',
                    hasAsset: false, noAsset: false, hasSw: false, noSw: false };
let buMap       = {};  // bu_code -> bu name

// ---- Asset State ----
let assetLoaded = false;
let assetFilters = { q: '', type: '', bu: '', status: '', ownership: '', machine_type: '', position: '', dept: '' };
let _assetRawData = null;   // cache ผลดิบจาก API สำหรับ toggle hide-return

// ---- Transfer State ----
let transferFromEmpId = null;
let transferAssets    = [];
let empSearchCache    = [];
let assetEmpMap       = {};   // {employee_id: จำนวนเครื่อง Active}
let adCurrent         = null; // หน้ารายละเอียดทรัพย์สินที่เปิดอยู่ {empId, empName, showAll}

// ---- Software State ----
let swEmpMap     = {};   // {employee_id: count}
let swCatalog    = [];   // คลังกลาง [{id, name, category, vendor, license_type, is_active, holders}]
let swCurrentEmp = null; // {id, name}
let swRows       = [];   // ร่างรายการในหน้าถือครอง — ยังไม่บันทึกจนกว่าจะกดยืนยัน
let swRowSeq     = 0;    // ตัวนับ key ของแถวในร่าง
let swCatEditId  = null; // id catalog ที่กำลังแก้ไขในหน้าคลัง
let swcBu         = '';         // แท็บ BU ในคลัง ('' = รวมทุก BU)
let swcBuList     = [];         // [{bu_code, bu}]
let swcMembers    = new Set();  // โปรแกรมที่ชุดรวมซึ่งกำลังแก้ครอบคลุม
let swcMembersAll = false;      // แสดงโปรแกรมของผู้ผลิตอื่นด้วย

// ---- Init ----
document.addEventListener('DOMContentLoaded', () => {
  loadFilters();
  loadEmployees();
  loadStats();
  loadAssetEmpMap();
  loadSoftwareEmpMap();

  // f-status change → show/hide asset transfer section
  document.getElementById('f-status').addEventListener('change', onStatusChange);

  // Tabs
  document.querySelectorAll('.tab').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.tab').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      const tab = btn.dataset.tab;
      document.querySelectorAll('.tab-content').forEach(c => c.style.display = 'none');
      document.getElementById('tab-' + tab).style.display = '';
      if (tab === 'dashboard') { loadStats(); loadRentalDashboard(); }
      if (tab === 'assets' && !assetLoaded) { loadAssetMeta(); loadAssets(); assetLoaded = true; }
      if (tab === 'specs' && !specsLoaded) { loadMachineSpecs(); }
    });
  });

  // Search
  const searchEl = document.getElementById('search');
  const clearBtn = document.getElementById('clear-search');
  let searchTimer;
  searchEl.addEventListener('input', () => {
    filters.q = searchEl.value.trim();
    clearBtn.style.display = filters.q ? '' : 'none';
    clearTimeout(searchTimer);
    searchTimer = setTimeout(() => { currentPage = 1; loadEmployees(); }, 300);
  });
  clearBtn.addEventListener('click', () => {
    searchEl.value = ''; filters.q = '';
    clearBtn.style.display = 'none';
    currentPage = 1; loadEmployees();
  });

  // Filters
  document.getElementById('filter-has-asset').addEventListener('change', onHasAssetChange);

  document.getElementById('filter-bu').addEventListener('change', async () => {
    filters.bu       = document.getElementById('filter-bu').value;
    filters.dept     = '';
    filters.position = '';
    await reloadDeptFilter(filters.bu);
    currentPage = 1;
    loadEmployees();
  });
  document.getElementById('filter-dept').addEventListener('change', async () => {
    filters.dept     = document.getElementById('filter-dept').value;
    filters.position = '';
    await reloadPositionFilter();
    currentPage = 1; loadEmployees();
  });
  document.getElementById('filter-position').addEventListener('change', () => {
    filters.position = document.getElementById('filter-position').value;
    currentPage = 1; loadEmployees();
  });
  document.getElementById('filter-status').addEventListener('change', () => {
    filters.status = document.getElementById('filter-status').value;
    currentPage = 1; loadEmployees();
  });
  document.getElementById('filter-software').addEventListener('change', () => {
    filters.software = document.getElementById('filter-software').value;
    currentPage = 1; loadEmployees();
  });

  // BU select in modal
  document.getElementById('f-bu-code').addEventListener('change', function() {
    const buName = buMap[this.value] || '';
    // auto-fill bu name (hidden field via buMap)
  });
});

// ---- Reload dept filter by BU (แล้วตำแหน่งตามไปด้วย) ----
async function reloadDeptFilter(bu) {
  const params = bu ? '?bu=' + encodeURIComponent(bu) : '';
  const data = await api('/api/filters' + params);
  const deptSel  = document.getElementById('filter-dept');
  const deptList = document.getElementById('dept-list');
  deptSel.innerHTML  = '<option value="">ทุกแผนก</option>';
  deptList.innerHTML = '';
  data.depts.forEach(d => {
    deptSel.insertAdjacentHTML('beforeend', `<option value="${esc(d)}">${esc(d)}</option>`);
    deptList.insertAdjacentHTML('beforeend', `<option value="${esc(d)}">`);
  });
  fillPositionSelect(data.positions);
}

/** ตำแหน่งมี 600+ ค่า — โหลดเฉพาะที่อยู่ใน BU/แผนกที่เลือกไว้ */
async function reloadPositionFilter() {
  const p = new URLSearchParams();
  if (filters.bu)   p.set('bu', filters.bu);
  if (filters.dept) p.set('dept', filters.dept);
  const data = await api('/api/filters' + (p.toString() ? '?' + p : ''));
  fillPositionSelect(data.positions);
}

function fillPositionSelect(positions) {
  const sel = document.getElementById('filter-position');
  sel.innerHTML = `<option value="">ทุกตำแหน่ง${positions ? ` (${positions.length})` : ''}</option>` +
    (positions || []).map(p =>
      `<option value="${esc(p.name)}">${esc(p.name)} (${p.count})</option>`).join('');
  sel.value = filters.position || '';
}

function fillSoftwareSelect(softwares) {
  const sel = document.getElementById('filter-software');
  sel.innerHTML = '<option value="">Software ทั้งหมด</option>' +
    (softwares || []).map(s =>
      `<option value="${s.id}">🧩 ${esc(s.name)} (${s.count})</option>`).join('');
  sel.value = filters.software || '';
}

// ---- Load filters ----
async function loadFilters() {
  const data = await api('/api/filters');
  const buSel = document.getElementById('filter-bu');
  const modalBuSel = document.getElementById('f-bu-code');
  data.bus.forEach(b => {
    buMap[b.bu_code] = b.bu;
    buSel.insertAdjacentHTML('beforeend', `<option value="${b.bu_code}">${b.bu_code} – ${b.bu}</option>`);
    modalBuSel.insertAdjacentHTML('beforeend', `<option value="${b.bu_code}" data-bu="${b.bu}">${b.bu_code} – ${b.bu}</option>`);
  });
  const deptSel = document.getElementById('filter-dept');
  const deptList = document.getElementById('dept-list');
  data.depts.forEach(d => {
    deptSel.insertAdjacentHTML('beforeend', `<option value="${esc(d)}">${esc(d)}</option>`);
    deptList.insertAdjacentHTML('beforeend', `<option value="${esc(d)}">`);
  });
  fillPositionSelect(data.positions);
  fillSoftwareSelect(data.softwares);
}

// ---- Load employees ----
async function loadEmployees() {
  // กรอง "มี/ไม่มี ทรัพย์สิน–Software" ทำฝั่ง client → ต้องดึงทั้งชุดมาก่อน
  const localFilterOn = filters.hasAsset || filters.noAsset || filters.hasSw || filters.noSw;
  const params = new URLSearchParams({
    page: localFilterOn ? 1 : currentPage,
    per_page: localFilterOn ? 9999 : 50,
    q: filters.q, bu: filters.bu, dept: filters.dept,
    position: filters.position, status: filters.status, software: filters.software
  });
  const data = await api('/api/employees?' + params);
  totalPages = data.pages;

  const tbody = document.getElementById('emp-tbody');
  const empty = document.getElementById('empty-state');

  document.getElementById('total-badge').textContent = `พนักงาน ${data.total.toLocaleString()} คน`;

  // client-side filter: มี/ไม่มี ทรัพย์สิน และ Software
  let employees = data.employees;
  if (filters.hasAsset)     employees = employees.filter(e => assetEmpMap[e.id]);
  else if (filters.noAsset) employees = employees.filter(e => !assetEmpMap[e.id]);
  if (filters.hasSw)        employees = employees.filter(e => swEmpMap[e.id]);
  else if (filters.noSw)    employees = employees.filter(e => !swEmpMap[e.id]);

  renderEmpFilterInfo(employees.length, data.total);

  if (!employees.length) {
    tbody.innerHTML = '';
    empty.style.display = '';
  } else {
    empty.style.display = 'none';
    tbody.innerHTML = employees.map((e, i) => `
      <tr>
        <td style="color:#94a3b8">${(currentPage - 1) * 50 + i + 1}</td>
        <td style="color:#64748b;font-size:.78rem;font-family:monospace">${esc(e.emp_code) || '—'}</td>
        <td><strong>${esc(e.name)}</strong></td>
        <td style="color:#64748b">${esc(e.nickname)}</td>
        <td><span class="bu-badge bu-${esc(e.bu_code)}">${esc(e.bu_code)}</span></td>
        <td>${esc(e.department)}</td>
        <td>${esc(e.position)}</td>
        <td style="color:#2563eb">${e.email ? `<a href="mailto:${esc(e.email)}" style="color:#2563eb;text-decoration:none">${esc(e.email)}</a>` : ''}</td>
        <td><span class="status-badge status-${e.status}">${e.status === 'active' ? 'Active' : 'Inactive'}</span></td>
        <td style="text-align:center">${assetEmpMap[e.id] ? `<span class="asset-badge" onclick="showAssetDetail(${e.id},'${esc(e.name)}')" title="เครื่องที่ใช้งานอยู่ ${assetEmpMap[e.id]} เครื่อง (สถานะ Active)">💻 ${assetEmpMap[e.id]}</span>` : ''}</td>
        <td class="sw-cell" data-emp="${e.id}" data-name="${esc(e.name)}">${swCellHtml(e.id, e.name)}</td>
        <td>
          <div class="action-btns">
            <button class="icon-btn edit" onclick="editEmployee(${e.id})" title="แก้ไข">✏️</button>
            <button class="icon-btn del" onclick="deleteEmployee(${e.id}, '${esc(e.name)}')" title="ลบ">🗑️</button>
          </div>
        </td>
      </tr>
    `).join('');
  }
  if (localFilterOn) {
    document.getElementById('pagination').innerHTML = '';
  } else {
    renderPagination(data.total, data.page, data.per_page);
  }
}

// ---- Pagination ----
function renderPagination(total, page, perPage) {
  const pages = Math.ceil(total / perPage);
  const pg = document.getElementById('pagination');
  if (pages <= 1) { pg.innerHTML = ''; return; }

  let html = `<button class="page-btn" onclick="goPage(${page-1})" ${page===1?'disabled':''}>‹</button>`;
  const start = Math.max(1, page - 2), end = Math.min(pages, page + 2);
  if (start > 1) html += `<button class="page-btn" onclick="goPage(1)">1</button>${start>2?'<span style="padding:0 4px;color:#94a3b8">…</span>':''}`;
  for (let p = start; p <= end; p++) {
    html += `<button class="page-btn ${p===page?'active':''}" onclick="goPage(${p})">${p}</button>`;
  }
  if (end < pages) html += `${end<pages-1?'<span style="padding:0 4px;color:#94a3b8">…</span>':''}<button class="page-btn" onclick="goPage(${pages})">${pages}</button>`;
  html += `<button class="page-btn" onclick="goPage(${page+1})" ${page===pages?'disabled':''}>›</button>`;
  pg.innerHTML = html;
}

function goPage(p) {
  if (p < 1 || p > totalPages) return;
  currentPage = p;
  loadEmployees();
  window.scrollTo({ top: 0, behavior: 'smooth' });
}

// ---- Modal ----
function openModal(emp) {
  document.getElementById('modal-title').textContent = emp ? 'แก้ไขข้อมูลพนักงาน' : 'เพิ่มพนักงาน';
  document.getElementById('emp-id').value      = emp ? emp.id : '';
  document.getElementById('f-name').value      = emp ? (emp.name || '') : '';
  document.getElementById('f-nickname').value  = emp ? (emp.nickname || '') : '';
  document.getElementById('f-bu-code').value   = emp ? (emp.bu_code || '') : '';
  document.getElementById('f-department').value= emp ? (emp.department || '') : '';
  document.getElementById('f-position').value  = emp ? (emp.position || '') : '';
  document.getElementById('f-email').value     = emp ? (emp.email || '') : '';
  document.getElementById('f-phone').value     = emp ? (emp.phone || '') : '';
  document.getElementById('f-start-date').value= emp ? (emp.start_date || '') : '';
  const statusEl = document.getElementById('f-status');
  statusEl.value = emp ? (emp.status || 'active') : 'active';
  statusEl.dataset.prev = emp ? (emp.status || 'active') : 'active';
  // reset asset transfer section
  transferAssets = [];
  document.getElementById('asset-transfer-section').style.display = 'none';
  // if already inactive when opening, load assets immediately
  if (emp && emp.status === 'inactive') {
    onStatusChange();
  }
  document.getElementById('f-note').value      = emp ? (emp.note || '') : '';
  document.getElementById('modal-overlay').classList.add('open');
  document.getElementById('f-name').focus();
}

function closeModal() {
  document.getElementById('modal-overlay').classList.remove('open');
  transferAssets = [];
}

function closeModalOnOverlay(e) {
  if (e.target === document.getElementById('modal-overlay')) closeModal();
}

async function editEmployee(id) {
  const emp = await api('/api/employees/' + id);
  openModal(emp);
}

async function saveEmployee() {
  const name = document.getElementById('f-name').value.trim();
  if (!name) { showToast('กรุณากรอกชื่อ-นามสกุล', 'error'); return; }

  const buCode = document.getElementById('f-bu-code').value;
  const buOpt  = document.querySelector(`#f-bu-code option[value="${buCode}"]`);
  const buName = buOpt ? (buOpt.dataset.bu || buMap[buCode] || '') : '';

  const payload = {
    name, bu_code: buCode, bu: buName,
    nickname:   document.getElementById('f-nickname').value.trim(),
    department: document.getElementById('f-department').value.trim(),
    position:   document.getElementById('f-position').value.trim(),
    email:      document.getElementById('f-email').value.trim(),
    phone:      document.getElementById('f-phone').value.trim(),
    start_date: document.getElementById('f-start-date').value,
    status:     document.getElementById('f-status').value,
    note:       document.getElementById('f-note').value.trim(),
  };

  const id = document.getElementById('emp-id').value;
  if (id) {
    // if inactive → run transfer first
    if (payload.status === 'inactive' && transferAssets.length) {
      const invalid = transferAssets.filter(t => t.to_type === 'employee' && !t.to_employee_id);
      if (invalid.length) {
        showToast(`กรุณาเลือกพนักงานให้ครบ ${invalid.length} รายการ`, 'error'); return;
      }
      await api('/api/assets/transfer-bulk', 'POST', {
        from_employee_id: parseInt(id),
        transfers: transferAssets.map(t => ({ asset_no: t.asset_no, to_type: t.to_type, to_employee_id: t.to_employee_id }))
      });
    }
    // เปลี่ยนเป็น Inactive → Software ที่ถืออยู่จะถูกถอนคืนคลัง แจ้งให้รู้ก่อน
    const swN = swEmpMap[parseInt(id)] || 0;
    if (payload.status === 'inactive' && swN &&
        !confirm(`พนักงานคนนี้ถือ Software อยู่ ${swN} รายการ\n` +
                 `เมื่อเปลี่ยนเป็น Inactive ระบบจะถอนคืนคลังทั้งหมด (มีบันทึกประวัติไว้)\n\nยืนยัน?`)) return;
    const res = await api('/api/employees/' + id, 'PUT', payload);
    if (res.software_released) {
      showToast(`อัปเดตแล้ว · ถอน Software คืนคลัง ${res.software_released} รายการ`, 'success');
      swDash = swVendor = null;
      loadSoftwareEmpMap();
      refreshSoftwareFilterOptions();
    } else {
      showToast('อัปเดตข้อมูลเรียบร้อย', 'success');
    }
  } else {
    await api('/api/employees', 'POST', payload);
    showToast('เพิ่มพนักงานเรียบร้อย', 'success');
  }
  closeModal();
  loadEmployees();
  loadStats();
  if (assetLoaded) loadAssets(true);
  loadAssetEmpMap();   // ต้องผ่านตัวนี้ เพราะมันแปลง key เป็นตัวเลขให้ตรงกับ e.id
}

async function deleteEmployee(id, name) {
  if (!confirm(`ต้องการลบ "${name}" ออกจากระบบ?`)) return;
  await api('/api/employees/' + id, 'DELETE');
  showToast(`ลบ ${name} เรียบร้อย`, 'success');
  loadEmployees();
  loadStats();
}

// ---- Export / Import ----
function exportExcel() {
  const params = new URLSearchParams({ q: filters.q, bu: filters.bu, dept: filters.dept });
  window.location = '/api/export/excel?' + params;
}

async function importExcel(input) {
  const file = input.files[0];
  if (!file) return;
  const fd = new FormData();
  fd.append('file', file);
  try {
    const res = await fetch('/api/import/excel', { method: 'POST', body: fd });
    const d = await res.json();
    showToast(`นำเข้าสำเร็จ ${d.added} รายการ${d.skipped ? ` (ข้าม ${d.skipped})` : ''}`, 'success');
    loadEmployees(); loadFilters(); loadStats();
  } catch { showToast('นำเข้าไม่สำเร็จ', 'error'); }
  input.value = '';
}

// ---- Dashboard ----
async function loadStats() {
  const d = await api('/api/stats');
  document.getElementById('dash-total').textContent  = d.total.toLocaleString();
  document.getElementById('dash-active').textContent = d.active.toLocaleString();
  document.getElementById('dash-bu-count').textContent   = d.by_bu.length;
  document.getElementById('dash-dept-count').textContent = d.by_dept.length + '+';

  const maxBu = Math.max(...d.by_bu.map(b => b.cnt), 1);
  document.getElementById('bu-bars').innerHTML = d.by_bu.map(b => `
    <div class="bar-row">
      <div class="bar-label" title="${b.bu}" style="width:56px;min-width:56px;text-align:right">${b.bu_code}</div>
      <div class="bar-track"><div class="bar-fill" style="width:${(b.cnt/maxBu*100).toFixed(1)}%"></div></div>
      <div class="bar-count">${b.cnt}</div>
    </div>
  `).join('');

  const maxDept = Math.max(...d.by_dept.map(b => b.cnt), 1);
  document.getElementById('dept-bars').innerHTML = d.by_dept.map(b => `
    <div class="bar-row">
      <div class="bar-label" title="${b.department}" style="width:200px;min-width:200px;text-align:right;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${b.department}</div>
      <div class="bar-track"><div class="bar-fill" style="width:${(b.cnt/maxDept*100).toFixed(1)}%"></div></div>
      <div class="bar-count">${b.cnt}</div>
    </div>
  `).join('');
}

// ==============================
// ---- IT Assets ----
// ==============================

async function loadAssetMeta() {
  const d = await api('/api/assets/meta');

  const typeSel = document.getElementById('a-filter-type');
  d.types.forEach(t => typeSel.insertAdjacentHTML('beforeend', `<option value="${t}">${t}</option>`));

  // populate ประเภทเครื่อง filter (จาก dropdown 'ประเภท' ใน eDevice)
  const machineSel = document.getElementById('a-filter-machine');
  (d.machine_types || []).forEach(m => machineSel.insertAdjacentHTML('beforeend', `<option value="${esc(m)}">${esc(m)}</option>`));
  machineSel.insertAdjacentHTML('beforeend', `<option value="-">— ไม่ระบุ —</option>`);

  // populate position filter
  const posSel = document.getElementById('a-filter-position');
  (d.positions || []).forEach(p => posSel.insertAdjacentHTML('beforeend', `<option value="${esc(p)}">${esc(p)}</option>`));

  // populate dept filter
  const deptSel = document.getElementById('a-filter-dept');
  (d.depts || []).forEach(dep => deptSel.insertAdjacentHTML('beforeend', `<option value="${esc(dep)}">${esc(dep)}</option>`));

  // populate BU filter from existing buMap (loaded with employees)
  const buSel = document.getElementById('a-filter-bu');
  Object.entries(buMap).forEach(([code, name]) => {
    buSel.insertAdjacentHTML('beforeend', `<option value="${code}">${code}</option>`);
  });

  // wire up filter events (fetch ใหม่เมื่อ filter เปลี่ยน)
  ['a-search', 'a-filter-type', 'a-filter-bu', 'a-filter-status', 'a-filter-ownership', 'a-filter-machine', 'a-filter-position', 'a-filter-dept'].forEach(id => {
    const el = document.getElementById(id);
    const evt = el.tagName === 'INPUT' ? 'input' : 'change';
    el.addEventListener(evt, () => {
      assetFilters.q         = document.getElementById('a-search').value.trim();
      assetFilters.type      = document.getElementById('a-filter-type').value;
      assetFilters.bu        = document.getElementById('a-filter-bu').value;
      assetFilters.status    = document.getElementById('a-filter-status').value;
      assetFilters.ownership = document.getElementById('a-filter-ownership').value;
      assetFilters.machine_type = document.getElementById('a-filter-machine').value;
      assetFilters.position  = document.getElementById('a-filter-position').value;
      assetFilters.dept      = document.getElementById('a-filter-dept').value;
      loadAssets();
    });
  });

  // checkbox / dropdown ที่ filter ฝั่ง client — toggle ทันทีโดยไม่ fetch ใหม่
  ['a-filter-resigned', 'a-filter-no-owner', 'a-filter-central', 'a-filter-missing-edevice'].forEach(id => {
    document.getElementById(id).addEventListener('change', () => {
      if (_assetRawData) renderAssetTable(_assetRawData);
    });
  });
  document.getElementById('a-filter-ed-status').addEventListener('change', () => {
    if (_assetRawData) renderAssetTable(_assetRawData);
  });
}

async function updateSheetsInfo() {
  const btn = document.getElementById('sheets-update-btn');
  const orig = btn.innerHTML;
  btn.disabled = true;
  btn.innerHTML = `<span style="font-size:.75rem">⏳ กำลังอัพเดท...</span>`;

  try {
    const res  = await fetch('/api/sheets/update-info', { method: 'POST' });
    const data = await res.json();

    if (data.ok) {
      btn.innerHTML = `<span style="color:#16a34a;font-size:.75rem">✓ อัพเดท ${data.updated} แถว</span>`;
      setTimeout(() => { btn.innerHTML = orig; btn.disabled = false; }, 4000);
    } else {
      btn.innerHTML = `<span style="color:#dc2626;font-size:.75rem">✕ ${data.error || 'ผิดพลาด'}</span>`;
      setTimeout(() => { btn.innerHTML = orig; btn.disabled = false; }, 5000);
    }
  } catch(e) {
    btn.innerHTML = `<span style="color:#dc2626;font-size:.75rem">✕ ไม่สามารถเชื่อมต่อได้</span>`;
    setTimeout(() => { btn.innerHTML = orig; btn.disabled = false; }, 5000);
  }
}

async function loadAssets(refresh = false) {
  const params = new URLSearchParams({
    q:         assetFilters.q,
    type:      assetFilters.type,
    bu:        assetFilters.bu,
    status:    assetFilters.status,
    ownership: assetFilters.ownership,
    machine_type: assetFilters.machine_type,
    position:  assetFilters.position,
    dept:      assetFilters.dept,
  });
  if (refresh) params.set('refresh', '1');

  document.getElementById('a-result-info').textContent = 'กำลังโหลด...';

  let d;
  try {
    d = await api('/api/assets?' + params);
  } catch(e) {
    showToast('โหลด Asset ไม่สำเร็จ', 'error');
    document.getElementById('a-result-info').textContent = 'เกิดข้อผิดพลาด';
    return;
  }

  // summary cards จะอัพเดทหลัง filter ใน renderAssetTable()

  if (d.cached_at) {
    document.getElementById('a-cache-info').textContent = `ข้อมูล ณ ${d.cached_at}`;
  }

  _assetRawData = d;
  window._lastAssetData = d;
  renderAssetTable(d);
}

function renderAssetTable(d) {
  const onlyResigned  = document.getElementById('a-filter-resigned')?.checked ?? false;
  const onlyNoOwner        = document.getElementById('a-filter-no-owner')?.checked ?? false;
  const onlyCentral        = document.getElementById('a-filter-central')?.checked ?? false;
  const onlyMissingEdevice = document.getElementById('a-filter-missing-edevice')?.checked ?? false;
  const edStatusF     = (document.getElementById('a-filter-ed-status')?.value || '').toLowerCase();

  let assets = d.assets;
  if (edStatusF)   assets = assets.filter(a => (a.edevice_status || '').toLowerCase() === edStatusF);
  if (onlyResigned)        assets = assets.filter(a => a.user_name && !a.employee_id && !a.is_central);
  if (onlyNoOwner)         assets = assets.filter(a => !a.user_name && !a.is_central);
  if (onlyCentral)         assets = assets.filter(a => a.is_central);
  if (onlyMissingEdevice)  assets = assets.filter(a => a.ownership_missing_edevice && a.contract_status !== 'returned');

  // ── อัพเดท summary cards ──────────────────────────────────────────
  // a-total = ยอดรวมทั้งหมดก่อน filter (เพื่อให้ตรงกับ eDevice sync)
  const shown = assets.length;
  const totalAll = d.assets.length;   // รวมทุกเครื่องก่อน filter
  const missingEdevice = d.assets.filter(a => a.ownership_missing_edevice && a.contract_status !== 'returned').length;
  const inEdevice = totalAll - missingEdevice;
  const monthly = assets.reduce((s, a) => s + (a.monthly_charge || 0), 0);
  const sc = { expired: 0, ed_expire: 0, critical: 0, warning: 0, ok: 0 };
  d.assets.forEach(a => {   // นับจาก raw data ไม่ใช่ filtered — การ์ดแสดงยอดรวมเสมอ
    const isBought   = a.ownership === 'ซื้อ';
    const isEdExpire = (a.edevice_status || '').toLowerCase() === 'expire';
    if (isEdExpire) { sc.ed_expire++; return; }   // ทุกเครื่อง (ซื้อ+เช่า) ที่ eDevice = Expire
    if (isBought) return;                          // เครื่องซื้อที่ไม่ Expire ไม่นับสัญญาเช่า
    if (sc[a.contract_status] !== undefined) sc[a.contract_status]++;
  });
  document.getElementById('a-total').textContent         = totalAll.toLocaleString();
  document.getElementById('a-total-in-edevice').textContent  = `✓ อยู่ใน eDevice ${inEdevice.toLocaleString()} เครื่อง`;
  const missingEl = document.getElementById('a-total-missing-edevice');
  if (missingEdevice > 0) {
    missingEl.textContent = `⚠ ยังไม่บันทึกใน eDevice ${missingEdevice} เครื่อง`;
    missingEl.style.display = '';
  } else {
    missingEl.style.display = 'none';
  }
  document.getElementById('a-monthly').textContent   = '฿' + monthly.toLocaleString('th', {minimumFractionDigits: 0, maximumFractionDigits: 0});
  document.getElementById('a-expired').textContent   = sc.expired.toLocaleString();
  document.getElementById('a-ed-expire').textContent = sc.ed_expire.toLocaleString();
  document.getElementById('a-critical').textContent  = sc.critical.toLocaleString();
  document.getElementById('a-warning').textContent   = sc.warning.toLocaleString();
  document.getElementById('a-ok').textContent        = sc.ok.toLocaleString();
  // ── filter tags พร้อม config สำหรับ clear แต่ละตัว ──────────────────
  const filterTagCfg = [];
  if (assetFilters.q)        filterTagCfg.push({ label: `🔍 "${assetFilters.q}"`,   clear: () => { document.getElementById('a-search').value=''; assetFilters.q=''; } });
  if (assetFilters.bu)       filterTagCfg.push({ label: `BU: ${assetFilters.bu}`,    clear: () => { document.getElementById('a-filter-bu').value=''; assetFilters.bu=''; } });
  if (assetFilters.type)     filterTagCfg.push({ label: `ประเภท: ${assetFilters.type}`, clear: () => { document.getElementById('a-filter-type').value=''; assetFilters.type=''; } });
  if (assetFilters.ownership)filterTagCfg.push({ label: `สัญญา: ${assetFilters.ownership}`, clear: () => { document.getElementById('a-filter-ownership').value=''; assetFilters.ownership=''; } });
  if (assetFilters.machine_type) filterTagCfg.push({ label: `ประเภทเครื่อง: ${assetFilters.machine_type === '-' ? 'ไม่ระบุ' : assetFilters.machine_type}`, clear: () => { document.getElementById('a-filter-machine').value=''; assetFilters.machine_type=''; } });
  if (assetFilters.status)   filterTagCfg.push({ label: `สถานะ: ${assetFilters.status}`, clear: () => { document.getElementById('a-filter-status').value=''; assetFilters.status=''; } });
  if (edStatusF)             filterTagCfg.push({ label: `eDevice: ${edStatusF}`,    clear: () => { document.getElementById('a-filter-ed-status').value=''; } });
  if (assetFilters.position) filterTagCfg.push({ label: `ตำแหน่ง: ${assetFilters.position}`, clear: () => { document.getElementById('a-filter-position').value=''; assetFilters.position=''; } });
  if (assetFilters.dept)     filterTagCfg.push({ label: `แผนก: ${assetFilters.dept}`, clear: () => { document.getElementById('a-filter-dept').value=''; assetFilters.dept=''; } });
  if (onlyResigned)          filterTagCfg.push({ label: `⚠ ไม่พบใน HR`,  clear: () => { document.getElementById('a-filter-resigned').checked=false; } });
  if (onlyNoOwner)           filterTagCfg.push({ label: `❔ ไม่มีผู้ถือครอง`, clear: () => { document.getElementById('a-filter-no-owner').checked=false; } });
  if (onlyCentral)           filterTagCfg.push({ label: `🏢 ส่วนกลาง`,   clear: () => { document.getElementById('a-filter-central').checked=false; } });
  if (onlyMissingEdevice)    filterTagCfg.push({ label: `✕ ยังไม่บันทึกใน eDevice`, clear: () => { document.getElementById('a-filter-missing-edevice').checked=false; } });

  const isFiltered = shown < totalAll || filterTagCfg.length > 0;

  // แสดง/ซ่อนปุ่ม reset
  const resetBtn = document.getElementById('a-reset-btn');
  const resetDiv = document.getElementById('a-reset-divider');
  if (resetBtn) resetBtn.style.display = isFiltered ? '' : 'none';
  if (resetDiv) resetDiv.style.display = isFiltered ? '' : 'none';

  const countHtml = isFiltered
    ? `<span class="ri-count">${shown.toLocaleString()}</span><span style="color:#94a3b8;font-size:.82rem"> / ${totalAll.toLocaleString()} รายการ</span>`
    : `<span class="ri-count">${shown.toLocaleString()}</span><span style="color:#94a3b8;font-size:.82rem"> รายการ</span>`;

  const monthlyHtml = `<span class="ri-monthly">฿${monthly.toLocaleString('th', {minimumFractionDigits: 0, maximumFractionDigits: 0})}</span><span style="color:#64748b;font-size:.78rem"> / เดือน</span>`;

  // tags กด × ได้ทีละอัน — store clear fn บน window แล้วเรียก by index
  window._filterClearFns = filterTagCfg.map(f => f.clear);
  const tagsHtml = filterTagCfg.map((f, i) =>
    `<span class="ri-filter-tag" onclick="window._filterClearFns[${i}]();renderAssetTable(window._lastAssetData)" title="คลิกเพื่อยกเลิก filter นี้">
      ${f.label} <span style="margin-left:3px;font-size:.7rem;opacity:.7">×</span>
    </span>`
  ).join('');

  const riEl = document.getElementById('a-result-info');
  riEl.innerHTML = `${countHtml} &nbsp;·&nbsp; ${monthlyHtml}${tagsHtml ? ' &nbsp;&nbsp;' + tagsHtml : ''}`;
  if (isFiltered) {
    riEl.style.background = '#eff6ff';
    riEl.style.borderBottom = '1px solid #bfdbfe';
    riEl.style.borderTop = '2px solid #3b82f6';
  } else {
    riEl.style.background = '';
    riEl.style.borderBottom = '';
    riEl.style.borderTop = '';
  }

  const tbody = document.getElementById('asset-tbody');
  const empty = document.getElementById('a-empty');

  if (!assets.length) {
    tbody.innerHTML = '';
    empty.style.display = '';
    return;
  }
  empty.style.display = 'none';
  // reassign local variable for the render loop below
  d = { ...d, assets };

  const statusLabel = (a) => {
    if (a.ownership === 'ซื้อ') {
      if ((a.edevice_status||'').toLowerCase() === 'expire') return '🗑 ตัดจำหน่าย';
      return '🏷 เครื่องซื้อ';
    }
    const d = a.days_remaining;
    if (a.contract_status === 'returned') return '↩ คืนแล้ว';
    if (a.contract_status === 'expired')  return `🔴 เกินกำหนด ${Math.abs(d)} วัน`;
    if (a.contract_status === 'critical') return `🟠 เหลือ ${d} วัน`;
    if (a.contract_status === 'warning')  return `🟡 เหลือ ${d} วัน`;
    if (a.contract_status === 'ok')       return d !== null ? `🟢 เหลือ ${d} วัน` : '🟢 ปกติ';
    return '— ไม่ระบุ';
  };

  // eDevice status badge (Active/Expire/Return/Spare/Error)
  const ED_STATUS_CFG = {
    active:  { bg: '#dcfce7', color: '#15803d', label: '● Active'  },
    expire:  { bg: '#fef9c3', color: '#854d0e', label: '⚠ Expire'  },
    return:  { bg: '#f1f5f9', color: '#475569', label: '↩ Return'  },
    spare:   { bg: '#ede9fe', color: '#6d28d9', label: '◎ Spare'   },
    error:   { bg: '#fee2e2', color: '#b91c1c', label: '✕ Error'   },
  };
  const edStatusBadge = (s) => {
    if (!s) return '<span style="color:#cbd5e1">—</span>';
    const c = ED_STATUS_CFG[s.toLowerCase()] || { bg:'#f1f5f9', color:'#475569', label: s };
    return `<span style="font-size:.72rem;padding:2px 8px;border-radius:5px;font-weight:600;background:${c.bg};color:${c.color}">${c.label}</span>`;
  };
  const pillClass   = { expired: 'pill-expired', critical: 'pill-critical', warning: 'pill-warning', ok: 'pill-ok', unknown: 'pill-unknown', bought: 'pill-bought' };
  const daysClass   = { expired: 'days-expired', critical: 'days-critical', warning: 'days-warning', ok: 'days-ok' };
  const rowClass    = { expired: 'contract-expired', critical: 'contract-critical', warning: 'contract-warning' };
  tbody.innerHTML = d.assets.map((a, i) => {
    const isBought = a.ownership === 'ซื้อ';
    const st = isBought ? 'bought' : a.contract_status;

    const buBadge = a.emp_bu_code
      ? `<span class="bu-badge bu-${esc(a.emp_bu_code)}">${esc(a.emp_bu_code)}</span>`
      : `<span style="color:#cbd5e1">—</span>`;

    const deptText = a.emp_dept || a.dept_sheet || '—';

    const endFmt = a.end_date
      ? new Date(a.end_date).toLocaleDateString('th-TH', {day:'numeric', month:'short', year:'2-digit'})
      : '—';

    const computerIdHtml = a.computer_id
      ? `<code style="font-size:.75rem;color:#334155">${esc(a.computer_id)}</code>`
      : '<span style="color:#cbd5e1">—</span>';

    const C = 'overflow:hidden;text-overflow:ellipsis;white-space:nowrap'; // shorthand
    return `<tr class="${rowClass[st] || ''}">
      <td style="color:#94a3b8;font-size:.75rem">${i+1}</td>
      <td style="${C}" title="${esc(a.asset_no)}"><code style="font-size:.75rem;color:#334155">${esc(a.asset_no)}</code></td>
      <td style="${C}" title="${esc(a.computer_id)}">${computerIdHtml}</td>
      <td style="${C}" title="${esc(a.serial_no)}"><code style="font-size:.73rem;color:#64748b">${esc(a.serial_no) || '—'}</code></td>
      <td style="text-align:center">
        ${a.edevice_matched && a.sheets_matched
          ? '<span style="font-size:.65rem;background:#dcfce7;color:#15803d;padding:1px 5px;border-radius:4px;font-weight:600;white-space:nowrap">eDevice+Sheets</span>'
          : a.edevice_matched
          ? '<span style="font-size:.65rem;background:#dbeafe;color:#1d4ed8;padding:1px 5px;border-radius:4px;font-weight:600">eDevice</span>'
          : a.sheets_matched
          ? '<span style="font-size:.65rem;background:#fef9c3;color:#854d0e;padding:1px 5px;border-radius:4px;font-weight:600">Sheets</span> <span style="font-size:.65rem;background:#fee2e2;color:#b91c1c;padding:1px 5px;border-radius:3px;font-weight:600;cursor:default" title="ไม่มีข้อมูลในระบบ eDevice — กรุณาเพิ่มเครื่องนี้ใน eDevice">+eDevice</span>'
          : '<span style="color:#cbd5e1">—</span>'}
      </td>
      <td style="${C};font-size:.78rem">${esc(a.asset_type)}</td>
      <td style="text-align:center">${
        ownershipBadge(a)
      }</td>
      <td style="${C};font-size:.75rem;color:#475569" title="${esc(a.machine_type)}">${esc(a.machine_type) || '<span style="color:#cbd5e1">—</span>'}</td>
      <td style="${C};font-size:.8rem" title="${esc(a.model)}">${esc(a.model)}</td>
      <td style="${C};font-size:.82rem" title="${esc(a.user_name)}">
        ${a.is_central
          ? '<span class="badge-central">🏢 ส่วนกลาง</span>'
          : `<strong>${esc(a.user_name) || '<span style="color:#94a3b8">—</span>'}</strong>${a.user_name && !a.employee_id ? ' <span style="font-size:.68rem;color:#ef4444;font-weight:600">(ไม่พบใน HR)</span>' : ''}`
        }
      </td>
      <td style="${C};font-size:.73rem;color:#64748b" title="${esc(a.emp_position)}">${esc(a.emp_position) || '<span style="color:#cbd5e1">—</span>'}</td>
      <td style="text-align:center">${buBadge}</td>
      <td style="${C};font-size:.75rem;color:#64748b" title="${esc(deptText)}">${esc(deptText)}</td>
      <td style="${C};font-size:.78rem;white-space:nowrap">${endFmt}</td>
      <td><span class="status-pill ${pillClass[st] || 'pill-unknown'}" style="font-size:.7rem;padding:2px 6px">${statusLabel(a)}</span></td>
      <td style="text-align:center">${edStatusBadge(a.edevice_status)}</td>
      <td style="text-align:right;font-size:.8rem;color:#374151">฿${(a.monthly_charge||0).toLocaleString()}</td>
    </tr>`;
  }).join('');
}

// ==============================
// ---- Asset Map & Badge ----
// ==============================

/** แถบผลลัพธ์ + ป้ายบอกว่ากรองอะไรอยู่ (คลิกที่ป้ายเพื่อยกเลิกเฉพาะอันนั้น) */
function renderEmpFilterInfo(showing, total) {
  const swName = (document.getElementById('filter-software')
                   .selectedOptions[0] || {}).textContent || '';
  const chips = [];
  if (filters.q)        chips.push(['q',        `ค้นหา: ${filters.q}`]);
  if (filters.bu)       chips.push(['bu',       `BU: ${filters.bu}`]);
  if (filters.dept)     chips.push(['dept',     `แผนก: ${filters.dept}`]);
  if (filters.position) chips.push(['position', `ตำแหน่ง: ${filters.position}`]);
  if (filters.status)   chips.push(['status',   `สถานะ: ${filters.status === 'active' ? 'Active' : 'Inactive'}`]);
  if (filters.software) chips.push(['software', swName.replace(/\s*\(\d+\)$/, '')]);
  if (filters.hasAsset) chips.push(['hasAsset', '💻 มีเครื่องใช้งาน (Active)']);
  if (filters.noAsset)  chips.push(['noAsset',  '🚫 ไม่มีเครื่อง Active']);
  if (filters.hasSw)    chips.push(['hasSw',    '🧩 มี Software']);
  if (filters.noSw)     chips.push(['noSw',     '🚫 ยังไม่บันทึก Software']);

  document.getElementById('result-info').innerHTML =
    `<span><span class="ri-count">${showing.toLocaleString()}</span> จาก ${total.toLocaleString()} รายการ</span>` +
    chips.map(([k, label]) =>
      `<span class="ri-filter-tag" onclick="clearEmpFilter('${k}')" title="คลิกเพื่อยกเลิกตัวกรองนี้">
         ${esc(label)} ✕</span>`).join('');

  const btn = document.getElementById('emp-reset-btn');
  if (btn) btn.style.display = chips.length ? '' : 'none';
}

async function clearEmpFilter(key) {
  const el = {
    q: 'search', bu: 'filter-bu', dept: 'filter-dept', position: 'filter-position',
    status: 'filter-status', software: 'filter-software',
    hasAsset: 'filter-has-asset', noAsset: 'filter-no-asset',
    hasSw: 'filter-has-sw', noSw: 'filter-no-sw',
  }[key];

  if (['hasAsset', 'noAsset', 'hasSw', 'noSw'].includes(key)) {
    filters[key] = false;
    const cb = document.getElementById(el);
    cb.checked = false;
    cb.closest('label').classList.remove('active');
  } else {
    filters[key] = '';
    document.getElementById(el).value = '';
    if (key === 'q') document.getElementById('clear-search').style.display = 'none';
    // ล้าง BU/แผนก แล้วตัวเลือกที่ไล่ตามกันต้องกว้างขึ้นด้วย
    if (key === 'bu')   { filters.dept = ''; filters.position = ''; await reloadDeptFilter(''); }
    if (key === 'dept') { filters.position = ''; await reloadPositionFilter(); }
  }
  currentPage = 1;
  loadEmployees();
}

async function resetEmpFilters() {
  filters = { q: '', bu: '', dept: '', position: '', status: '', software: '',
              hasAsset: false, noAsset: false, hasSw: false, noSw: false };
  ['search', 'filter-bu', 'filter-dept', 'filter-position', 'filter-status', 'filter-software']
    .forEach(id => { document.getElementById(id).value = ''; });
  ['filter-has-asset', 'filter-no-asset', 'filter-has-sw', 'filter-no-sw'].forEach(id => {
    const cb = document.getElementById(id);
    cb.checked = false;
    cb.closest('label').classList.remove('active');
  });
  document.getElementById('clear-search').style.display = 'none';
  await reloadDeptFilter('');
  currentPage = 1;
  loadEmployees();
}

/** เช็กบ็อกซ์ 2 ตัวในคู่เดียวกันเลือกพร้อมกันไม่ได้ */
function _toggleEmpPair(cbId, otherId, key, otherKey) {
  const cb = document.getElementById(cbId);
  filters[key] = cb.checked;
  cb.closest('label').classList.toggle('active', cb.checked);
  if (cb.checked) {
    const other = document.getElementById(otherId);
    other.checked = false;
    other.closest('label').classList.remove('active');
    filters[otherKey] = false;
  }
  currentPage = 1;
  loadEmployees();
}

function onHasSwChange() { _toggleEmpPair('filter-has-sw', 'filter-no-sw', 'hasSw', 'noSw'); }
function onNoSwChange()  { _toggleEmpPair('filter-no-sw', 'filter-has-sw', 'noSw', 'hasSw'); }

function onHasAssetChange() {
  const cb = document.getElementById('filter-has-asset');
  filters.hasAsset = cb.checked;
  cb.closest('label').classList.toggle('active', cb.checked);
  if (cb.checked) {
    const other = document.getElementById('filter-no-asset');
    other.checked = false;
    other.closest('label').classList.remove('active');
    filters.noAsset = false;
  }
  currentPage = 1;
  loadEmployees();
}

function onNoAssetChange() {
  const cb = document.getElementById('filter-no-asset');
  filters.noAsset = cb.checked;
  cb.closest('label').classList.toggle('active', cb.checked);
  if (cb.checked) {
    const other = document.getElementById('filter-has-asset');
    other.checked = false;
    other.closest('label').classList.remove('active');
    filters.hasAsset = false;
  }
  currentPage = 1;
  loadEmployees();
}

async function loadAssetEmpMap() {
  try {
    const raw = await api('/api/assets/employee-map?status=active');
    // normalize keys to numbers
    assetEmpMap = {};
    Object.entries(raw).forEach(([k, v]) => { assetEmpMap[parseInt(k)] = v; });
  } catch(e) {}
}

/** หน้ารายละเอียดทรัพย์สิน — ค่าปกติแสดงเฉพาะเครื่องที่ eDevice ระบุ Active
 *  เครื่องสถานะอื่น (Expire / Spare / Error) ซ่อนไว้ แต่บอกจำนวนและกดดูได้ */
async function showAssetDetail(empId, empName, showAll) {
  adCurrent = { empId, empName, showAll: !!showAll };
  document.getElementById('ad-subtitle').textContent = empName;
  document.getElementById('ad-list').innerHTML =
    '<div style="text-align:center;padding:24px;color:#94a3b8">กำลังโหลด...</div>';
  document.getElementById('asset-detail-overlay').classList.add('open');

  const all      = await api(`/api/employees/${empId}/assets`);
  const active   = all.filter(a => a.is_active_now);
  const hidden   = all.filter(a => !a.is_active_now);
  const assets   = showAll ? all : active;

  // แถบบอกว่าซ่อนอะไรไว้ + ปุ่มสลับ — กันเครื่องหายเงียบ ๆ
  const byStatus = {};
  hidden.forEach(a => {
    const k = (a.edevice_status || 'ไม่ระบุสถานะ').toLowerCase();
    byStatus[k] = (byStatus[k] || 0) + 1;
  });
  const LBL = { expire: '⚠ Expire', spare: '◎ Spare', return: '↩ Return',
                error: '✕ Error', 'ไม่ระบุสถานะ': 'ไม่ระบุสถานะ' };
  const noticeBar = !hidden.length ? '' : `
    <div class="ad-notice">
      <span>${showAll
        ? `แสดงทุกเครื่อง — มี ${active.length} เครื่อง Active และ ${hidden.length} เครื่องสถานะอื่น`
        : `แสดงเฉพาะเครื่อง Active · ซ่อน ${hidden.length} เครื่อง
           (${Object.entries(byStatus).map(([k, n]) => `${LBL[k] || k} ${n}`).join(' · ')})`}</span>
      <button class="btn-sm" onclick="showAssetDetail(${empId},'${esc(empName).replace(/'/g, '&#39;')}',${!showAll})">
        ${showAll ? 'แสดงเฉพาะ Active' : 'แสดงทั้งหมด'}
      </button>
    </div>`;

  if (!assets.length) {
    document.getElementById('ad-list').innerHTML = noticeBar + (hidden.length
      ? `<div style="text-align:center;padding:24px;color:#b45309;font-size:.85rem">
           ไม่มีเครื่องสถานะ Active — เครื่องทั้ง ${hidden.length} เครื่องของคนนี้เป็นสถานะอื่น</div>`
      : '<div style="text-align:center;padding:24px;color:#16a34a;font-size:.85rem">✓ ไม่มีทรัพย์สินที่ถือครองอยู่</div>');
    return;
  }
  const LB = 'width:130px;min-width:130px;padding:7px 14px 7px 16px;font-size:.75rem;font-weight:600;color:#64748b;vertical-align:middle;border-bottom:1px solid #f1f5f9;white-space:nowrap';
  const VB = 'padding:7px 16px 7px 10px;font-size:.82rem;color:#1e293b;vertical-align:middle;border-bottom:1px solid #f1f5f9';

  const adCards = assets.map((a, idx) => {
    const borderColor = a.contract_status === 'expired'  ? '#fca5a5'
                      : a.contract_status === 'critical' ? '#fdba74'
                      : a.contract_status === 'returned' ? '#cbd5e1'
                      : '#c7d2fe';
    const headerBg    = a.contract_status === 'expired'  ? '#fff1f2'
                      : a.contract_status === 'critical' ? '#fff7ed'
                      : a.contract_status === 'returned' ? '#f8fafc'
                      : '#eef2ff';

    const rows = [
      ['Asset No.',      `<span style="font-family:monospace;color:#475569;font-size:.82rem">${esc(a.asset_no)||'—'}</span>`],
      ['รหัสเครื่อง',   `<code style="color:#334155;font-size:.82rem">${esc(a.computer_id)||'—'}</code>`],
      ['Serial No.',     `<span style="font-family:monospace;color:#475569;font-size:.82rem">${esc(a.serial_no)||'—'}</span>`],
      ['แหล่งข้อมูล',   _srcBadge(a)],
      ['ประเภท',         esc(a.asset_type)||'—'],
      ['ประเภทสัญญา',   ownershipBadge(a)],
      ['ประเภทเครื่อง', esc(a.machine_type)||'—'],
      ['ยี่ห้อ / รุ่น',  `${esc(a.brand)||''} ${esc(a.model)||''}`.trim() || '—'],
      ['ผู้ถือครอง',     a.is_central
          ? '<span class="badge-central">🏢 ส่วนกลาง</span>'
          : a.user_name
            ? `<strong>${esc(a.user_name)}</strong>${!a.employee_id ? ' <span style="font-size:.68rem;color:#ef4444">(ไม่พบใน HR)</span>' : ''}`
            : '<em style="color:#94a3b8">ไม่ระบุ</em>'],
      ['แผนก',           esc(a.emp_dept)||'—'],
      ['วันเริ่มสัญญา',  _dateFmt(a.start_date)],
      ['วันหมดสัญญา',   _dateFmt(a.end_date)],
      ['สถานะสัญญา',    _contractPill(a)],
      ['สถานะ eDevice',  _edBadge(a.edevice_status)],
      ['ค่าเช่า/เดือน',  a.monthly_charge ? `<strong style="color:#1e293b">฿${a.monthly_charge.toLocaleString()}</strong>` : '<span style="color:#94a3b8">฿0</span>'],
    ];

    return `
      <div style="border:1.5px solid ${borderColor};border-radius:12px;overflow:hidden;background:#fff;${idx > 0 ? 'margin-top:14px' : ''}">
        <div style="background:${headerBg};padding:10px 16px;display:flex;align-items:center;gap:10px;border-bottom:1px solid ${borderColor}">
          <span style="font-size:.8rem;font-weight:700;color:#475569">#${idx+1}</span>
          <span style="font-weight:700;font-size:.9rem;color:#1e293b">${esc(a.model)||esc(a.brand)||'ไม่ระบุรุ่น'}</span>
          <span style="font-size:.72rem;background:#fff;border:1px solid ${borderColor};border-radius:5px;padding:1px 8px;color:#64748b">${esc(a.asset_type)||''}</span>
          <span style="margin-left:auto">${_contractPill(a)}</span>
        </div>
        <table style="width:100%;border-collapse:collapse">
          <tbody>
            ${rows.map(([label, val]) => `
              <tr style="border-bottom:1px solid #f1f5f9">
                <td style="width:130px;padding:8px 12px 8px 16px;font-size:.74rem;font-weight:600;color:#94a3b8;white-space:nowrap;vertical-align:middle">${label}</td>
                <td style="padding:8px 16px 8px 8px;font-size:.82rem;color:#1e293b;vertical-align:middle">${val}</td>
              </tr>`).join('')}
          </tbody>
        </table>
      </div>`;
  }).join('');

  document.getElementById('ad-list').innerHTML =
    noticeBar + `<div style="padding:16px">${adCards}</div>`;
}

function closeAssetDetail() {
  document.getElementById('asset-detail-overlay').classList.remove('open');
}
function closeAssetDetailOnOverlay(e) {
  if (e.target === document.getElementById('asset-detail-overlay')) closeAssetDetail();
}

// ==============================
// ---- Software ถือครอง ----
// ==============================

const SW_LICENSE_LABEL = {
  subscription: 'รายปี', perpetual: 'ซื้อขาด', oem: 'ติดมากับเครื่อง', free: 'ฟรี'
};

async function loadSoftwareEmpMap() {
  try {
    const raw = await api('/api/software/employee-map');
    swEmpMap = {};
    Object.entries(raw).forEach(([k, v]) => { swEmpMap[parseInt(k)] = v; });
    refreshSwCells();
    // ถ้ากรอง "มี/ไม่มี Software" อยู่ตอนที่ยอดเพิ่งมาถึง ต้องกรองใหม่ให้ตรง
    if (filters.hasSw || filters.noSw) loadEmployees();
  } catch (e) {}
}

/** โหลดคลังกลาง — ใช้ทั้ง dropdown และหน้าจัดการคลัง */
async function loadSwCatalogData(includeInactive, bu) {
  const p = new URLSearchParams();
  if (includeInactive) p.set('all', '1');
  if (bu) p.set('bu', bu);
  swCatalog = await api('/api/software/catalog' + (p.toString() ? '?' + p : ''));
  return swCatalog;
}

function swCellHtml(empId, empName) {
  const n = swEmpMap[empId] || 0;
  const safeName = esc(empName).replace(/'/g, '&#39;');
  return n
    ? `<span class="sw-badge" onclick="openSoftware(${empId},'${safeName}')" title="ดู/แก้ไข Software ${n} รายการ">🧩 ${n} รายการ</span>`
    : `<button class="sw-add-btn" onclick="openSoftware(${empId},'${safeName}')" title="เพิ่ม Software">+ เพิ่ม</button>`;
}

/** อัปเดตเฉพาะช่อง Software ในตาราง โดยไม่ต้องโหลดพนักงานใหม่ */
function refreshSwCells() {
  document.querySelectorAll('#emp-tbody .sw-cell').forEach(td => {
    td.innerHTML = swCellHtml(parseInt(td.dataset.emp), td.dataset.name);
  });
}

// ---- modal: Software ที่พนักงานถือครอง ----
// การแก้ทุกอย่างเป็นแค่ "ร่าง" อยู่ใน swRows จนกว่าจะกดยืนยัน แล้วส่งทีเดียวผ่าน /software/batch

async function openSoftware(empId, empName) {
  swCurrentEmp = { id: empId, name: empName, inactive: false };
  document.getElementById('sw-subtitle').textContent = empName;
  swSetError('');
  document.getElementById('sw-list').innerHTML =
    '<div style="text-align:center;padding:24px;color:#94a3b8">กำลังโหลด...</div>';
  document.getElementById('software-overlay').classList.add('open');

  if (!swCatalog.length) { try { await loadSwCatalogData(false); } catch (e) {} }
  // คน Inactive ถูกถอน Software คืนคลังแล้ว — เพิ่มใหม่ไม่ได้
  try {
    const emp = await api('/api/employees/' + empId);
    swCurrentEmp.inactive = emp.status !== 'active';
  } catch (e) {}
  await reloadSwRows();
  document.getElementById('sw-select').focus();
}

/** ดึงของจริงจากเซิร์ฟเวอร์มาเป็นจุดตั้งต้นของร่าง */
async function reloadSwRows() {
  const list = await api(`/api/employees/${swCurrentEmp.id}/software`);
  swRows = list.map(s => ({
    key: ++swRowSeq, id: s.id, software_id: s.software_id, name: s.software,
    category: s.category, license_type: s.license_type, is_active: s.is_active,
    note: s.note || '', origNote: s.note || '', isNew: false, removed: false,
    created_at: s.created_at, is_bundle: s.is_bundle, covers: s.covers || [],
  }));
  // ชุดรวมนับเป็น 1 — โปรแกรมที่อยู่ในชุดไม่นับซ้ำ (ให้ตรงกับ /software/employee-map)
  swEmpMap[swCurrentEmp.id] = list.filter(s => !(s.covered_by || []).length).length;
  refreshSwCells();
  renderSwRows();
}

/** ตัวเลือกที่ยังเลือกได้ = ในคลัง − ที่อยู่ในร่างแล้ว (ที่กากบาทลบไว้ กลับมาเลือกได้) */
function fillSwSelect() {
  const sel   = document.getElementById('sw-select');
  const taken = new Set(swRows.filter(r => !r.removed).map(r => r.software_id));
  const avail = swCatalog.filter(c => c.is_active !== 0 && !taken.has(c.id));

  sel.disabled = !!(swCurrentEmp && swCurrentEmp.inactive);
  if (sel.disabled) {
    sel.innerHTML = '<option value="">— พนักงาน Inactive: Software ถูกถอนคืนคลังแล้ว เพิ่มไม่ได้ —</option>';
    return;
  }
  if (!avail.length) {
    sel.innerHTML = swCatalog.length
      ? '<option value="">— เลือกครบทุกรายการในคลังแล้ว —</option>'
      : '<option value="">— คลังยังว่าง กด "จัดการคลัง Software" เพื่อเพิ่ม —</option>';
    return;
  }

  const byCat = {};
  avail.forEach(c => { (byCat[c.category || 'ยังไม่จัดหมวด'] ||= []).push(c); });

  sel.innerHTML = '<option value="">＋ เลือก Software เพื่อเพิ่มเข้ารายการ…</option>' +
    Object.keys(byCat).sort().map(cat => `
      <optgroup label="${esc(cat)}">
        ${byCat[cat].map(c => {
          const lic = SW_LICENSE_LABEL[c.license_type] || '';
          const bun = c.is_bundle ? ` · ชุดรวม ${(c.members || []).length} โปรแกรม` : '';
          return `<option value="${c.id}">${esc(c.name)}${bun}${lic ? ' · ' + lic : ''}</option>`;
        }).join('')}
      </optgroup>`).join('');
}

/** เลือกจาก dropdown = เข้ารายการทันที (ยังไม่บันทึกจนกว่าจะกดยืนยัน) */
function onSwSelectChange() {
  const sel = document.getElementById('sw-select');
  const cid = parseInt(sel.value);
  sel.value = '';
  if (!cid) return;

  const c = swCatalog.find(x => x.id === cid);
  if (!c) return;
  swSetError('');
  swRows.push({
    key: ++swRowSeq, id: null, software_id: c.id, name: c.name,
    category: c.category, license_type: c.license_type, is_active: c.is_active,
    note: '', origNote: '', isNew: true, removed: false, created_at: null,
    is_bundle: c.is_bundle, covers: (c.members || []).map(m => m.name),
  });
  renderSwRows();

  // เลื่อนไปที่แถวที่เพิ่งเพิ่ม แล้วโฟกัสช่องหมายเหตุให้พิมพ์ต่อได้เลย
  const el = document.querySelector(`.sw-item[data-key="${swRowSeq}"]`);
  if (el) {
    el.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
    const inp = el.querySelector('.sw-note-input');
    if (inp) inp.focus();
  }
}

function renderSwRows() {
  fillSwSelect();
  const el = document.getElementById('sw-list');

  if (!swRows.length) {
    el.innerHTML = '<div class="sw-empty">ยังไม่มี Software — เลือกจากช่องด้านบนได้เลย</div>';
    updateSwFooter();
    return;
  }

  // โปรแกรมที่อยู่ในชุดรวมที่คนนี้ถือ → ย้ายไปแสดงเป็นรายการย่อยใต้ชุดรวม
  const bundles  = swRows.filter(r => r.is_bundle && !r.removed);
  const members  = b => {
    const c = swCatalog.find(x => x.id === b.software_id);
    return c ? c.members : [];
  };
  const parentOf = {};
  swRows.forEach(r => {
    if (r.is_bundle) return;
    const b = bundles.find(b => members(b).some(m => m.id === r.software_id));
    if (b) parentOf[r.key] = b.key;
  });
  const childrenOf = b => swRows.filter(r => parentOf[r.key] === b.key);
  // ชุดรวมนับเป็น 1 รายการ — โปรแกรมย่อยข้างในไม่นับซ้ำ
  const active = swRows.filter(r => !r.removed && !parentOf[r.key]).length;

  const rowHtml = (r, child) => {
    const lic  = SW_LICENSE_LABEL[r.license_type] || '';
    const edit = !r.isNew && !r.removed && r.note !== r.origNote;
    const cls  = r.removed ? ' removed' : (r.isNew ? ' staged' : (edit ? ' edited' : ''));
    const tag  = r.removed ? '<span class="sw-tag del">จะลบ</span>'
               : r.isNew   ? '<span class="sw-tag new">เพิ่มใหม่</span>'
               : edit      ? '<span class="sw-tag edit">แก้หมายเหตุ</span>' : '';
    let meta;
    if (r.is_bundle) {
      const used = childrenOf(r).filter(c => !c.removed).length;
      meta = r.removed ? `ชุดรวม ${r.covers.length} โปรแกรม`
                       : `ชุดรวม · ใช้อยู่ ${used} จาก ${r.covers.length} โปรแกรม`;
    } else {
      meta = (r.category ? esc(r.category) : '<span style="color:#cbd5e1">ไม่ระบุหมวด</span>') +
             (lic && !child ? ' · ' + lic : '');
    }
    return `
      <div class="sw-item${cls}${r.is_bundle && !r.removed ? ' sw-bundle-main' : ''}${child ? ' sw-child' : ''}"
           data-key="${r.key}">
        <div class="sw-item-main">
          <div class="sw-item-name">${esc(r.name)} ${tag}
            ${r.is_bundle ? '<span class="sw-bundle-tag">ชุดรวม</span>' : ''}
            ${r.is_active === 0 ? '<span class="sw-off">ปิดใช้งานในคลัง</span>' : ''}
          </div>
          <div class="sw-item-meta">${meta}
            ${r.created_at ? ' · บันทึก ' + _dateFmt(r.created_at.slice(0, 10)) : ''}
          </div>
        </div>
        <input class="sw-note-input" type="text" placeholder="หมายเหตุ (เลข License, เวอร์ชัน)"
               value="${esc(r.note)}" ${r.removed ? 'disabled' : ''}
               oninput="onSwNoteInput(${r.key}, this.value)">
        <button class="icon-btn ${r.removed ? 'undo' : 'del'}" onclick="toggleSwRemove(${r.key})"
                title="${r.removed ? 'ยกเลิกการลบ' : 'เอาออก'}">${r.removed ? '↩' : '🗑️'}</button>
      </div>`;
  };

  const groupHtml = b => {
    const kids  = childrenOf(b);
    const have  = new Set(kids.filter(k => !k.removed).map(k => k.software_id));
    const other = members(b).filter(m => !have.has(m.id)).map(m => m.name);
    return `
      <div class="sw-group">
        ${rowHtml(b, false)}
        <div class="sw-children">
          ${kids.map(k => rowHtml(k, true)).join('')}
          ${!kids.length ? '<div class="sw-child-empty">ยังไม่ได้บันทึกว่าใช้โปรแกรมไหน</div>' : ''}
          ${other.length ? `<div class="sw-covers-more">ใช้ได้อีก: ${other.map(esc).join(', ')}</div>` : ''}
        </div>
      </div>`;
  };

  // ชุดรวมขึ้นก่อน (พร้อมรายการย่อย) แล้วตามด้วยตัวที่ซื้อแยก
  const top = swRows.filter(r => !parentOf[r.key]);
  el.innerHTML = `
    <div class="sw-count">${active} รายการ</div>
    ${top.filter(r => bundles.includes(r)).map(groupHtml).join('')}
    ${top.filter(r => !bundles.includes(r)).map(r => rowHtml(r, false)).join('')}`;
  updateSwFooter();
}

/** พิมพ์หมายเหตุ — อัปเดตร่างโดยไม่ re-render (กันเคอร์เซอร์เด้ง) */
function onSwNoteInput(key, val) {
  const r = swRows.find(x => x.key === key);
  if (!r) return;
  r.note = val;
  const item = document.querySelector(`.sw-item[data-key="${key}"]`);
  if (item && !r.isNew && !r.removed) {
    const changed = r.note !== r.origNote;
    item.classList.toggle('edited', changed);
    // สลับเฉพาะป้าย "แก้หมายเหตุ" — ป้ายอื่น (ชุดรวม ฯลฯ) คงไว้
    const nameEl = item.querySelector('.sw-item-name');
    const old    = nameEl.querySelector('.sw-tag.edit');
    if (changed && !old) {
      nameEl.firstChild.after(Object.assign(document.createElement('span'),
        { className: 'sw-tag edit', textContent: 'แก้หมายเหตุ' }), ' ');
    } else if (!changed && old) {
      old.remove();
    }
  }
  updateSwFooter();
}

function toggleSwRemove(key) {
  const i = swRows.findIndex(x => x.key === key);
  if (i < 0) return;
  const r = swRows[i];
  if (r.isNew) swRows.splice(i, 1);   // ตัวที่ยังไม่บันทึก เอาออกได้เลย
  else         r.removed = !r.removed;
  swSetError('');
  renderSwRows();
}

/** สรุปสิ่งที่จะส่งไปบันทึก */
function swChanges() {
  return {
    add:    swRows.filter(r => r.isNew && !r.removed)
                  .map(r => ({ software_id: r.software_id, note: r.note })),
    update: swRows.filter(r => !r.isNew && !r.removed && r.note !== r.origNote)
                  .map(r => ({ id: r.id, note: r.note })),
    remove: swRows.filter(r => !r.isNew && r.removed).map(r => r.id),
  };
}

function updateSwFooter() {
  const ch    = swChanges();
  const n     = ch.add.length + ch.update.length + ch.remove.length;
  const parts = [];
  if (ch.add.length)    parts.push(`เพิ่ม ${ch.add.length}`);
  if (ch.update.length) parts.push(`แก้หมายเหตุ ${ch.update.length}`);
  if (ch.remove.length) parts.push(`ลบ ${ch.remove.length}`);

  document.getElementById('sw-change-summary').innerHTML = n
    ? `<span class="sw-dirty">● ยังไม่ได้บันทึก</span> ${parts.join(' · ')}`
    : '<span style="color:#94a3b8">บันทึกไว้ครบแล้ว</span>';

  const btn = document.getElementById('sw-confirm-btn');
  btn.disabled    = !n;
  btn.textContent = n ? `ยืนยัน (${n})` : 'ยืนยัน';
  document.getElementById('sw-revert-btn').style.display = n ? '' : 'none';
}

function swSetError(msg) {
  const el = document.getElementById('sw-error');
  el.textContent = msg || '';
  el.style.display = msg ? '' : 'none';
}

async function confirmSoftware() {
  const ch = swChanges();
  if (!ch.add.length && !ch.update.length && !ch.remove.length) return;

  const btn = document.getElementById('sw-confirm-btn');
  btn.disabled = true;
  try {
    const res = await api(`/api/employees/${swCurrentEmp.id}/software/batch`, 'POST', ch);
    const said = [];
    if (res.added)   said.push(`เพิ่ม ${res.added}`);
    if (res.updated) said.push(`แก้ ${res.updated}`);
    if (res.removed) said.push(`ลบ ${res.removed}`);
    showToast('บันทึกแล้ว — ' + said.join(' · '), 'success');
    swSetError('');
    swDash = swVendor = null;   // ตัวเลขในหน้า Dashboard ต้องโหลดใหม่รอบหน้า
    await reloadSwRows();
  } catch (e) {
    swSetError(e.error || 'บันทึกไม่สำเร็จ');
    updateSwFooter();
  }
}

async function revertSwChanges() {
  if (!confirm('ย้อนกลับไปเป็นข้อมูลที่บันทึกไว้ล่าสุด? สิ่งที่แก้ค้างไว้จะหายไป')) return;
  swSetError('');
  await reloadSwRows();
}

/** แก้ชื่อ/หมวดในคลังระหว่างที่ยังมีร่างค้างอยู่ — อัปเดตชื่อในร่างโดยไม่ทิ้งสิ่งที่แก้ไว้ */
function syncSwRowsWithCatalog() {
  if (!swRows.length || !document.getElementById('software-overlay').classList.contains('open')) return;
  swRows.forEach(r => {
    const c = swCatalog.find(x => x.id === r.software_id);
    if (c) {
      r.name = c.name; r.category = c.category;
      r.license_type = c.license_type; r.is_active = c.is_active;
      r.is_bundle = c.is_bundle; r.covers = (c.members || []).map(m => m.name);
    }
  });
  renderSwRows();
}

function closeSoftware() {
  const ch = swChanges();
  const n  = ch.add.length + ch.update.length + ch.remove.length;
  if (n && !confirm(`ยังมี ${n} รายการที่ยังไม่ได้กดยืนยัน ปิดหน้านี้แล้วจะไม่ถูกบันทึก`)) return;
  swRows = [];
  document.getElementById('software-overlay').classList.remove('open');
  refreshSoftwareFilterOptions();   // ยอดในตัวกรอง Software ต้องตรงกับที่เพิ่งแก้
}

/** อัปเดตตัวเลือก/ยอดของ dropdown "Software" ในแถบกรอง */
async function refreshSoftwareFilterOptions() {
  try {
    const p = new URLSearchParams();
    if (filters.bu)   p.set('bu', filters.bu);
    if (filters.dept) p.set('dept', filters.dept);
    const data = await api('/api/filters' + (p.toString() ? '?' + p : ''));
    fillSoftwareSelect(data.softwares);
    // ถ้ากรอง Software ตัวที่ไม่เหลือผู้ถือครองแล้ว ให้ถอยกลับเป็นทั้งหมด
    if (filters.software && !data.softwares.some(s => String(s.id) === String(filters.software))) {
      filters.software = '';
      document.getElementById('filter-software').value = '';
      loadEmployees();
    }
  } catch (e) {}
}

function closeSoftwareOnOverlay(e) {
  if (e.target === document.getElementById('software-overlay')) closeSoftware();
}

// ==============================
// ---- คลัง Software (master data) ----
// ==============================

async function openSwCatalog() {
  swCatEditId = null;
  swcSetError('');
  cancelSwCatalogEdit();
  document.getElementById('swc-search').value = '';
  document.getElementById('swcat-list').innerHTML =
    '<div style="text-align:center;padding:24px;color:#94a3b8">กำลังโหลด...</div>';
  document.getElementById('swcat-overlay').classList.add('open');
  if (!swcBuList.length) {
    try { swcBuList = (await api('/api/filters')).bus || []; } catch (e) {}
  }
  renderSwcBuTabs();
  await loadSwCatalog();
  document.getElementById('swc-name').focus();
}

/** แท็บ BU — ทั้งหมด = ผลรวม (ดูอย่างเดียว), แท็บ BU = กรอกจำนวนซื้อของ BU นั้น */
function renderSwcBuTabs() {
  const tabs = [{ bu_code: '', bu: 'รวมทุก BU' }, ...swcBuList];
  document.getElementById('swc-bu-tabs').innerHTML = tabs.map(b => `
    <button class="swc-bu-tab${swcBu === b.bu_code ? ' active' : ''}"
            onclick="switchSwcBu('${esc(b.bu_code)}')" title="${esc(b.bu || '')}">
      ${b.bu_code ? esc(b.bu_code) : 'รวมทุก BU'}</button>`).join('');
  document.getElementById('swc-bu-note').innerHTML = swcBu
    ? `กำลังดูของ <b>${esc(swcBu)}</b> — จำนวนที่ซื้อ / วันต่ออายุ / ราคา และยอดใช้ เป็นของ ${esc(swcBu)} เท่านั้น`
    : 'ยอดรวมทุก BU — จำนวนที่ซื้อแก้ได้ในแท็บของแต่ละ BU';
  // แท็บรวม: ช่องจำนวนซื้อเป็นผลรวม แก้ตรงไม่ได้
  ['swc-seats', 'swc-renew', 'swc-price'].forEach(id => {
    const el = document.getElementById(id);
    el.disabled = !swcBu;
    el.title = swcBu ? '' : 'เลือกแท็บ BU ก่อน แล้วกรอกจำนวนของ BU นั้น';
  });
}

async function switchSwcBu(bu) {
  if (swcBu === bu) return;
  swcBu = bu;
  cancelSwCatalogEdit();
  renderSwcBuTabs();
  document.getElementById('swcat-list').innerHTML =
    '<div style="text-align:center;padding:24px;color:#94a3b8">กำลังโหลด...</div>';
  await loadSwCatalog(true);
}

async function loadSwCatalog(fromToggle) {
  const showInactive = document.getElementById('swc-show-inactive').checked;
  try {
    await loadSwCatalogData(showInactive, swcBu);
  } catch (e) {
    document.getElementById('swcat-list').innerHTML =
      '<div class="sw-empty">โหลดคลังไม่สำเร็จ</div>';
    return;
  }
  // เติมรายการหมวดที่มีอยู่ให้ช่องกรอกหมวด
  const cats = [...new Set(swCatalog.map(c => c.category).filter(Boolean))].sort();
  document.getElementById('swc-cat-list').innerHTML =
    cats.map(c => `<option value="${esc(c)}">`).join('');
  renderSwCatalog();
  // ถ้าเปิดจากหน้าถือครองอยู่ ให้ dropdown ตามคลังล่าสุด
  if (fromToggle !== true && swCurrentEmp) fillSwSelect();
}

function renderSwCatalog() {
  const q  = document.getElementById('swc-search').value.trim().toLowerCase();
  const el = document.getElementById('swcat-list');
  const rows = swCatalog.filter(c => !q ||
    (c.name || '').toLowerCase().includes(q) ||
    (c.category || '').toLowerCase().includes(q) ||
    (c.vendor || '').toLowerCase().includes(q));

  const nOver  = swCatalog.filter(c => c.over > 0).length;
  const nNoSet = swCatalog.filter(c => c.seats == null && c.used > 0).length;
  document.getElementById('swc-count').innerHTML =
    `${rows.length} รายการ` + (q ? ` (จาก ${swCatalog.length})` : '') +
    (nOver  ? ` · <b style="color:#dc2626">ใช้เกินจำนวนซื้อ ${nOver}</b>` : '') +
    (nNoSet ? ` · <span style="color:#b45309">ยังไม่ระบุจำนวนซื้อ ${nNoSet}</span>` : '');

  if (!rows.length) {
    el.innerHTML = '<div class="sw-empty">ไม่พบรายการ</div>';
    return;
  }

  const byCat = {};
  rows.forEach(c => { (byCat[c.category || 'ยังไม่จัดหมวด'] ||= []).push(c); });

  el.innerHTML = Object.keys(byCat).sort().map(cat => `
    <div class="swcat-group">
      <div class="swcat-group-head">${esc(cat)} <span>${byCat[cat].length}</span></div>
      ${byCat[cat].map(c => `
        <div class="swcat-row${c.is_active === 0 ? ' off' : ''}${c.over > 0 ? ' over' : ''}">
          <div class="swcat-main">
            <div class="swcat-name">${esc(c.name)}
              ${c.is_bundle ? '<span class="sw-bundle-tag">ชุดรวม</span>' : ''}
              ${c.is_active === 0 ? '<span class="sw-off">ปิดใช้งาน</span>' : ''}
            </div>
            <div class="swcat-meta">
              ${c.vendor ? esc(c.vendor) : '<span style="color:#cbd5e1">ไม่ระบุผู้ผลิต</span>'}
              ${c.license_type ? ' · ' + (SW_LICENSE_LABEL[c.license_type] || esc(c.license_type)) : ''}
              ${c.renew_date ? ' · ' + swRenewHtml(c.renew_date) : ''}
              ${c.unit_price != null ? ' · ' + Number(c.unit_price).toLocaleString('th-TH') + ' บาท/license' : ''}
              ${c.note ? ' · ' + esc(c.note) : ''}
            </div>
            ${c.is_bundle && c.members.length ? `<div class="sw-covers">ครอบคลุม ${c.members.length} โปรแกรม:
              ${c.members.map(m => esc(m.name)).join(', ')}</div>` : ''}
            ${c.is_bundle && !c.members.length ? `<div class="sw-covers" style="color:#b45309">
              ยังไม่ได้เลือกโปรแกรมที่ชุดนี้ครอบคลุม — กด ✏️</div>` : ''}
          </div>
          ${swSeatCellHtml(c)}
          <div class="action-btns">
            <button class="icon-btn edit" onclick="startSwCatalogEdit(${c.id})" title="แก้ไข">✏️</button>
            <button class="icon-btn del" onclick="deleteSwCatalog(${c.id})"
                    title="${c.holders ? 'มีผู้ถือครองอยู่ — ลบไม่ได้' : 'ลบ'}">🗑️</button>
          </div>
        </div>`).join('')}
    </div>`).join('');
}

function swcSetError(msg) {
  const el = document.getElementById('swc-error');
  el.textContent = msg || '';
  el.style.display = msg ? '' : 'none';
}

function startSwCatalogEdit(cid) {
  const c = swCatalog.find(x => x.id === cid);
  if (!c) return;
  swCatEditId = cid;
  document.getElementById('swc-name').value     = c.name || '';
  document.getElementById('swc-category').value = c.category || '';
  document.getElementById('swc-vendor').value   = c.vendor || '';
  document.getElementById('swc-license').value  = c.license_type || '';
  document.getElementById('swc-note').value     = c.note || '';
  document.getElementById('swc-active').checked = c.is_active !== 0;
  document.getElementById('swc-seats').value    = c.seats ?? '';
  document.getElementById('swc-renew').value    = c.renew_date || '';
  document.getElementById('swc-price').value    = c.unit_price ?? '';
  document.getElementById('swc-bundle').checked = !!c.is_bundle;
  swcMembers = new Set((c.members || []).map(m => m.id));
  swcMembersAll = false;
  renderSwcMembers();
  document.getElementById('swc-active-wrap').style.display = '';
  document.getElementById('swc-save-btn').textContent = 'บันทึก';
  document.getElementById('swc-cancel-btn').style.display = '';
  swcSetError('');
  document.getElementById('swc-name').focus();
  document.querySelector('#swcat-overlay .modal-body').scrollTop = 0;
}

function cancelSwCatalogEdit() {
  swCatEditId = null;
  ['swc-name', 'swc-category', 'swc-vendor', 'swc-note',
   'swc-seats', 'swc-renew', 'swc-price'].forEach(id => {
    document.getElementById(id).value = '';
  });
  document.getElementById('swc-license').value = '';
  document.getElementById('swc-bundle').checked = false;
  swcMembers = new Set();
  swcMembersAll = false;
  renderSwcMembers();
  document.getElementById('swc-active').checked = true;
  document.getElementById('swc-active-wrap').style.display = 'none';
  document.getElementById('swc-save-btn').textContent = 'เพิ่มเข้าคลัง';
  document.getElementById('swc-cancel-btn').style.display = 'none';
  swcSetError('');
}

async function saveSwCatalog() {
  const body = {
    name:         document.getElementById('swc-name').value.trim(),
    category:     document.getElementById('swc-category').value.trim(),
    vendor:       document.getElementById('swc-vendor').value.trim(),
    license_type: document.getElementById('swc-license').value,
    note:         document.getElementById('swc-note').value.trim(),
    is_active:    document.getElementById('swc-active').checked ? 1 : 0,
    seats:        document.getElementById('swc-seats').value,
    renew_date:   document.getElementById('swc-renew').value,
    unit_price:   document.getElementById('swc-price').value,
    is_bundle:    document.getElementById('swc-bundle').checked ? 1 : 0,
  };
  // เลิกเป็นชุดรวม = ล้างรายการที่ครอบคลุมทิ้งด้วย
  body.members = body.is_bundle ? [...swcMembers] : [];
  // จำนวนซื้อเป็นของแท็บ BU ที่เปิดอยู่ — แท็บรวมไม่ส่ง (ฝั่ง server ไม่แตะ)
  if (swcBu) body.bu = swcBu;
  else { delete body.seats; delete body.renew_date; delete body.unit_price; }
  if (!body.name) { swcSetError('กรุณาระบุชื่อ Software'); return; }
  if (body.seats != null && body.seats !== '' && (!/^\d+$/.test(body.seats))) {
    swcSetError('จำนวนที่ซื้อต้องเป็นจำนวนเต็มตั้งแต่ 0 ขึ้นไป'); return;
  }
  if (body.is_bundle && !body.members.length) {
    swcSetError('ชุดรวมต้องเลือกโปรแกรมที่ครอบคลุมอย่างน้อย 1 ตัว'); return;
  }

  const btn = document.getElementById('swc-save-btn');
  btn.disabled = true;
  try {
    if (swCatEditId) {
      await api(`/api/software/catalog/${swCatEditId}`, 'PUT', body);
      showToast('แก้ไขรายการในคลังแล้ว', 'success');
    } else {
      await api('/api/software/catalog', 'POST', body);
      showToast('เพิ่มเข้าคลังแล้ว', 'success');
    }
    cancelSwCatalogEdit();
    await loadSwCatalog();
    syncSwRowsWithCatalog();
    swDash = swVendor = null;   // ยอดใช้/ชุดรวมเปลี่ยน หน้า dashboard ต้องโหลดใหม่
  } catch (e) {
    swcSetError(e.error || 'บันทึกไม่สำเร็จ');
  } finally {
    btn.disabled = false;
  }
}

async function deleteSwCatalog(cid) {
  const c = swCatalog.find(x => x.id === cid);
  if (!c) return;

  let url = `/api/software/catalog/${cid}`;
  if (c.holders) {
    // มีคนถือครองอยู่ = ลบแล้วข้อมูลของคนเหล่านั้นหายด้วย ต้องพิมพ์ยืนยันจำนวน
    const typed = prompt(
      `⚠️ ลบ "${c.name}" ออกจากคลัง\n\n` +
      `มีพนักงาน ${c.holders} คนถือครองอยู่ — ข้อมูลของทุกคนจะถูกลบไปด้วย และกู้คืนไม่ได้\n` +
      `ถ้าเพียงอยากให้หายจากตัวเลือก ให้กด ✏️ แล้วเอาเครื่องหมาย "เปิดใช้งาน" ออกแทน\n\n` +
      `ยืนยันโดยพิมพ์จำนวน license ที่จะถูกลบ (${c.holders}):`);
    if (typed === null) return;
    if (typed.trim() !== String(c.holders)) {
      swcSetError(`ยกเลิกการลบ — ต้องพิมพ์ ${c.holders} ให้ตรงเพื่อยืนยัน`);
      return;
    }
    url += '?with_assignments=1';
  } else if (!confirm(`ลบ "${c.name}" ออกจากคลัง?`)) {
    return;
  }

  try {
    const res = await api(url, 'DELETE');
    if (swCatEditId === cid) cancelSwCatalogEdit();
    showToast(res.removed_assignments
      ? `ลบ "${res.name}" และ license ${res.removed_assignments} ใบแล้ว`
      : 'ลบออกจากคลังแล้ว', 'success');
    swcSetError('');
    await loadSwCatalog();
    // ยอดทุกที่ที่อ้างถึง software ตัวนี้ต้องรีเฟรช
    swDash = swVendor = null;
    loadSoftwareEmpMap();
    refreshSoftwareFilterOptions();
    if (swCurrentEmp && document.getElementById('software-overlay').classList.contains('open')) {
      await reloadSwRows();
    }
  } catch (e) {
    swcSetError(e.error || 'ลบไม่สำเร็จ');
  }
}

/** ช่องยอด ใช้ / ซื้อ / เหลือ ของแต่ละรายการในคลัง */
function swSeatCellHtml(c) {
  const used = c.used ?? c.holders;
  const via  = c.covered
    ? `<div class="s" title="ถือชุดรวมที่มีโปรแกรมนี้อยู่แล้ว ไม่กิน license ของตัวนี้">+${c.covered} คนใช้ผ่านชุดรวม</div>`
    : '';
  if (c.seats == null) {
    return `<div class="swcat-seats" title="ใช้ = จำนวนคนที่ต้องมี license ของตัวนี้">
      <div class="n">${used || '—'}${used ? ' <small>คนใช้</small>' : ''}</div>
      ${used ? '<div class="s nos">ยังไม่ระบุจำนวนซื้อ</div>' : ''}${via}</div>`;
  }
  const st = c.over > 0 ? `<div class="s over">⚠ ใช้เกิน ${c.over}</div>`
                        : `<div class="s ok">เหลือ ${c.available}</div>`;
  // แท็บรวม: บอกว่ายอดซื้อมาจาก BU ไหนบ้าง
  const parts = !swcBu && c.seats_by_bu && Object.keys(c.seats_by_bu).length > 1
    ? `<div class="s">${Object.entries(c.seats_by_bu).map(([b, n]) => `${esc(b)} ${n}`).join(' · ')}</div>` : '';
  return `<div class="swcat-seats" title="ใช้ / ซื้อ">
    <div class="n">${used} <small>/ ${c.seats} ซื้อ</small></div>${st}${parts}${via}</div>`;
}

/** วันต่ออายุ — แดงถ้าเลยแล้ว ส้มถ้าเหลือไม่ถึง 60 วัน */
function swRenewHtml(d) {
  const days = Math.round((new Date(d) - new Date(new Date().toDateString())) / 86400000);
  const txt  = 'ต่ออายุ ' + _dateFmt(d);
  if (days < 0)  return `<span style="color:#dc2626;font-weight:600">${txt} (เลยมา ${-days} วัน)</span>`;
  if (days < 60) return `<span style="color:#b45309;font-weight:600">${txt} (อีก ${days} วัน)</span>`;
  return txt;
}

/** ตัวเลือกโปรแกรมที่ชุดรวมครอบคลุม — ตั้งต้นแสดงเฉพาะผู้ผลิตเดียวกัน */
function renderSwcMembers() {
  const on   = document.getElementById('swc-bundle').checked;
  const wrap = document.getElementById('swc-members-wrap');
  wrap.style.display = on ? '' : 'none';
  if (!on) return;

  const vendor = document.getElementById('swc-vendor').value.trim().toLowerCase();
  const cand   = swCatalog.filter(c => !c.is_bundle && c.id !== swCatEditId);
  const same   = c => vendor && (c.vendor || '').toLowerCase() === vendor;
  const shown  = (swcMembersAll || !vendor) ? cand
               : cand.filter(c => same(c) || swcMembers.has(c.id));
  shown.sort((a, b) => (same(b) - same(a)) || a.name.localeCompare(b.name));

  const hidden = cand.length - shown.length;
  document.getElementById('swc-members-count').textContent = `(เลือก ${swcMembers.size})`;
  document.getElementById('swc-members').innerHTML = shown.map(c => `
      <label class="swc-chip${swcMembers.has(c.id) ? ' on' : ''}">
        <input type="checkbox" data-id="${c.id}" ${swcMembers.has(c.id) ? 'checked' : ''}
               onchange="toggleSwcMember(${c.id}, this.checked)">${esc(c.name)}
      </label>`).join('') +
    (shown.length ? `<a href="#" class="swc-chip swc-chip-other"
        onclick="swcSelectAllShown(event)">เลือกทั้งหมดที่แสดง</a>` : '') +
    (hidden ? `<a href="#" class="swc-chip swc-chip-other"
        onclick="swcMembersAll=true;renderSwcMembers();return false">
        + แสดงผู้ผลิตอื่นอีก ${hidden} รายการ</a>` : '') +
    (!shown.length ? '<span style="font-size:.74rem;color:#94a3b8">ไม่มีโปรแกรมให้เลือก</span>' : '');
}

function toggleSwcMember(id, on) {
  if (on) swcMembers.add(id); else swcMembers.delete(id);
  renderSwcMembers();
}

function swcSelectAllShown(e) {
  e.preventDefault();
  document.querySelectorAll('#swc-members input[data-id]').forEach(cb => {
    swcMembers.add(parseInt(cb.dataset.id));
  });
  renderSwcMembers();
}

function closeSwCatalog() {
  document.getElementById('swcat-overlay').classList.remove('open');
}
function closeSwCatalogOnOverlay(e) {
  if (e.target === document.getElementById('swcat-overlay')) closeSwCatalog();
}

// ==============================
// ---- Inline Asset Transfer ----
// ==============================

async function onStatusChange() {
  const empId  = document.getElementById('emp-id').value;
  const status = document.getElementById('f-status').value;
  const section = document.getElementById('asset-transfer-section');

  if (status !== 'inactive' || !empId) {
    section.style.display = 'none';
    transferAssets = [];
    return;
  }

  section.style.display = '';
  document.getElementById('asset-transfer-loading').style.display = '';
  document.getElementById('asset-transfer-body').innerHTML =
    '<div id="asset-transfer-loading" style="text-align:center;padding:20px;color:#94a3b8;font-size:.82rem">กำลังตรวจสอบ...</div>';

  // preload employee cache for search
  if (!empSearchCache.length) {
    const d = await api('/api/employees?per_page=9999&status=active');
    empSearchCache = d.employees;
  }

  const assets = await api(`/api/employees/${empId}/assets`);

  if (!assets.length) {
    transferAssets = [];
    document.getElementById('asset-transfer-body').innerHTML = `
      <div class="tr-no-asset" style="margin:4px 0">
        ✓ ไม่มีทรัพย์สิน IT ที่ถือครองอยู่
      </div>`;
    return;
  }

  transferAssets = assets.map(a => ({
    asset_no: a.asset_no, model: a.model, serial_no: a.serial_no,
    asset_type: a.asset_type, to_type: 'stock', to_employee_id: null, to_name: ''
  }));
  renderInlineTransfer();
}

function renderInlineTransfer() {
  const empDatalist = empSearchCache.map(e =>
    `<option value="${esc(e.name)}" data-id="${e.id}">`).join('');

  document.getElementById('asset-transfer-body').innerHTML = `
    <datalist id="inline-emp-list">${empDatalist}</datalist>
    <div style="display:flex;gap:6px;flex-wrap:wrap;margin-bottom:10px;align-items:center">
      <span style="font-size:.75rem;color:#64748b">Apply ทั้งหมด:</span>
      <button type="button" class="btn btn-secondary" style="font-size:.75rem;padding:3px 9px" onclick="inlineApplyAll('stock')">📦 สต๊อก IT</button>
      <button type="button" class="btn btn-secondary" style="font-size:.75rem;padding:3px 9px" onclick="inlineApplyAll('employee')">👤 โอนให้:</button>
      <input id="inline-bulk-emp" type="text" placeholder="ชื่อพนักงาน..." list="inline-emp-list"
        style="padding:3px 8px;border:1px solid #cbd5e1;border-radius:6px;font-size:.75rem;width:160px">
    </div>
    ${transferAssets.map((t, i) => `
      <div class="tr-inline-row">
        <div class="tr-inline-info">
          <span class="tr-asset-type">${esc(t.asset_type)}</span>
          <span class="tr-asset-model">${esc(t.model)}</span>
          <span class="tr-asset-sn">${esc(t.serial_no)}</span>
        </div>
        <div class="tr-inline-controls">
          <div class="tr-radio-group">
            <button type="button" class="tr-radio-btn ${t.to_type==='stock'?'selected':''}"
              onclick="inlineSetType(${i},'stock')">📦 สต๊อก IT</button>
            <button type="button" class="tr-radio-btn ${t.to_type==='employee'?'selected':''}"
              onclick="inlineSetType(${i},'employee')">👤 โอนให้พนักงาน</button>
          </div>
          ${t.to_type==='employee' ? `
            <input class="tr-emp-search" type="text" placeholder="ชื่อพนักงาน..."
              value="${esc(t.to_name)}" list="inline-emp-list"
              oninput="inlineSetEmp(${i},this.value)">
          ` : `<span style="font-size:.75rem;color:#94a3b8">→ IT Stock</span>`}
        </div>
      </div>
    `).join('')}
  `;
}

function inlineSetType(idx, type) {
  transferAssets[idx].to_type = type;
  if (type === 'stock') { transferAssets[idx].to_employee_id = null; transferAssets[idx].to_name = ''; }
  renderInlineTransfer();
}
function inlineSetEmp(idx, name) {
  transferAssets[idx].to_name = name;
  const emp = empSearchCache.find(e => e.name.trim() === name.trim());
  transferAssets[idx].to_employee_id = emp ? emp.id : null;
}
function inlineApplyAll(type) {
  if (type === 'employee') {
    const name = document.getElementById('inline-bulk-emp').value.trim();
    const emp  = empSearchCache.find(e => e.name.trim() === name);
    if (!name) { showToast('กรุณาพิมพ์ชื่อพนักงาน', 'error'); return; }
    if (!emp)  { showToast(`ไม่พบ "${name}"`, 'error'); return; }
    transferAssets.forEach(t => { t.to_type = 'employee'; t.to_employee_id = emp.id; t.to_name = emp.name; });
  } else {
    transferAssets.forEach(t => { t.to_type = 'stock'; t.to_employee_id = null; t.to_name = ''; });
  }
  renderInlineTransfer();
}

// ==============================
// ---- Transfer Assets (legacy modal kept for compatibility) ----
// ==============================

async function checkAndOpenTransfer(empId, empName) {
  const assets = await api(`/api/employees/${empId}/assets`);
  if (!assets.length) return;
  openTransferModal(empId, empName, assets);
}

async function openTransferModal(empId, empName, assets) {
  transferFromEmpId = empId;
  transferAssets = assets.map(a => ({
    asset_no:       a.asset_no,
    model:          a.model,
    serial_no:      a.serial_no,
    asset_type:     a.asset_type,
    to_type:        'stock',
    to_employee_id: null,
    to_name:        '',
    note:           ''
  }));

  document.getElementById('tr-subtitle').textContent =
    `${empName} มี ${assets.length} เครื่องที่ต้องโอน`;
  document.getElementById('tr-count').textContent =
    `${assets.length} รายการ`;

  // preload employee list for search if not cached
  if (!empSearchCache.length) {
    const d = await api('/api/employees?per_page=9999&status=active');
    empSearchCache = d.employees;
    const dl = document.getElementById('tr-emp-list');
    empSearchCache.forEach(e => {
      dl.insertAdjacentHTML('beforeend', `<option value="${esc(e.name)}" data-id="${e.id}">`);
    });
  }

  renderTransferRows();
  document.getElementById('transfer-overlay').classList.add('open');
}

function renderTransferRows() {
  const container = document.getElementById('tr-asset-list');
  container.innerHTML = transferAssets.map((t, i) => `
    <div class="tr-asset-row">
      <div class="tr-asset-info">
        <span class="tr-asset-type">${esc(t.asset_type)}</span>
        <span class="tr-asset-model">${esc(t.model)}</span>
        <span class="tr-asset-sn">${esc(t.serial_no)}</span>
      </div>
      <div class="tr-options">
        <div class="tr-radio-group">
          <button class="tr-radio-btn ${t.to_type === 'stock' ? 'selected' : ''}"
            onclick="setToType(${i},'stock')">📦 สต๊อก IT</button>
          <button class="tr-radio-btn ${t.to_type === 'employee' ? 'selected' : ''}"
            onclick="setToType(${i},'employee')">👤 โอนให้พนักงาน</button>
        </div>
        ${t.to_type === 'employee' ? `
          <input class="tr-emp-search" type="text" placeholder="พิมพ์ชื่อพนักงาน..."
            value="${esc(t.to_name)}" list="tr-emp-list"
            oninput="setToEmployee(${i}, this.value)"
            data-idx="${i}">
        ` : `<span style="font-size:.78rem;color:#94a3b8">จะย้ายเข้า IT Stock</span>`}
      </div>
    </div>
  `).join('');
}

function setToType(idx, type) {
  transferAssets[idx].to_type = type;
  if (type === 'stock') {
    transferAssets[idx].to_employee_id = null;
    transferAssets[idx].to_name = '';
  }
  renderTransferRows();
}

function setToEmployee(idx, name) {
  transferAssets[idx].to_name = name;
  // find employee id from cache
  const emp = empSearchCache.find(e => e.name.trim() === name.trim());
  transferAssets[idx].to_employee_id = emp ? emp.id : null;
}

function applyAllStock() {
  transferAssets.forEach(t => { t.to_type = 'stock'; t.to_employee_id = null; t.to_name = ''; });
  renderTransferRows();
}

function applyAllEmployee() {
  const name = document.getElementById('tr-bulk-emp').value.trim();
  const emp  = empSearchCache.find(e => e.name.trim() === name);
  if (!name) { showToast('กรุณาพิมพ์ชื่อพนักงาน', 'error'); return; }
  if (!emp)  { showToast(`ไม่พบพนักงาน "${name}"`, 'error'); return; }
  transferAssets.forEach(t => { t.to_type = 'employee'; t.to_employee_id = emp.id; t.to_name = emp.name; });
  renderTransferRows();
}

async function confirmTransfer() {
  // validate: employee-type rows must have an employee selected
  const invalid = transferAssets.filter(t => t.to_type === 'employee' && !t.to_employee_id);
  if (invalid.length) {
    showToast(`กรุณาเลือกพนักงานให้ครบ (${invalid.length} รายการ)`, 'error');
    return;
  }

  const transfers = transferAssets.map(t => ({
    asset_no:       t.asset_no,
    to_type:        t.to_type,
    to_employee_id: t.to_employee_id,
    note:           t.note
  }));

  try {
    const r = await api('/api/assets/transfer-bulk', 'POST', {
      from_employee_id: transferFromEmpId,
      transfers
    });
    showToast(`โอนเรียบร้อย ${r.transferred} รายการ`, 'success');
    closeTransferModal();
    if (assetLoaded) loadAssets(true);
  } catch(e) {
    showToast('โอนไม่สำเร็จ', 'error');
  }
}

function closeTransferModal() {
  document.getElementById('transfer-overlay').classList.remove('open');
  transferAssets = [];
  transferFromEmpId = null;
}

function renderResolution(a, resLabel, resClass) {
  const isExpired = a.contract_status === 'expired';
  const res = a.resolution || 'pending';
  const label = resLabel[res] || res;
  const cls   = resClass[res] || 'res-pending';
  const assetJson = esc(JSON.stringify({ asset_no: a.asset_no, model: a.model, user_name: a.user_name, end_date: a.end_date, resolution: res, note: a.resolution_note || '' }));

  if (!isExpired) return '<span style="color:#cbd5e1;font-size:.75rem">—</span>';
  return `<div style="display:flex;align-items:center;gap:4px">
    <span class="resolution-badge ${cls}">${label}</span>
    <button class="edit-res-btn" onclick='openResolutionModal(${assetJson})' title="แก้ไข">✏️</button>
  </div>`;
}

function openResolutionModal(a) {
  document.getElementById('r-asset-no').value    = a.asset_no;
  document.getElementById('r-resolution').value  = a.resolution || 'pending';
  document.getElementById('r-note').value        = a.note || '';
  const endFmt = a.end_date
    ? new Date(a.end_date).toLocaleDateString('th-TH', {day:'numeric', month:'short', year:'2-digit'})
    : '—';
  document.getElementById('r-asset-info').innerHTML =
    `<strong>${esc(a.model)}</strong> &nbsp;|&nbsp; S/N: ${esc(a.asset_no)}`+
    (a.user_name ? ` &nbsp;|&nbsp; ผู้ถือ: <strong>${esc(a.user_name)}</strong>` : '')+
    `<br><span style="color:#dc2626">หมดสัญญา: ${endFmt}</span>`;
  document.getElementById('resolution-overlay').classList.add('open');
}

function closeResolutionModal() {
  document.getElementById('resolution-overlay').classList.remove('open');
}

function closeResolutionOnOverlay(e) {
  if (e.target === document.getElementById('resolution-overlay')) closeResolutionModal();
}

async function saveResolution() {
  const asset_no   = document.getElementById('r-asset-no').value;
  const resolution = document.getElementById('r-resolution').value;
  const note       = document.getElementById('r-note').value.trim();
  try {
    await api(`/api/assets/${encodeURIComponent(asset_no)}/resolution`, 'PUT', { resolution, note });
    showToast('บันทึกสถานะเรียบร้อย', 'success');
    closeResolutionModal();
    loadAssets(true);
  } catch(e) {
    showToast('บันทึกไม่สำเร็จ', 'error');
  }
}

function resetAssetFilters() {
  // ล้าง dropdowns
  ['a-search','a-filter-bu','a-filter-type','a-filter-ownership','a-filter-machine',
   'a-filter-status','a-filter-ed-status','a-filter-position','a-filter-dept'
  ].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.value = '';
  });
  // ล้าง checkboxes
  ['a-filter-resigned','a-filter-no-owner','a-filter-central','a-filter-missing-edevice'].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.checked = false;
  });
  // reset state
  assetFilters = { q: '', type: '', bu: '', status: '', ownership: '', machine_type: '', position: '', dept: '' };
  loadAssets();
}

function filterAssetStatus(status, ownership) {
  document.getElementById('a-filter-status').value = status;
  assetFilters.status = status;
  if (ownership !== undefined) {
    document.getElementById('a-filter-ownership').value = ownership;
    assetFilters.ownership = ownership;
  }
  loadAssets();
  document.getElementById('tab-assets').scrollIntoView({ behavior: 'smooth' });
}

function filterAssetEdExpire() {
  // filter เครื่องเช่าที่ eDevice = Expire
  const edEl = document.getElementById('a-filter-ed-status');
  if (edEl) edEl.value = 'expire';
  document.getElementById('a-filter-ownership').value = 'เช่า';
  assetFilters.ownership = 'เช่า';
  loadAssets();
  document.getElementById('tab-assets').scrollIntoView({ behavior: 'smooth' });
}

// ออกรายงาน PDF ตาม filter ปัจจุบันทั้งหมด — รวม filter ฝั่ง client (checkbox/eDevice status)
// เพื่อให้ตัวเลขในรายงานตรงกับที่เห็นบนหน้าจอ
function exportAssetReport(btn) {
  const params = new URLSearchParams({
    q:            assetFilters.q,
    type:         assetFilters.type,
    bu:           assetFilters.bu,
    status:       assetFilters.status,
    ownership:    assetFilters.ownership,
    machine_type: assetFilters.machine_type,
    position:     assetFilters.position,
    dept:         assetFilters.dept,
    ed_status:    document.getElementById('a-filter-ed-status')?.value || '',
  });
  [['a-filter-resigned',        'only_resigned'],
   ['a-filter-no-owner',        'only_no_owner'],
   ['a-filter-central',         'only_central'],
   ['a-filter-missing-edevice', 'only_missing_edevice']
  ].forEach(([id, key]) => {
    if (document.getElementById(id)?.checked) params.set(key, '1');
  });

  // รายงานใช้เวลาสร้างสักครู่ — บอกสถานะบนปุ่มไว้ก่อน
  if (btn) {
    const orig = btn.innerHTML;
    btn.innerHTML = '<span style="font-size:.75rem">⏳ กำลังสร้าง...</span>';
    setTimeout(() => { btn.innerHTML = orig; }, 4000);
  }
  window.location = '/api/assets/report.pdf?' + params;
}

function exportAssets() {
  const params = new URLSearchParams({
    status:   assetFilters.status,
    type:     assetFilters.type,
    bu:       assetFilters.bu,
  });
  window.location = '/api/assets/export?' + params;
}

// ==============================
// ---- Intranet Sync ----
// ==============================

let syncData = null;
let syncCurrentTab = 'inactive';

async function openSyncModal() {
  syncData = null;
  document.getElementById('sync-loading').style.display = '';
  document.getElementById('sync-result').style.display = 'none';
  document.getElementById('sync-footer').style.display = 'none';
  document.getElementById('sync-subtitle').textContent = 'กำลังดึงข้อมูลจาก Intranet...';
  document.getElementById('sync-overlay').classList.add('open');

  try {
    syncData = await api('/api/sync/preview');
    document.getElementById('sync-loading').style.display = 'none';
    document.getElementById('sync-result').style.display = '';
    document.getElementById('sync-footer').style.display = 'flex';

    const structural = (syncData.to_update || []).filter(e => e.has_structural);
    const enrich     = (syncData.to_update || []).filter(e => !e.has_structural);

    document.getElementById('sync-intranet-total').textContent = syncData.intranet_total.toLocaleString();
    document.getElementById('sync-db-total').textContent       = syncData.db_total.toLocaleString();
    document.getElementById('sync-inactive-count').textContent = syncData.to_inactive.length.toLocaleString();
    document.getElementById('sync-add-count').textContent      = syncData.to_add.length.toLocaleString();
    document.getElementById('sync-update-count').textContent   = (syncData.to_update || []).length.toLocaleString();

    const setBadge = (id, count, activeBg, activeColor) => {
      const el = document.getElementById(id);
      el.textContent = count;
      el.style.background = count ? activeBg : '#f1f5f9';
      el.style.color      = count ? activeColor : '#64748b';
    };
    setBadge('sync-inactive-badge',   syncData.to_inactive.length,  '#fef9c3', '#854d0e');
    setBadge('sync-add-badge',        syncData.to_add.length,        '#dcfce7', '#15803d');
    setBadge('sync-structural-badge', structural.length,             '#dbeafe', '#1d4ed8');
    setBadge('sync-enrich-badge',     enrich.length,                 '#f3e8ff', '#7e22ce');

    document.getElementById('sync-subtitle').textContent =
      `Intranet: ${syncData.intranet_total} คน · ระบบ: ${syncData.db_total} คน`;
    document.getElementById('sync-note').textContent =
      `Inactive ${syncData.to_inactive.length} · เพิ่ม ${syncData.to_add.length} · ย้าย ${structural.length} · Email/เบอร์ ${enrich.length} คน`;

    showSyncTab(structural.length ? 'update' : 'inactive');
  } catch(e) {
    const msg = (e && e.error) ? e.error : (e && e.message) ? e.message : 'เชื่อมต่อ Intranet ไม่ได้';
    document.getElementById('sync-loading').innerHTML =
      `<div style="text-align:center;padding:30px 20px;color:#dc2626">
        <div style="font-size:1.5rem;margin-bottom:8px">❌</div>
        <div style="font-weight:700;margin-bottom:6px">เชื่อมต่อ Intranet ไม่สำเร็จ</div>
        <div style="font-size:.8rem;color:#64748b;white-space:pre-wrap;text-align:left;background:#fff7f7;border:1px solid #fecaca;border-radius:6px;padding:10px 14px;margin-top:8px">${esc(msg)}</div>
      </div>`;
  }
}

function showSyncTab(tab) {
  syncCurrentTab = tab;
  ['inactive','add','update','enrich'].forEach(t => {
    document.getElementById(`sync-tab-${t}`)?.classList.toggle('active', t === tab);
  });

  const list = document.getElementById('sync-list');
  if (!syncData) return;

  const structural = (syncData.to_update || []).filter(e => e.has_structural);
  const enrich     = (syncData.to_update || []).filter(e => !e.has_structural);

  const empty = msg => `<div style="text-align:center;padding:24px;color:#16a34a;font-size:.85rem">✓ ${msg}</div>`;

  if (tab === 'inactive') {
    if (!syncData.to_inactive.length) { list.innerHTML = empty('ไม่มีพนักงานที่ต้อง Inactive'); return; }
    list.innerHTML = syncData.to_inactive.map(e => `
      <div class="sync-row">
        <div style="flex:1;min-width:0">
          <strong>${esc(e.name)}</strong>
          <span style="font-size:.75rem;color:#94a3b8;margin-left:6px">${esc(e.bu_code)} · ${esc(e.department)}</span>
        </div>
        ${e.asset_count ? `<span class="sync-asset-warn">💻 ${e.asset_count} เครื่อง</span>` : ''}
        <span style="font-size:.75rem;color:#ea580c;font-weight:600">→ Inactive</span>
      </div>`).join('');

  } else if (tab === 'add') {
    if (!syncData.to_add.length) { list.innerHTML = empty('ไม่มีพนักงานใหม่ที่ต้องเพิ่ม'); return; }
    list.innerHTML = syncData.to_add.map(e => `
      <div class="sync-row">
        <div style="flex:1;min-width:0">
          <strong>${esc(e.name)}</strong>
          ${e.nickname ? `<span style="font-size:.75rem;color:#94a3b8"> (${esc(e.nickname)})</span>` : ''}
          <span style="font-size:.75rem;color:#94a3b8;margin-left:6px">${esc(e.bu_code)} · ${esc(e.department)}</span>
        </div>
        ${e.email ? `<span style="font-size:.75rem;color:#2563eb">${esc(e.email)}</span>` : ''}
        <span style="font-size:.75rem;color:#16a34a;font-weight:600">+ เพิ่มใหม่</span>
      </div>`).join('');

  } else if (tab === 'update') {
    if (!structural.length) { list.innerHTML = empty('ไม่มีการย้าย BU/แผนก/ตำแหน่ง'); return; }
    list.innerHTML = structural.map(e => `
      <div class="sync-row" style="flex-direction:column;align-items:flex-start;gap:6px">
        <div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap">
          <strong>${esc(e.name)}</strong>
          <span style="font-size:.75rem;color:#94a3b8">${esc(e.bu_code)} · ${esc(e.department)}</span>
        </div>
        <div style="display:flex;flex-direction:column;gap:3px;padding-left:8px;border-left:3px solid #dbeafe">
          ${e.structural_changes.map(c => `
            <div style="font-size:.78rem;display:flex;align-items:center;gap:6px;flex-wrap:wrap">
              <span style="color:#64748b;min-width:70px">${esc(c.label)}:</span>
              <span style="background:#fee2e2;color:#dc2626;padding:1px 7px;border-radius:5px;text-decoration:line-through">${esc(c.old) || '—'}</span>
              <span style="color:#94a3b8">→</span>
              <span style="background:#dcfce7;color:#16a34a;padding:1px 7px;border-radius:5px">${esc(c.new)}</span>
            </div>`).join('')}
        </div>
      </div>`).join('');

  } else if (tab === 'enrich') {
    if (!enrich.length) { list.innerHTML = empty('ไม่มีข้อมูล Email/เบอร์ที่ต้องอัพเดท'); return; }
    list.innerHTML = enrich.map(e => `
      <div class="sync-row">
        <div style="flex:1;min-width:0">
          <strong>${esc(e.name)}</strong>
          <span style="font-size:.75rem;color:#94a3b8;margin-left:6px">${esc(e.bu_code)}</span>
        </div>
        <div style="display:flex;gap:10px;font-size:.75rem;flex-wrap:wrap">
          ${e.changes.map(c =>
            `<span style="color:#7e22ce">${esc(c.label)}: <strong>${esc(c.new)}</strong></span>`
          ).join('')}
        </div>
      </div>`).join('');
  }
}

async function applySyncConfirm() {
  const btn = document.getElementById('sync-confirm-btn');
  btn.disabled = true;
  btn.textContent = 'กำลัง Sync...';
  try {
    const r = await api('/api/sync/apply', 'POST');
    showToast(`Sync เสร็จสิ้น · Inactive ${r.inactivated} · เพิ่ม ${r.added} · อัพเดท ${r.updated} คน` +
              (r.software_released ? ` · ถอน Software คืนคลัง ${r.software_released} รายการ` : ''), 'success');
    if (r.software_released) {
      swDash = swVendor = null;
      loadSoftwareEmpMap();
    }
    closeSyncModal();
    loadEmployees();
    loadStats();
    api('/api/assets/employee-map?status=active').then(m => {
      Object.entries(m).forEach(([k, v]) => { assetEmpMap[parseInt(k)] = v; });
    });
  } catch(e) {
    showToast('Sync ไม่สำเร็จ', 'error');
  } finally {
    btn.disabled = false;
    btn.textContent = '✓ ยืนยัน Sync';
  }
}

function closeSyncModal() {
  document.getElementById('sync-overlay').classList.remove('open');
}
function closeSyncOnOverlay(e) {
  if (e.target === document.getElementById('sync-overlay')) closeSyncModal();
}

// ==============================
// ---- Rental Dashboard ----
// ==============================

async function loadRentalDashboard() {
  let d;
  try { d = await api('/api/dashboard/rental'); }
  catch(e) { return; }

  // summary cards
  document.getElementById('r-total').textContent   = d.total_rental.toLocaleString();
  document.getElementById('r-monthly').textContent = '฿' + (d.total_monthly||0).toLocaleString('th', {maximumFractionDigits:0});
  const sc = d.by_status || {};
  document.getElementById('r-expired').textContent   = (sc.expired   || 0).toLocaleString();
  document.getElementById('r-ed-expire').textContent = (sc.ed_expire || 0).toLocaleString();
  document.getElementById('r-critical').textContent = (sc.critical || 0).toLocaleString();
  document.getElementById('r-warning').textContent  = (sc.warning  || 0).toLocaleString();
  document.getElementById('r-ok').textContent       = (sc.ok       || 0).toLocaleString();
  document.getElementById('r-unknown').textContent  = (sc.unknown  || 0).toLocaleString();

  // helper: ย่อตัวเลขเงิน เช่น 461999 → "462K"
  const shortMoney = v => v >= 1000 ? `฿${Math.round(v/1000)}K` : v ? `฿${Math.round(v)}` : '—';

  // BU bars — แสดง BU เป็นตารางขนาดกะทัดรัด (BU มีแค่ 4 แถว ทำ table ดีกว่า bar)
  document.getElementById('r-bu-bars').innerHTML = `
    <table style="width:100%;border-collapse:collapse;font-size:.82rem">
      <thead><tr style="border-bottom:2px solid #f1f5f9;color:#94a3b8;font-size:.72rem;font-weight:600">
        <th style="padding:4px 8px;text-align:left">BU</th>
        <th style="padding:4px 8px;text-align:right">เครื่อง</th>
        <th style="padding:4px 8px;text-align:right">฿/เดือน</th>
        <th style="padding:4px 8px;text-align:left;min-width:100px">สัดส่วน</th>
      </tr></thead>
      <tbody>
        ${d.by_bu.map(b => {
          const buLabel = b.bu_code === '—' ? 'ไม่ระบุ BU' : b.bu_code;
          const pct = (b.count / d.total_rental * 100).toFixed(0);
          const monthly = b.monthly ? Math.round(b.monthly).toLocaleString() : '—';
          return `<tr style="border-bottom:1px solid #f8fafc">
            <td style="padding:6px 8px;font-weight:600;color:#374151">${esc(buLabel)}</td>
            <td style="padding:6px 8px;text-align:right;font-weight:700">${b.count}</td>
            <td style="padding:6px 8px;text-align:right;color:#64748b;font-size:.78rem">฿${monthly}</td>
            <td style="padding:6px 8px">
              <div style="display:flex;align-items:center;gap:6px">
                <div style="flex:1;height:8px;background:#f1f5f9;border-radius:4px;overflow:hidden">
                  <div style="width:${pct}%;height:100%;background:linear-gradient(90deg,#f97316,#fb923c);border-radius:4px"></div>
                </div>
                <span style="font-size:.7rem;color:#94a3b8;min-width:28px">${pct}%</span>
              </div>
            </td>
          </tr>`;
        }).join('')}
      </tbody>
    </table>`;

  // Dept bars
  const maxDept = Math.max(...d.by_dept.map(b => b.count), 1);
  document.getElementById('r-dept-bars').innerHTML = d.by_dept.map(b => {
    const deptLabel = b.dept === '—' ? 'ไม่ระบุแผนก' : b.dept;
    return `<div class="bar-row" style="margin-bottom:5px">
      <div class="bar-label" title="${esc(deptLabel)}" style="width:200px;min-width:200px;max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;text-align:right">${esc(deptLabel)}</div>
      <div class="bar-track" style="flex:1"><div class="bar-fill orange" style="width:${(b.count/maxDept*100).toFixed(1)}%"></div></div>
      <div class="bar-count" style="min-width:24px">${b.count}</div>
    </div>`;
  }).join('');

  // ── helper: สร้าง mini timeline chart จาก list of {month, count} ──
  const BU_COLOR = {
    'AOMNI':'#6366f1','AMTV':'#0ea5e9','APRINT':'#10b981',
    'APUB':'#f59e0b','ABOOK':'#ec4899','ACS':'#8b5cf6',
    'AME':'#f97316','—':'#94a3b8',
  };
  // ── expand panel สำหรับ timeline bar click ──
  let _tlExpandKey = null;  // track ว่า panel ไหนเปิดอยู่

  const renderTimelineExpand = (key, bu, rentalIndex) => {
    const rows = rentalIndex[key] || [];
    if (!rows.length) return '';
    const csColor = { expired:'#dc2626', critical:'#f97316', warning:'#eab308', ok:'#16a34a', unknown:'#94a3b8' };
    const csLabel = { expired:'เกินกำหนด', critical:'ใกล้หมด', warning:'เฝ้าระวัง', ok:'ปกติ', unknown:'ไม่ระบุ' };
    const rowsHtml = rows.map(r => {
      const d = r.days_remaining;
      const dStr = d === null ? '—' : d < 0 ? `เกิน ${Math.abs(d)} วัน` : `เหลือ ${d} วัน`;
      const endFmt = r.end_date ? new Date(r.end_date).toLocaleDateString('th-TH',{day:'numeric',month:'short',year:'2-digit'}) : '—';
      return `<tr style="border-bottom:1px solid #f1f5f9;font-size:.78rem">
        <td style="padding:5px 8px"><code style="font-size:.72rem;color:#334155">${esc(r.computer_id)||'—'}</code></td>
        <td style="padding:5px 8px">${esc(r.asset_type)} ${esc(r.model)}</td>
        <td style="padding:5px 8px">${r.is_central ? '<span class="badge-central">🏢 ส่วนกลาง</span>' : `<strong>${esc(r.user_name)||'—'}</strong>${r.user_name && !r.employee_id ? ' <span style="font-size:.65rem;color:#ef4444">(ไม่พบใน HR)</span>' : ''}`}</td>
        <td style="padding:5px 8px;color:#64748b;font-size:.75rem">${esc(r.emp_dept)||'—'}</td>
        <td style="padding:5px 8px;white-space:nowrap">${endFmt}</td>
        <td style="padding:5px 8px;white-space:nowrap;color:${csColor[r.contract_status]||'#64748b'};font-weight:600;font-size:.75rem">${dStr}</td>
        <td style="padding:5px 8px;text-align:right;color:#374151">฿${(r.monthly_charge||0).toLocaleString()}</td>
      </tr>`;
    }).join('');
    return `<div style="margin-top:8px;border:1px solid #e2e8f0;border-radius:8px;overflow:hidden;background:#fff">
      <table style="width:100%;border-collapse:collapse">
        <thead><tr style="background:#f8fafc;font-size:.72rem;color:#64748b">
          <th style="padding:6px 8px;text-align:left">รหัสเครื่อง</th>
          <th style="padding:6px 8px;text-align:left">ประเภท/รุ่น</th>
          <th style="padding:6px 8px;text-align:left">ผู้ถือครอง</th>
          <th style="padding:6px 8px;text-align:left">แผนก</th>
          <th style="padding:6px 8px;text-align:left">วันหมด</th>
          <th style="padding:6px 8px;text-align:left">สถานะ</th>
          <th style="padding:6px 8px;text-align:right">฿/เดือน</th>
        </tr></thead>
        <tbody>${rowsHtml}</tbody>
      </table>
    </div>`;
  };

  const makeTimelineCols = (rows, barColor, BAR_AREA = 90, buKey = 'ALL', rentalIndex = {}) => {
    const maxT = Math.max(...rows.map(t => t.count), 1);
    const statusColor = (month) => {
      const today = new Date();
      const [y, m] = month.split('-').map(Number);
      const diff = (y - today.getFullYear()) * 12 + (m - today.getMonth() - 1);
      if (diff < 0)  return '#dc2626';
      if (diff <= 3) return '#f97316';
      if (diff <= 6) return '#eab308';
      return barColor || '#2563eb';
    };
    return rows.map(t => {
      if (t.count === 0) {
        const label = new Date(t.month + '-01').toLocaleDateString('th-TH', {month:'short', year:'2-digit'});
        return `<div class="timeline-col" style="position:relative;opacity:.3">
          <div class="timeline-bar-wrap" style="height:${BAR_AREA}px;align-items:flex-end;display:flex;width:100%">
            <div style="height:2px;background:#e2e8f0;width:100%"></div>
          </div>
          <div class="timeline-label">${label}</div>
        </div>`;
      }
      const h = Math.max(Math.round((t.count / maxT) * BAR_AREA), 4);
      const color = barColor ? (BU_COLOR[barColor] || barColor) : statusColor(t.month);
      const label = new Date(t.month + '-01').toLocaleDateString('th-TH', {month:'short', year:'2-digit'});
      const expandKey = `${t.month}|${buKey}`;
      const expandId  = `tl-expand-${expandKey.replace(/[|-]/g,'_')}`;
      return `<div class="timeline-col" style="position:relative">
        <div class="timeline-bar-wrap" style="height:${BAR_AREA}px;align-items:flex-end;display:flex;width:100%">
          <div class="timeline-bar" data-expand="${expandId}" data-key="${expandKey}" data-bu="${buKey}"
               style="height:${h}px;background:${color};width:100%;position:relative;cursor:pointer;transition:opacity .15s"
               onmouseover="this.style.opacity='.75'" onmouseout="this.style.opacity='1'"
               onclick="toggleTimelineExpand(this, '${expandKey}', '${buKey}')">
            <span style="position:absolute;top:-18px;left:50%;transform:translateX(-50%);font-size:.65rem;font-weight:700;color:#1e293b;white-space:nowrap">${t.count}</span>
          </div>
        </div>
        <div class="timeline-label">${label}</div>
      </div>`;
    }).join('');
  };

  const rentalIndex = d.rental_index || {};

  // Timeline รวม (ทุก BU)
  if (d.timeline.length) {
    document.getElementById('r-timeline').innerHTML = `
      <div style="overflow-x:auto;padding-top:20px">
        <div class="timeline-wrap" style="padding-bottom:4px">${makeTimelineCols(d.timeline, null, 90, 'ALL', rentalIndex)}</div>
      </div>
      <div id="tl-expand-all-wrap"></div>
      <div style="display:flex;gap:16px;margin-top:8px;font-size:.72rem;color:#64748b">
        <span><span style="display:inline-block;width:10px;height:10px;background:#dc2626;border-radius:2px;margin-right:3px"></span>หมดแล้ว</span>
        <span><span style="display:inline-block;width:10px;height:10px;background:#f97316;border-radius:2px;margin-right:3px"></span>&lt;3 เดือน</span>
        <span><span style="display:inline-block;width:10px;height:10px;background:#eab308;border-radius:2px;margin-right:3px"></span>&lt;6 เดือน</span>
        <span><span style="display:inline-block;width:10px;height:10px;background:#2563eb;border-radius:2px;margin-right:3px"></span>ปกติ</span>
      </div>`;
  } else {
    document.getElementById('r-timeline').innerHTML =
      '<div style="text-align:center;padding:24px;color:#94a3b8;font-size:.82rem">ไม่มีข้อมูล timeline</div>';
  }

  // Timeline แยก BU — คนละกรอบ
  const tbl = d.timeline_by_bu || [];
  document.getElementById('r-timeline-by-bu').innerHTML = tbl.map(b => {
    const hasData = b.months.some(m => m.count > 0);
    if (!hasData) return '';
    const color = BU_COLOR[b.bu_code] || '#94a3b8';
    const cols  = makeTimelineCols(b.months, b.bu_code, 80, b.bu_code, rentalIndex);
    const total = b.months.reduce((s, m) => s + m.count, 0);
    const safeId = b.bu_code.replace(/[^a-zA-Z0-9]/g,'_');
    return `<div style="margin-top:16px;border:1px solid #e2e8f0;border-radius:10px;padding:14px 16px;background:#fafafa">
      <div style="font-size:.8rem;font-weight:700;color:${color};margin-bottom:6px">
        <span style="display:inline-block;width:10px;height:10px;background:${color};border-radius:50%;margin-right:5px"></span>
        ${b.bu_code} <span style="font-weight:400;color:#94a3b8;margin-left:6px">${total} เครื่อง</span>
      </div>
      <div style="overflow-x:auto;padding-top:20px">
        <div class="timeline-wrap" style="padding-bottom:4px">${cols}</div>
      </div>
      <div id="tl-expand-bu-wrap-${safeId}"></div>
    </div>`;
  }).join('');

  // เก็บ rentalIndex ไว้ให้ toggleTimelineExpand ใช้
  window._tlRentalIndex = rentalIndex;

  // การ์ดคู่ timeline: เครื่องเช่าที่ไม่มีข้อมูลวันหมดสัญญา แยก BU
  const ntl = d.no_timeline_by_bu || [];
  const ntlTotal = ntl.reduce((s, b) => s + b.count, 0);
  document.getElementById('r-no-timeline-total').textContent = `${ntlTotal.toLocaleString()} เครื่อง`;
  const maxNtl = Math.max(...ntl.map(b => b.count), 1);
  window._ntlByBu = {};
  ntl.forEach(b => { window._ntlByBu[b.bu_code] = b.items || []; });
  document.getElementById('r-no-timeline-bars').innerHTML = ntl.length
    ? ntl.map(b => {
        const buLabel = b.bu_code === '—' ? 'ไม่ระบุ BU' : b.bu_code;
        const color = BU_COLOR[b.bu_code] || '#94a3b8';
        const safeId = b.bu_code.replace(/[^a-zA-Z0-9]/g,'_');
        return `<div class="bar-row" style="margin-bottom:6px;cursor:pointer" onclick="toggleNoTimelineDetail('${esc(b.bu_code)}','${safeId}')" title="คลิกเพื่อดูรายการเครื่อง">
          <div class="bar-label" style="width:110px;min-width:110px;text-align:right;font-weight:600;color:${color}">${esc(buLabel)} ▾</div>
          <div class="bar-track" style="flex:1"><div class="bar-fill" style="width:${(b.count/maxNtl*100).toFixed(1)}%;background:${color}"></div></div>
          <div class="bar-count" style="min-width:36px">${b.count}</div>
        </div>
        <div id="ntl-detail-${safeId}" style="display:none;margin:2px 0 10px 116px"></div>`;
      }).join('')
    : '<div style="text-align:center;padding:24px;color:#16a34a;font-size:.82rem">✓ ทุกเครื่องมีข้อมูลวันหมดสัญญาครบ</div>';

  // Urgent table
  const tbody = document.getElementById('r-urgent-tbody');
  const empty = document.getElementById('r-urgent-empty');
  if (!d.urgent.length) {
    tbody.innerHTML = '';
    empty.style.display = '';
    return;
  }
  empty.style.display = 'none';
  const pillCls = { expired: 'pill-expired', critical: 'pill-critical' };
  const pillLabel = (a) => {
    if (a.contract_status === 'expired')  return `🔴 เกินกำหนด ${Math.abs(a.days_remaining)} วัน`;
    if (a.contract_status === 'critical') return `🟠 เหลือ ${a.days_remaining} วัน`;
    return '';
  };
  const edBadgeCfg = {
    active:  { bg: '#dcfce7', color: '#15803d', label: '● Active'  },
    expire:  { bg: '#fef9c3', color: '#854d0e', label: '⚠ Expire'  },
    return:  { bg: '#f1f5f9', color: '#475569', label: '↩ Return'  },
    spare:   { bg: '#ede9fe', color: '#6d28d9', label: '◎ Spare'   },
    error:   { bg: '#fee2e2', color: '#b91c1c', label: '✕ Error'   },
  };
  const edBadge = (s) => {
    if (!s) return '—';
    const c = edBadgeCfg[s.toLowerCase()] || { bg:'#f1f5f9', color:'#475569', label: s };
    return `<span style="font-size:.72rem;padding:2px 7px;border-radius:5px;font-weight:600;background:${c.bg};color:${c.color}">${c.label}</span>`;
  };
  const dateFmt = d => d
    ? new Date(d).toLocaleDateString('th-TH', {day:'numeric', month:'short', year:'2-digit'})
    : '—';

  tbody.innerHTML = d.urgent.map(a => {
    const ownershipCell = ownershipBadge(a);

    const typeModel = [esc(a.asset_type), esc(a.model)||esc(a.brand)].filter(Boolean).join(' ');
    const rowBg = a.contract_status === 'expired' ? 'background:#fff5f5' : '';

    return `<tr style="border-bottom:1px solid #f1f5f9;${rowBg}">
      <td style="padding:7px 10px;font-size:.78rem;color:#64748b;font-family:monospace;white-space:nowrap">${esc(a.asset_no)||'—'}</td>
      <td style="padding:7px 10px"><code style="font-size:.78rem;color:#334155">${esc(a.computer_id)||'—'}</code></td>
      <td style="padding:7px 10px;font-size:.75rem;color:#64748b;font-family:monospace;white-space:nowrap">${esc(a.serial_no)||'—'}</td>
      <td style="padding:7px 10px;font-size:.78rem;max-width:180px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="${esc(typeModel)}">${typeModel||'—'}</td>
      <td style="padding:7px 10px;white-space:nowrap">${ownershipCell}</td>
      <td style="padding:7px 10px;font-size:.82rem;max-width:160px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="${esc(a.user_name)||''}">
        ${a.is_central
          ? '<span class="badge-central">🏢 ส่วนกลาง</span>'
          : a.user_name ? `<strong>${esc(a.user_name)}</strong>` : '<span style="color:#94a3b8">ไม่ระบุ</span>'}
      </td>
      <td style="padding:7px 10px;white-space:nowrap"><span class="bu-badge bu-${esc(a.emp_bu_code)}">${esc(a.emp_bu_code)||'—'}</span></td>
      <td style="padding:7px 10px;font-size:.78rem;color:#64748b;max-width:140px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="${esc(a.emp_dept)||''}">${esc(a.emp_dept)||'—'}</td>
      <td style="padding:7px 10px;white-space:nowrap;font-size:.78rem;color:#94a3b8">${dateFmt(a.start_date)}</td>
      <td style="padding:7px 10px;white-space:nowrap;font-size:.82rem;font-weight:600">${dateFmt(a.end_date)}</td>
      <td style="padding:7px 10px;text-align:center;white-space:nowrap">
        <span class="status-pill ${pillCls[a.contract_status]||''}">${pillLabel(a)}</span>
      </td>
      <td style="padding:7px 10px;text-align:center">${edBadge(a.edevice_status)}</td>
      <td style="padding:7px 10px;text-align:right;font-size:.8rem;font-weight:600">฿${(a.monthly_charge||0).toLocaleString()}</td>
    </tr>`;
  }).join('');

  // ── shared helpers อยู่ใน global scope แล้ว (_anomalyHead, _anomalyRow, etc.) ──

  // ---- Anomaly panel 1: ไม่มีข้อมูลสัญญา ----
  const nc = d.no_contract || [];
  document.getElementById('r-unknown').textContent = nc.length.toLocaleString();
  document.getElementById('r-no-contract-head').innerHTML = _anomalyHead(true);
  document.getElementById('r-no-contract-count').textContent =
    nc.length ? `${nc.length} เครื่อง ⚠️` : '0 เครื่อง ✓';
  document.getElementById('r-no-contract-tbody').innerHTML = nc.length
    ? nc.map(a => _anomalyRow(a)).join('')
    : '<tr><td colspan="14" style="text-align:center;padding:16px;color:#16a34a;font-size:.82rem">✓ เครื่องเช่าทุกเครื่องมีข้อมูลสัญญาครบ</td></tr>';

  // ---- Anomaly panel 2: ไม่มี BU ----
  const nb = d.no_bu || [];
  const nbHasDept = nb.filter(a => a.has_dept).length;
  const nbNoDept  = nb.filter(a => !a.has_dept).length;
  const nbHasUser = nb.filter(a => a.user_name && !a.is_central && !a.employee_id).length;

  document.getElementById('r-no-bu-badge').textContent = nb.length.toLocaleString();
  document.getElementById('r-no-bu-head').innerHTML = _anomalyHead(true);
  document.getElementById('r-no-bu-count').textContent =
    nb.length ? `${nb.length} เครื่อง ⚠️` : '0 เครื่อง ✓';
  document.getElementById('r-no-bu-summary').innerHTML = nb.length ? `
    <span style="background:#fef3c7;color:#92400e;padding:2px 10px;border-radius:10px">📋 มีแผนก แต่ไม่มี BU: <strong>${nbHasDept}</strong></span>
    <span style="background:#fee2e2;color:#991b1b;padding:2px 10px;border-radius:10px">❌ ไม่มีทั้ง BU และแผนก: <strong>${nbNoDept}</strong></span>
    ${nbHasUser ? `<span style="background:#ede9fe;color:#6d28d9;padding:2px 10px;border-radius:10px">👤 มีชื่อแต่ไม่พบใน HR: <strong>${nbHasUser}</strong></span>` : ''}` : '';
  document.getElementById('r-panel-no-bu').style.display = '';
  document.getElementById('r-no-bu-tbody').innerHTML = nb.length
    ? nb.map(a => _anomalyRow(a)).join('')
    : '<tr><td colspan="14" style="text-align:center;padding:16px;color:#16a34a;font-size:.82rem">✓ เครื่องเช่าทุกเครื่องระบุ BU ครบแล้ว</td></tr>';

  // ---- Anomaly panel 3: ยังไม่บันทึกใน eDevice ----
  const me = d.missing_edevice || [];
  document.getElementById('r-missing-edevice-head').innerHTML = _anomalyHead(true);
  document.getElementById('r-missing-edevice-badge').textContent = me.length.toLocaleString();
  document.getElementById('r-missing-edevice-count').textContent =
    me.length ? `${me.length} เครื่อง ⚠️` : '0 เครื่อง ✓';
  document.getElementById('r-missing-edevice-tbody').innerHTML = me.length
    ? me.map(a => _anomalyRow(a)).join('')
    : '<tr><td colspan="14" style="text-align:center;padding:16px;color:#16a34a;font-size:.82rem">✓ ทุกเครื่องมีข้อมูลใน eDevice ครบแล้ว</td></tr>';

  // ---- Anomaly panel 4: eDevice ไม่ระบุการถือครอง (ownership_needs_update) ----
  const nu = d.needs_update || [];
  document.getElementById('r-needs-update-head').innerHTML = _anomalyHead(true);
  document.getElementById('r-needs-update-badge').textContent = nu.length.toLocaleString();
  document.getElementById('r-needs-update-count').textContent =
    nu.length ? `${nu.length} เครื่อง ⚠️` : '0 เครื่อง ✓';
  document.getElementById('r-needs-update-tbody').innerHTML = nu.length
    ? nu.map(a => _anomalyRow(a)).join('')
    : '<tr><td colspan="14" style="text-align:center;padding:16px;color:#16a34a;font-size:.82rem">✓ ทุกเครื่องระบุ เช่า/ซื้อ ครบแล้ว</td></tr>';
}

function toggleTimelineExpand(barEl, key, bu) {
  const rentalIndex = window._tlRentalIndex || {};
  const rows = rentalIndex[key] || [];

  // หา wrap container: ถ้า bu=ALL ใช้ tl-expand-all-wrap ไม่งั้นใช้ wrap ของ BU นั้น
  const safeId = bu.replace(/[^a-zA-Z0-9]/g,'_');
  const wrapId = bu === 'ALL' ? 'tl-expand-all-wrap' : `tl-expand-bu-wrap-${safeId}`;
  const wrap   = document.getElementById(wrapId);
  if (!wrap) return;

  // ถ้าคลิกซ้ำ key เดิม → ปิด
  if (wrap.dataset.openKey === key) {
    wrap.innerHTML = '';
    wrap.dataset.openKey = '';
    barEl.style.outline = '';
    return;
  }

  // reset outline แท่งเก่า
  document.querySelectorAll('.timeline-bar[data-bu="' + bu + '"]').forEach(b => b.style.outline = '');
  barEl.style.outline = '2px solid #1e293b';
  wrap.dataset.openKey = key;

  const monthLabel = new Date(key.split('|')[0] + '-01').toLocaleDateString('th-TH',{month:'long',year:'numeric'});

  if (!rows.length) {
    wrap.innerHTML = `<div style="padding:10px;color:#94a3b8;font-size:.8rem">ไม่มีข้อมูล</div>`;
    return;
  }

  const rowsHtml = rows.map(r => _anomalyRow(r)).join('');

  wrap.innerHTML = `
    <div style="margin-top:10px;border:1px solid #cbd5e1;border-radius:8px;overflow:hidden;background:#fff">
      <div style="padding:8px 12px;background:#f1f5f9;font-size:.78rem;font-weight:600;color:#334155;display:flex;justify-content:space-between;align-items:center">
        <span>📋 ${monthLabel}${bu !== 'ALL' ? ' · ' + bu : ''} — ${rows.length} เครื่อง</span>
        <span style="cursor:pointer;color:#94a3b8;font-size:1rem" onclick="this.closest('[id^=tl-expand]').innerHTML='';this.closest('[id^=tl-expand]').dataset.openKey='';document.querySelectorAll('.timeline-bar').forEach(b=>b.style.outline='')">✕</span>
      </div>
      <div style="overflow-x:auto">
        <table style="width:100%;border-collapse:collapse">
          <thead><tr style="background:#f8fafc">${_anomalyHead(true)}</tr></thead>
          <tbody>${rowsHtml}</tbody>
        </table>
      </div>
    </div>`;
}

function switchDashTab(name) {
  document.querySelectorAll('.dash-subtab').forEach(b => b.classList.toggle('active', b.dataset.subtab === name));
  document.querySelectorAll('.dash-pane').forEach(p => p.style.display = 'none');
  const pane = document.getElementById('dash-pane-' + name);
  if (pane) pane.style.display = '';
  if (name === 'rental') loadRentalExportOptions();
  if (name === 'software') loadSoftwareDashboard();
  if (name === 'printer')  loadPrinters();
}

// ==============================
// ---- Dashboard: บริหาร Software ----
// ==============================

let swDash = null;   // ผลจาก /api/dashboard/software

async function loadSoftwareDashboard(force) {
  if (force) swVendor = null;
  if (swDash && !force) { renderSwDash(); return; }
  document.getElementById('sd-table-wrap').innerHTML =
    '<div style="text-align:center;padding:24px;color:#94a3b8">กำลังโหลด...</div>';
  try {
    swDash = await api('/api/dashboard/software');
  } catch (e) {
    document.getElementById('sd-table-wrap').innerHTML =
      '<div class="sw-empty">โหลดข้อมูลไม่สำเร็จ</div>';
    return;
  }
  const sel = document.getElementById('sd-bu');
  const keep = sel.value;
  sel.innerHTML = '<option value="">ทุก BU</option>' +
    swDash.bus.map(b => `<option value="${esc(b)}">${esc(b)}</option>`).join('');
  sel.value = keep;
  renderSwDash();
}

function renderSwDash() {
  const s = swDash.summary;
  const pct = s.employees_active ? (s.employees_with / s.employees_active * 100) : 0;

  document.getElementById('sd-licenses').textContent = s.licenses.toLocaleString();
  document.getElementById('sd-licenses-sub').textContent =
    `${s.catalog_used} รายการที่ต่างกัน` +
    (s.covered ? ` · ชุดรวมนับ 1 (ไม่นับโปรแกรมในชุดอีก ${s.covered.toLocaleString()})` : '') +
    (s.orphan_licenses ? ` · ${s.orphan_licenses} ใบหาเจ้าของใน HR ไม่เจอ` : '');

  document.getElementById('sd-emps').textContent = s.employees_with.toLocaleString();
  document.getElementById('sd-emps-sub').textContent =
    `${pct.toFixed(0)}% ของพนักงาน Active ${s.employees_active.toLocaleString()} คน`;

  document.getElementById('sd-catalog').textContent = `${s.catalog_used} / ${s.catalog_total}`;
  document.getElementById('sd-catalog-sub').textContent =
    s.catalog_unused ? `ยังไม่มีใครถือ ${s.catalog_unused} รายการ ▾` : 'มีผู้ถือครองทุกรายการ';

  document.getElementById('sd-inactive').textContent = s.inactive_licenses.toLocaleString();

  renderSwDashTable();
  renderSwDashBuBars();
  renderSwDashUnused();
  renderSwDashInactive();
  if (!swVendor) loadSwVendor(); else renderSwVendor();
}

/** ตาราง Software × BU — กรอง BU แล้วคอลัมน์จะเหลือเฉพาะ BU นั้น */
function renderSwDashTable() {
  const q   = (document.getElementById('sd-search').value || '').trim().toLowerCase();
  const bu  = document.getElementById('sd-bu').value;
  const all = swDash.by_software;

  let rows = all.filter(s =>
    !q || (s.name || '').toLowerCase().includes(q) ||
          (s.category || '').toLowerCase().includes(q) ||
          (s.vendor || '').toLowerCase().includes(q));
  if (bu) rows = rows.filter(s => (s.by_bu[bu] || 0) > 0);

  const cols = bu ? [bu] : swDash.bus.filter(b => all.some(s => s.by_bu[b]));
  const tot  = r => bu ? (r.by_bu[bu] || 0) : r.total;
  rows = rows.slice().sort((a, b) => tot(b) - tot(a) || (b.covered || 0) - (a.covered || 0) ||
                                     a.name.localeCompare(b.name));
  const grand = rows.reduce((n, r) => n + tot(r), 0);

  const TH = 'padding:8px 10px;text-align:left;font-size:.74rem;font-weight:700;color:#475569;white-space:nowrap';
  const TD = 'padding:7px 10px;font-size:.82rem;border-bottom:1px solid #f8fafc';

  document.getElementById('sd-table-wrap').innerHTML = !rows.length
    ? '<div class="sw-empty">ไม่พบรายการ</div>'
    : `<table class="sd-table" style="width:100%;border-collapse:collapse">
      <thead><tr style="background:#f8fafc;border-bottom:2px solid #e2e8f0">
        <th style="${TH}">Software</th>
        <th style="${TH}">หมวด</th>
        <th style="${TH}">ลิขสิทธิ์</th>
        ${cols.map(c => `<th style="${TH};text-align:right">${esc(c)}</th>`).join('')}
        <th style="${TH};text-align:right">รวม</th>
        <th style="${TH};text-align:right" title="ถือโดยพนักงานที่ไม่ Active">⚠️</th>
      </tr></thead>
      <tbody>
        ${rows.map(r => `
          <tr class="sd-row" onclick="toggleSwHolders(${r.id}, this)" title="คลิกดูรายชื่อผู้ถือครอง">
            <td style="${TD};font-weight:600;color:#1e293b">
              <span class="sd-caret">▸</span> ${esc(r.name)}
              ${r.is_bundle ? '<span class="sw-bundle-tag">ชุดรวม</span>' : ''}
              ${r.is_active === 0 ? '<span class="sw-off">ปิดใช้งานในคลัง</span>' : ''}
              ${r.covered ? `<span class="sd-covered" title="คนที่ถือชุดรวมอยู่แล้ว ใช้ตัวนี้ได้โดยไม่ต้องซื้อแยก — ไม่นับในตัวเลข">+${r.covered.toLocaleString()} ใช้ในชุดรวม</span>` : ''}
            </td>
            <td style="${TD};color:#64748b">${esc(r.category) || '—'}</td>
            <td style="${TD};color:#64748b">${SW_LICENSE_LABEL[r.license_type] || '—'}</td>
            ${cols.map(c => `<td style="${TD};text-align:right;color:#475569">${r.by_bu[c] || '<span style="color:#e2e8f0">—</span>'}</td>`).join('')}
            <td style="${TD};text-align:right;font-weight:800;color:#7e22ce">${tot(r).toLocaleString()}</td>
            <td style="${TD};text-align:right">${r.inactive ? `<span class="sd-warn">${r.inactive}</span>` : ''}</td>
          </tr>`).join('')}
      </tbody>
      <tfoot><tr style="background:#f8fafc;border-top:2px solid #e2e8f0;font-weight:700">
        <td style="${TD}">รวม ${rows.length} รายการ</td><td style="${TD}"></td><td style="${TD}"></td>
        ${cols.map(c => `<td style="${TD};text-align:right">${rows.reduce((n, r) => n + (r.by_bu[c] || 0), 0).toLocaleString()}</td>`).join('')}
        <td style="${TD};text-align:right;color:#7e22ce">${grand.toLocaleString()}</td>
        <td style="${TD}"></td>
      </tr></tfoot>
    </table>`;
}

/** กางรายชื่อผู้ถือครองใต้แถวที่คลิก */
async function toggleSwHolders(cid, rowEl) {
  const open = rowEl.nextElementSibling &&
               rowEl.nextElementSibling.classList.contains('sd-holders');
  document.querySelectorAll('.sd-holders').forEach(el => el.remove());
  document.querySelectorAll('.sd-row .sd-caret').forEach(c => c.textContent = '▸');
  if (open) return;

  const ncols = rowEl.children.length;
  rowEl.querySelector('.sd-caret').textContent = '▾';
  rowEl.insertAdjacentHTML('afterend',
    `<tr class="sd-holders"><td colspan="${ncols}" style="padding:0">
       <div style="padding:12px 16px;color:#94a3b8;font-size:.8rem">กำลังโหลด...</div></td></tr>`);

  let list;
  try {
    list = await api(`/api/software/catalog/${cid}/holders`);
  } catch (e) {
    rowEl.nextElementSibling.querySelector('div').textContent = 'โหลดรายชื่อไม่สำเร็จ';
    return;
  }

  const bu = document.getElementById('sd-bu').value;
  // ซื้อแยกขึ้นก่อน คนที่ใช้ผ่านชุดรวมตามหลัง
  const shown = (bu ? list.filter(h => (h.bu_code || 'ไม่ระบุ BU') === bu) : list)
    .slice().sort((a, b) => a.via_bundle - b.via_bundle);
  const nVia = shown.filter(h => h.via_bundle).length;
  const TD = 'padding:5px 10px;font-size:.78rem;border-bottom:1px solid #f1f5f9';

  rowEl.nextElementSibling.querySelector('td').innerHTML = `
    <div class="sd-holders-box">
      <div style="font-size:.72rem;color:#94a3b8;margin-bottom:6px">
        ${nVia
          ? `ซื้อแยก <b style="color:#7e22ce">${(shown.length - nVia).toLocaleString()}</b> คน ·
             ใช้ผ่านชุดรวม ${nVia.toLocaleString()} คน (ไม่นับเป็น license)`
          : `ผู้ถือครอง ${shown.length.toLocaleString()} คน`}${bu ? ` (เฉพาะ ${esc(bu)})` : ''}
      </div>
      <div style="max-height:320px;overflow-y:auto">
        <table style="width:100%;border-collapse:collapse">
          <tbody>
            ${shown.map(h => `
              <tr>
                <td style="${TD};font-family:monospace;color:#94a3b8;width:70px">${esc(h.emp_code) || '—'}</td>
                <td style="${TD};font-weight:600;color:#1e293b">
                  ${h.emp_id
                    ? `<a href="#" onclick="openSoftware(${h.emp_id},'${esc(h.emp_name).replace(/'/g, '&#39;')}');return false" style="color:#1e293b;text-decoration:none;border-bottom:1px dotted #cbd5e1">${esc(h.emp_name)}</a>`
                    : '<span style="color:#ef4444">(ไม่พบใน HR)</span>'}
                  ${h.status && h.status !== 'active'
                    ? '<span class="sw-tag del" style="margin-left:6px">Inactive</span>' : ''}
                  ${h.via_bundle ? '<span class="sw-inbundle-tag">ในชุดรวม</span>' : ''}
                </td>
                <td style="${TD};width:70px"><span class="bu-badge bu-${esc(h.bu_code)}">${esc(h.bu_code) || '—'}</span></td>
                <td style="${TD};color:#64748b">${esc(h.department) || '—'}</td>
                <td style="${TD};color:#64748b">${esc(h.position) || '—'}</td>
                <td style="${TD};color:#94a3b8;font-size:.74rem">${esc(h.note) || ''}</td>
              </tr>`).join('')}
          </tbody>
        </table>
      </div>
    </div>`;
}

function renderSwDashBuBars() {
  const rows = swDash.by_bu;
  const zero = swDash.bus.filter(b =>
    b !== 'ไม่ระบุ BU' && !rows.some(r => r.bu_code === b));
  const max = Math.max(1, ...rows.map(r => r.licenses));
  const TD = 'padding:6px 8px;font-size:.8rem';

  document.getElementById('sd-bu-bars').innerHTML = `
    <table style="width:100%;border-collapse:collapse">
      <thead><tr style="border-bottom:2px solid #f1f5f9;color:#94a3b8;font-size:.72rem;font-weight:600">
        <th style="padding:4px 8px;text-align:left">BU</th>
        <th style="padding:4px 8px;text-align:right">License</th>
        <th style="padding:4px 8px;text-align:right">คนที่มีข้อมูล</th>
        <th style="padding:4px 8px;text-align:left;min-width:110px">สัดส่วนคนที่บันทึกแล้ว</th>
      </tr></thead>
      <tbody>
        ${rows.map(b => {
          const cov = b.emp_total ? (b.employees / b.emp_total * 100) : 0;
          return `<tr style="border-bottom:1px solid #f8fafc">
            <td style="${TD};font-weight:600;color:#374151">${esc(b.bu_code)}</td>
            <td style="${TD};text-align:right;font-weight:700">${b.licenses.toLocaleString()}</td>
            <td style="${TD};text-align:right;color:#64748b">
              ${b.employees.toLocaleString()}${b.emp_total ? ` / ${b.emp_total.toLocaleString()}` : ''}</td>
            <td style="${TD}">
              <div style="display:flex;align-items:center;gap:6px">
                <div style="flex:1;height:8px;background:#f1f5f9;border-radius:4px;overflow:hidden">
                  <div style="width:${Math.min(100, cov).toFixed(0)}%;height:100%;background:linear-gradient(90deg,#7e22ce,#a855f7);border-radius:4px"></div>
                </div>
                <span style="font-size:.7rem;color:#94a3b8;min-width:30px">${cov.toFixed(0)}%</span>
              </div>
            </td>
          </tr>`;
        }).join('')}
      </tbody>
    </table>
    ${zero.length ? `
      <div style="margin-top:12px;padding:10px 12px;background:#fffbeb;border:1px solid #fde68a;border-radius:8px;font-size:.78rem;color:#92400e">
        <b>ยังไม่มีข้อมูลเลย ${zero.length} BU:</b> ${zero.map(esc).join(' · ')}
      </div>` : ''}`;
}

function renderSwDashUnused() {
  const list = swDash.unused;
  document.getElementById('sd-unused-count').textContent = list.length.toLocaleString();
  document.getElementById('sd-unused-list').innerHTML = !list.length
    ? '<div class="sw-empty">มีผู้ถือครองทุกรายการในคลัง</div>'
    : `<div class="sd-chips">${list.map(c => `
        <span class="sd-chip${c.is_active ? '' : ' off'}" title="${esc(c.category) || 'ยังไม่จัดหมวด'}${c.is_active ? '' : ' · ปิดใช้งานแล้ว'}">
          ${esc(c.name)}</span>`).join('')}</div>
       <div style="margin-top:10px;font-size:.74rem;color:#94a3b8">
         จัดการรายการเหล่านี้ได้ที่ <a href="#" onclick="openSwCatalog();return false" style="color:#7e22ce;font-weight:600;text-decoration:none">คลัง Software</a>
       </div>`;
}

function renderSwDashInactive() {
  const list = swDash.inactive;
  document.getElementById('sd-inactive-count').textContent = list.length.toLocaleString();
  const TD = 'padding:7px 10px;font-size:.82rem;border-bottom:1px solid #f8fafc';
  document.getElementById('sd-inactive-list').innerHTML = !list.length
    ? '<div style="text-align:center;padding:20px;color:#16a34a;font-size:.85rem">✓ ไม่มี license ค้างที่พนักงานที่ไม่ Active</div>'
    : `<table style="width:100%;border-collapse:collapse">
        <thead><tr style="background:#f8fafc;border-bottom:2px solid #e2e8f0">
          ${['รหัส', 'ชื่อ-สกุล', 'BU', 'แผนก', 'Software', 'หมายเหตุ'].map(h =>
            `<th style="padding:8px 10px;text-align:left;font-size:.74rem;font-weight:700;color:#475569">${h}</th>`).join('')}
        </tr></thead>
        <tbody>
          ${list.map(r => `
            <tr>
              <td style="${TD};font-family:monospace;color:#94a3b8">${esc(r.emp_code) || '—'}</td>
              <td style="${TD};font-weight:600">
                ${r.emp_id
                  ? `<a href="#" onclick="openSoftware(${r.emp_id},'${esc(r.emp_name).replace(/'/g, '&#39;')}');return false" style="color:#1e293b;text-decoration:none;border-bottom:1px dotted #cbd5e1">${esc(r.emp_name)}</a>`
                  : '<span style="color:#ef4444">(ไม่พบใน HR)</span>'}
              </td>
              <td style="${TD}"><span class="bu-badge bu-${esc(r.bu_code)}">${esc(r.bu_code) || '—'}</span></td>
              <td style="${TD};color:#64748b">${esc(r.department) || '—'}</td>
              <td style="${TD}">${esc(r.software)}
                ${r.covers && r.covers.length
                  ? `<div style="font-size:.7rem;color:#a78bfa">รวม ${r.covers.length} โปรแกรมในชุด</div>` : ''}</td>
              <td style="${TD};color:#94a3b8;font-size:.76rem">${esc(r.note) || ''}</td>
            </tr>`).join('')}
        </tbody>
      </table>`;
}

// ---- แยกตามผู้ผลิต: BU → ฝ่าย → คน ----

let swVendor     = null;                 // ผลจาก /api/dashboard/software/vendor
let swVendorName = 'Adobe';
let svOpen       = {};                   // {'bu:AMTV': true, 'dept:AMTV|ฝ่าย': true}

async function loadSwVendor() {
  const sel = document.getElementById('sv-vendor');
  if (sel.value) swVendorName = sel.value;
  document.getElementById('sv-tree').innerHTML =
    '<div style="text-align:center;padding:20px;color:#94a3b8">กำลังโหลด...</div>';
  try {
    swVendor = await api('/api/dashboard/software/vendor?name=' + encodeURIComponent(swVendorName));
  } catch (e) {
    document.getElementById('sv-tree').innerHTML = '<div class="sw-empty">โหลดข้อมูลไม่สำเร็จ</div>';
    return;
  }
  // ตัวเลือกผู้ผลิต เรียงจากที่มี license มากสุด
  sel.innerHTML = swVendor.vendors.map(v =>
    `<option value="${esc(v.name)}"${v.name === swVendor.vendor ? ' selected' : ''}>
       ${esc(v.name)} (${v.licenses.toLocaleString()})</option>`).join('');
  svOpen = {};
  if (swVendor.by_bu.length === 1) svOpen['bu:' + swVendor.by_bu[0].bu_code] = true;
  renderSwVendor();
}

function renderSwVendor() {
  const v = swVendor;
  const q = (document.getElementById('sv-search').value || '').trim().toLowerCase();
  document.getElementById('sv-title').textContent = v.vendor;

  const s = v.summary;
  const R = v.rule;

  // ตัวเลือก BU สำหรับ Export — เฉพาะ BU ที่มีคนใช้ของผู้ผลิตนี้
  const exSel = document.getElementById('sv-export-bu');
  const keep  = exSel.value;
  exSel.innerHTML = '<option value="">Export ทุก BU</option>' +
    v.by_bu.map(b => `<option value="${esc(b.bu_code)}">Export เฉพาะ ${esc(b.bu_code)} (${b.people} คน)</option>`).join('');
  exSel.value = v.by_bu.some(b => b.bu_code === keep) ? keep : '';

  document.getElementById('sv-summary').innerHTML = `
    <span title="ชุดรวม All Apps นับเป็น 1 — โปรแกรมที่อยู่ในชุดไม่นับซ้ำ"><b>${s.licenses.toLocaleString()}</b> license</span>
    <span><b>${s.people.toLocaleString()}</b> คน</span>
    <span><b>${s.products}</b> โปรแกรม</span>
    <span><b>${s.bus}</b> BU · <b>${s.depts}</b> ฝ่าย</span>
    ${R ? `<span class="sv-cc-sum"><span class="sv-cc">✓</span> ${esc(R.label)}
             <b>${s.cc.toLocaleString()}</b> คน
             ${v.groups && v.groups.cc_pending
               ? `<small>(ยังไม่ได้บันทึกชุด ${v.groups.cc_pending})</small>` : ''}</span>` : ''}
    ${v.unused.length ? `<span class="sv-none">ยังไม่มีใครถือ: ${v.unused.map(esc).join(' · ')}</span>` : ''}`;

  document.getElementById('sv-products').innerHTML = v.products.map(p =>
    `<span class="sv-prod"><b>${p.total.toLocaleString()}</b> ${esc(p.name)}</span>`).join('') +
    (R ? `<span class="sv-rule-note"><span class="sv-cc">✓</span> =
            ถือชุด ${esc(R.label)} อยู่ หรือใช้ ${esc(v.vendor)} ตั้งแต่ ${R.min} ตัวขึ้นไป
            (ไม่นับ ${R.exclude.map(x => esc(x.replace(/^Adobe /, ''))).join(', ')})</span>` : '');

  // ค้นหา = กรองคน แล้วเก็บเฉพาะฝ่าย/BU ที่ยังมีคนเหลือ (กางให้เองเพื่อเห็นผลทันที)
  const match = p => !q ||
    (p.name || '').toLowerCase().includes(q) ||
    (p.emp_code || '').toLowerCase().includes(q) ||
    (p.position || '').toLowerCase().includes(q) ||
    p.products.some(x => x.toLowerCase().includes(q));

  const bus = v.by_bu.map(b => {
    const depts = b.depts.map(d => {
      const people = q ? d.people_list.filter(match) : d.people_list;
      const hit = q && ((d.department || '').toLowerCase().includes(q));
      return { ...d, shown: hit ? d.people_list : people };
    }).filter(d => d.shown.length);
    return { ...b, depts };
  }).filter(b => b.depts.length);

  renderSwGroups();

  const el = document.getElementById('sv-tree');
  if (!bus.length) { el.innerHTML = '<div class="sw-empty">ไม่พบคนที่ตรงกับที่ค้นหา</div>'; return; }

  el.innerHTML = bus.map(b => {
    const buKey   = 'bu:' + b.bu_code;
    const buOpen  = q ? true : !!svOpen[buKey];
    return `
    <div class="sv-bu">
      <div class="sv-bu-head" onclick="toggleSv('${esc(buKey)}')">
        <span class="sv-caret">${buOpen ? '▾' : '▸'}</span>
        <span class="bu-badge bu-${esc(b.bu_code)}">${esc(b.bu_code)}</span>
        <span class="sv-bu-num"><b>${b.licenses.toLocaleString()}</b> license · ${b.people.toLocaleString()} คน · ${b.depts.length} ฝ่าย
          ${R && b.cc ? `· <span class="sv-cc">✓</span> <b class="sv-cc-b">${b.cc}</b> คนใช้ All Apps` : ''}</span>
        <span class="sv-bu-prods">${Object.entries(b.products)
          .sort((x, y) => y[1] - x[1])
          .map(([n, c]) => `${esc(n.replace(/^Adobe /, ''))} ${c}`).join(' · ')}</span>
      </div>
      ${!buOpen ? '' : b.depts.map(d => {
        const dKey  = `dept:${b.bu_code}|${d.department}`;
        const dOpen = q ? true : !!svOpen[dKey];
        const prods = Object.keys(d.products).sort((x, y) =>
          d.products[y] - d.products[x] || x.localeCompare(y));
        return `
        <div class="sv-dept">
          <div class="sv-dept-head" onclick="toggleSv('${esc(dKey).replace(/'/g, '&#39;')}')">
            <span class="sv-caret">${dOpen ? '▾' : '▸'}</span>
            <span class="sv-dept-name">${esc(d.department)}</span>
            <span class="sv-dept-num">${d.licenses.toLocaleString()} license · ${d.people.toLocaleString()} คน
              ${R && d.cc ? `· <span class="sv-cc">✓</span> <b class="sv-cc-b">${d.cc}</b>` : ''}</span>
          </div>
          ${!dOpen ? '' : `
          <div class="sv-matrix-wrap">
            <table class="sv-matrix">
              <thead>
                <tr>
                  <th class="sv-sticky">ชื่อ-สกุล</th>
                  <th>ตำแหน่ง</th>
                  ${prods.map(p => `<th class="sv-rot" title="${esc(p)}">${esc(p.replace(/^Adobe /, ''))}</th>`).join('')}
                  <th>รวม</th>
                  ${R ? `<th class="sv-rot sv-cc-th"
                          title="ถือชุด ${esc(R.label)} หรือใช้ ${esc(v.vendor)} ≥ ${R.min} ตัว (ไม่นับ ${R.exclude.join(', ')})"
                          >${esc(R.label)}</th>` : ''}
                </tr>
              </thead>
              <tbody>
                ${d.shown.map(p => `
                  <tr>
                    <td class="sv-sticky">
                      ${p.emp_id
                        ? `<a href="#" onclick="openSoftware(${p.emp_id},'${esc(p.name).replace(/'/g, '&#39;')}');return false">${esc(p.name)}</a>`
                        : `<span style="color:#ef4444">${esc(p.name)}</span>`}
                      ${p.status && p.status !== 'active'
                        ? '<span class="sw-tag del">Inactive</span>' : ''}
                      <span class="sv-code">${esc(p.emp_code) || ''}</span>
                    </td>
                    <td class="sv-pos">${esc(p.position) || '—'}</td>
                    ${prods.map(pr => {
                      const it = p.items.find(i => i.product === pr);
                      return `<td class="sv-cell">${it
                        ? `<span class="sv-on${it.in_bundle ? ' sv-in-bundle' : ''}"
                                 title="${it.in_bundle ? 'ใช้ผ่านชุดรวม — ไม่นับเป็น license แยก' : 'ซื้อแยก'}${it.note ? ' · ' + esc(it.note) : ''}">●</span>`
                        : '<span class="sv-off">·</span>'}</td>`;
                    }).join('')}
                    <td class="sv-cell" title="${p.has_bundle
                        ? `ชุดรวมนับ 1 · ใช้ ${p.items.length} โปรแกรมในชุด` : 'จำนวน license'}"><b>${p.licenses}</b></td>
                    ${R ? `<td class="sv-cell">${p.has_bundle
                      ? `<span class="sv-cc" title="ถือชุด ${esc(p.bundles.join(', '))} · ใช้ ${p.counted.length} ตัว">✓</span>`
                      : p.cc
                      ? `<span class="sv-cc sv-cc-pending" title="ใช้ ${p.counted.length} ตัว (${esc(p.counted.map(x => x.replace(/^Adobe /, '')).join(', '))}) แต่ยังไม่ได้บันทึกชุด All Apps">✓</span>`
                      : '<span class="sv-off">·</span>'}</td>` : ''}
                  </tr>`).join('')}
              </tbody>
              <tfoot>
                <tr>
                  <td class="sv-sticky">รวม ${d.shown.length.toLocaleString()} คน</td><td></td>
                  ${prods.map(pr => `<td class="sv-cell">${d.shown.filter(p =>
                    p.products.includes(pr)).length}</td>`).join('')}
                  <td class="sv-cell"><b>${d.shown.reduce((n, p) => n + p.licenses, 0)}</b></td>
                  ${R ? `<td class="sv-cell sv-cc-b">${d.shown.filter(p => p.cc).length}</td>` : ''}
                </tr>
              </tfoot>
            </table>
          </div>`}
        </div>`;
      }).join('')}
    </div>`;
  }).join('');
}

/** แผนต่ออายุ license — All Apps กี่ชุด และตัวแยกอย่างละกี่ชุด */
function renderSwGroups() {
  const panel = document.getElementById('sg-panel');
  const g = swVendor.groups;
  if (!g) { panel.style.display = 'none'; return; }
  panel.style.display = '';

  const R       = g.rule;
  const singles = g.plan.filter(p => p.kind === 'single');
  const singleQ = singles.reduce((n, p) => n + p.qty, 0);
  const bundleQ = g.plan[0].qty;

  document.getElementById('sg-title').textContent = swVendor.vendor;
  document.getElementById('sg-rule-note').textContent =
    `All Apps = คนที่ถือชุด All Apps อยู่ หรือใช้ตั้งแต่ ${R.min} ตัวขึ้นไป` +
    (R.exclude.length ? ` (ไม่นับ ${R.exclude.map(x => x.replace(/^Adobe /, '')).join(', ')})` : '');

  // ช่องเทียบกับจำนวนที่ซื้อไว้ในคลัง — ว่าง = ยังไม่ได้ระบุ
  const seatTd = p => p.seats == null
    ? '<td class="sg-r"><span class="sv-off" title="ยังไม่ได้ระบุจำนวนที่ซื้อในคลัง">—</span></td><td></td>'
    : `<td class="sg-r">${p.seats.toLocaleString()}</td>
       <td class="sg-r">${p.seats - p.qty < 0
         ? `<b style="color:#dc2626">ขาด ${(p.qty - p.seats).toLocaleString()}</b>`
         : p.seats - p.qty > 0
         ? `<span style="color:#15803d">เหลือ ${(p.seats - p.qty).toLocaleString()}</span>`
         : '<span style="color:#15803d">พอดี</span>'}</td>`;

  // ยอดรวมซื้อไว้ — ระบุจำนวนซื้อไม่ครบจะไม่สรุปขาด/เหลือ
  const sumTd = items => {
    const known = items.filter(p => p.seats != null);
    if (!known.length) return '<td class="sg-r"><span class="sv-off">—</span></td><td></td>';
    const tot = known.reduce((n, p) => n + p.seats, 0);
    if (known.length < items.length)
      return `<td class="sg-r"><b>${tot.toLocaleString()}</b></td>
              <td class="sg-r" style="color:#b45309;font-size:.72rem">ระบุแล้ว ${known.length}/${items.length}</td>`;
    return seatTd({ seats: tot, qty: items.reduce((n, p) => n + p.qty, 0) });
  };

  // ตารางหลัก = ใบสั่งซื้อ: รายการ + จำนวน
  document.getElementById('sg-plan').innerHTML = `
    <table class="sg-table sg-plan-table">
      <thead><tr>
        <th>รายการ</th><th class="sg-r">ต้องใช้</th>
        <th class="sg-r">ซื้อไว้</th><th class="sg-r">ขาด / เหลือ</th><th>ไว้ให้ใคร</th>
      </tr></thead>
      <tbody>
        <tr class="sg-plan-bundle">
          <td><b>${esc(g.plan[0].catalog_name || g.plan[0].item)}</b></td>
          <td class="sg-r"><b class="sg-qty">${bundleQ.toLocaleString()}</b></td>
          ${seatTd(g.plan[0])}
          <td class="sg-who">${esc(g.plan[0].note)}</td>
        </tr>
        ${singles.length ? `<tr class="sg-plan-sep"><td colspan="5">ซื้อแยกเฉพาะตัว — สำหรับ ${g.few.people.toLocaleString()} คนที่ใช้ไม่ถึง ${R.min} ตัว</td></tr>` : ''}
        ${singles.map(p => `
          <tr>
            <td>${esc(p.item)}</td>
            <td class="sg-r"><b class="sg-qty-s">${p.qty.toLocaleString()}</b></td>
            ${seatTd(p)}
            <td class="sg-who">${p.qty ? p.qty.toLocaleString() + ' คน' : esc(p.note)}</td>
          </tr>`).join('')}
      </tbody>
      <tfoot>
        <tr><td>รวมตัวแยก</td><td class="sg-r">${singleQ.toLocaleString()}</td>
            ${sumTd(singles)}<td></td></tr>
        <tr><td><b>รวมทั้งหมด</b></td>
            <td class="sg-r"><b>${(bundleQ + singleQ).toLocaleString()}</b></td>
            ${sumTd(g.plan)}
            <td class="sg-who">${bundleQ} All Apps + ${singleQ} ตัวแยก</td></tr>
      </tfoot>
    </table>`;

  const noSeats = g.plan.filter(p => p.seats == null).length;
  document.getElementById('sg-plan-foot').innerHTML =
    `บันทึกการใช้โปรแกรมไว้ <b>${g.current_singles.toLocaleString()}</b> รายการ —
     ต้องมี <b>${bundleQ}</b> All Apps + <b>${singleQ}</b> ตัวแยก
     (คนที่อยู่ใน All Apps ใช้โปรแกรมข้างในได้เลย ไม่ต้องซื้อแยก ${g.cc.licenses.toLocaleString()} รายการ)` +
    (noSeats ? `<br><span style="color:#b45309">ยังไม่ได้ระบุจำนวนที่ซื้อ ${noSeats} รายการ —
       กรอกได้ที่ "จัดการคลัง Software" → ✏️ → จำนวนที่ซื้อ</span>` : '');

  // แยกตาม BU/ฝ่าย — คอลัมน์เท่ากับรายการในแผน
  const cols = singles.filter(p => p.qty).map(p => p.item);
  const cell = v => v ? v.toLocaleString() : '<span class="sv-off">·</span>';
  document.getElementById('sg-plan-bu').innerHTML = `
    <table class="sg-table">
      <thead><tr>
        <th>BU / ฝ่าย</th>
        <th class="sg-r sg-th-bundle">All Apps</th>
        ${cols.map(c => `<th class="sg-r" title="${esc(c)}">${esc(c.replace(/^Adobe /, ''))}</th>`).join('')}
        <th class="sg-r">รวม</th>
      </tr></thead>
      <tbody>
        ${g.plan_by_bu.map(b => {
          const row = (label, o, cls) => {
            const sum = o.allapps + cols.reduce((n, c) => n + (o.items[c] || 0), 0);
            return `<tr class="${cls}">
              <td>${label}</td>
              <td class="sg-r sg-cell-bundle">${cell(o.allapps)}</td>
              ${cols.map(c => `<td class="sg-r">${cell(o.items[c] || 0)}</td>`).join('')}
              <td class="sg-r"><b>${sum.toLocaleString()}</b></td>
            </tr>`;
          };
          return row(`<span class="bu-badge bu-${esc(b.bu_code)}">${esc(b.bu_code)}</span>`, b, 'sg-bu-row') +
            b.depts.map(d => row(`<span class="sg-dept">${esc(d.department)}</span>`, d, '')).join('');
        }).join('')}
      </tbody>
      <tfoot><tr>
        <td>รวมทุก BU</td>
        <td class="sg-r sg-cell-bundle">${bundleQ.toLocaleString()}</td>
        ${cols.map(c => `<td class="sg-r">${(singles.find(p => p.item === c) || {}).qty.toLocaleString()}</td>`).join('')}
        <td class="sg-r"><b>${(bundleQ + singleQ).toLocaleString()}</b></td>
      </tr></tfoot>
    </table>`;
}

function toggleSv(key) {
  svOpen[key] = !svOpen[key];
  renderSwVendor();
}

function expandSwVendor(open) {
  svOpen = {};
  if (open) {
    swVendor.by_bu.forEach(b => {
      svOpen['bu:' + b.bu_code] = true;
      b.depts.forEach(d => { svOpen[`dept:${b.bu_code}|${d.department}`] = true; });
    });
  }
  renderSwVendor();
}

function exportSwVendor(btn) {
  const bu = document.getElementById('sv-export-bu').value;
  _downloadXlsx(btn, '/api/software/export?vendor=' + encodeURIComponent(swVendor.vendor) +
                     (bu ? '&bu=' + encodeURIComponent(bu) : ''),
                'software_vendor.xlsx');
}

function exportSwVendorDeck(btn) {
  const bu = document.getElementById('sv-export-bu').value;
  _downloadXlsx(btn, '/api/software/vendor-presentation?name=' + encodeURIComponent(swVendor.vendor) +
                     (bu ? '&bu=' + encodeURIComponent(bu) : ''),
                'vendor_presentation.pptx');
}

function exportSoftwareDeck(btn) {
  const bu = document.getElementById('sd-bu').value;
  _downloadXlsx(btn, '/api/software/presentation' +
                     (bu && bu !== 'ไม่ระบุ BU' ? '?bu=' + encodeURIComponent(bu) : ''),
                'software_presentation.pptx');
}

function exportSoftware(btn) {
  const bu = document.getElementById('sd-bu').value;
  _downloadXlsx(btn, '/api/software/export' + (bu ? '?bu=' + encodeURIComponent(bu) : ''),
                'software.xlsx');
}

/** ดาวน์โหลดไฟล์ Excel จาก endpoint พร้อมสถานะบนปุ่ม */
async function _downloadXlsx(btn, url, fallbackName) {
  const old = btn.textContent;
  btn.disabled = true; btn.textContent = 'กำลังสร้างไฟล์...';
  try {
    const res = await fetch(url);
    if (!res.ok) throw new Error('export failed');
    const blob = await res.blob();
    const cd   = res.headers.get('Content-Disposition') || '';
    const m    = cd.match(/filename[^;=\n]*=(?:UTF-8''|")?([^;"\n]*)/i);
    const a    = document.createElement('a');
    a.href     = URL.createObjectURL(blob);
    a.download = m ? decodeURIComponent(m[1]) : fallbackName;
    document.body.appendChild(a); a.click(); a.remove();
    URL.revokeObjectURL(a.href);
    showToast('ดาวน์โหลดไฟล์แล้ว', 'success');
  } catch (e) {
    showToast('Export ไม่สำเร็จ', 'error');
  } finally {
    btn.disabled = false; btn.textContent = old;
  }
}

// ==============================
// ---- Export เครื่องเช่า (ทำรายงานขอเช่าปีถัดไป) ----
// ==============================

let rentalOpts = null;   // ตัวเลือก + จำนวนจาก /api/rental/export-options

/** โหลดตัวเลือกจากข้อมูลจริง — โหลดครั้งเดียวต่อการเปิดหน้า */
async function loadRentalExportOptions() {
  if (rentalOpts) return;
  try { rentalOpts = await api('/api/rental/export-options'); }
  catch (e) { return; }

  const o = rentalOpts;
  const chk = (group, val, label, n) => `
    <label class="rx-chk" data-g="${group}" data-v="${esc(val)}">
      <input type="checkbox" onchange="onRentalChk(this)">
      <span>${esc(label)}</span><span class="n">${n.toLocaleString()}</span>
    </label>`;

  document.getElementById('rx-bu').innerHTML =
    o.bus.map(b => chk('bu', b.bu_code, b.bu_code, b.count)).join('');
  document.getElementById('rx-year').innerHTML =
    o.years.map(y => chk('year', y.year, y.year, y.count)).join('') ||
    '<span style="font-size:.75rem;color:#94a3b8">ไม่มีเครื่องที่ระบุวันหมดสัญญา</span>';
  document.getElementById('rx-type').innerHTML =
    o.types.map(t => chk('machine_type', t.name, t.name, t.count)).join('');

  document.getElementById('rx-no-year').textContent = o.no_year.toLocaleString();
  document.getElementById('rx-no-type').textContent = o.no_type.toLocaleString();

  // เตือนไว้ตรงหัวข้อว่าข้อมูลไม่ครบแค่ไหน จะได้ไม่เข้าใจผิดว่ากรองแล้วได้ครบ
  const pct = n => Math.round(n / Math.max(1, o.total) * 100);
  if (o.no_bu)
    document.getElementById('rx-bu-note').textContent =
      `— ยังไม่ระบุ BU ${o.no_bu.toLocaleString()} เครื่อง (ไม่อยู่ในตัวเลือก)`;
  if (o.no_year)
    document.getElementById('rx-year-note').textContent =
      `— ไม่มีข้อมูล ${o.no_year.toLocaleString()} เครื่อง (${pct(o.no_year)}%)`;
  if (o.no_type)
    document.getElementById('rx-type-note').textContent =
      `— ไม่มีข้อมูล ${o.no_type.toLocaleString()} เครื่อง (${pct(o.no_type)}%)`;

  updateRentalPreview();
}

function onRentalChk(input) {
  input.closest('.rx-chk').classList.toggle('on', input.checked);
  updateRentalPreview();
}

function rentalPicked(group) {
  return [...document.querySelectorAll(`.rx-chk[data-g="${group}"] input:checked`)]
    .map(i => i.closest('.rx-chk').dataset.v);
}

/** นับล่วงหน้าว่าจะได้กี่เครื่อง — ให้เห็นผลก่อนกดดาวน์โหลด
 *  นับจาก count ของแต่ละตัวเลือกได้เฉพาะตอนกรองแกนเดียว ถ้ากรองหลายแกน
 *  จำนวนจริงเป็น intersection ซึ่งฝั่ง client ไม่มีข้อมูลพอจะคำนวณ */
function updateRentalPreview() {
  if (!rentalOpts) return;
  const o = rentalOpts;
  const bu = rentalPicked('bu'), yr = rentalPicked('year'), mt = rentalPicked('machine_type');

  // ช่อง "รวมที่ไม่มีข้อมูล" มีความหมายเฉพาะตอนกรองแกนนั้นจริงๆ
  document.getElementById('rx-inc-year-wrap').classList.toggle('show', yr.length > 0 && o.no_year > 0);
  document.getElementById('rx-inc-type-wrap').classList.toggle('show', mt.length > 0 && o.no_type > 0);

  const incY = document.getElementById('rx-inc-year').checked;
  const incT = document.getElementById('rx-inc-type').checked;
  const sum  = (list, picked, key) =>
    list.filter(x => picked.includes(x[key])).reduce((s, x) => s + x.count, 0);

  const axes = [bu.length, yr.length, mt.length].filter(n => n > 0).length;
  let txt;
  if (axes === 0) {
    txt = `ไม่ได้กรอง — จะได้ <b>${o.total.toLocaleString()}</b> เครื่อง (เครื่องเช่าทั้งหมด)`;
  } else if (axes === 1) {
    let n = bu.length ? sum(o.bus, bu, 'bu_code')
          : yr.length ? sum(o.years, yr, 'year') + (incY ? o.no_year : 0)
                      : sum(o.types, mt, 'name') + (incT ? o.no_type : 0);
    txt = `จะได้ <b>${n.toLocaleString()}</b> เครื่อง`;
  } else {
    txt = 'เลือกหลายเงื่อนไข — จำนวนจริงดูได้ในไฟล์ที่ดาวน์โหลด';
  }
  const parts = [];
  if (bu.length) parts.push('BU: ' + bu.join(', '));
  if (yr.length) parts.push('ปีหมดสัญญา: ' + yr.join(', ') + (incY ? ' + ไม่มีวันหมด' : ''));
  if (mt.length) parts.push(mt.length + ' ประเภทเครื่อง' + (incT ? ' + ยังไม่ระบุ' : ''));
  document.getElementById('rx-preview').innerHTML =
    txt + (parts.length ? ` <span style="color:#94a3b8">· ${esc(parts.join(' · '))}</span>` : '');
}

function clearRentalExport() {
  document.querySelectorAll('.rx-chk input:checked').forEach(i => {
    i.checked = false;
    i.closest('.rx-chk').classList.remove('on');
  });
  ['rx-inc-year', 'rx-inc-type'].forEach(id => document.getElementById(id).checked = false);
  updateRentalPreview();
}

function exportRental(btn) {
  const params = new URLSearchParams();
  const bu = rentalPicked('bu'), yr = rentalPicked('year'), mt = rentalPicked('machine_type');
  if (bu.length) params.set('bu', bu.join(','));
  if (yr.length) params.set('year', yr.join(','));
  if (mt.length) params.set('machine_type', mt.join(','));
  if (yr.length && document.getElementById('rx-inc-year').checked) params.set('include_no_year', '1');
  if (mt.length && document.getElementById('rx-inc-type').checked) params.set('include_no_type', '1');

  if (btn) {
    const orig = btn.innerHTML;
    btn.innerHTML = '⏳ กำลังสร้างไฟล์...';
    btn.disabled = true;
    setTimeout(() => { btn.innerHTML = orig; btn.disabled = false; }, 3500);
  }
  window.location = '/api/rental/export?' + params;
}

function scrollToAnomalyPanel(panelId) {
  const el = document.getElementById(panelId);
  if (!el) return;
  el.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

function toggleAnomalyPanel(panelId) {
  const el = document.getElementById(panelId);
  if (!el) return;
  el.style.display = el.style.display === 'none' ? '' : 'none';
}

function switchToAssets(status, ownership, edStatus) {
  // สลับไปแท็บ IT Assets แล้ว filter ตามที่กด
  document.querySelectorAll('.tab').forEach(b => b.classList.remove('active'));
  document.querySelector('.tab[data-tab="assets"]').classList.add('active');
  document.querySelectorAll('.tab-content').forEach(c => c.style.display = 'none');
  document.getElementById('tab-assets').style.display = '';
  if (!assetLoaded) { loadAssetMeta(); assetLoaded = true; }

  document.getElementById('a-filter-status').value     = status    || '';
  document.getElementById('a-filter-ownership').value  = ownership || '';
  const edEl = document.getElementById('a-filter-ed-status');
  if (edEl) edEl.value = edStatus || '';
  assetFilters.status    = status    || '';
  assetFilters.ownership = ownership || '';
  loadAssets();
}

// ==============================
// ---- eDevice Sync ----
// ==============================

let edSyncData = null;
let edCurrentTab = 'unmatched';

function _edShowPreview(data) {
  edSyncData = data;
  document.getElementById('ed-loading').style.display = 'none';
  document.getElementById('ed-result').style.display = '';
  document.getElementById('ed-footer').style.display = 'flex';
  document.getElementById('ed-refresh-btn').disabled = false;

  const s = data.stats;
  document.getElementById('ed-total').textContent        = (s.total || 0).toLocaleString();
  document.getElementById('ed-matched-code').textContent = (s.matched_code || 0).toLocaleString();
  document.getElementById('ed-matched-name').textContent = (s.matched_name || 0).toLocaleString();
  document.getElementById('ed-unmatched').textContent    = (s.unmatched || 0).toLocaleString();

  const codeCount = (data.code_updates || []).length;
  document.getElementById('ed-code-update-info').textContent =
    codeCount
      ? `🔑 พบ ${codeCount} รายการที่สามารถอัพเดทรหัสพนักงานได้อัตโนมัติ`
      : 'ไม่มีรหัสพนักงานที่ต้องอัพเดท';

  document.getElementById('ed-unmatched-badge').textContent = s.unmatched || '';
  document.getElementById('ed-code-badge').textContent      = codeCount || '';

  const source = data.cached_file ? 'ใช้ข้อมูลจากไฟล์ cache' : 'ดึงข้อมูลสดจาก eDevice';
  document.getElementById('ed-subtitle').textContent =
    `Asset ทั้งหมด ${s.total} รายการ · ${source}`;

  showEdTab('unmatched');
}

let _edPollTimer = null;

async function startEdeviceFetch() {
  document.getElementById('ed-refresh-btn').disabled = true;
  document.getElementById('ed-result').style.display = 'none';
  document.getElementById('ed-footer').style.display = 'none';
  document.getElementById('ed-loading').style.display = '';
  document.getElementById('ed-loading-text').textContent = 'กำลังดึงข้อมูลจาก eDevice...';
  document.getElementById('ed-fetch-progress').style.display = '';
  document.getElementById('ed-subtitle').textContent = 'กำลังดึงข้อมูล (ใช้เวลา ~3-5 นาที)';

  await api('/api/sync/edevice/fetch-start', 'POST', {});
  _pollEdeviceFetch();
}

function _pollEdeviceFetch() {
  if (_edPollTimer) clearTimeout(_edPollTimer);
  _edPollTimer = setTimeout(async () => {
    try {
      const s = await api('/api/sync/edevice/fetch-status');
      const bar = document.getElementById('ed-progress-bar');
      if (s.total > 0) {
        bar.classList.remove('indeterminate');
        const pct = Math.round(s.count / s.total * 100);
        bar.style.width = pct + '%';
        document.getElementById('ed-progress-text').textContent =
          `${s.count.toLocaleString()} / ${s.total.toLocaleString()} รายการ (${pct}%)`;
      } else if (s.running) {
        bar.classList.add('indeterminate');
        document.getElementById('ed-progress-text').textContent = s.phase || 'กำลังเชื่อมต่อและโหลดรายการ...';
      }
      if (s.running) {
        _pollEdeviceFetch();
      } else if (s.error) {
        document.getElementById('ed-subtitle').textContent = 'ดึงข้อมูลไม่สำเร็จ';
        document.getElementById('ed-loading-text').textContent = '❌ ' + s.error;
        document.getElementById('ed-refresh-btn').disabled = false;
      } else if (s.cache_ready) {
        document.getElementById('ed-loading-text').textContent = 'กำลังวิเคราะห์ข้อมูล...';
        document.getElementById('ed-fetch-progress').style.display = 'none';
        const data = await api('/api/sync/edevice/preview');
        _edShowPreview(data);
      }
    } catch (e) { _pollEdeviceFetch(); }
  }, 3000);
}

async function openEdeviceSyncModal() {
  if (_edPollTimer) { clearTimeout(_edPollTimer); _edPollTimer = null; }
  edSyncData = null;
  document.getElementById('ed-loading').style.display = '';
  document.getElementById('ed-fetch-progress').style.display = 'none';
  document.getElementById('ed-loading-text').textContent = 'กำลังวิเคราะห์ข้อมูล...';
  document.getElementById('ed-result').style.display = 'none';
  document.getElementById('ed-footer').style.display = 'none';
  document.getElementById('ed-subtitle').textContent = 'กำลังโหลด...';
  document.getElementById('edevice-overlay').classList.add('open');

  try {
    // ตรวจก่อนว่า background fetch กำลังทำงานอยู่ไหม
    const status = await api('/api/sync/edevice/fetch-status');
    if (status.running) {
      document.getElementById('ed-subtitle').textContent = 'กำลังดึงข้อมูล (ใช้เวลา ~3-5 นาที)';
      document.getElementById('ed-fetch-progress').style.display = '';
      _pollEdeviceFetch();
      return;
    }
    if (!status.cache_ready) {
      // ยังไม่มี cache — เริ่ม background fetch ทันที
      await startEdeviceFetch();
      return;
    }
    const data = await api('/api/sync/edevice/preview');
    _edShowPreview(data);
  } catch (e) {
    document.getElementById('ed-subtitle').textContent = 'เชื่อมต่อไม่สำเร็จ';
    document.getElementById('ed-loading').innerHTML =
      '<div style="text-align:center;padding:40px;color:#dc2626">❌ โหลดข้อมูล eDevice ไม่สำเร็จ</div>';
  }
}

function closeEdeviceSyncModal() {
  document.getElementById('edevice-overlay').classList.remove('open');
  edSyncData = null;
  if (_edPollTimer) { clearTimeout(_edPollTimer); _edPollTimer = null; }
}

function closeEdeviceOnOverlay(e) {
  if (e.target === document.getElementById('edevice-overlay')) closeEdeviceSyncModal();
}

function showEdTab(tab) {
  edCurrentTab = tab;
  ['unmatched', 'code_update'].forEach(t => {
    document.getElementById(`ed-tab-${t}`)?.classList.toggle('active', t === tab);
  });

  const list = document.getElementById('ed-list');
  if (!edSyncData) return;

  const empty = msg =>
    `<div style="text-align:center;padding:24px;color:#16a34a;font-size:.85rem">✓ ${msg}</div>`;

  if (tab === 'unmatched') {
    const rows = edSyncData.unmatched || [];
    if (!rows.length) { list.innerHTML = empty('ไม่มี Asset ที่หาพนักงานไม่พบ'); return; }
    list.innerHTML = rows.map(r => `
      <div class="sync-row">
        <div style="flex:1;min-width:0">
          <strong>${esc(r.emp_name || '—')}</strong>
          ${r.emp_code ? `<span style="font-size:.75rem;color:#94a3b8;margin-left:6px">รหัส: ${esc(r.emp_code)}</span>` : ''}
        </div>
        <span style="font-size:.75rem;color:#64748b">${esc(r.bu_th || '')}</span>
        <span style="font-size:.73rem;color:#94a3b8;font-family:monospace">${esc(r.computer_id)}</span>
        <span style="font-size:.75rem;color:#dc2626;font-weight:600">❓ ไม่พบ</span>
      </div>`).join('');

  } else if (tab === 'code_update') {
    const rows = edSyncData.code_updates || [];
    if (!rows.length) { list.innerHTML = empty('ไม่มีรหัสพนักงานที่ต้องอัพเดท'); return; }
    list.innerHTML = rows.map(r => `
      <div class="sync-row">
        <div style="flex:1;min-width:0">
          <strong>${esc(r.name)}</strong>
        </div>
        <span style="font-size:.75rem;color:#2563eb">รหัสใหม่: <strong>${esc(r.emp_code)}</strong></span>
        <span style="font-size:.75rem;color:#7e22ce;font-weight:600">🔑 อัพเดท</span>
      </div>`).join('');
  }
}

async function applyEdeviceSync() {
  const btn = document.getElementById('ed-confirm-btn');
  btn.disabled = true;
  btn.textContent = 'กำลัง Sync...';

  try {
    const r = await api('/api/sync/edevice/apply', 'POST', { force_live: false });
    showToast(
      `Sync eDevice เสร็จสิ้น · กำหนด ${r.assigned} · อัพเดทรหัส ${r.code_updated} · ข้าม ${r.skipped}`,
      'success'
    );
    closeEdeviceSyncModal();
    loadAssetEmpMap();
    if (assetLoaded) loadAssets(true);
  } catch (e) {
    showToast('Sync eDevice ไม่สำเร็จ', 'error');
  } finally {
    btn.disabled = false;
    btn.textContent = '✓ ยืนยัน Sync';
  }
}

// ============================================================
//  กำหนดคุณสมบัติเครื่องคอมพิวเตอร์ (ประเภทเครื่อง × BU)
// ============================================================
let specsLoaded  = false;
let specsData    = null;                 // { types, bus, specs }
const specDirty  = new Map();            // key(ประเภท+BU) → ข้อความที่แก้แล้วยังไม่บันทึก
const specClosed = new Set();            // ชื่อประเภทที่ย่ออยู่

// ชื่อประเภทเครื่องมีช่องว่างในตัวเอง — ใช้ตัวคั่นที่ไม่มีทางอยู่ในข้อมูล
const SPEC_SEP = '\u0000';
function specKey(mt, bu) { return mt + SPEC_SEP + bu; }

function specValue(mt, bu) {
  const k = specKey(mt, bu);
  if (specDirty.has(k)) return specDirty.get(k);
  return specsData?.specs?.[mt]?.[bu]?.spec || '';
}

async function loadMachineSpecs() {
  const wrap = document.getElementById('spec-list');
  try {
    specsData = await api('/api/machine-specs');
  } catch (e) {
    wrap.innerHTML = `<div class="empty-state"><div class="empty-icon">⚠️</div>โหลดข้อมูลไม่สำเร็จ: ${esc(e.error || e.message)}</div>`;
    return;
  }
  specsLoaded = true;

  // ตัวกรอง BU
  const sel = document.getElementById('spec-bu-filter');
  sel.innerHTML = '<option value="">ทุก BU</option>' +
    specsData.bus.map(b => `<option value="${esc(b.bu_code)}">${esc(b.bu_code)} — ${esc(b.bu)}</option>`).join('');
  sel.onchange = () => { specClosed.clear(); renderMachineSpecs(); };

  // ค่าเริ่มต้น: กางทุกการ์ด — เห็นคุณสมบัติทุกประเภท × ทุก BU ได้ในหน้าเดียว
  specClosed.clear();
  renderMachineSpecs();
}

function specVisibleBus() {
  const f = document.getElementById('spec-bu-filter').value;
  return f ? specsData.bus.filter(b => b.bu_code === f) : specsData.bus;
}

function _baht(n) {
  return n == null ? '—' : Math.round(n).toLocaleString('en-US');
}

/** รุ่นที่ BU นี้เคยเช่ามาในอดีต สำหรับประเภทเครื่องนี้ — ใช้อ้างอิงตอนกำหนด spec
 *  ความสูงกล่องตั้งจาก equalizeSpecHistHeights() ให้เท่ากันในบรรทัดเดียวกัน
 *  เพื่อให้ textarea ด้านล่างเรียงตรงกันเทียบด้วยตาได้ */
function specHistoryHtml(mt, buCode) {
  const list = specsData.history?.[mt]?.[buCode] || [];
  if (!list.length) {
    return `<div class="spec-hist"><div class="spec-hist-none">— ไม่เคยเช่าประเภทนี้ —</div></div>`;
  }

  const total    = list.reduce((n, h) => n + h.count, 0);
  const sumMonth = list.reduce((n, h) => n + (h.monthly_total || 0), 0);

  const chips = list.map((h, i) => {
    const tip = [
      esc(h.model),
      `${h.count} เครื่อง`,
      _specYears(h) ? `เริ่มเช่าปี ${_specYears(h)}` : 'ไม่มีข้อมูลปีที่เริ่มเช่า',
      h.monthly == null
        ? 'ไม่มีข้อมูลค่าเช่า'
        : `ค่าเช่า ${_baht(h.monthly)}/เครื่อง/เดือน` +
          (h.monthly_min !== h.monthly_max ? ` (${_baht(h.monthly_min)}-${_baht(h.monthly_max)})` : '') +
          (h.monthly_known < h.count ? ` · มีตัวเลข ${h.monthly_known}/${h.count} เครื่อง` : '') +
          ` · รวม ${_baht(h.monthly_total)}/เดือน`,
      h.last_end ? `สัญญาหมดล่าสุด ${esc(h.last_end)}` : '',
      'คลิกจำนวนเพื่อดูผู้ถือครอง',
    ].filter(Boolean).join('\n');

    const yr = _specYears(h);
    return `
      <div class="spec-hist-item">
        <span class="spec-hist-chip" title="${tip}">
          <span class="spec-hist-model">${esc(h.model)}</span>
          <span class="spec-hist-year ${yr ? '' : 'na'}">${yr || '—'}</span>
          <span class="spec-hist-rate ${h.monthly == null ? 'na' : ''}">${
            h.monthly == null ? '—' : _baht(h.monthly)}</span>
          <button type="button" class="spec-hist-count" title="ดูผู้ถือครอง"
                  onclick="toggleSpecHolders(this)"
                  data-mt="${esc(mt)}" data-bu="${esc(buCode)}" data-i="${i}">${h.count} ▾</button>
        </span>
      </div>`;
  }).join('');

  return `
    <div class="spec-hist">
      <div class="spec-hist-label">รุ่นที่เคยเช่า <span>${list.length} รุ่น · ${total} เครื่อง${
        sumMonth ? ' · ' + _baht(sumMonth) + '/ด.' : ''}</span></div>
      <div class="spec-hist-sub">
        <span>รุ่น</span><span>ปีเริ่ม</span><span>฿/เครื่อง/ด.</span><span>จำนวน</span>
      </div>
      <div class="spec-hist-chips">${chips}</div>
    </div>`;
}

/** รายงาน PDF สรุปคุณสมบัติที่แต่ละ BU กำหนด — ตามตัวกรอง BU ที่เลือกอยู่ */
function downloadSpecReport() {
  const bu = document.getElementById('spec-bu-filter').value;
  window.location = '/api/machine-specs/report.pdf' + (bu ? '?bu=' + encodeURIComponent(bu) : '');
}

/** ปีที่เริ่มเช่า — ปีเดียว "2023", ต่อเนื่อง "2022–24", กระโดด "2020, 2023" */
function _specYears(h) {
  const ys = h.years || [];
  if (!ys.length) return '';
  if (ys.length === 1) return String(ys[0]);
  if (ys[ys.length - 1] - ys[0] === ys.length - 1) {
    return ys[0] + '–' + String(ys[ys.length - 1]).slice(-2);
  }
  return ys.map((y, i) => (i ? String(y).slice(-2) : y)).join(',');
}

const SPEC_STATUS_TH = {
  ok: 'ปกติ', warning: 'ใกล้หมด', critical: 'ใกล้หมด', expired: 'หมดอายุ',
  returned: 'คืนแล้ว', unknown: 'ไม่มีวันหมด',
};

/** กาง/พับ รายละเอียดผู้ถือครองของรุ่นนั้น เมื่อคลิกที่จำนวน */
function toggleSpecHolders(btn) {
  const item = btn.closest('.spec-hist-item');
  const card = btn.closest('.spec-card');
  const open = item.querySelector('.spec-hist-holders');
  if (open) {
    open.remove();
    btn.classList.remove('open');
    equalizeSpecHistHeights(card);
    return;
  }
  const h = specsData.history?.[btn.dataset.mt]?.[btn.dataset.bu]?.[+btn.dataset.i];
  const rows = (h?.holders || []).map(x => `
    <div class="spec-holder">
      <span class="spec-holder-name">${esc(x.name || '— ไม่ระบุผู้ถือครอง —')}</span>
      <span class="spec-holder-pos" title="${esc(x.position)}">${esc(x.position || '—')}</span>
      <span class="spec-holder-date">${esc((x.start_date || '—').slice(0, 7))}</span>
      <span class="spec-holder-st st-${esc(x.status)}">${esc(SPEC_STATUS_TH[x.status] || x.status || '—')}</span>
    </div>`).join('');

  item.insertAdjacentHTML('beforeend', `
    <div class="spec-hist-holders">
      <div class="spec-holder-head">
        <span>ผู้ถือครอง</span><span>ตำแหน่งงาน</span><span>เริ่ม</span><span>สถานะ</span>
      </div>
      ${rows || '<div class="spec-holder-none">— ไม่มีข้อมูล —</div>'}
    </div>`);
  btn.classList.add('open');
  equalizeSpecHistHeights(card);
}

// จำนวนคอลัมน์ต่อบรรทัด — 7 BU จะตกเป็น 3 บรรทัด (3+3+1) ไม่แน่นและไม่ต้องเลื่อนแนวนอน
const SPEC_COLS_PER_ROW = 3;

function renderMachineSpecs() {
  const bus  = specVisibleBus();
  const nCol = Math.min(SPEC_COLS_PER_ROW, bus.length);

  document.getElementById('spec-list').innerHTML = specsData.types.map(t => {
    const filled = bus.filter(b => specValue(t.name, b.bu_code).trim()).length;
    const isDirty = bus.some(b => specDirty.has(specKey(t.name, b.bu_code)));

    // แต่ละ BU = 1 คอลัมน์ ตกบรรทัดละ 3 คอลัมน์ — ใน 1 บรรทัดเทียบคุณสมบัติด้วยตาได้ทันที
    const cols = bus.map(b => {
      const cur   = specValue(t.name, b.bu_code);
      const dirty = specDirty.has(specKey(t.name, b.bu_code));
      const meta  = specsData.specs?.[t.name]?.[b.bu_code];
      return `
        <div class="spec-bu-col bu-c-${esc(b.bu_code)} ${dirty ? 'dirty' : ''}">
          <div class="spec-bu-head">
            <span class="bu-badge bu-${esc(b.bu_code)}">${esc(b.bu_code)}</span>
            <span class="spec-bu-name">${esc(b.bu)}</span>
          </div>
          ${specHistoryHtml(t.name, b.bu_code)}
          <div class="spec-input-label">✎ คุณสมบัติที่จะ เช่า/ซื้อ ปีนี้</div>
          <textarea rows="6" class="${dirty ? 'dirty' : ''}"
                    data-mt="${esc(t.name)}" data-bu="${esc(b.bu_code)}"
                    oninput="onSpecInput(this)"
                    placeholder="ระบุคุณสมบัติที่ ${esc(b.bu_code)} ต้องการ เช่น\nCPU\nRAM\nStorage\nจอ\nระบบปฏิบัติการ">${esc(cur)}</textarea>
          <div class="spec-bu-updated">${dirty ? '● ยังไม่บันทึก'
                                      : meta?.updated_at ? 'บันทึก ' + esc(meta.updated_at) : '—'}</div>
        </div>`;
    }).join('');

    return `
      <div class="spec-card mt-${t.no} ${specClosed.has(t.name) ? 'collapsed' : ''} ${isDirty ? 'dirty' : ''}"
           data-mt="${esc(t.name)}">
        <div class="spec-card-head" onclick="toggleSpecCard(this)">
          <div class="spec-no">${t.no}</div>
          <div class="spec-titles">
            <div class="spec-name">${esc(t.name)}</div>
            <div class="spec-full">${esc(t.full_name)}</div>
          </div>
          <span class="spec-filled-badge ${filled === bus.length ? 'done' : ''}">กรอกแล้ว ${filled}/${bus.length} BU</span>
          <span class="spec-caret">▼</span>
        </div>
        <div class="spec-card-body">
          <div class="spec-bu-grid" data-cols="${nCol}"
               style="grid-template-columns:repeat(${nCol},minmax(0,1fr));min-width:${nCol * 250 + (nCol - 1) * 12}px">
            ${cols}
          </div>
        </div>
        <div class="spec-card-foot">
          <button class="btn btn-primary" onclick="saveMachineSpecs(this)">
            💾 บันทึกประเภทนี้
          </button>
        </div>
      </div>`;
  }).join('');

  equalizeSpecHistHeights();
  updateSpecDirtyInfo();
}

/** กล่อง "รุ่นที่เคยเช่า" สูงพอดีเนื้อหา ไม่ต้องมีแถบเลื่อนในกล่อง
 *  เท่ากัน "ต่อบรรทัด" (ทีละ nCol คอลัมน์) ไม่ใช่ทั้งการ์ด — พอให้ช่องกรอกใน
 *  บรรทัดเดียวกันเริ่มระดับเดียวกัน โดยไม่ลากบรรทัดอื่นให้สูงตาม BU ที่มีรุ่นเยอะ
 *  วัดจาก DOM จริงแทนคำนวณพิกเซล — ไม่ต้องแก้ตามเมื่อขนาดฟอนต์เปลี่ยน
 *  ใช้ getBoundingClientRect ไม่ใช่ scrollHeight เพราะ box-sizing:border-box ทั้งโปรเจกต์
 *  (scrollHeight ไม่นับเส้นขอบ → ตั้ง height เท่านั้นจะล้น 2px แล้วขึ้นแถบเลื่อน) */
function equalizeSpecHistHeights(card) {
  const cards = card ? [card] : document.querySelectorAll('.spec-card');
  cards.forEach(c => {
    if (c.classList.contains('collapsed')) return;   // วัดไม่ได้ตอนย่อ — ไว้วัดตอนกาง
    const grid  = c.querySelector('.spec-bu-grid');
    const nCol  = Math.max(1, +grid.dataset.cols || 1);
    const boxes = [...c.querySelectorAll('.spec-hist')];
    boxes.forEach(b => { b.style.height = 'auto'; });
    for (let i = 0; i < boxes.length; i += nCol) {
      const band = boxes.slice(i, i + nCol);
      const max  = Math.max(...band.map(b => b.getBoundingClientRect().height));
      band.forEach(b => { b.style.height = Math.ceil(max) + 'px'; });
    }
  });
}

function onSpecInput(el) {
  const mt = el.dataset.mt, bu = el.dataset.bu, k = specKey(mt, bu);
  const orig = specsData.specs?.[mt]?.[bu]?.spec || '';
  if (el.value === orig) specDirty.delete(k); else specDirty.set(k, el.value);
  const col = el.closest('.spec-bu-col');
  el.classList.toggle('dirty', specDirty.has(k));
  col.classList.toggle('dirty', specDirty.has(k));
  const upd = col.querySelector('.spec-bu-updated');
  const at  = specsData.specs?.[mt]?.[bu]?.updated_at;
  upd.textContent = specDirty.has(k) ? '● ยังไม่บันทึก' : at ? 'บันทึก ' + at : '—';
  el.closest('.spec-card').classList.toggle('dirty',
    specVisibleBus().some(b => specDirty.has(specKey(mt, b.bu_code))));
  updateSpecDirtyInfo();
}

function updateSpecDirtyInfo() {
  const n = specDirty.size;
  document.getElementById('spec-dirty-info').textContent = n ? `แก้ไข ${n} รายการ ยังไม่บันทึก` : '';
  document.getElementById('spec-save-all').disabled = n === 0;
}

function toggleSpecCard(headEl) {
  const card = headEl.closest('.spec-card');
  const mt   = card.dataset.mt;
  if (specClosed.has(mt)) specClosed.delete(mt); else specClosed.add(mt);
  card.classList.toggle('collapsed', specClosed.has(mt));
  equalizeSpecHistHeights(card);
}

function toggleAllSpecCards(open) {
  specClosed.clear();
  if (!open) specsData?.types.forEach(t => specClosed.add(t.name));
  document.querySelectorAll('.spec-card').forEach(c => c.classList.toggle('collapsed', !open));
  if (open) equalizeSpecHistHeights();
}

/** btn = ปุ่มในการ์ด → บันทึกเฉพาะประเภทนั้น; ไม่ส่ง → บันทึกทุกรายการที่แก้ไว้ */
async function saveMachineSpecs(btn) {
  const machineType = btn ? btn.closest('.spec-card').dataset.mt : null;
  const items = [];
  for (const [k, spec] of specDirty) {
    const [mt, bu] = k.split(SPEC_SEP);
    if (machineType && mt !== machineType) continue;
    items.push({ machine_type: mt, bu_code: bu, spec });
  }
  if (!items.length) {
    showToast(machineType ? 'ประเภทนี้ไม่มีการแก้ไข' : 'ไม่มีการแก้ไข');
    return;
  }

  try {
    await api('/api/machine-specs', 'POST', { items });
  } catch (e) {
    showToast('บันทึกไม่สำเร็จ: ' + (e.error || e.message), 'error');
    return;
  }

  // merge ค่าที่บันทึกแล้วเข้า specsData แล้วเคลียร์ dirty เฉพาะรายการที่ส่งไป
  const now = new Date().toLocaleString('sv-SE').replace('T', ' ');
  items.forEach(it => {
    const store = specsData.specs[it.machine_type] || (specsData.specs[it.machine_type] = {});
    if (it.spec.trim()) store[it.bu_code] = { spec: it.spec, updated_at: now };
    else delete store[it.bu_code];
    specDirty.delete(specKey(it.machine_type, it.bu_code));
  });

  renderMachineSpecs();
  showToast(`บันทึกคุณสมบัติแล้ว ${items.length} รายการ`, 'success');
}

window.addEventListener('beforeunload', e => {
  if (specDirty.size) { e.preventDefault(); e.returnValue = ''; }
});

// ---- Helpers ----
// ==============================
// ---- Dashboard: บริหาร Printer ----
// ==============================

let printers   = null;   // ผลจาก /api/printers {rows, summary, by_building}
let prEditId   = null;   // id เครื่องที่กำลังแก้ (null = เพิ่มใหม่)

const PR_STATUS = {
  expired: { label: 'หมดสัญญาแล้ว', cls: 'expired' },
  soon:    { label: 'ใกล้หมด',       cls: 'soon' },
  active:  { label: 'อยู่ในสัญญา',   cls: 'active' },
  none:    { label: 'ไม่ระบุสัญญา',  cls: 'none' },
};

const _prMoney = v => v == null ? '—'
  : Number(v).toLocaleString('th-TH', { minimumFractionDigits: 2, maximumFractionDigits: 4 });
const _prPct = p => p == null ? '<span class="sv-off">—</span>'
  : p > 0 ? `<span class="pr-up">▲ ${p.toLocaleString('th-TH')}%</span>`
  : p < 0 ? `<span class="pr-down">▼ ${Math.abs(p).toLocaleString('th-TH')}%</span>`
  : '<span class="pr-same">0%</span>';
const _prBE = y => y ? String(y + 543) : '—';   // เก็บ ค.ศ. แสดง พ.ศ.

async function loadPrinters(force) {
  if (printers && !force) { renderPrinters(); return; }
  document.getElementById('pr-table-wrap').innerHTML =
    '<div style="text-align:center;padding:24px;color:#94a3b8">กำลังโหลด...</div>';
  try {
    printers = await api('/api/printers');
  } catch (e) {
    document.getElementById('pr-table-wrap').innerHTML =
      '<div class="sw-empty">โหลดข้อมูลไม่สำเร็จ</div>';
    return;
  }
  // ตัวเลือกในตัวกรอง + ช่องกรอกในฟอร์ม มาจากข้อมูลที่มีอยู่
  const uniq = f => [...new Set(printers.rows.map(r => r[f]).filter(Boolean))]
                      .sort((a, b) => a.localeCompare(b));
  const fillSel = (id, label, vals) => {
    const el = document.getElementById(id), keep = el.value;
    el.innerHTML = `<option value="">${label}</option>` +
      vals.map(v => `<option value="${esc(v)}">${esc(v)}</option>`).join('');
    el.value = vals.includes(keep) ? keep : '';
  };
  fillSel('pr-building', 'ทุกอาคาร', uniq('building'));
  fillSel('pr-brand', 'ทุกยี่ห้อ', uniq('brand'));
  const fillList = (id, vals) => {
    document.getElementById(id).innerHTML = vals.map(v => `<option value="${esc(v)}">`).join('');
  };
  fillList('pf-brand-list', uniq('brand'));
  fillList('pf-building-list', uniq('building'));
  fillList('pf-ink-list', [...new Set(['Toner ขาวดำ', 'Toner สี', 'Ink Tank', 'Ink Cartridge',
                                        ...uniq('ink_type')])]);
  fillList('pf-paper-list', [...new Set(['A4', 'A3', 'A4, A3', 'A4, A3, B4', ...uniq('paper')])]);
  renderPrinters();
}

function renderPrinters() {
  const s = printers.summary;
  document.getElementById('pr-total').textContent = s.total.toLocaleString();
  document.getElementById('pr-total-sub').textContent =
    printers.by_building.length ? `${printers.by_building.length} อาคาร` : 'ยังไม่มีข้อมูล — กด "＋ เพิ่มเครื่อง"';
  document.getElementById('pr-age').textContent = s.avg_age == null ? '—' : `${s.avg_age} ปี`;
  document.getElementById('pr-age-sub').textContent =
    s.old_5y ? `ใช้งานมาแล้ว 5 ปีขึ้นไป ${s.old_5y} เครื่อง` : '';
  document.getElementById('pr-contract').textContent = (s.expired + s.soon).toLocaleString();
  document.getElementById('pr-contract-sub').textContent =
    `หมดแล้ว ${s.expired} · เหลือ ≤ ${s.soon_days} วัน ${s.soon}` +
    (s.no_contract ? ` · ไม่ระบุ ${s.no_contract}` : '') + ' ▾';
  const ch = document.getElementById('pr-change');
  ch.innerHTML = s.avg_change == null ? '—' : _prPct(s.avg_change);
  document.getElementById('pr-change-sub').textContent =
    s.avg_change == null ? 'ยังไม่มีข้อมูลราคาเดิม/ใหม่' : `เพิ่มขึ้น ${s.up} เครื่อง · ลดลง ${s.down} เครื่อง`;

  // ตัวกรอง
  const q  = (document.getElementById('pr-search').value || '').trim().toLowerCase();
  const bd = document.getElementById('pr-building').value;
  const br = document.getElementById('pr-brand').value;
  const st = document.getElementById('pr-status').value;
  const rows = printers.rows.filter(r =>
    (!q || ['brand', 'model', 'serial_no', 'building', 'ink_type', 'paper', 'note']
             .some(f => (r[f] || '').toLowerCase().includes(q))) &&
    (!bd || r.building === bd) &&
    (!br || r.brand === br) &&
    (!st || (st === 'due' ? ['expired', 'soon'].includes(r.contract_status)
                          : r.contract_status === st)));

  // แยกตามอาคาร — คลิกเพื่อกรอง
  document.getElementById('pr-buildings').innerHTML = printers.by_building.length > 1
    ? printers.by_building.map(([b, n]) => `
        <span class="pr-bchip${bd === b ? ' on' : ''}" onclick="setPrinterBuilding('${esc(b).replace(/'/g, '&#39;')}')">
          ${esc(b)} <b>${n}</b></span>`).join('')
    : '';

  const wrap = document.getElementById('pr-table-wrap');
  if (!printers.rows.length) {
    wrap.innerHTML = '<div class="sw-empty">ยังไม่มีเครื่องในระบบ — กด "＋ เพิ่มเครื่อง" เพื่อเริ่มบันทึก</div>';
    return;
  }
  if (!rows.length) {
    wrap.innerHTML = '<div class="sw-empty">ไม่พบเครื่องตามตัวกรอง</div>';
    return;
  }
  wrap.innerHTML = `
    <table class="pr-table">
      <thead><tr>
        <th>ยี่ห้อ</th><th>รุ่น</th><th>อาคารที่ตั้ง</th><th>เลขเครื่อง</th><th>ชนิดหมึก</th>
        <th class="r">สำเนา/นาที</th><th class="r">ปีที่ซื้อ</th><th class="r">อายุ</th><th>กระดาษ</th>
        <th class="r">ค่าสำเนา<br>ราคาเดิม</th><th class="r">ค่าสำเนา<br>ราคาใหม่</th><th class="r">เพิ่ม/ลด</th>
        <th>สัญญา (เริ่มต้น – สิ้นสุด)</th><th></th>
      </tr></thead>
      <tbody>
        ${rows.map(r => {
          const S = PR_STATUS[r.contract_status];
          const left = r.contract_status === 'soon' ? ` · เหลือ ${r.days_left} วัน`
                     : r.contract_status === 'expired' ? ` · เลยมา ${-r.days_left} วัน` : '';
          return `
          <tr>
            <td class="b">${esc(r.brand) || '—'}</td>
            <td>${esc(r.model) || '—'}</td>
            <td>${esc(r.building) || '<span class="sv-off">—</span>'}</td>
            <td class="mono">${esc(r.serial_no) || '—'}</td>
            <td>${esc(r.ink_type) || '—'}</td>
            <td class="r">${r.ppm != null ? r.ppm.toLocaleString() : '—'}</td>
            <td class="r">${_prBE(r.purchase_year)}</td>
            <td class="r${r.age_years >= 5 ? ' pr-old' : ''}">${r.age_years != null ? r.age_years + ' ปี' : '—'}</td>
            <td>${esc(r.paper) || '—'}</td>
            <td class="r">${_prMoney(r.price_old)}</td>
            <td class="r"><b>${_prMoney(r.price_new)}</b></td>
            <td class="r">${_prPct(r.change_pct)}</td>
            <td class="nowrap">
              ${r.contract_start || r.contract_end
                ? `${_dateFmt(r.contract_start)} – ${_dateFmt(r.contract_end)}` : ''}
              <div><span class="pr-st ${S.cls}">${S.label}${left}</span></div>
            </td>
            <td class="nowrap">
              <button class="icon-btn edit" onclick="openPrinterForm(${r.id})" title="แก้ไข">✏️</button>
              <button class="icon-btn del" onclick="deletePrinter(${r.id})" title="ลบ">🗑️</button>
            </td>
          </tr>`;
        }).join('')}
      </tbody>
      <tfoot><tr><td colspan="14">แสดง ${rows.length.toLocaleString()} จาก ${printers.rows.length.toLocaleString()} เครื่อง</td></tr></tfoot>
    </table>`;
}

function setPrinterStatusFilter(v) {
  document.getElementById('pr-status').value = v;
  if (printers) renderPrinters();
}

function setPrinterBuilding(b) {
  const el = document.getElementById('pr-building');
  el.value = el.value === b ? '' : b;
  renderPrinters();
}

const PF_FIELDS = {
  brand: 'pf-brand', model: 'pf-model', building: 'pf-building', serial_no: 'pf-serial',
  ink_type: 'pf-ink', ppm: 'pf-ppm', purchase_year: 'pf-year', paper: 'pf-paper',
  price_old: 'pf-price-old', price_new: 'pf-price-new',
  contract_start: 'pf-start', contract_end: 'pf-end', note: 'pf-note',
};

function openPrinterForm(id) {
  const r = id ? printers.rows.find(x => x.id === id) : null;
  prEditId = r ? r.id : null;
  document.getElementById('pr-form-title').textContent = r ? 'แก้ไขเครื่อง Printer' : 'เพิ่มเครื่อง Printer';
  Object.entries(PF_FIELDS).forEach(([f, el]) => {
    let v = r ? r[f] : '';
    if (f === 'purchase_year' && v) v = v + 543;   // แสดงเป็น พ.ศ.
    document.getElementById(el).value = v == null ? '' : v;
  });
  prSetError('');
  updatePrinterPreview();
  document.getElementById('printer-overlay').classList.add('open');
  document.getElementById('pf-brand').focus();
}

function closePrinterForm() {
  document.getElementById('printer-overlay').classList.remove('open');
}

function prSetError(msg) {
  const el = document.getElementById('pf-error');
  el.textContent = msg || '';
  el.style.display = msg ? '' : 'none';
}

/** อายุ และ % ราคาเปลี่ยน คำนวณให้ดูทันทีขณะกรอก */
function updatePrinterPreview() {
  let y = parseInt(document.getElementById('pf-year').value);
  if (y > 2400) y -= 543;
  const age = y ? new Date().getFullYear() - y : null;
  document.getElementById('pf-age').innerHTML =
    age != null && age >= 0 ? `${age} ปี <span class="pf-hint">(ซื้อปี พ.ศ. ${y + 543})</span>` : '—';

  const po = parseFloat(document.getElementById('pf-price-old').value);
  const pn = parseFloat(document.getElementById('pf-price-new').value);
  const el = document.getElementById('pf-change');
  if (po > 0 && !isNaN(pn)) {
    const pct = Math.round((pn - po) / po * 10000) / 100;
    const diff = Math.round((pn - po) * 10000) / 10000;
    el.innerHTML = `${_prPct(pct)} <span class="pf-hint">(${diff >= 0 ? '+' : '−'}${_prMoney(Math.abs(diff))} บาท/แผ่น)</span>`;
  } else {
    el.textContent = '—';
  }
}

async function savePrinter() {
  const body = {};
  Object.entries(PF_FIELDS).forEach(([f, el]) => { body[f] = document.getElementById(el).value.trim(); });
  if (!body.brand && !body.model && !body.serial_no) {
    prSetError('กรอกอย่างน้อย ยี่ห้อ รุ่น หรือเลขเครื่อง'); return;
  }
  const btn = document.getElementById('pf-save-btn');
  btn.disabled = true;
  try {
    if (prEditId) await api(`/api/printers/${prEditId}`, 'PUT', body);
    else          await api('/api/printers', 'POST', body);
    showToast(prEditId ? 'แก้ไขข้อมูลเครื่องแล้ว' : 'เพิ่มเครื่องแล้ว', 'success');
    closePrinterForm();
    await loadPrinters(true);
  } catch (e) {
    prSetError(e.error || 'บันทึกไม่สำเร็จ');
  } finally {
    btn.disabled = false;
  }
}

async function deletePrinter(id) {
  const r = printers.rows.find(x => x.id === id);
  if (!r) return;
  const label = [r.brand, r.model, r.serial_no && `(${r.serial_no})`].filter(Boolean).join(' ');
  if (!confirm(`ลบเครื่อง ${label}${r.building ? ' ที่ ' + r.building : ''} ออกจากระบบ?`)) return;
  try {
    await api(`/api/printers/${id}`, 'DELETE');
    showToast('ลบเครื่องแล้ว', 'success');
    await loadPrinters(true);
  } catch (e) {
    showToast(e.error || 'ลบไม่สำเร็จ', 'error');
  }
}

function exportPrinters(btn) {
  _downloadXlsx(btn, '/api/printers/export', 'printers.xlsx');
}

async function api(url, method = 'GET', body) {
  const opts = { method, headers: {} };
  if (body) { opts.headers['Content-Type'] = 'application/json'; opts.body = JSON.stringify(body); }
  const res = await fetch(url, opts);
  if (!res.ok) {
    let errBody; try { errBody = await res.json(); } catch { errBody = { error: await res.text() }; }
    const err = new Error(errBody.error || res.statusText);
    err.error = errBody.error || res.statusText;
    throw err;
  }
  return res.json();
}

function esc(s) {
  if (!s) return '';
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

let toastTimer;
function showToast(msg, type = '') {
  const t = document.getElementById('toast');
  t.textContent = msg;
  t.className = 'toast show' + (type ? ' ' + type : '');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => t.classList.remove('show'), 3000);
}
