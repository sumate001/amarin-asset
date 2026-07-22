"""สร้างรายงาน PDF การใช้งานเครื่อง IT — เน้นความสัมพันธ์ ประเภทเครื่อง × ตำแหน่งงาน

ใช้ฟอนต์ Sarabun (OFL) ที่ bundle มาใน static/fonts เพราะเครื่อง server
ไม่มีฟอนต์ไทยติดตั้งไว้ — ถ้าไม่ embed ตัวอักษรไทยจะกลายเป็นสี่เหลี่ยม
"""
import io
import os
from collections import Counter, defaultdict
from datetime import datetime

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (BaseDocTemplate, Frame, KeepTogether, PageBreak,
                                PageTemplate, Paragraph, Spacer, Table, TableStyle)

FONT_DIR = os.path.join(os.path.dirname(__file__), 'static', 'fonts')
FONT     = 'Sarabun'
FONT_B   = 'Sarabun-Bold'

# ── palette (ล้อสีกับหน้าเว็บ) ─────────────────────────────────────
NAVY    = colors.HexColor('#1E3A5F')
BLUE    = colors.HexColor('#2563eb')
SLATE   = colors.HexColor('#475569')
MUTED   = colors.HexColor('#94a3b8')
LINE    = colors.HexColor('#e2e8f0')
BG_ALT  = colors.HexColor('#f8fafc')
BG_HEAD = colors.HexColor('#eff6ff')
GREEN   = colors.HexColor('#15803d')
AMBER   = colors.HexColor('#b45309')

_fonts_ready = False


def _ensure_fonts():
    global _fonts_ready
    if _fonts_ready:
        return
    pdfmetrics.registerFont(TTFont(FONT,   os.path.join(FONT_DIR, 'Sarabun-Regular.ttf')))
    pdfmetrics.registerFont(TTFont(FONT_B, os.path.join(FONT_DIR, 'Sarabun-Bold.ttf')))
    pdfmetrics.registerFontFamily(FONT, normal=FONT, bold=FONT_B)
    _fonts_ready = True


def _style(name, size, color=colors.black, bold=False, align=TA_LEFT, leading=None, space=0):
    return ParagraphStyle(name, fontName=FONT_B if bold else FONT, fontSize=size,
                          textColor=color, alignment=align,
                          leading=leading or size * 1.35, spaceAfter=space)


UNSPEC_MACHINE  = '(ยังไม่ระบุ)'
UNSPEC_POSITION = '(ไม่ระบุตำแหน่ง)'
MAX_POSITIONS   = 28    # แถวในตารางไขว้ — เกินกว่านี้ยุบเป็น 'อื่น ๆ'
MAX_DETAIL_ROWS = 400   # กันไฟล์บวมเมื่อ filter กว้าง


def _machine_of(r):
    return (r.get('machine_type') or '').strip() or UNSPEC_MACHINE


def _position_of(r):
    if r.get('is_central'):
        return 'ส่วนกลาง (ไม่มีผู้ถือครอง)'
    return (r.get('emp_position') or '').strip() or UNSPEC_POSITION


def _fmt_baht(n):
    return '฿{:,.0f}'.format(n or 0)


# ══════════════════════════════════════════════════════════════════
#  page furniture
# ══════════════════════════════════════════════════════════════════

def _draw_frame(canvas, doc):
    canvas.saveState()
    w, h = landscape(A4)

    # แถบหัวกระดาษ
    canvas.setFillColor(NAVY)
    canvas.rect(0, h - 17 * mm, w, 17 * mm, stroke=0, fill=1)
    canvas.setFillColor(colors.white)
    canvas.setFont(FONT_B, 12)
    canvas.drawString(12 * mm, h - 11 * mm, 'รายงานการใช้งานเครื่อง IT — ประเภทเครื่อง × ตำแหน่งงาน')
    canvas.setFont(FONT, 8.5)
    canvas.drawRightString(w - 12 * mm, h - 11 * mm, 'Amarin Employee Database')

    # เส้นคั่นท้ายกระดาษ + เลขหน้า
    canvas.setStrokeColor(LINE)
    canvas.setLineWidth(0.6)
    canvas.line(12 * mm, 12 * mm, w - 12 * mm, 12 * mm)
    canvas.setFillColor(MUTED)
    canvas.setFont(FONT, 7.5)
    canvas.drawString(12 * mm, 8 * mm,
                      'ออกรายงานเมื่อ ' + doc._generated_at)
    canvas.drawRightString(w - 12 * mm, 8 * mm, 'หน้า %d' % doc.page)
    canvas.restoreState()


