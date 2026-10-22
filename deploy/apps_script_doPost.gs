const SHEET_NAME = 'Sheet1';   // ⚠️ แก้เป็นชื่อแท็บจริงของข้อมูล asset (ดูชื่อแท็บล่างซ้ายของชีต)

function doPost(e) {
  const data = JSON.parse(e.postData.contents);
  const ss    = SpreadsheetApp.openById('ใส่_SHEET_ID_ที่นี่');
  const sheet = ss.getSheetByName(SHEET_NAME);
  if (!sheet) {
    return ContentService.createTextOutput(JSON.stringify(
      {ok: false, error: 'ไม่พบแท็บชื่อ ' + SHEET_NAME}
    )).setMimeType(ContentService.MimeType.JSON);
  }

  const range  = sheet.getDataRange();
  const rows   = range.getValues();
  const header = rows[0];

  const COL_SN   = header.indexOf('Serial Number');
  const COL_NAME = header.indexOf('ชื่อ-สกุล');
  const COL_DEPT = header.indexOf('แผนก');
  const COL_DIV  = header.indexOf('ฝ่าย');
  const COL_RET  = header.indexOf('Returned');

  // map: serial → update (เร็วกว่า find ในลูปมาก)
  const updMap = {};
  data.updates.forEach(u => { updMap[u.serial.toUpperCase()] = u; });

  // เลือกแถวเป้าหมายต่อ 1 serial: แถวที่ยังไม่ Returned ก่อน
  // ถ้าซ้ำกันหลายแถวและ Returned หมด → ใช้แถวล่างสุด (ตรงกับ logic ฝั่งเว็บ)
  const targetRow = {};   // serial → row index
  for (let i = 1; i < rows.length; i++) {
    const sn = (rows[i][COL_SN] || '').toString().trim().toUpperCase();
    if (!sn || !updMap[sn]) continue;
    const returned = COL_RET >= 0 && (rows[i][COL_RET] || '').toString().trim() !== '';
    const prev = targetRow[sn];
    if (prev === undefined || !returned) targetRow[sn] = i;
  }

  // แก้ค่าใน array แล้วเขียนกลับทีเดียว (เร็วกว่า setValue ทีละเซลล์)
  let updated = 0;
  for (const sn in targetRow) {
    const i   = targetRow[sn];
    const upd = updMap[sn];
    if (COL_NAME >= 0 && upd.name)     rows[i][COL_NAME] = upd.name;
    if (COL_DEPT >= 0 && upd.dept)     rows[i][COL_DEPT] = upd.dept;
    if (COL_DIV  >= 0 && upd.division) rows[i][COL_DIV]  = upd.division;
    updated++;
  }
  range.setValues(rows);

  return ContentService.createTextOutput(JSON.stringify({ok: true, updated}))
    .setMimeType(ContentService.MimeType.JSON);
}

function testAuth() {
  const sheet = SpreadsheetApp.openById('ใส่_SHEET_ID_ที่นี่');
  Logger.log(sheet.getName());
}
