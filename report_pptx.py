"""Presentation สรุปบริหาร Software สำหรับผู้บริหาร (.pptx)

สร้างจากข้อมูลชุดเดียวกับหน้า Dashboard → บริหาร Software
ใช้ python-pptx เพราะเครื่อง server ไม่มี node / LibreOffice
"""
import io
from datetime import date

from pptx import Presentation
from pptx.chart.data import CategoryChartData
from pptx.dml.color import RGBColor
from pptx.enum.chart import XL_CHART_TYPE, XL_LEGEND_POSITION, XL_LABEL_POSITION
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.oxml.ns import qn
from pptx.util import Inches, Pt, Emu

FONT = 'Tahoma'          # มีทั้ง Windows / Mac และรองรับภาษาไทย

# โทนม่วงเดียวกับหน้า Software ในระบบ
INK      = RGBColor(0x1E, 0x29, 0x3B)
MUTED    = RGBColor(0x64, 0x74, 0x8B)
DARK     = RGBColor(0x2E, 0x10, 0x65)    # พื้นสไลด์เปิด/ปิด
PRIMARY  = RGBColor(0x7E, 0x22, 0xCE)
SOFT     = RGBColor(0xF5, 0xF3, 0xFF)    # พื้นการ์ด
SOFT2    = RGBColor(0xE9, 0xD5, 0xFF)
LAVENDER = RGBColor(0xC4, 0xB5, 0xFD)
WHITE    = RGBColor(0xFF, 0xFF, 0xFF)
RED      = RGBColor(0xDC, 0x26, 0x26)
GREEN    = RGBColor(0x15, 0x80, 0x3D)
AMBER    = RGBColor(0xB4, 0x53, 0x09)

TH_MONTH = ['', 'ม.ค.', 'ก.พ.', 'มี.ค.', 'เม.ย.', 'พ.ค.', 'มิ.ย.',
            'ก.ค.', 'ส.ค.', 'ก.ย.', 'ต.ค.', 'พ.ย.', 'ธ.ค.']


def th_date(d):
    if isinstance(d, str):
        d = date.fromisoformat(d[:10])
    return f'{d.day} {TH_MONTH[d.month]} {d.year + 543}'


# ---------- ตัวช่วยวาด ----------

def _style_run(run, size, bold=False, color=INK, italic=False):
    f = run.font
    f.size = Pt(size)
    f.bold = bold
    f.italic = italic
    f.color.rgb = color
    f.name = FONT
    # ตัวอักษรไทยใช้ฟอนต์ช่อง cs — ต้องตั้งเอง ไม่งั้น PowerPoint ใช้ฟอนต์ไทยของธีม
    rPr = run._r.get_or_add_rPr()
    for tag in ('a:ea', 'a:cs'):
        el = rPr.find(qn(tag))
        if el is None:
            el = rPr.makeelement(qn(tag), {})
            rPr.append(el)
        el.set('typeface', FONT)


def text(slide, x, y, w, h, parts, size=16, color=INK, bold=False, align=PP_ALIGN.LEFT,
         anchor=MSO_ANCHOR.TOP, name=None):
    """parts = ข้อความ หรือ list ของบรรทัด; แต่ละบรรทัดเป็นข้อความหรือ list ของ (text, opts)"""
    tb = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    if name:
        tb.name = name
    tf = tb.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    tf.vertical_anchor = anchor
    lines = parts if isinstance(parts, list) else [parts]
    for i, line in enumerate(lines):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        runs = line if isinstance(line, list) else [(line, {})]
        for t, o in runs:
            r = p.add_run()
            r.text = t
            _style_run(r, o.get('size', size), o.get('bold', bold),
                       o.get('color', color), o.get('italic', False))
        if i:
            p.space_before = Pt(6)
    return tb


def card(slide, x, y, w, h, fill=SOFT, name=None):
    s = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE,
                               Inches(x), Inches(y), Inches(w), Inches(h))
    s.adjustments[0] = 0.08
    s.fill.solid()
    s.fill.fore_color.rgb = fill
    s.line.fill.background()
    s.shadow.inherit = False
    if name:
        s.name = name
    return s


def bg(slide, color):
    f = slide.background.fill
    f.solid()
    f.fore_color.rgb = color


def title(slide, t, sub=None):
    """หัวข้อสไลด์เนื้อหา — ตำแหน่ง/ขนาดเดียวกันทุกหน้า"""
    text(slide, 0.6, 0.45, 12.1, 0.75, t, size=32, bold=True, color=DARK, name='Title')
    if sub:
        text(slide, 0.6, 1.2, 12.1, 0.4, sub, size=14, color=MUTED, name='Subtitle')


