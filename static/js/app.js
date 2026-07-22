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

// ---- State ----
let currentPage = 1;
let totalPages  = 1;
let filters     = { q: '', bu: '', dept: '', status: '', hasAsset: false, noAsset: false };
let buMap       = {};  // bu_code -> bu name

// ---- Asset State ----
let assetLoaded = false;
let assetFilters = { q: '', type: '', bu: '', status: '', ownership: '', machine_type: '', position: '', dept: '' };
let _assetRawData = null;   // cache ผลดิบจาก API สำหรับ toggle hide-return

// ---- Transfer State ----
let transferFromEmpId = null;
let transferAssets    = [];
let empSearchCache    = [];
let assetEmpMap       = {};   // {employee_id: count}

// ---- Init ----
document.addEventListener('DOMContentLoaded', () => {
  loadFilters();
  loadEmployees();
  loadStats();
  loadAssetEmpMap();

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
    filters.bu   = document.getElementById('filter-bu').value;
    filters.dept = '';
    await reloadDeptFilter(filters.bu);
    currentPage = 1;
    loadEmployees();
  });
  document.getElementById('filter-dept').addEventListener('change', () => {
    filters.dept = document.getElementById('filter-dept').value;
    currentPage = 1; loadEmployees();
  });
  document.getElementById('filter-status').addEventListener('change', () => {
    filters.status = document.getElementById('filter-status').value;
    currentPage = 1; loadEmployees();
  });

  // BU select in modal
  document.getElementById('f-bu-code').addEventListener('change', function() {
    const buName = buMap[this.value] || '';
    // auto-fill bu name (hidden field via buMap)
  });
});

// ---- Reload dept filter by BU ----
async function reloadDeptFilter(bu) {
  const params = bu ? '?bu=' + encodeURIComponent(bu) : '';
  const data = await api('/api/filters' + params);
  const deptSel  = document.getElementById('filter-dept');
  const deptList = document.getElementById('dept-list');
  deptSel.innerHTML  = '<option value="">ทุกแผนก</option>';
  deptList.innerHTML = '';
  data.depts.forEach(d => {
    deptSel.insertAdjacentHTML('beforeend', `<option value="${d}">${d}</option>`);
    deptList.insertAdjacentHTML('beforeend', `<option value="${d}">`);
  });
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
    deptSel.insertAdjacentHTML('beforeend', `<option value="${d}">${d}</option>`);
    deptList.insertAdjacentHTML('beforeend', `<option value="${d}">`);
  });
}

// ---- Load employees ----
async function loadEmployees() {
  const assetFilterOn = filters.hasAsset || filters.noAsset;
  const params = new URLSearchParams({
    page: assetFilterOn ? 1 : currentPage,
    per_page: assetFilterOn ? 9999 : 50,
    q: filters.q, bu: filters.bu,
    dept: filters.dept, status: filters.status
  });
  const data = await api('/api/employees?' + params);
  totalPages = data.pages;

  const tbody = document.getElementById('emp-tbody');
  const empty = document.getElementById('empty-state');
  const info  = document.getElementById('result-info');

  document.getElementById('total-badge').textContent = `พนักงาน ${data.total.toLocaleString()} คน`;
  const showing = assetFilterOn
    ? data.employees.filter(e => filters.hasAsset ? assetEmpMap[e.id] : !assetEmpMap[e.id]).length
    : data.employees.length;
  const isFiltered = filters.q || filters.bu || filters.dept || filters.status || assetFilterOn;
  info.textContent = `แสดง ${showing} จาก ${data.total.toLocaleString()} รายการ` +
    (isFiltered ? ' (กรองแล้ว)' : '');

  // client-side filter: has asset
  let employees = data.employees;
  if (filters.hasAsset) {
    employees = employees.filter(e => assetEmpMap[e.id]);
  } else if (filters.noAsset) {
    employees = employees.filter(e => !assetEmpMap[e.id]);
  }

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
        <td style="text-align:center">${assetEmpMap[e.id] ? `<span class="asset-badge" onclick="showAssetDetail(${e.id},'${esc(e.name)}')" title="มี ${assetEmpMap[e.id]} เครื่อง">💻 ${assetEmpMap[e.id]}</span>` : ''}</td>
        <td>
          <div class="action-btns">
            <button class="icon-btn edit" onclick="editEmployee(${e.id})" title="แก้ไข">✏️</button>
            <button class="icon-btn del" onclick="deleteEmployee(${e.id}, '${esc(e.name)}')" title="ลบ">🗑️</button>
          </div>
        </td>
      </tr>
    `).join('');
  }
  if (assetFilterOn) {
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
    await api('/api/employees/' + id, 'PUT', payload);
    showToast('อัปเดตข้อมูลเรียบร้อย', 'success');
  } else {
    await api('/api/employees', 'POST', payload);
    showToast('เพิ่มพนักงานเรียบร้อย', 'success');
  }
  closeModal();
  loadEmployees();
  loadStats();
  if (assetLoaded) loadAssets(true);
  api('/api/assets/employee-map').then(m => { assetEmpMap = m; });
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
    const raw = await api('/api/assets/employee-map');
    // normalize keys to numbers
    assetEmpMap = {};
    Object.entries(raw).forEach(([k, v]) => { assetEmpMap[parseInt(k)] = v; });
  } catch(e) {}
}

async function showAssetDetail(empId, empName) {
  document.getElementById('ad-subtitle').textContent = empName;
  document.getElementById('ad-list').innerHTML =
    '<div style="text-align:center;padding:24px;color:#94a3b8">กำลังโหลด...</div>';
  document.getElementById('asset-detail-overlay').classList.add('open');

  const assets = await api(`/api/employees/${empId}/assets`);
  if (!assets.length) {
    document.getElementById('ad-list').innerHTML =
      '<div style="text-align:center;padding:24px;color:#16a34a;font-size:.85rem">✓ ไม่มีทรัพย์สินที่ถือครองอยู่</div>';
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

  document.getElementById('ad-list').innerHTML = `<div style="padding:16px">${adCards}</div>`;
}

function closeAssetDetail() {
  document.getElementById('asset-detail-overlay').classList.remove('open');
}
function closeAssetDetailOnOverlay(e) {
  if (e.target === document.getElementById('asset-detail-overlay')) closeAssetDetail();
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
    showToast(`Sync เสร็จสิ้น · Inactive ${r.inactivated} · เพิ่ม ${r.added} · อัพเดท ${r.updated} คน`, 'success');
    closeSyncModal();
    loadEmployees();
    loadStats();
    api('/api/assets/employee-map').then(m => {
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
  document.getElementById('r-missing-edevice-head').innerHTML = _anomalyHead(false);
  document.getElementById('r-missing-edevice-badge').textContent = me.length.toLocaleString();
  document.getElementById('r-missing-edevice-count').textContent =
    me.length ? `${me.length} เครื่อง ⚠️` : '0 เครื่อง ✓';
  document.getElementById('r-missing-edevice-tbody').innerHTML = me.length
    ? me.map(a => _anomalyRow(a, {showEdStatus: false})).join('')
    : '<tr><td colspan="13" style="text-align:center;padding:16px;color:#16a34a;font-size:.82rem">✓ ทุกเครื่องมีข้อมูลใน eDevice ครบแล้ว</td></tr>';

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

// ---- Helpers ----
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