def _doc(buf, generated_at):
    w, h = landscape(A4)
    doc = BaseDocTemplate(buf, pagesize=landscape(A4),
                          leftMargin=12 * mm, rightMargin=12 * mm,
                          topMargin=22 * mm, bottomMargin=16 * mm,
                          title='รายงานการใช้งานเครื่อง IT',
                          author='Amarin Employee Database')
    doc._generated_at = generated_at
    frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id='main')
    doc.addPageTemplates([PageTemplate(id='all', frames=[frame], onPage=_draw_frame)])
    return doc


def _section(title, note=None):
    out = [Spacer(1, 5 * mm),
           Paragraph(title, _style('h2', 11.5, NAVY, bold=True))]
    if note:
        out.append(Paragraph(note, _style('note', 8, MUTED, space=1)))
    out.append(Spacer(1, 2 * mm))
    return out


# ══════════════════════════════════════════════════════════════════
#  main
# ══════════════════════════════════════════════════════════════════

def build_asset_report(rows, filter_labels):
    """rows = asset dict ที่ผ่าน filter แล้ว, filter_labels = list ข้อความ filter ที่ใช้"""
    _ensure_fonts()
    generated_at = datetime.now().strftime('%d/%m/%Y %H:%M น.')
    buf = io.BytesIO()
    doc = _doc(buf, generated_at)
    W   = doc.width
    story = []

    # ── ตัวกรองที่ใช้ ────────────────────────────────────────────
    story.append(Paragraph(
        'ตัวกรองที่ใช้: ' + (' &nbsp;·&nbsp; '.join(filter_labels) if filter_labels
                             else 'ไม่มี (แสดงข้อมูลทั้งหมด)'),
        _style('flt', 8.5, SLATE)))
    story.append(Spacer(1, 4 * mm))

    # ── KPI ─────────────────────────────────────────────────────
    total    = len(rows)
    monthly  = sum(r.get('monthly_charge') or 0 for r in rows)
    machines = Counter(_machine_of(r) for r in rows)
    spec_cnt = total - machines.get(UNSPEC_MACHINE, 0)
    positions = {_position_of(r) for r in rows}
    pct = (spec_cnt / total * 100) if total else 0

    kpis = [
        ('เครื่องทั้งหมด',        '{:,}'.format(total),                  NAVY),
        ('ค่าเช่ารวม / เดือน',    _fmt_baht(monthly),                    BLUE),
        ('ระบุประเภทเครื่องแล้ว', '{:,} ({:.1f}%)'.format(spec_cnt, pct),
                                   GREEN if pct >= 50 else AMBER),
        ('ประเภทเครื่องที่พบ',    '{:,}'.format(len([m for m in machines if m != UNSPEC_MACHINE]))
                                   + ' ประเภท',                          NAVY),
        ('ตำแหน่งงานที่เกี่ยวข้อง', '{:,}'.format(len(positions)) + ' ตำแหน่ง', NAVY),
    ]
    kpi_tbl = Table(
        [[Paragraph(lbl, _style('kl', 8, SLATE, align=TA_CENTER)) for lbl, _, _ in kpis],
         [Paragraph(val, _style('kv', 15, col, bold=True, align=TA_CENTER)) for _, val, col in kpis]],
        colWidths=[W / len(kpis)] * len(kpis))
    kpi_tbl.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), BG_ALT),
        ('BOX',        (0, 0), (-1, -1), 0.6, LINE),
        ('INNERGRID',  (0, 0), (-1, -1), 0.6, colors.white),
        ('VALIGN',     (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, 0), 6), ('BOTTOMPADDING', (0, 1), (-1, 1), 7),
    ]))
    story.append(kpi_tbl)

    if not total:
        story += _section('ไม่พบข้อมูล')
        story.append(Paragraph('ไม่มีเครื่องที่ตรงกับตัวกรองที่เลือกไว้', _style('e', 10, SLATE)))
        doc.build(story)
        buf.seek(0)
        return buf

    # ══ 1. ตารางไขว้ ประเภทเครื่อง × ตำแหน่งงาน ═══════════════════
    # คอลัมน์ = ประเภทเครื่อง (ที่ระบุแล้วก่อน, ยังไม่ระบุไว้ท้ายสุด)
    cols = sorted([m for m in machines if m != UNSPEC_MACHINE],
                  key=lambda m: (-machines[m], m))
    if UNSPEC_MACHINE in machines:
        cols.append(UNSPEC_MACHINE)

    grid = defaultdict(Counter)
    for r in rows:
        grid[_position_of(r)][_machine_of(r)] += 1

    # เรียงตามจำนวนเครื่องที่ "ระบุประเภทแล้ว" ก่อน — ไม่งั้นแถวที่มีข้อมูลจริง
    # จะจมอยู่ใต้ตำแหน่งที่มีเครื่องเยอะแต่ยังไม่ได้กรอกประเภทเลย
    def _spec(p):
        return sum(n for m, n in grid[p].items() if m != UNSPEC_MACHINE)

    xt_order  = sorted(grid, key=lambda p: (-_spec(p), -sum(grid[p].values()), p))
    pos_order = sorted(grid, key=lambda p: (-sum(grid[p].values()), p))
    shown_pos, rest = xt_order[:MAX_POSITIONS], xt_order[MAX_POSITIONS:]

    hdr_st  = _style('th', 7.2, colors.white, bold=True, align=TA_CENTER, leading=8.6)
    pos_st  = _style('tp', 7.6, colors.black, leading=9.2)
    num_st  = _style('tn', 8, colors.black, align=TA_CENTER)
    zero_st = _style('tz', 8, colors.HexColor('#cbd5e1'), align=TA_CENTER)
    tot_st  = _style('tt', 8, NAVY, bold=True, align=TA_CENTER)

    def cell(n, style=None):
        return Paragraph('{:,}'.format(n) if n else '·', style or (num_st if n else zero_st))

    head = [Paragraph('ตำแหน่งงาน', hdr_st)] + \
           [Paragraph(c, hdr_st) for c in cols] + \
           [Paragraph('รวม', hdr_st)]
    body = []
    for p in shown_pos:
        c = grid[p]
        body.append([Paragraph(p, pos_st)] + [cell(c.get(m, 0)) for m in cols] +
                    [cell(sum(c.values()), tot_st)])
    if rest:
        agg = Counter()
        for p in rest:
            agg.update(grid[p])
        body.append([Paragraph('อื่น ๆ อีก {:,} ตำแหน่ง'.format(len(rest)),
                               _style('to', 7.6, SLATE))] +
                    [cell(agg.get(m, 0)) for m in cols] + [cell(sum(agg.values()), tot_st)])
    foot = [Paragraph('รวมทั้งสิ้น', _style('tf', 8, NAVY, bold=True))] + \
           [cell(machines.get(m, 0), tot_st) for m in cols] + [cell(total, tot_st)]

    pos_w  = 62 * mm
    each_w = (W - pos_w - 20 * mm) / max(len(cols), 1)
    xt = Table([head] + body + [foot],
               colWidths=[pos_w] + [each_w] * len(cols) + [20 * mm],
               repeatRows=1)
    xt.setStyle(TableStyle([
        ('BACKGROUND',    (0, 0), (-1, 0), NAVY),
        ('BACKGROUND',    (0, -1), (-1, -1), BG_HEAD),
        ('ROWBACKGROUNDS', (0, 1), (-1, -2), [colors.white, BG_ALT]),
        ('GRID',          (0, 0), (-1, -1), 0.4, LINE),
        ('BOX',           (0, 0), (-1, -1), 0.7, NAVY),
        ('LINEABOVE',     (0, -1), (-1, -1), 0.9, NAVY),
        ('VALIGN',        (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING',    (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('LEFTPADDING',   (0, 0), (-1, -1), 4),
        ('RIGHTPADDING',  (0, 0), (-1, -1), 4),
    ]))
    story += _section('1. ตารางไขว้ — ตำแหน่งงาน × ประเภทเครื่อง',
                      'เรียงตามจำนวนเครื่องที่ระบุประเภทแล้วมากไปน้อย · '
                      'เครื่องหมาย · คือไม่มีเครื่องในช่องนั้น')
    story.append(xt)

    # ══ 2. สรุปตามประเภทเครื่อง ══════════════════════════════════
    story.append(PageBreak())
    story += _section('2. สรุปรายประเภทเครื่อง',
                      'ตำแหน่งงานหลัก = ตำแหน่งที่ใช้เครื่องประเภทนั้นมากที่สุด 3 อันดับแรก')

    m_rows = [[Paragraph(t, hdr_st) for t in
               ['ประเภทเครื่อง', 'จำนวน', 'สัดส่วน', 'ค่าเช่า/เดือน',
                'ตำแหน่งงานหลัก (3 อันดับแรก)', 'BU หลัก']]]
    for m in cols:
        sub = [r for r in rows if _machine_of(r) == m]
        top_pos = Counter(_position_of(r) for r in sub).most_common(3)
        top_bu  = Counter((r.get('emp_bu_code') or '—') for r in sub).most_common(3)
        m_rows.append([
            Paragraph(m, _style('m', 8, colors.black if m != UNSPEC_MACHINE else MUTED)),
            Paragraph('{:,}'.format(len(sub)), _style('m', 8, align=TA_CENTER, bold=True)),
            Paragraph('{:.1f}%'.format(len(sub) / total * 100), _style('m', 8, SLATE, align=TA_CENTER)),
            Paragraph(_fmt_baht(sum(r.get('monthly_charge') or 0 for r in sub)),
                      _style('m', 8, align=TA_CENTER)),
            Paragraph(' · '.join('%s (%d)' % (p, n) for p, n in top_pos) or '—',
                      _style('m', 7.6, SLATE, leading=9.2)),
            Paragraph(' · '.join('%s (%d)' % (b, n) for b, n in top_bu) or '—',
                      _style('m', 7.6, SLATE)),
        ])
    mt = Table(m_rows, colWidths=[W * .20, W * .07, W * .07, W * .11, W * .40, W * .15], repeatRows=1)
    mt.setStyle(TableStyle([
        ('BACKGROUND',     (0, 0), (-1, 0), NAVY),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, BG_ALT]),
        ('GRID',           (0, 0), (-1, -1), 0.4, LINE),
        ('BOX',            (0, 0), (-1, -1), 0.7, NAVY),
        ('VALIGN',         (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING',     (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING',  (0, 0), (-1, -1), 4),
    ]))
    story.append(mt)

    # ══ 3. Top ตำแหน่งงาน ════════════════════════════════════════
    story += _section('3. ตำแหน่งงานที่ใช้เครื่องมากที่สุด 15 อันดับแรก',
                      'แถบแสดงสัดส่วนจำนวนเครื่องเทียบกับอันดับ 1')
    top15 = pos_order[:15]
    top_n = sum(grid[top15[0]].values()) if top15 else 1
    BAR_W = W * .30
    p_rows = [[Paragraph(t, hdr_st) for t in
               ['อันดับ', 'ตำแหน่งงาน', 'จำนวนเครื่อง', 'สัดส่วน', 'ประเภทเครื่องที่ใช้']]]
    for i, p in enumerate(top15, 1):
        n = sum(grid[p].values())
        bar_len = max(int(BAR_W * n / top_n), 2)
        bar = Table([['']], colWidths=[bar_len], rowHeights=[6])
        bar.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, -1), BLUE),
                                 ('LEFTPADDING', (0, 0), (-1, -1), 0),
                                 ('RIGHTPADDING', (0, 0), (-1, -1), 0)]))
        p_rows.append([
            Paragraph(str(i), _style('p', 8, MUTED, align=TA_CENTER)),
            Paragraph(p, _style('p', 8)),
            Paragraph('{:,}'.format(n), _style('p', 8, bold=True, align=TA_CENTER)),
            bar,
            Paragraph(' · '.join('%s (%d)' % (m, c) for m, c in grid[p].most_common()),
                      _style('p', 7.4, SLATE, leading=9)),
        ])
    pt = Table(p_rows, colWidths=[W * .06, W * .24, W * .09, BAR_W, W - (W * .39) - BAR_W],
               repeatRows=1)
    pt.setStyle(TableStyle([
        ('BACKGROUND',     (0, 0), (-1, 0), NAVY),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, BG_ALT]),
        ('GRID',           (0, 0), (-1, -1), 0.4, LINE),
        ('BOX',            (0, 0), (-1, -1), 0.7, NAVY),
        ('VALIGN',         (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN',          (3, 1), (3, -1), 'LEFT'),
        ('TOPPADDING',     (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING',  (0, 0), (-1, -1), 4),
    ]))
    story.append(pt)

    # ══ 4. รายการเครื่องที่ระบุประเภทแล้ว ═════════════════════════
    detail = [r for r in rows if _machine_of(r) != UNSPEC_MACHINE]
    detail.sort(key=lambda r: (_machine_of(r), _position_of(r), r.get('user_name') or ''))
    if detail:
        story.append(PageBreak())
        note = 'เฉพาะเครื่องที่กรอกช่อง “ประเภท” ใน eDevice แล้ว ({:,} จาก {:,} เครื่อง)'.format(
            len(detail), total)
        if len(detail) > MAX_DETAIL_ROWS:
            note += ' · แสดง {:,} รายการแรก'.format(MAX_DETAIL_ROWS)
            detail = detail[:MAX_DETAIL_ROWS]
        story += _section('4. รายการเครื่องที่ระบุประเภทเครื่องแล้ว', note)

        d_rows = [[Paragraph(t, hdr_st) for t in
                   ['ประเภทเครื่อง', 'Asset No.', 'รหัสเครื่อง', 'ประเภท', 'รุ่น',
                    'ผู้ถือครอง', 'ตำแหน่งงาน', 'BU', 'แผนก', 'สัญญา']]]
        cell_st = _style('d', 7.2, colors.black, leading=8.8)
        for r in detail:
            d_rows.append([
                Paragraph(_machine_of(r), cell_st),
                Paragraph(r.get('asset_no') or '—', cell_st),
                Paragraph(r.get('computer_id') or '—', cell_st),
                Paragraph(r.get('asset_type') or '—', cell_st),
                Paragraph(r.get('model') or r.get('brand') or '—', cell_st),
                Paragraph('ส่วนกลาง' if r.get('is_central') else (r.get('user_name') or '—'), cell_st),
                Paragraph(_position_of(r), cell_st),
                Paragraph(r.get('emp_bu_code') or '—', cell_st),
                Paragraph(r.get('emp_dept') or r.get('dept_sheet') or '—', cell_st),
                Paragraph(r.get('ownership') or '—', cell_st),
            ])
        dt = Table(d_rows, colWidths=[W * .155, W * .075, W * .07, W * .06, W * .105,
                                      W * .115, W * .16, W * .04, W * .155, W * .045],
                   repeatRows=1)
        dt.setStyle(TableStyle([
            ('BACKGROUND',     (0, 0), (-1, 0), NAVY),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, BG_ALT]),
            ('GRID',           (0, 0), (-1, -1), 0.4, LINE),
            ('BOX',            (0, 0), (-1, -1), 0.7, NAVY),
            ('VALIGN',         (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING',     (0, 0), (-1, -1), 2.5),
            ('BOTTOMPADDING',  (0, 0), (-1, -1), 2.5),
        ]))
        story.append(dt)

    # ── หมายเหตุท้ายรายงาน ──────────────────────────────────────
    unspec = machines.get(UNSPEC_MACHINE, 0)
    if unspec:
        story.append(Spacer(1, 5 * mm))
        story.append(Paragraph(
            '⚠ หมายเหตุ: มี {:,} เครื่อง ({:.1f}%) ที่ยังไม่ได้กรอกช่อง “ประเภท” ใน eDevice '
            'ตัวเลขในรายงานนี้จึงสะท้อนเฉพาะเครื่องที่มีข้อมูลครบ '
            'แนะนำให้ปรับปรุงข้อมูลใน eDevice เพื่อให้รายงานสมบูรณ์ขึ้น'.format(
                unspec, unspec / total * 100),
            _style('warn', 8, AMBER, leading=11)))

    doc.build(story)
    buf.seek(0)
    return buf
