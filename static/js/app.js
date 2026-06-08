// ---- State ----
let currentPage = 1;
let totalPages  = 1;
let filters     = { q: '', bu: '', dept: '', status: '', hasAsset: false };
let buMap       = {};  // bu_code -> bu name

// ---- Asset State ----
let assetLoaded = false;
let assetFilters = { q: '', customer: '', type: '', bu: '', status: '', ownership: '' };

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
  const params = new URLSearchParams({
    page: filters.hasAsset ? 1 : currentPage,
    per_page: filters.hasAsset ? 9999 : 50,
    q: filters.q, bu: filters.bu,
    dept: filters.dept, status: filters.status
  });
  const data = await api('/api/employees?' + params);
  totalPages = data.pages;

  const tbody = document.getElementById('emp-tbody');
  const empty = document.getElementById('empty-state');
  const info  = document.getElementById('result-info');

  document.getElementById('total-badge').textContent = `พนักงาน ${data.total.toLocaleString()} คน`;
  const showing = filters.hasAsset
    ? data.employees.filter(e => assetEmpMap[e.id]).length
    : data.employees.length;
  const isFiltered = filters.q || filters.bu || filters.dept || filters.status || filters.hasAsset;
  info.textContent = `แสดง ${showing} จาก ${data.total.toLocaleString()} รายการ` +
    (isFiltered ? ' (กรองแล้ว)' : '');

  // client-side filter: has asset
  let employees = data.employees;
  if (filters.hasAsset) {
    employees = employees.filter(e => assetEmpMap[e.id]);
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
  if (filters.hasAsset) {
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

  const custSel = document.getElementById('a-filter-customer');
  d.customers.forEach(c => {
    const short = c.name.replace('อมรินทร์ ', '').replace(' จำกัด', '').replace(' (มหา', '');
    custSel.insertAdjacentHTML('beforeend', `<option value="${c.code}">${short}</option>`);
  });

  const typeSel = document.getElementById('a-filter-type');
  d.types.forEach(t => typeSel.insertAdjacentHTML('beforeend', `<option value="${t}">${t}</option>`));

  // populate BU filter from existing buMap (loaded with employees)
  const buSel = document.getElementById('a-filter-bu');
  Object.entries(buMap).forEach(([code, name]) => {
    buSel.insertAdjacentHTML('beforeend', `<option value="${code}">${code}</option>`);
  });

  // wire up filter events
  ['a-search', 'a-filter-customer', 'a-filter-type', 'a-filter-bu', 'a-filter-status', 'a-filter-ownership'].forEach(id => {
    const el = document.getElementById(id);
    const evt = el.tagName === 'INPUT' ? 'input' : 'change';
    el.addEventListener(evt, () => {
      assetFilters.q         = document.getElementById('a-search').value.trim();
      assetFilters.customer  = document.getElementById('a-filter-customer').value;
      assetFilters.type      = document.getElementById('a-filter-type').value;
      assetFilters.bu        = document.getElementById('a-filter-bu').value;
      assetFilters.status    = document.getElementById('a-filter-status').value;
      assetFilters.ownership = document.getElementById('a-filter-ownership').value;
      loadAssets();
    });
  });
}

async function loadAssets(refresh = false) {
  const params = new URLSearchParams({
    q:         assetFilters.q,
    customer:  assetFilters.customer,
    type:      assetFilters.type,
    bu:        assetFilters.bu,
    status:    assetFilters.status,
    ownership: assetFilters.ownership,
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

  // update summary cards
  document.getElementById('a-total').textContent   = d.total.toLocaleString();
  document.getElementById('a-monthly').textContent = '฿' + (d.total_monthly || 0).toLocaleString('th', {minimumFractionDigits: 0, maximumFractionDigits: 0});
  const sc = d.status_counts || {};
  document.getElementById('a-expired').textContent  = (sc.expired  || 0).toLocaleString();
  document.getElementById('a-critical').textContent = (sc.critical || 0).toLocaleString();
  document.getElementById('a-warning').textContent  = (sc.warning  || 0).toLocaleString();
  document.getElementById('a-ok').textContent       = (sc.ok       || 0).toLocaleString();

  if (d.cached_at) {
    document.getElementById('a-cache-info').textContent = `ข้อมูล ณ ${d.cached_at}`;
  }

  document.getElementById('a-result-info').textContent =
    `แสดง ${d.total.toLocaleString()} รายการ · ค่าเช่ารวม ฿${(d.total_monthly||0).toLocaleString('th', {minimumFractionDigits:2})} / เดือน`;

  const tbody = document.getElementById('asset-tbody');
  const empty = document.getElementById('a-empty');

  if (!d.assets.length) {
    tbody.innerHTML = '';
    empty.style.display = '';
    return;
  }
  empty.style.display = 'none';

  const statusLabel = (a) => {
    const d = a.days_remaining;
    if (a.contract_status === 'expired')  return `🔴 เกินกำหนด ${Math.abs(d)} วัน`;
    if (a.contract_status === 'critical') return `🟠 เหลือ ${d} วัน`;
    if (a.contract_status === 'warning')  return `🟡 เหลือ ${d} วัน`;
    if (a.contract_status === 'ok')       return d !== null ? `🟢 เหลือ ${d} วัน` : '🟢 ปกติ';
    return '— ไม่ระบุ';
  };
  const pillClass   = { expired: 'pill-expired', critical: 'pill-critical', warning: 'pill-warning', ok: 'pill-ok', unknown: 'pill-unknown' };
  const daysClass   = { expired: 'days-expired', critical: 'days-critical', warning: 'days-warning', ok: 'days-ok' };
  const rowClass    = { expired: 'contract-expired', critical: 'contract-critical', warning: 'contract-warning' };
  const resLabel    = {
    pending:          '⏳ ยังไม่ดำเนินการ',
    returned:         '📦 คืนแล้ว',
    bought:           '🛒 ซื้อแล้ว',
    renewed:          '🔄 ต่อสัญญาแล้ว',
    buy_requested:    '📋 รอขอซื้อ',
    renew_requested:  '📋 รอต่อสัญญา',
  };
  const resClass    = {
    pending: 'res-pending', returned: 'res-returned', bought: 'res-bought',
    renewed: 'res-renewed', buy_requested: 'res-buy_requested', renew_requested: 'res-renew_requested',
  };

  tbody.innerHTML = d.assets.map((a, i) => {
    const st = a.contract_status;

    const buBadge = a.emp_bu_code
      ? `<span class="bu-badge bu-${esc(a.emp_bu_code)}">${esc(a.emp_bu_code)}</span>`
      : `<span style="color:#cbd5e1">—</span>`;

    const deptText = a.emp_dept || a.dept_sheet || '—';

    const custShort = (a.customer_name || '')
      .replace('อมรินทร์ ', '').replace(' จำกัด', '').replace(' (มหา', '');

    const endFmt = a.end_date
      ? new Date(a.end_date).toLocaleDateString('th-TH', {day:'numeric', month:'short', year:'2-digit'})
      : '—';

    const computerIdHtml = a.computer_id
      ? `<code style="font-size:.75rem;color:#334155">${esc(a.computer_id)}</code>`
      : '<span style="color:#cbd5e1">—</span>';

    return `<tr class="${rowClass[st] || ''}">
      <td style="color:#94a3b8">${i+1}</td>
      <td><code style="font-size:.78rem;color:#334155">${esc(a.asset_no)}</code></td>
      <td>${computerIdHtml}</td>
      <td><code style="font-size:.75rem;color:#64748b">${esc(a.serial_no) || '—'}</code></td>
      <td style="white-space:nowrap">${esc(a.asset_type)}</td>
      <td style="white-space:nowrap">${a.ownership === 'เช่า'
        ? '<span style="font-size:.72rem;background:#fef3c7;color:#92400e;padding:2px 7px;border-radius:5px;font-weight:600">เช่า</span>'
        : a.ownership === 'ซื้อ'
        ? '<span style="font-size:.72rem;background:#dcfce7;color:#15803d;padding:2px 7px;border-radius:5px;font-weight:600">ซื้อ</span>'
        : '<span style="color:#cbd5e1">—</span>'}</td>
      <td style="font-size:.8rem">${esc(a.model)}</td>
      <td><strong>${esc(a.user_name) || '<span style="color:#94a3b8">ไม่ระบุ</span>'}</strong></td>
      <td>${buBadge}</td>
      <td style="font-size:.78rem;color:#64748b;max-width:140px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="${esc(deptText)}">${esc(deptText)}</td>
      <td style="font-size:.75rem;color:#64748b;white-space:nowrap">${esc(custShort)}</td>
      <td style="white-space:nowrap;font-size:.82rem">${endFmt}</td>
      <td><span class="status-pill ${pillClass[st] || 'pill-unknown'}">${statusLabel(a)}</span></td>
      <td>${renderResolution(a, resLabel, resClass)}</td>
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
  document.getElementById('ad-list').innerHTML = assets.map(a => {
    const endFmt = a.end_date
      ? new Date(a.end_date).toLocaleDateString('th-TH', {day:'numeric',month:'short',year:'2-digit'})
      : '—';
    const st = a.contract_status;
    const pillCls = {expired:'pill-expired',critical:'pill-critical',warning:'pill-warning',ok:'pill-ok'};
    const stLabel = (a) => {
      const d = a.days_remaining;
      if (st==='expired')  return `🔴 เกินกำหนด ${Math.abs(d)} วัน`;
      if (st==='critical') return `🟠 เหลือ ${d} วัน`;
      if (st==='warning')  return `🟡 เหลือ ${d} วัน`;
      return d!=null ? `🟢 เหลือ ${d} วัน` : '🟢 ปกติ';
    };
    return `<div style="padding:12px 16px;border-bottom:1px solid #f1f5f9;display:flex;flex-direction:column;gap:4px">
      <div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap">
        <span style="background:#f1f5f9;border-radius:6px;padding:2px 7px;font-size:.72rem;color:#475569">${esc(a.asset_type)}</span>
        <strong style="font-size:.85rem">${esc(a.model)}</strong>
        <code style="font-size:.75rem;color:#94a3b8">${esc(a.serial_no)}</code>
      </div>
      <div style="display:flex;align-items:center;gap:8px;font-size:.78rem;color:#64748b">
        <span>หมดสัญญา: ${endFmt}</span>
        <span class="status-pill ${pillCls[st]||'pill-unknown'}">${stLabel(a)}</span>
      </div>
    </div>`;
  }).join('');
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

function filterAssetStatus(status) {
  document.getElementById('a-filter-status').value = status;
  assetFilters.status = status;
  loadAssets();
  // scroll to table
  document.getElementById('tab-assets').scrollIntoView({ behavior: 'smooth' });
}

function exportAssets() {
  const params = new URLSearchParams({
    status:   assetFilters.status,
    type:     assetFilters.type,
    customer: assetFilters.customer,
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
    document.getElementById('sync-loading').innerHTML =
      '<div style="text-align:center;padding:40px;color:#dc2626">❌ เชื่อมต่อ Intranet ไม่ได้</div>';
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
  document.getElementById('r-expired').textContent  = (sc.expired  || 0).toLocaleString();
  document.getElementById('r-critical').textContent = (sc.critical || 0).toLocaleString();
  document.getElementById('r-warning').textContent  = (sc.warning  || 0).toLocaleString();
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

  // Timeline — bar height proportional, count label floating on top of bar
  if (d.timeline.length) {
    const maxT = Math.max(...d.timeline.map(t => t.count), 1);
    const BAR_AREA = 100; // px — พื้นที่วาดแท่ง
    const statusColor = (month) => {
      const today = new Date();
      const [y, m] = month.split('-').map(Number);
      const diff = (y - today.getFullYear()) * 12 + (m - today.getMonth() - 1);
      if (diff < 0)   return '#dc2626';
      if (diff <= 3)  return '#f97316';
      if (diff <= 6)  return '#eab308';
      return '#2563eb';
    };
    const cols = d.timeline.map(t => {
      const h  = Math.max(Math.round((t.count / maxT) * BAR_AREA), 4);
      const color = statusColor(t.month);
      const label = new Date(t.month + '-01').toLocaleDateString('th-TH', {month:'short', year:'2-digit'});
      const tip = `${t.month}: ${t.count} เครื่อง  ฿${Math.round(t.monthly||0).toLocaleString()}/เดือน`;
      return `<div class="timeline-col" title="${tip}" style="position:relative">
        <div class="timeline-bar-wrap" style="height:${BAR_AREA}px;align-items:flex-end;display:flex;width:100%">
          <div class="timeline-bar" style="height:${h}px;background:${color};width:100%;position:relative">
            <span style="position:absolute;top:-18px;left:50%;transform:translateX(-50%);font-size:.68rem;font-weight:700;color:#1e293b;white-space:nowrap">${t.count}</span>
          </div>
        </div>
        <div class="timeline-label">${label}</div>
      </div>`;
    }).join('');
    document.getElementById('r-timeline').innerHTML = `
      <div style="overflow-x:auto;padding-top:20px">
        <div class="timeline-wrap" style="padding-bottom:4px">${cols}</div>
      </div>
      <div style="display:flex;gap:16px;margin-top:10px;font-size:.72rem;color:#64748b">
        <span><span style="display:inline-block;width:10px;height:10px;background:#dc2626;border-radius:2px;margin-right:3px"></span>หมดแล้ว</span>
        <span><span style="display:inline-block;width:10px;height:10px;background:#f97316;border-radius:2px;margin-right:3px"></span>&lt;3 เดือน</span>
        <span><span style="display:inline-block;width:10px;height:10px;background:#eab308;border-radius:2px;margin-right:3px"></span>&lt;6 เดือน</span>
        <span><span style="display:inline-block;width:10px;height:10px;background:#2563eb;border-radius:2px;margin-right:3px"></span>ปกติ</span>
      </div>`;
  } else {
    document.getElementById('r-timeline').innerHTML =
      '<div style="text-align:center;padding:24px;color:#94a3b8;font-size:.82rem">ไม่มีข้อมูล timeline</div>';
  }

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
  tbody.innerHTML = d.urgent.map(a => {
    const endFmt = a.end_date
      ? new Date(a.end_date).toLocaleDateString('th-TH', {day:'numeric',month:'short',year:'2-digit'})
      : '—';
    return `<tr>
      <td><code style="font-size:.78rem">${esc(a.computer_id) || '—'}</code></td>
      <td style="font-size:.8rem">${esc(a.model) || esc(a.brand)}</td>
      <td><strong>${esc(a.user_name) || '<span style="color:#94a3b8">ไม่ระบุ</span>'}</strong></td>
      <td><span class="bu-badge bu-${esc(a.emp_bu_code)}">${esc(a.emp_bu_code) || '—'}</span></td>
      <td style="font-size:.78rem;color:#64748b">${esc(a.emp_dept) || '—'}</td>
      <td style="white-space:nowrap;font-size:.82rem">${endFmt}</td>
      <td style="text-align:center"><span class="status-pill ${pillCls[a.contract_status]||''}">${pillLabel(a)}</span></td>
      <td style="text-align:right;font-size:.8rem">฿${(a.monthly_charge||0).toLocaleString()}</td>
    </tr>`;
  }).join('');

  // ---- Anomaly panel 1: เครื่องเช่าไม่มีข้อมูลสัญญา ----
  const nc = d.no_contract || [];
  document.getElementById('r-no-contract-count').textContent =
    nc.length ? `${nc.length} เครื่อง ⚠️` : '0 เครื่อง ✓';
  document.getElementById('r-no-contract-tbody').innerHTML = nc.length
    ? nc.map(a => `
      <tr style="border-bottom:1px solid #f1f5f9">
        <td style="padding:6px 10px"><code style="font-size:.78rem;color:#334155">${esc(a.computer_id)||'—'}</code></td>
        <td style="padding:6px 10px;font-size:.75rem;color:#64748b;font-family:monospace">${esc(a.serial_no)||'—'}</td>
        <td style="padding:6px 10px;font-size:.78rem">${esc(a.device_type)||''} ${esc(a.model)||esc(a.brand)||''}</td>
        <td style="padding:6px 10px;font-size:.82rem">${esc(a.user_name)||'<span style="color:#cbd5e1">—</span>'}</td>
        <td style="padding:6px 10px"><span class="bu-badge bu-${esc(a.emp_bu_code)}">${esc(a.emp_bu_code)||'—'}</span></td>
        <td style="padding:6px 10px;font-size:.78rem;color:#64748b">${esc(a.emp_dept)||'—'}</td>
        <td style="padding:6px 10px;text-align:right;font-size:.8rem;color:#64748b">${a.monthly_charge?'฿'+a.monthly_charge.toLocaleString():'—'}</td>
      </tr>`).join('')
    : '<tr><td colspan="7" style="text-align:center;padding:16px;color:#16a34a;font-size:.82rem">✓ เครื่องเช่าทุกเครื่องมีข้อมูลสัญญาครบ</td></tr>';

  // ---- Anomaly panel 2: เครื่องเช่าที่ไม่มี BU (= กลุ่มเดียวกับ "ไม่ระบุ BU" ในกราฟ) ----
  const nb = d.no_bu || [];
  const nbHasDept = nb.filter(a => a.has_dept).length;
  const nbNoDept  = nb.filter(a => !a.has_dept).length;

  document.getElementById('r-no-bu-count').textContent =
    nb.length ? `${nb.length} เครื่อง ⚠️` : '0 เครื่อง ✓';

  // sub-summary badges
  document.getElementById('r-no-bu-summary').innerHTML = nb.length ? `
    <span style="background:#fef3c7;color:#92400e;padding:2px 10px;border-radius:10px">
      📋 มีแผนก (Sheets) แต่ไม่มี BU: <strong>${nbHasDept}</strong> เครื่อง
    </span>
    <span style="background:#fee2e2;color:#991b1b;padding:2px 10px;border-radius:10px">
      ❌ ไม่มีทั้ง BU และแผนก: <strong>${nbNoDept}</strong> เครื่อง
    </span>` : '';

  document.getElementById('r-panel-no-bu').style.display = '';
  document.getElementById('r-no-bu-tbody').innerHTML = nb.length
    ? nb.map(a => {
        const endFmt = a.end_date
          ? new Date(a.end_date).toLocaleDateString('th-TH', {day:'numeric',month:'short',year:'2-digit'})
          : '—';
        const deptCell = a.emp_dept
          ? `<span style="color:#374151">${esc(a.emp_dept)}</span>`
          : `<span style="color:#fca5a5;font-size:.75rem">ไม่มีข้อมูล</span>`;
        const rowBg = a.has_dept ? '' : 'background:#fff5f5';
        return `<tr style="border-bottom:1px solid #f1f5f9;${rowBg}">
          <td style="padding:6px 10px"><code style="font-size:.78rem;color:#334155">${esc(a.computer_id)||'—'}</code></td>
          <td style="padding:6px 10px;font-size:.75rem;color:#64748b;font-family:monospace">${esc(a.serial_no)||'—'}</td>
          <td style="padding:6px 10px;font-size:.78rem">${esc(a.device_type)||''} ${esc(a.model)||esc(a.brand)||''}</td>
          <td style="padding:6px 10px;font-size:.82rem;color:#94a3b8">${esc(a.user_name)||'<em style="color:#cbd5e1">ไม่ระบุ</em>'}</td>
          <td style="padding:6px 10px;font-size:.78rem">${deptCell}</td>
          <td style="padding:6px 10px;white-space:nowrap;font-size:.8rem">${endFmt}</td>
          <td style="padding:6px 10px;text-align:right;font-size:.8rem;color:#64748b">${a.monthly_charge?'฿'+a.monthly_charge.toLocaleString():'—'}</td>
        </tr>`;
      }).join('')
    : '<tr><td colspan="7" style="text-align:center;padding:16px;color:#16a34a;font-size:.82rem">✓ เครื่องเช่าทุกเครื่องระบุ BU ครบแล้ว</td></tr>';
}

function toggleAnomalyPanel(panelId) {
  const el = document.getElementById(panelId);
  if (!el) return;
  el.style.display = el.style.display === 'none' ? '' : 'none';
}

function switchToAssets(status, ownership) {
  // สลับไปแท็บ IT Assets แล้ว filter ตามที่กด
  document.querySelectorAll('.tab').forEach(b => b.classList.remove('active'));
  document.querySelector('.tab[data-tab="assets"]').classList.add('active');
  document.querySelectorAll('.tab-content').forEach(c => c.style.display = 'none');
  document.getElementById('tab-assets').style.display = '';
  if (!assetLoaded) { loadAssetMeta(); assetLoaded = true; }

  document.getElementById('a-filter-status').value     = status || '';
  document.getElementById('a-filter-ownership').value  = ownership || '';
  assetFilters.status    = status || '';
  assetFilters.ownership = ownership || '';
  loadAssets();
}

// ==============================
// ---- eDevice Sync ----
// ==============================

let edSyncData = null;
let edCurrentTab = 'unmatched';

async function openEdeviceSyncModal() {
  edSyncData = null;
  document.getElementById('ed-loading').style.display = '';
  document.getElementById('ed-result').style.display = 'none';
  document.getElementById('ed-footer').style.display = 'none';
  document.getElementById('ed-subtitle').textContent = 'กำลังวิเคราะห์ข้อมูล...';
  document.getElementById('edevice-overlay').classList.add('open');

  try {
    edSyncData = await api('/api/sync/edevice/preview');
    document.getElementById('ed-loading').style.display = 'none';
    document.getElementById('ed-result').style.display = '';
    document.getElementById('ed-footer').style.display = 'flex';

    const s = edSyncData.stats;
    document.getElementById('ed-total').textContent        = (s.total || 0).toLocaleString();
    document.getElementById('ed-matched-code').textContent = (s.matched_code || 0).toLocaleString();
    document.getElementById('ed-matched-name').textContent = (s.matched_name || 0).toLocaleString();
    document.getElementById('ed-unmatched').textContent    = (s.unmatched || 0).toLocaleString();

    const codeCount = (edSyncData.code_updates || []).length;
    document.getElementById('ed-code-update-info').textContent =
      codeCount
        ? `🔑 พบ ${codeCount} รายการที่สามารถอัพเดทรหัสพนักงานได้อัตโนมัติ`
        : 'ไม่มีรหัสพนักงานที่ต้องอัพเดท';

    const setBadge = (id, count) => {
      const el = document.getElementById(id);
      el.textContent = count || '';
    };
    setBadge('ed-unmatched-badge', s.unmatched);
    setBadge('ed-code-badge',      codeCount);

    const source = edSyncData.cached_file ? 'ใช้ข้อมูลจากไฟล์ cache' : 'ดึงข้อมูลสดจาก eDevice';
    document.getElementById('ed-subtitle').textContent =
      `Asset ทั้งหมด ${s.total} รายการ · ${source}`;

    showEdTab('unmatched');
  } catch (e) {
    document.getElementById('ed-subtitle').textContent = 'เชื่อมต่อไม่สำเร็จ';
    document.getElementById('ed-loading').innerHTML =
      '<div style="text-align:center;padding:40px;color:#dc2626">❌ โหลดข้อมูล eDevice ไม่สำเร็จ</div>';
  }
}

function closeEdeviceSyncModal() {
  document.getElementById('edevice-overlay').classList.remove('open');
  edSyncData = null;
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

  const forceLive = document.getElementById('ed-force-live').checked;

  try {
    const r = await api('/api/sync/edevice/apply', 'POST', { force_live: forceLive });
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
  if (!res.ok) throw new Error(await res.text());
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