def footer(slide, n, label):
    text(slide, 0.6, 7.0, 9, 0.3, label, size=10, color=MUTED, name='Footer')
    text(slide, 11.7, 7.0, 1.0, 0.3, str(n), size=10, color=MUTED, align=PP_ALIGN.RIGHT,
         name='Slide number')


def stat(slide, x, y, w, h, value, label, sub='', color=PRIMARY):
    card(slide, x, y, w, h)
    text(slide, x + 0.3, y + 0.25, w - 0.6, 1.0, value, size=48, bold=True, color=color)
    text(slide, x + 0.3, y + 1.3, w - 0.6, 0.45, label, size=14, bold=True, color=INK)
    if sub:
        text(slide, x + 0.3, y + 1.8, w - 0.6, h - 1.95, sub, size=11, color=MUTED)


def _chart_fonts(chart, size=11):
    chart.font.name = FONT
    chart.font.size = Pt(size)
    chart.font.color.rgb = MUTED


def table(slide, x, y, w, rows, col_w, head_fill=DARK, size=12, row_h=0.36,
          align_right=(), bold_last=False, colors=None):
    """rows[0] = หัวตาราง · colors = {(r, c): RGBColor} ไว้ไฮไลต์ช่อง"""
    shp = slide.shapes.add_table(len(rows), len(rows[0]), Inches(x), Inches(y),
                                 Inches(w), Inches(row_h * len(rows)))
    tbl = shp.table
    for i, cw in enumerate(col_w):
        tbl.columns[i].width = Inches(cw)
    for r, row in enumerate(rows):
        tbl.rows[r].height = Inches(row_h)
        for c, val in enumerate(row):
            cell = tbl.cell(r, c)
            cell.margin_left = cell.margin_right = Inches(0.1)
            cell.margin_top = cell.margin_bottom = Inches(0.03)
            cell.vertical_anchor = MSO_ANCHOR.MIDDLE
            cell.fill.solid()
            last = bold_last and r == len(rows) - 1
            cell.fill.fore_color.rgb = head_fill if r == 0 else (SOFT2 if last else
                                       (SOFT if r % 2 == 0 else WHITE))
            tf = cell.text_frame
            tf.word_wrap = True
            p = tf.paragraphs[0]
            p.alignment = PP_ALIGN.RIGHT if c in align_right else PP_ALIGN.LEFT
            run = p.add_run()
            run.text = '' if val is None else str(val)
            col = WHITE if r == 0 else (colors or {}).get((r, c), INK)
            _style_run(run, size, bold=(r == 0 or last or (colors or {}).get((r, c)) is not None),
                       color=col)
    return shp


def fmt(n):
    return f'{n:,}' if isinstance(n, (int, float)) else ('—' if n is None else str(n))


def gap_text(seats, need):
    if seats is None and not need:
        return 'ไม่ได้ใช้', MUTED
    if seats is None:
        return 'ยังไม่ระบุ', AMBER
    if seats < need:
        return f'ขาด {need - seats:,}', RED
    if seats > need:
        return f'เหลือ {seats - need:,}', GREEN
    return 'พอดี', GREEN


# ---------- สร้างทั้งชุด ----------

def build_software_deck(d):
    """d = ข้อมูลที่ app.py เตรียมให้ (ดู _software_deck_data)"""
    prs = Presentation()
    prs.slide_width, prs.slide_height = Inches(13.333), Inches(7.5)
    blank = prs.slide_layouts[6]
    scope = d['scope']                       # 'ทุก BU' หรือ 'AMTV'
    foot  = f'รายงานบริหาร Software · {scope} · ข้อมูล ณ {th_date(d["today"])}'
    n = 0

    def new_slide():
        nonlocal n
        n += 1
        s = prs.slides.add_slide(blank)
        return s

    # 1) หน้าปก ─────────────────────────────────────────────
    s = new_slide()
    bg(s, DARK)
    text(s, 0.9, 2.2, 11.5, 0.5, 'รายงานสำหรับผู้บริหาร', size=18, color=LAVENDER)
    text(s, 0.9, 2.75, 11.5, 1.2, 'บริหาร Software ถือครอง', size=48, bold=True, color=WHITE)
    text(s, 0.9, 3.95, 11.5, 0.6, f'ขอบเขต: {scope}', size=22, color=SOFT2)
    text(s, 0.9, 5.9, 11.5, 0.4, f'ข้อมูล ณ วันที่ {th_date(d["today"])} · จากระบบ Amarin Employee Database',
         size=13, color=LAVENDER)
    s.notes_slide.notes_text_frame.text = (
        'ตัวเลขทั้งหมดดึงจากระบบ ณ วันที่ออกรายงาน — ชุดรวม Adobe All Apps นับเป็น 1 license '
        'ไม่นับโปรแกรมที่อยู่ในชุดซ้ำ')

    # 2) ภาพรวม ─────────────────────────────────────────────
    k = d['kpi']
    s = new_slide()
    bg(s, WHITE)
    title(s, f'ภาพรวม Software — {scope}',
          'ชุดรวม Adobe All Apps นับเป็น 1 license — ไม่นับโปรแกรมที่อยู่ในชุดซ้ำ')
    w, gx, x0, y0 = 2.85, 0.233, 0.6, 1.95
    stat(s, x0, y0, w, 2.6, fmt(k['licenses']), 'License ที่ใช้งาน',
         f'{k["products"]} รายการ Software ที่มีคนใช้')
    stat(s, x0 + (w + gx), y0, w, 2.6, fmt(k['employees']), 'พนักงานที่มี Software',
         f'จากพนักงาน Active {fmt(k["emp_active"])} คน' if k.get('emp_active') else '')
    stat(s, x0 + 2 * (w + gx), y0, w, 2.6, fmt(k['seats_total']), 'License ที่ซื้อไว้',
         f'ระบุจำนวนซื้อแล้ว {k["seats_known"]} จาก {k["products"]} รายการ')
    stat(s, x0 + 3 * (w + gx), y0, w, 2.6, fmt(k['over']), 'ใช้เกินจำนวนซื้อ',
         'ต้องซื้อเพิ่มหรือเรียกคืน' if k['over'] else 'ไม่มีรายการใช้เกิน',
         color=RED if k['over'] else GREEN)
    # ข้อความสรุปใต้ตัวเลข
    msg = [[('ประเด็นสำคัญ  ', {'bold': True, 'color': PRIMARY})]]
    for line in d['highlights'][:3]:
        msg.append([('•  ' + line, {})])
    card(s, 0.6, 4.85, 12.1, 1.85, fill=WHITE).line.color.rgb = SOFT2
    text(s, 0.9, 5.05, 11.5, 1.5, msg, size=15)
    footer(s, n, foot)

    # 3) Software ที่ใช้มากที่สุด ───────────────────────────
    top = d['top'][:10]
    if top:
        s = new_slide()
        bg(s, WHITE)
        title(s, f'Software ที่ใช้มากที่สุด {len(top)} อันดับแรก',
              'จำนวน license ที่ใช้งานจริง เทียบกับจำนวนที่ซื้อไว้')
        cd = CategoryChartData()
        cd.categories = [t['name'] for t in reversed(top)]
        cd.add_series('ใช้งาน', [t['used'] for t in reversed(top)])
        cd.add_series('ซื้อไว้', [t['seats'] or 0 for t in reversed(top)])
        gf = s.shapes.add_chart(XL_CHART_TYPE.BAR_CLUSTERED, Inches(0.6), Inches(1.75),
                                Inches(8.2), Inches(5.1), cd)
        ch = gf.chart
        _chart_fonts(ch)
        ch.has_legend = True
        ch.legend.position = XL_LEGEND_POSITION.TOP
        ch.legend.include_in_layout = False
        ch.legend.font.size = Pt(11)
        plot = ch.plots[0]
        plot.gap_width = 60
        plot.overlap = -10
        plot.has_data_labels = True
        plot.data_labels.font.size = Pt(10)
        plot.data_labels.font.color.rgb = INK
        plot.data_labels.position = XL_LABEL_POSITION.OUTSIDE_END
        for ser, col in zip(plot.series, (PRIMARY, LAVENDER)):
            ser.format.fill.solid()
            ser.format.fill.fore_color.rgb = col
        ch.value_axis.has_major_gridlines = False
        ch.value_axis.visible = False
        ch.category_axis.tick_labels.font.size = Pt(11)
        ch.category_axis.format.line.color.rgb = SOFT2
        # คอลัมน์ขวา: ข้อสังเกต
        card(s, 9.2, 1.75, 3.5, 5.1)
        text(s, 9.5, 2.0, 2.9, 0.4, 'ข้อสังเกต', size=18, bold=True, color=PRIMARY)
        notes = []
        for t in top:
            if t['seats'] is None:
                continue
            if t['used'] > t['seats']:
                notes.append([(f'{t["name"]}', {'bold': True}),
                              (f'  ใช้เกิน {t["used"] - t["seats"]:,}', {'color': RED, 'bold': True})])
            elif t['seats'] - t['used'] >= max(3, t['seats'] * 0.15):
                notes.append([(f'{t["name"]}', {'bold': True}),
                              (f'  ว่าง {t["seats"] - t["used"]:,}', {'color': GREEN, 'bold': True})])
        no_seat = [t['name'] for t in top if t['seats'] is None]
        if no_seat:
            notes.append([(f'ยังไม่ระบุจำนวนซื้อ {len(no_seat)} รายการ', {'color': AMBER, 'bold': True})])
        if not notes:
            notes = [[('ทุกรายการใช้ไม่เกินจำนวนที่ซื้อ', {})]]
        text(s, 9.5, 2.55, 2.9, 4.1, notes[:7], size=13)
        footer(s, n, foot)

    # 4) Adobe: ต้องต่ออายุเท่าไร ──────────────────────────
    ad = d.get('adobe')
    if ad and (ad['allapps'] or ad['singles']):
        s = new_slide()
        bg(s, WHITE)
        single_q = sum(x['qty'] for x in ad['singles'])
        title(s, 'แผนต่ออายุ License Adobe',
              f'All Apps สำหรับคนที่ถือชุดอยู่ หรือใช้ตั้งแต่ {ad["min"]} โปรแกรมขึ้นไป · '
              f'ที่เหลือซื้อแยกเฉพาะตัว')
        # ตัวเลขใหญ่ 3 ช่อง
        stat(s, 0.6, 1.95, 3.0, 2.2, fmt(ad['allapps']), 'All Apps (ชุดรวม)',
             (gap_text(ad['allapps_seats'], ad['allapps'])[0] +
              f' จากที่ซื้อ {ad["allapps_seats"]:,}') if ad['allapps_seats'] is not None
             else ('BU นี้ไม่ได้ใช้ All Apps' if not ad['allapps'] else 'ยังไม่ระบุจำนวนซื้อ'))
        stat(s, 0.6, 4.4, 3.0, 2.2, fmt(single_q), 'ซื้อแยกเฉพาะตัว',
             f'{len([x for x in ad["singles"] if x["qty"]])} โปรแกรม')
        rows = [['รายการ', 'ต้องใช้', 'ซื้อไว้', 'ขาด / เหลือ']]
        colors = {}
        items = [{'item': 'Creative Cloud (All Apps)', 'qty': ad['allapps'],
                  'seats': ad['allapps_seats']}] + ad['singles']
        for it in items:
            g, col = gap_text(it['seats'], it['qty'])
            rows.append([it['item'].replace('Adobe ', ''), fmt(it['qty']), fmt(it['seats']), g])
            colors[(len(rows) - 1, 3)] = col
        known = [it['seats'] for it in items if it['seats'] is not None]
        need = sum(it['qty'] for it in items)
        tot_seats = sum(known) if known else None
        tg = gap_text(tot_seats, need)[0] if len(known) == len(items) else (
             f'ระบุแล้ว {len(known)}/{len(items)}')
        rows.append(['รวมทั้งหมด', fmt(need), fmt(tot_seats), tg])
        table(s, 3.95, 1.95, 8.75, rows, [3.6, 1.6, 1.6, 1.95], align_right=(1, 2, 3),
              row_h=min(0.42, 4.7 / len(rows)), size=13, bold_last=True, colors=colors)
        footer(s, n, foot)

    # 5) แยกตาม BU (เฉพาะรายงานรวมทุก BU) ─────────────────
    if d.get('by_bu') and len(d['by_bu']) > 1:
        s = new_slide()
        bg(s, WHITE)
        title(s, 'Software แยกตาม BU', 'จำนวน license ที่ใช้ และสัดส่วนพนักงานที่บันทึกข้อมูลแล้ว')
        bus = d['by_bu'][:8]
        cd = CategoryChartData()
        cd.categories = [b['bu_code'] for b in bus]
        cd.add_series('License', [b['licenses'] for b in bus])
        gf = s.shapes.add_chart(XL_CHART_TYPE.COLUMN_CLUSTERED, Inches(0.6), Inches(1.75),
                                Inches(6.2), Inches(5.0), cd)
        ch = gf.chart
        _chart_fonts(ch)
        ch.has_legend = False
        plot = ch.plots[0]
        plot.gap_width = 70
        plot.has_data_labels = True
        plot.data_labels.font.size = Pt(12)
        plot.data_labels.font.bold = True
        plot.data_labels.font.color.rgb = INK
        plot.data_labels.position = XL_LABEL_POSITION.OUTSIDE_END
        plot.series[0].format.fill.solid()
        plot.series[0].format.fill.fore_color.rgb = PRIMARY
        ch.value_axis.visible = False
        ch.value_axis.has_major_gridlines = False
        ch.category_axis.tick_labels.font.size = Pt(12)
        rows = [['BU', 'License', 'คนที่มีข้อมูล', 'All Apps']]
        for b in bus:
            rows.append([b['bu_code'], fmt(b['licenses']),
                         f'{b["employees"]:,} / {b["emp_total"]:,}' if b.get('emp_total') else fmt(b['employees']),
                         fmt(b.get('allapps') or 0)])
        table(s, 7.2, 1.95, 5.5, rows, [1.2, 1.2, 1.7, 1.4], align_right=(1, 2, 3),
              row_h=0.42, size=13)
        footer(s, n, foot)

    # 6) สิ่งที่ต้องดำเนินการ ───────────────────────────────
    s = new_slide()
    bg(s, DARK)
    text(s, 0.6, 0.45, 12.1, 0.75, 'สิ่งที่ต้องดำเนินการ', size=32, bold=True, color=WHITE)
    acts = d['actions'] or [('✓', 'ไม่มีรายการเร่งด่วน', 'License ทุกรายการอยู่ในจำนวนที่ซื้อ และไม่มีรายการใกล้หมดอายุ')]
    cols = 2 if len(acts) > 2 else len(acts)
    rows_n = (len(acts[:4]) + cols - 1) // cols
    cw = (12.1 - 0.3 * (cols - 1)) / cols
    ch_ = min(2.4, (5.3 - 0.3 * (rows_n - 1)) / rows_n)
    for i, (_icon, head, body) in enumerate(acts[:4]):
        icon = '✓' if not d['actions'] else str(i + 1)   # ตัวเลขแทน emoji — ฟอนต์บางเครื่องไม่มี
        cx = 0.6 + (i % cols) * (cw + 0.3)
        cy = 1.6 + (i // cols) * (ch_ + 0.3)
        card(s, cx, cy, cw, ch_, fill=RGBColor(0x3B, 0x1A, 0x78))
        circ = s.shapes.add_shape(MSO_SHAPE.OVAL, Inches(cx + 0.3), Inches(cy + 0.3),
                                  Inches(0.6), Inches(0.6))
        circ.fill.solid()
        circ.fill.fore_color.rgb = PRIMARY
        circ.line.fill.background()
        text(s, cx + 0.3, cy + 0.3, 0.6, 0.6, icon, size=18, bold=True, color=WHITE,
             align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
        text(s, cx + 1.1, cy + 0.3, cw - 1.4, 0.6, head, size=18, bold=True, color=WHITE,
             anchor=MSO_ANCHOR.MIDDLE)
        text(s, cx + 1.1, cy + 1.0, cw - 1.4, ch_ - 1.15, body, size=13, color=SOFT2)
    text(s, 0.6, 7.0, 9, 0.3, foot, size=10, color=LAVENDER)
    text(s, 11.7, 7.0, 1.0, 0.3, str(n), size=10, color=LAVENDER, align=PP_ALIGN.RIGHT)

    buf = io.BytesIO()
    prs.save(buf)
    buf.seek(0)
    return buf


def build_vendor_deck(d):
    """Presentation เฉพาะผู้ผลิต (ตั้งต้น Adobe) — ใช้ใคร ใช้อะไร ต้องต่ออายุเท่าไร แยกฝ่าย"""
    prs = Presentation()
    prs.slide_width, prs.slide_height = Inches(13.333), Inches(7.5)
    blank = prs.slide_layouts[6]
    V, scope = d['vendor'], d['scope']
    foot = f'รายงาน License {V} · {scope} · ข้อมูล ณ {th_date(d["today"])}'
    n = 0

    def new_slide(color=WHITE):
        nonlocal n
        n += 1
        s = prs.slides.add_slide(blank)
        bg(s, color)
        return s

    plan = d.get('plan')          # None = ผู้ผลิตนี้ไม่มีเกณฑ์ชุดรวม

    # 1) ปก ──────────────────────────────────────────────
    s = new_slide(DARK)
    text(s, 0.9, 2.2, 11.5, 0.5, 'รายงานสำหรับผู้บริหาร', size=18, color=LAVENDER)
    text(s, 0.9, 2.75, 11.5, 1.2, f'License {V}' + (' — แผนต่ออายุ' if plan else ''),
         size=48, bold=True, color=WHITE)
    text(s, 0.9, 3.95, 11.5, 0.6, f'ขอบเขต: {scope}', size=22, color=SOFT2)
    text(s, 0.9, 5.9, 11.5, 0.4, f'ข้อมูล ณ วันที่ {th_date(d["today"])} · จากระบบ Amarin Employee Database',
         size=13, color=LAVENDER)
    if plan:
        s.notes_slide.notes_text_frame.text = (
            f'All Apps = คนที่ถือชุด All Apps อยู่ หรือใช้ {V} ตั้งแต่ {plan["min"]} โปรแกรมขึ้นไป '
            f'คนที่เหลือซื้อแยกเฉพาะโปรแกรมที่ใช้')

    # 2) ภาพรวม ──────────────────────────────────────────
    k = d['kpi']
    s = new_slide()
    title(s, f'ภาพรวมการใช้ {V} — {scope}',
          f'คนที่ใช้ {V} {k["people"]:,} คน ใน {k["depts"]} ฝ่าย')
    w, gx, x0, y0 = 2.85, 0.233, 0.6, 1.95
    stat(s, x0, y0, w, 2.6, fmt(k['people']), f'คนที่ใช้ {V}', f'{k["products"]} โปรแกรมที่มีคนใช้')
    if plan:
        stat(s, x0 + (w + gx), y0, w, 2.6, fmt(plan['allapps']), 'All Apps (ชุดรวม)',
             f'ใช้ได้ทุกโปรแกรมของ {V}')
        stat(s, x0 + 2 * (w + gx), y0, w, 2.6, fmt(plan['single_total']), 'License ซื้อแยก',
             f'สำหรับ {plan["few_people"]:,} คนที่ใช้ไม่ถึง {plan["min"]} โปรแกรม')
        if plan['seats_complete']:
            g, col = gap_text(plan['seats_total'], plan['need_total'])
            sub = f'ซื้อไว้ {plan["seats_total"]:,} → {g}'
        else:
            col, sub = AMBER, f'ระบุจำนวนซื้อแล้ว {plan["seats_known"]}/{plan["items_n"]} รายการ'
        stat(s, x0 + 3 * (w + gx), y0, w, 2.6, fmt(plan['need_total']), 'License ที่ต้องมี',
             sub, color=col if col == RED else PRIMARY)
    else:
        stat(s, x0 + (w + gx), y0, w, 2.6, fmt(k['licenses']), 'License ที่ใช้', '')
        stat(s, x0 + 2 * (w + gx), y0, w, 2.6, fmt(k.get('seats')), 'License ที่ซื้อไว้',
             f'ระบุจำนวนซื้อแล้ว {k.get("seats_known", 0)}/{k["products"]} รายการ')
        stat(s, x0 + 3 * (w + gx), y0, w, 2.6, fmt(k.get('over', 0)), 'ใช้เกินจำนวนซื้อ',
             'ต้องซื้อเพิ่มหรือเรียกคืน' if k.get('over') else 'ไม่มีรายการใช้เกิน',
             color=RED if k.get('over') else GREEN)
    msg = [[('ประเด็นสำคัญ  ', {'bold': True, 'color': PRIMARY})]]
    for line in d['highlights'][:3]:
        msg.append([('•  ' + line, {})])
    card(s, 0.6, 4.85, 12.1, 1.85, fill=WHITE).line.color.rgb = SOFT2
    text(s, 0.9, 5.05, 11.5, 1.5, msg, size=15)
    footer(s, n, foot)

    # 3) ใช้โปรแกรมไหนบ้าง (ผ่านชุดรวม vs ซื้อแยก) ─────────────
    prods = d['products'][:9]
    if prods:
        s = new_slide()
        title(s, f'คนใช้โปรแกรม {V} ตัวไหนบ้าง',
              'จำนวนคนที่ใช้แต่ละโปรแกรม — แยกว่าใช้ผ่าน All Apps หรือต้องซื้อแยก' if plan
              else 'จำนวนคนที่ใช้แต่ละโปรแกรม')
        cd = CategoryChartData()
        cd.categories = [p['name'].replace(f'{V} ', '') for p in reversed(prods)]
        if plan:
            cd.add_series('ใช้ผ่าน All Apps', [p['total'] - p['single'] for p in reversed(prods)])
            cd.add_series('ซื้อแยก', [p['single'] for p in reversed(prods)])
            kind = XL_CHART_TYPE.BAR_STACKED
        else:
            cd.add_series('คนที่ใช้', [p['total'] for p in reversed(prods)])
            kind = XL_CHART_TYPE.BAR_CLUSTERED
        gf = s.shapes.add_chart(kind, Inches(0.6), Inches(1.75), Inches(8.2), Inches(5.1), cd)
        ch = gf.chart
        _chart_fonts(ch)
        ch.has_legend = bool(plan)
        if plan:
            ch.legend.position = XL_LEGEND_POSITION.TOP
            ch.legend.include_in_layout = False
            ch.legend.font.size = Pt(11)
        pl = ch.plots[0]
        pl.gap_width = 55
        if plan:
            pl.overlap = 100
        pl.has_data_labels = True
        pl.data_labels.font.size = Pt(10)
        pl.data_labels.position = XL_LABEL_POSITION.CENTER if plan else XL_LABEL_POSITION.OUTSIDE_END
        for ser, col in zip(pl.series, (LAVENDER, PRIMARY)):
            ser.format.fill.solid()
            ser.format.fill.fore_color.rgb = col
        if plan:   # ป้ายบนแท่งเข้มเป็นสีขาว
            pl.series[1].data_labels.font.color.rgb = WHITE
            pl.series[1].data_labels.font.size = Pt(10)
            pl.series[1].data_labels.position = XL_LABEL_POSITION.CENTER
        ch.value_axis.visible = False
        ch.value_axis.has_major_gridlines = False
        ch.category_axis.tick_labels.font.size = Pt(11)
        ch.category_axis.format.line.color.rgb = SOFT2
        card(s, 9.2, 1.75, 3.5, 5.1)
        text(s, 9.5, 2.0, 2.9, 0.4, 'อ่านกราฟนี้', size=18, bold=True, color=PRIMARY)
        lines = []
        if plan:
            top1 = max(prods, key=lambda p: p['total'])
            lines.append([(f'{top1["name"].replace(V + " ", "")} ', {'bold': True}),
                          (f'มีคนใช้มากที่สุด {top1["total"]:,} คน', {})])
            cov = sum(p['total'] - p['single'] for p in prods)
            tot = sum(p['total'] for p in prods)
            if not plan['allapps']:
                lines.append([('ไม่มีคนใช้ All Apps ', {'bold': True}),
                              ('— ทุกคนใช้ license ที่ซื้อแยกเฉพาะโปรแกรม', {})])
            elif tot:
                lines.append([(f'{cov / tot * 100:.0f}% ', {'bold': True, 'color': PRIMARY}),
                              ('ของการใช้งานอยู่ใน All Apps แล้ว ไม่ต้องซื้อแยก', {})])
            lines.append([('ส่วนสีเข้ม ', {'bold': True}),
                          ('คือ license ที่ต้องซื้อแยกให้คนที่ใช้ไม่ถึงเกณฑ์', {})])
        else:
            for p in prods[:5]:
                lines.append([(p['name'], {'bold': True}), (f'  {p["total"]:,} คน', {})])
        text(s, 9.5, 2.55, 2.9, 4.1, lines, size=13)
        footer(s, n, foot)

    # 4) แผนต่ออายุ ───────────────────────────────────────
    if plan:
        s = new_slide()
        title(s, 'ต้องต่ออายุอะไร กี่ License',
              f'All Apps สำหรับคนที่ถือชุดอยู่ หรือใช้ตั้งแต่ {plan["min"]} โปรแกรมขึ้นไป · ที่เหลือซื้อแยก')
        rows = [['รายการ', 'ต้องใช้', 'ซื้อไว้', 'ขาด / เหลือ', 'ไว้ให้ใคร']]
        colors = {}
        for it in plan['items']:
            g, col = gap_text(it['seats'], it['qty'])
            rows.append([it['item'].replace(f'{V} ', ''), fmt(it['qty']), fmt(it['seats']), g, it['who']])
            colors[(len(rows) - 1, 3)] = col
        tg = gap_text(plan['seats_total'], plan['need_total'])[0] if plan['seats_complete'] \
            else f'ระบุแล้ว {plan["seats_known"]}/{plan["items_n"]}'
        rows.append(['รวมทั้งหมด', fmt(plan['need_total']), fmt(plan['seats_total']), tg,
                     f'{plan["allapps"]:,} All Apps + {plan["single_total"]:,} ซื้อแยก'])
        table(s, 0.6, 1.85, 12.1, rows, [3.4, 1.4, 1.4, 1.9, 4.0], align_right=(1, 2, 3),
              row_h=min(0.44, 4.9 / len(rows)), size=13, bold_last=True, colors=colors)
        footer(s, n, foot)

    # 5) แยกตามฝ่าย ──────────────────────────────────────
    depts = d['depts']
    if depts:
        s = new_slide()
        show = depts[:10]
        title(s, f'ฝ่ายที่ใช้ {V} มากที่สุด',
              f'{len(show)} จาก {len(depts)} ฝ่าย เรียงตามจำนวนคนที่ใช้' if len(depts) > len(show)
              else f'ทุกฝ่ายที่ใช้ {V} เรียงตามจำนวนคน')
        multi_bu = len({x['bu_code'] for x in depts}) > 1
        head = (['BU'] if multi_bu else []) + ['ฝ่าย / แผนก', 'คนที่ใช้'] + \
               (['All Apps', 'ซื้อแยก', 'รวม License'] if plan else ['License'])
        rows = [head]
        for x in show:
            r = ([x['bu_code']] if multi_bu else []) + [x['department'], fmt(x['people'])]
            r += [fmt(x['allapps']), fmt(x['singles']), fmt(x['allapps'] + x['singles'])] if plan \
                else [fmt(x['licenses'])]
            rows.append(r)
        nc = len(head)
        num_w = 1.45
        first = [1.1] if multi_bu else []
        dept_w = 12.1 - sum(first) - num_w * (nc - len(first) - 1)
        table(s, 0.6, 1.85, 12.1, rows, first + [dept_w] + [num_w] * (nc - len(first) - 1),
              align_right=tuple(range(len(first) + 1, nc)),
              row_h=min(0.42, 4.9 / len(rows)), size=12)
        footer(s, n, foot)

    # 6) สิ่งที่ต้องดำเนินการ ──────────────────────────────
    s = new_slide(DARK)
    text(s, 0.6, 0.45, 12.1, 0.75, 'สิ่งที่ต้องดำเนินการ', size=32, bold=True, color=WHITE)
    acts = d['actions'] or [('', 'ไม่มีรายการเร่งด่วน',
                             f'License {V} พอกับจำนวนที่ใช้ และไม่มีรายการใกล้หมดอายุ')]
    cols = 2 if len(acts) > 1 else 1
    rows_n = (len(acts[:4]) + cols - 1) // cols
    cw = (12.1 - 0.3 * (cols - 1)) / cols
    chh = min(2.4, (5.3 - 0.3 * (rows_n - 1)) / rows_n)
    for i, (_i, head, body) in enumerate(acts[:4]):
        cx = 0.6 + (i % cols) * (cw + 0.3)
        cy = 1.6 + (i // cols) * (chh + 0.3)
        card(s, cx, cy, cw, chh, fill=RGBColor(0x3B, 0x1A, 0x78))
        circ = s.shapes.add_shape(MSO_SHAPE.OVAL, Inches(cx + 0.3), Inches(cy + 0.3),
                                  Inches(0.6), Inches(0.6))
        circ.fill.solid()
        circ.fill.fore_color.rgb = PRIMARY
        circ.line.fill.background()
        text(s, cx + 0.3, cy + 0.3, 0.6, 0.6, '✓' if not d['actions'] else str(i + 1),
             size=18, bold=True, color=WHITE, align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
        text(s, cx + 1.1, cy + 0.3, cw - 1.4, 0.6, head, size=18, bold=True, color=WHITE,
             anchor=MSO_ANCHOR.MIDDLE)
        text(s, cx + 1.1, cy + 1.0, cw - 1.4, chh - 1.15, body, size=13, color=SOFT2)
    text(s, 0.6, 7.0, 9, 0.3, foot, size=10, color=LAVENDER)
    text(s, 11.7, 7.0, 1.0, 0.3, str(n), size=10, color=LAVENDER, align=PP_ALIGN.RIGHT)

    buf = io.BytesIO()
    prs.save(buf)
    buf.seek(0)
    return buf
