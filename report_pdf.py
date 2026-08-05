"""สร้างรายงาน PDF การใช้งานเครื่อง IT — ประเภทเครื่อง × ตำแหน่งงาน × รุ่นเครื่อง

ใช้ฟอนต์ Sarabun (OFL) ที่ bundle มาใน static/fonts เพราะเครื่อง server
ไม่มีฟอนต์ไทยติดตั้งไว้ — ถ้าไม่ embed ตัวอักษรไทยจะกลายเป็นสี่เหลี่ยม
"""
import io
import os
import re
from collections import Counter, defaultdict
from datetime import datetime

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (BaseDocTemplate, CondPageBreak, Frame, PageBreak,
                                PageTemplate, Paragraph, Spacer, Table, TableStyle)

FONT_DIR = os.path.join(os.path.dirname(__file__), 'static', 'fonts')
FONT     = 'Sarabun'
FONT_B   = 'Sarabun-Bold'

# ── palette ────────────────────────────────────────────────────────
# categorical slots ตามลำดับตายตัว (ห้ามวนซ้ำ) — ผ่านเกณฑ์ CVD/contrast
# สำหรับคู่สีที่อยู่ติดกันบนพื้นสว่าง ซึ่งตรงกับการใช้งานที่นี่
# (หัวคอลัมน์เรียงติดกัน) และทุกช่องมี label กำกับเสมอ
CAT = ['#2a78d6', '#eb6834', '#1baf7a', '#eda100', '#e87ba4',
       '#008300', '#4a3aa7', '#e34948', '#0f766e', '#9a3412']
NEUTRAL = '#94a3b8'          # ใช้กับ "(ยังไม่ระบุ)" — เป็นความว่าง ไม่ใช่ identity

INK     = colors.HexColor('#0f172a')
SLATE   = colors.HexColor('#475569')
MUTED   = colors.HexColor('#94a3b8')
LINE    = colors.HexColor('#dbe3ec')
WHITE   = colors.white
BRAND   = colors.HexColor('#2a78d6')
GREEN   = colors.HexColor('#008300')
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


def _tint(hex_color, alpha):
    """ผสมสีกับพื้นขาว — ได้เฉดอ่อนของ hue เดิม (sequential ramp หนึ่ง hue)"""
    c = colors.HexColor(hex_color)
    return colors.Color(1 - (1 - c.red) * alpha,
                        1 - (1 - c.green) * alpha,
                        1 - (1 - c.blue) * alpha)


def _style(name, size, color=INK, bold=False, align=TA_LEFT, leading=None):
    return ParagraphStyle(name, fontName=FONT_B if bold else FONT, fontSize=size,
                          textColor=color, alignment=align, leading=leading or size * 1.3)


UNSPEC_MACHINE  = '(ยังไม่ระบุ)'
UNSPEC_POSITION = '(ไม่ระบุตำแหน่ง)'

# ── ลำดับมาตรฐานของประเภทเครื่อง + ชื่อเต็มตามที่หน่วยงานกำหนด ──────
# คอลัมน์/แถวในรายงานเรียงตามลำดับนี้เสมอ (ไม่เรียงตามจำนวน)
# ประเภทที่ไม่อยู่ในลิสต์นี้จะต่อท้ายตามจำนวนมากไปน้อย
MACHINE_ORDER = [
    ('NB สำนักงานทั่วไป',
     'เครื่องคอมพิวเตอร์แบบพกพาสำหรับใช้งานสำนักงานทั่วไป'),
    ('NB สำนักงานประสิทธิภาพสูง 15.6 นิ้ว',
     'เครื่องคอมพิวเตอร์แบบพกพาสำหรับใช้งานสำนักงาน (ประสิทธิภาพสูง) จอ 15.6 นิ้ว'),
    ('NB สำนักงานประสิทธิภาพสูง 14 นิ้ว',
     'เครื่องคอมพิวเตอร์แบบพกพาสำหรับใช้งานสำนักงาน (ประสิทธิภาพสูง) จอ 14 นิ้ว'),
    ('NB สำหรับงานปรับแต่งภาพ',
     'เครื่องคอมพิวเตอร์แบบพกพาสำหรับใช้งานปรับแต่งภาพ'),
    ('NB สำหรับงานปรับแต่งภาพและงานวีดีทัศน์',
     'เครื่องคอมพิวเตอร์แบบพกพาสำหรับใช้ตัดต่องานวีดีทัศน์'),
    ('PC สำหรับงานวีดีทัศน์',
     'เครื่องคอมพิวเตอร์สำหรับงานตัดต่อวีดีทัศน์'),
    ('PC สำนักงานประสิทธิภาพสูง',
     'เครื่องคอมพิวเตอร์สำหรับใช้งานสำนักงาน (ประสิทธิภาพสูง)'),
    ('Macbook',
     'เครื่องคอมพิวเตอร์แบบพกพา Apple (MacBook)'),
    ('iMac',
     'เครื่องคอมพิวเตอร์ตั้งโต๊ะ Apple (iMac)'),
]

# ลำดับ 8-9 ไม่ได้มาจากช่อง "ประเภท" ใน eDevice แต่อนุมานจากช่อง "รุ่น"
MAC_MACHINE  = 'Macbook'
IMAC_MACHINE = 'iMac'


def _norm_machine(s):
    """normalize ชื่อประเภทเครื่องก่อนเทียบ — กัน 'สํา' (นิคหิต+สระอา)
    กับ 'สำ' (สระอำ) ที่หน้าตาเหมือนกันแต่ unicode ต่างกัน + ตัดช่องว่างซ้ำ"""
    s = (s or '').replace('ํา', 'ำ')   # ◌ํ + า  →  ำ
    return ' '.join(s.split())


_ORDER_RANK = {_norm_machine(k): i for i, (k, _) in enumerate(MACHINE_ORDER)}
_FULL_NAME  = {_norm_machine(k): v for k, v in MACHINE_ORDER}


def _machine_rank(m):
    """คีย์เรียงลำดับ: ประเภทในลิสต์มาก่อน (ตามลำดับ), นอกลิสต์ต่อท้ายตามจำนวน"""
    return _ORDER_RANK.get(_norm_machine(m), len(MACHINE_ORDER))


def _full_name(m):
    return _FULL_NAME.get(_norm_machine(m), '')


def _machine_of(r):
    mt = (r.get('machine_type') or '').strip()
    if mt:
        return mt
    # ยังไม่ได้ระบุประเภทใน eDevice — อนุมานจากช่อง "รุ่น" กรณีเป็นเครื่อง Mac
    text = '%s %s %s' % (r.get('model') or '', r.get('brand') or '', r.get('asset_type') or '')
    text = text.lower()
    if 'imac' in text:
        return IMAC_MACHINE
    if 'macbook' in text or 'mac book' in text:
        return MAC_MACHINE
    return UNSPEC_MACHINE


def _position_of(r):
    if r.get('is_central'):
        return 'ส่วนกลาง (ไม่มีผู้ถือครอง)'
    return (r.get('emp_position') or '').strip() or UNSPEC_POSITION


UNSPEC_MODEL = '(ไม่ระบุรุ่น)'
_NULL_MODEL  = {'-', '--', '—', 'n/a', 'na', 'none', 'null', 'mixed', '.'}


def _model_of(r):
    """ชื่อรุ่นเครื่อง — eDevice เก็บไว้ในช่อง 'รุ่น' (brand) เช่น 'Dell Latitude 3550'
    ส่วน model มาจาก Sheets ใช้เป็นตัวสำรองเมื่อไม่มีข้อมูลฝั่ง eDevice"""
    s = ' '.join(((r.get('brand') or '').strip() or (r.get('model') or '').strip()).split())
    return UNSPEC_MODEL if not s or s.lower() in _NULL_MODEL else s


def _esc(s):
    return (s or '').replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')




# ══════════════════════════════════════════════════════════════════
#  page furniture
# ══════════════════════════════════════════════════════════════════

def _draw_frame(canvas, doc):
    doc._pages = max(getattr(doc, '_pages', 0), doc.page)
    canvas.saveState()
    w, h = landscape(A4)

    canvas.setFillColor(BRAND)
    canvas.rect(0, h - 15 * mm, w, 15 * mm, stroke=0, fill=1)
    canvas.setFillColor(WHITE)
    canvas.setFont(FONT_B, 12)
    canvas.drawString(11 * mm, h - 10 * mm, doc._header_title)
    canvas.setFont(FONT, 8)
    canvas.drawRightString(w - 11 * mm, h - 10 * mm, 'Amarin Employee Database')

    canvas.setFillColor(MUTED)
    canvas.setFont(FONT, 7)
    canvas.drawString(11 * mm, 7 * mm, 'ออกรายงานเมื่อ ' + doc._generated_at)
    if doc._footer_note:
        canvas.drawCentredString(w / 2, 7 * mm, doc._footer_note)
    # หน้า x / y — y รู้ได้ต่อเมื่อ build รอบแรกจบแล้ว (ดู build_spec_report)
    total = getattr(doc, '_total_pages', 0)
    canvas.drawRightString(w - 11 * mm, 7 * mm,
                           'หน้า %d / %d' % (doc.page, total) if total else 'หน้า %d' % doc.page)
    canvas.restoreState()


def _doc(buf, generated_at,
         header_title='รายงานการใช้งานเครื่อง IT — ประเภทเครื่อง × ตำแหน่งงาน',
         title='รายงานการใช้งานเครื่อง IT', footer_note=''):
    doc = BaseDocTemplate(buf, pagesize=landscape(A4),
                          leftMargin=11 * mm, rightMargin=11 * mm,
                          topMargin=19 * mm, bottomMargin=11 * mm,
                          title=title,
                          author='Amarin Employee Database')
    doc._generated_at  = generated_at
    doc._header_title  = header_title
    doc._footer_note   = footer_note
    doc.addPageTemplates([PageTemplate(
        id='all',
        frames=[Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id='m')],
        onPage=_draw_frame)])
    return doc


def _heading(num, title, note):
    return Table(
        [[Paragraph('%s %s' % (num, title), _style('h', 10.5, INK, bold=True)),
          Paragraph(note, _style('hn', 7.2, MUTED, align=TA_CENTER))]],
        colWidths=[None, None], hAlign='LEFT', style=TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'BOTTOM'),
            ('LEFTPADDING', (0, 0), (0, 0), 0),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
            ('LINEBELOW', (0, 0), (-1, -1), 1.2, BRAND),
        ]))


# ══════════════════════════════════════════════════════════════════
#  main
# ══════════════════════════════════════════════════════════════════

def _story(rows, filter_labels, W):
    total    = len(rows)
    machines = Counter(_machine_of(r) for r in rows)
    spec_cnt = total - machines.get(UNSPEC_MACHINE, 0)
    n_pos    = len({_position_of(r) for r in rows})
    pct      = (spec_cnt / total * 100) if total else 0

    # ── แถบตัวกรอง — เน้นให้เห็นชัดว่ารายงานอิงข้อมูลชุดไหน ──────────
    if filter_labels:
        flt_html = ('<font size="8" color="#475569">ตัวกรองที่ใช้&nbsp;&nbsp;</font>'
                    + '<b>' + '&nbsp;&nbsp;·&nbsp;&nbsp;'.join(filter_labels) + '</b>')
        flt_cell = Paragraph(flt_html, _style('flt', 13, BRAND, bold=True, leading=17))
        flt_bg, flt_bar = _tint(CAT[0], .10), BRAND
    else:
        flt_cell = Paragraph('<font color="#94a3b8">ไม่มีตัวกรอง — แสดงข้อมูลทั้งหมด</font>',
                             _style('flt', 9, MUTED, leading=12))
        flt_bg, flt_bar = colors.HexColor('#f1f5f9'), colors.HexColor('#cbd5e1')
    flt_tbl = Table([[flt_cell]], colWidths=[W])
    flt_tbl.setStyle(TableStyle([
        ('BACKGROUND',    (0, 0), (-1, -1), flt_bg),
        ('LINEBEFORE',    (0, 0), (0, -1), 3.5, flt_bar),
        ('VALIGN',        (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING',   (0, 0), (-1, -1), 8),
        ('RIGHTPADDING',  (0, 0), (-1, -1), 8),
        ('TOPPADDING',    (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    story = [flt_tbl, Spacer(1, 3 * mm)]

    # ── KPI ──────────────────────────────────────────────────────
    kpis = [('เครื่องทั้งหมด', '{:,}'.format(total), CAT[0]),
            ('ระบุประเภทเครื่องแล้ว', '{:,} ({:.1f}%)'.format(spec_cnt, pct),
             CAT[1] if pct < 50 else CAT[5]),
            ('ประเภทเครื่องที่พบ',
             '{:,} / {} ประเภท'.format(len([m for m in machines if m != UNSPEC_MACHINE]),
                                        len(MACHINE_ORDER)), CAT[6]),
            ('ตำแหน่งงานที่เกี่ยวข้อง', '{:,} ตำแหน่ง'.format(n_pos), CAT[4])]
    kpi = Table([[Paragraph(l, _style('kl', 7.5, SLATE, align=TA_CENTER)) for l, _, _ in kpis],
                 [Paragraph(v, _style('kv', 14, colors.HexColor(c), bold=True, align=TA_CENTER))
                  for _, v, c in kpis]],
                colWidths=[W / len(kpis)] * len(kpis))
    kpi_style = [('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                 ('TOPPADDING', (0, 0), (-1, 0), 4),
                 ('BOTTOMPADDING', (0, 1), (-1, 1), 5),
                 ('INNERGRID', (0, 0), (-1, -1), 2, WHITE)]
    for i, (_, _, c) in enumerate(kpis):
        kpi_style += [('BACKGROUND', (i, 0), (i, -1), _tint(c, .10)),
                      ('LINEABOVE', (i, 0), (i, 0), 2.2, colors.HexColor(c))]
    kpi.setStyle(TableStyle(kpi_style))
    story.append(kpi)

    if not total:
        story += [Spacer(1, 6 * mm),
                  Paragraph('ไม่มีเครื่องที่ตรงกับตัวกรองที่เลือกไว้', _style('e', 10, SLATE))]
        return story

    # all_types = ทุกประเภทในแค็ตตาล็อกมาตรฐานเสมอ (แม้จำนวน = 0 ก็คงลำดับไว้ ไม่ข้าม)
    #             + ประเภทนอกแค็ตตาล็อกที่พบจริง (ต่อท้ายตามจำนวน)
    catalog = [name for name, _ in MACHINE_ORDER]
    extra   = sorted([m for m in machines if m != UNSPEC_MACHINE and m not in catalog],
                     key=lambda m: (-machines[m], m))
    all_types = catalog + extra
    # สีผูกตามลำดับ (คงที่ ไม่ขึ้นกับว่าพบเครื่องหรือไม่)
    hue = {m: CAT[i % len(CAT)] for i, m in enumerate(all_types)}
    hue[UNSPEC_MACHINE] = NEUTRAL

    # ตารางไขว้ (ข้อ 2) แสดงเฉพาะคอลัมน์ที่มีเครื่องจริง — เลี่ยงคอลัมน์ว่างเปล่า
    cols = [m for m in all_types if machines.get(m)]
    if UNSPEC_MACHINE in machines:
        cols.append(UNSPEC_MACHINE)

    grid = defaultdict(Counter)
    for r in rows:
        grid[_position_of(r)][_machine_of(r)] += 1

    def spec(p):
        return sum(n for m, n in grid[p].items() if m != UNSPEC_MACHINE)

    hdr   = _style('th', 6.8, WHITE, bold=True, align=TA_CENTER, leading=8)
    hdr_d = _style('thd', 6.8, SLATE, bold=True, align=TA_CENTER, leading=8)
    hdr_sm = _style('ths', 6.1, WHITE, bold=True, align=TA_CENTER, leading=7.2)

    # ══ 1. สรุปรายประเภทเครื่อง ═══════════════════════════════════
    BAR = W * .13
    m_head = [Paragraph(t, hdr_d) for t in
              ['#', 'ประเภทเครื่อง (ชื่อในระบบ eDevice / ชื่อเต็ม)', 'จำนวน', 'สัดส่วน',
               'ตำแหน่งงานที่ใช้มากที่สุด (3 อันดับแรก)', 'BU หลัก']]
    m_body, m_style = [], []
    # แสดงทุกประเภทในแค็ตตาล็อกเสมอ (จำนวน 0 ก็คงลำดับไว้) + แถวยังไม่ระบุท้ายสุด
    summary_types = all_types + ([UNSPEC_MACHINE] if UNSPEC_MACHINE in machines else [])
    top_n = max([machines[m] for m in all_types] or [1])
    for i, m in enumerate(summary_types, 1):
        sub = [r for r in rows if _machine_of(r) == m]
        n   = len(sub)
        rank = _machine_rank(m)
        no   = str(rank + 1) if rank < len(MACHINE_ORDER) else '—'
        full = _full_name(m)
        # แถวที่ไม่มีเครื่อง (0) และแถวยังไม่ระบุ → ใช้สีจาง
        faded = (n == 0) or (m == UNSPEC_MACHINE)
        # ช่องแรก: ชื่อในระบบ (ตัวหนา) + ชื่อเต็มบรรทัดล่าง (สีจาง)
        name_cell = ('<b>%s</b>' % m) + ('<br/><font size="6" color="#94a3b8">%s</font>' % full if full else '')
        if n:
            bar = Table([['']], colWidths=[min(max(BAR * n / top_n, 1.2), BAR)], rowHeights=[5],
                        style=TableStyle([('BACKGROUND', (0, 0), (-1, -1), colors.HexColor(hue[m])),
                                          ('LEFTPADDING', (0, 0), (-1, -1), 0),
                                          ('RIGHTPADDING', (0, 0), (-1, -1), 0)]))
        else:
            bar = Paragraph('—', _style('bz', 7, colors.HexColor('#cbd5e1')))
        m_body.append([
            Paragraph(no, _style('mno', 7.6, SLATE if not faded else MUTED, bold=True, align=TA_CENTER)),
            Paragraph(name_cell, _style('m', 7.4, INK if not faded else MUTED, leading=8.6)),
            Paragraph('{:,}'.format(n), _style('m', 8, INK if not faded else MUTED, bold=True, align=TA_CENTER)),
            bar,
            Paragraph(' · '.join('%s (%d)' % (p, c) for p, c in
                                 Counter(_position_of(r) for r in sub).most_common(3)) or '—',
                      _style('m', 7.2, SLATE, leading=8.6)),
            Paragraph(' · '.join('%s (%d)' % (b, c) for b, c in
                                 Counter((r.get('emp_bu_code') or '—') for r in sub).most_common(3)) or '—',
                      _style('m', 7.2, SLATE)),
        ])
        m_style.append(('LINEBEFORE', (1, i), (1, i), 2.5, colors.HexColor(hue[m])))
    mt = Table([m_head] + m_body,
               colWidths=[W * .035, W * .275, W * .06, BAR, W * .35,
                          W - (W * .72) - BAR],
               repeatRows=1)
    mt.setStyle(TableStyle(m_style + [
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f1f5f9')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [WHITE, colors.HexColor('#fafcff')]),
        ('LINEBELOW', (0, 0), (-1, -2), 0.4, LINE),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN', (3, 1), (3, -1), 'LEFT'),
        ('TOPPADDING', (0, 0), (-1, -1), 2.5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2.5),
    ]))
    story += [Spacer(1, 4 * mm),
              _heading('1.', 'สรุปรายประเภทเครื่อง', 'แถบสีแสดงสัดส่วนจำนวนเครื่อง'),
              Spacer(1, 1.5 * mm), mt]

    unspec = machines.get(UNSPEC_MACHINE, 0)
    if unspec:
        story += [Spacer(1, 2.5 * mm), Paragraph(
            '⚠ มี {:,} เครื่อง ({:.1f}%) ที่ยังไม่ได้กรอกช่อง “ประเภท” ใน eDevice — '
            'ตัวเลขในรายงานสะท้อนเฉพาะเครื่องที่มีข้อมูลครบ'.format(unspec, unspec / total * 100),
            _style('w', 7.4, AMBER))]

    # ══ 2. ตารางไขว้ ตำแหน่งงาน × ประเภทเครื่อง (ทุกตำแหน่ง) ═══════
    pos_s = _style('tp', 7.2, INK, leading=8.6)
    zero  = _style('tz', 7.5, colors.HexColor('#cbd5e1'), align=TA_CENTER)

    # แสดงทุกตำแหน่งที่มีเครื่องระบุประเภทแล้ว — เรียงตามจำนวนที่ระบุมากไปน้อย
    # ตำแหน่งที่ยังไม่กรอกประเภทเลย (มีแต่คอลัมน์ยังไม่ระบุ) ยุบเป็นแถวเดียว
    ranked = sorted([p for p in grid if spec(p)],
                    key=lambda p: (-spec(p), -sum(grid[p].values()), p))
    rest = [p for p in grid if not spec(p)]

    head = [Paragraph('ตำแหน่งงาน', hdr_d)] + \
           [Paragraph(c, (hdr if c != UNSPEC_MACHINE else hdr_d) if len(c) <= 26
                      else (hdr_sm if c != UNSPEC_MACHINE else hdr_d)) for c in cols] + \
           [Paragraph('รวม', hdr_d)]

    col_max = {m: max([grid[p].get(m, 0) for p in ranked] or [0]) or 1 for m in cols}
    body, tints = [], []
    for ri, p in enumerate(ranked, 1):
        c = grid[p]
        line = [Paragraph(p, pos_s)]
        for ci, m in enumerate(cols, 1):
            n = c.get(m, 0)
            if n:
                line.append(Paragraph('{:,}'.format(n),
                                      _style('n', 7.8, INK, bold=True, align=TA_CENTER)))
                if m != UNSPEC_MACHINE:
                    # sequential ramp ภายในคอลัมน์ — hue เดียว เข้มตามจำนวน
                    tints.append((ci, ri, _tint(hue[m], .12 + .38 * n / col_max[m])))
            else:
                line.append(Paragraph('·', zero))
        line.append(Paragraph('{:,}'.format(sum(c.values())),
                              _style('n', 7.8, BRAND, bold=True, align=TA_CENTER)))
        body.append(line)

    if rest:
        agg = Counter()
        for p in rest:
            agg.update(grid[p])
        body.append([Paragraph('ตำแหน่งอื่น ๆ อีก {:,} ตำแหน่ง (ยังไม่ระบุประเภทเครื่อง)'.format(len(rest)),
                               _style('to', 7, MUTED))] +
                    [Paragraph('{:,}'.format(agg.get(m, 0)) if agg.get(m, 0) else '·',
                               _style('n', 7.5, SLATE, align=TA_CENTER) if agg.get(m, 0) else zero)
                     for m in cols] +
                    [Paragraph('{:,}'.format(sum(agg.values())),
                               _style('n', 7.5, SLATE, align=TA_CENTER))])
    foot = [Paragraph('รวมทั้งสิ้น', _style('tf', 7.8, INK, bold=True))] + \
           [Paragraph('{:,}'.format(machines.get(m, 0)),
                      _style('n', 7.8, INK, bold=True, align=TA_CENTER)) for m in cols] + \
           [Paragraph('{:,}'.format(total), _style('n', 7.8, BRAND, bold=True, align=TA_CENTER))]

    tot_w  = 15 * mm
    each_w = min((W - 55 * mm - tot_w) / len(cols), 42 * mm)
    pos_w  = W - tot_w - each_w * len(cols)
    xt = Table([head] + body + [foot],
               colWidths=[pos_w] + [each_w] * len(cols) + [tot_w],
               repeatRows=1)
    xs = [('GRID', (0, 0), (-1, -1), 0.4, LINE),
          ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
          ('TOPPADDING', (0, 0), (-1, -1), 2.2),
          ('BOTTOMPADDING', (0, 0), (-1, -1), 2.2),
          ('LEFTPADDING', (0, 0), (-1, -1), 3),
          ('RIGHTPADDING', (0, 0), (-1, -1), 3),
          ('BACKGROUND', (0, 0), (0, 0), colors.HexColor('#f1f5f9')),
          ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#f1f5f9')),
          ('LINEABOVE', (0, -1), (-1, -1), 1, BRAND)]
    for ci, m in enumerate(cols, 1):
        xs.append(('BACKGROUND', (ci, 0), (ci, 0),
                   colors.HexColor(hue[m]) if m != UNSPEC_MACHINE else colors.HexColor('#f1f5f9')))
    xs.append(('BACKGROUND', (len(cols) + 1, 0), (len(cols) + 1, 0), colors.HexColor('#f1f5f9')))
    xs += [('BACKGROUND', (c, r), (c, r), t) for c, r, t in tints]
    xt.setStyle(TableStyle(xs))

    story += [Spacer(1, 5 * mm),
              _heading('2.', 'ตำแหน่งงาน × ประเภทเครื่อง (ทุกตำแหน่ง)',
                       'เรียงตามจำนวนเครื่องที่ระบุประเภทแล้ว · ยิ่งเข้ม = ยิ่งมาก · · คือไม่มี'),
              Spacer(1, 1.5 * mm), xt]

    # ══ 3. รุ่นเครื่องในแต่ละประเภท ═══════════════════════════════
    # จัดรุ่นเป็น 3 คอลัมน์ต่อบรรทัด (หน้าแนวนอนกว้าง) เรียงจากรุ่นที่มีมากไปน้อย
    NCOL, TOP_MODELS = 3, 15
    pair_w  = W / NCOL
    col_ws  = [pair_w * .74, pair_w * .26] * NCOL

    by_type = defaultdict(list)
    for r in rows:
        by_type[_machine_of(r)].append(_model_of(r))

    story += [Spacer(1, 5 * mm),
              _heading('3.', 'รุ่นเครื่องในแต่ละประเภท',
                       'ชื่อรุ่นตามที่บันทึกใน eDevice · เรียงจากรุ่นที่มีมากที่สุด · '
                       'เกิน %d รุ่นยุบเป็นบรรทัดเดียว' % TOP_MODELS),
              Spacer(1, 1.5 * mm)]

    for m in summary_types:
        items = by_type.get(m) or []
        n_all = len(items)
        # รวมรุ่นที่สะกดต่างกันแค่ตัวพิมพ์เล็ก/ใหญ่ (OptiPlex vs Optiplex) เข้าด้วยกัน
        variants = defaultdict(Counter)
        for s in items:
            variants[s.lower()][s] += 1
        models = sorted(((v.most_common(1)[0][0], sum(v.values())) for v in variants.values()),
                        key=lambda t: (t[0] == UNSPEC_MODEL, -t[1], t[0]))
        shown, restm = models[:TOP_MODELS], models[TOP_MODELS:]

        # ประเภทที่ยังไม่มีเครื่องก็แสดงหัวข้อไว้ — คงลำดับ 1-9 ให้ครบเหมือนข้อ 1
        faded = (m == UNSPEC_MACHINE) or not n_all
        c_hex = hue[m]
        rank  = _machine_rank(m)
        no    = '%d.' % (rank + 1) if rank < len(MACHINE_ORDER) else '•'
        head_txt = ('<b>%s %s</b>&nbsp;&nbsp;<font size="7" color="#475569">%s</font>'
                    % (no, _esc(m),
                       'รวม {:,} เครื่อง · {:,} รุ่น'.format(n_all, len(models)) if n_all
                       else 'ยังไม่มีเครื่องในประเภทนี้'))
        g_rows = [[Paragraph(head_txt, _style('g', 8.4, colors.HexColor(c_hex) if not faded else SLATE,
                                              leading=10))] + [''] * (NCOL * 2 - 1)]

        cells = []
        for name, n in shown:
            unspec = (name == UNSPEC_MODEL)
            cells.append([
                Paragraph(_esc(name), _style('mn', 7.2, INK if not (faded or unspec) else MUTED,
                                             leading=8.4)),
                Paragraph('<b>{:,}</b>&nbsp;<font size="5.5" color="#94a3b8">{:.0f}%</font>'
                          .format(n, n / n_all * 100),
                          _style('mc', 7.6, colors.HexColor(c_hex) if not faded else SLATE)),
            ])
        if restm:
            cells.append([
                Paragraph('อื่น ๆ อีก %d รุ่น' % len(restm), _style('mo', 7, MUTED, leading=8.4)),
                Paragraph('{:,}'.format(sum(n for _, n in restm)), _style('mc', 7.2, MUTED)),
            ])
        while len(cells) % NCOL:
            cells.append(['', ''])
        for i in range(0, len(cells), NCOL):
            line = []
            for pair in cells[i:i + NCOL]:
                line += pair
            g_rows.append(line)

        gt = Table(g_rows, colWidths=col_ws, repeatRows=1)
        gs = [('SPAN', (0, 0), (-1, 0)),
              ('BACKGROUND', (0, 0), (-1, 0), _tint(c_hex, .16) if not faded
               else colors.HexColor('#f1f5f9')),
              ('LINEBEFORE', (0, 0), (0, -1), 2.5, colors.HexColor(c_hex)),
              ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
              ('TOPPADDING', (0, 0), (-1, -1), 2.2),
              ('BOTTOMPADDING', (0, 0), (-1, -1), 2.2),
              ('LEFTPADDING', (0, 0), (-1, -1), 5)]
        if len(g_rows) > 1:
            gs += [('ROWBACKGROUNDS', (0, 1), (-1, -1), [WHITE, colors.HexColor('#fafcff')]),
                   ('ALIGN', (1, 1), (-1, -1), 'RIGHT')]
            for k in range(1, NCOL):
                gs.append(('LINEBEFORE', (k * 2, 1), (k * 2, -1), 0.4, LINE))
        gt.setStyle(TableStyle(gs))
        story += [gt, Spacer(1, 2.5 * mm)]

    return story


def build_asset_report(rows, filter_labels):
    """rows = asset dict ที่ผ่าน filter แล้ว

    ข้อ 1 = สรุปรายประเภทเครื่อง · ข้อ 2 = ตารางไขว้ตำแหน่งงาน × ประเภทเครื่อง
    ข้อ 3 = รุ่นเครื่องที่พบในแต่ละประเภท
    (แสดงทุกตำแหน่ง — กี่หน้าก็ได้ ตารางแตกหน้าเองพร้อมหัวตารางซ้ำ)
    """
    _ensure_fonts()
    generated_at = datetime.now().strftime('%d/%m/%Y %H:%M น.')
    buf = io.BytesIO()
    doc = _doc(buf, generated_at)
    doc.build(_story(rows, filter_labels, doc.width))
    buf.seek(0)
    return buf


# ══════════════════════════════════════════════════════════════════
#  รายงานคุณสมบัติเครื่องที่จะเช่า/ซื้อ (หน้ากำหนดคุณสมบัติ) — สำหรับผู้บริหาร
#
#  แนวคิดการจัดหน้า: ไม่พิมพ์ 7 คอลัมน์เท่ากัน (ค่าเดิมซ้ำ 7 รอบ = กำแพงตัวหนังสือ
#  และคอลัมน์แคบจนค่าจริงตัดบรรทัด 4-5 บรรทัด) แต่พิมพ์ "ข้อกำหนดกลาง" หนึ่งชุด
#  แล้วแสดงเฉพาะ BU ที่ขอต่างออกไป — หมึกลดลงมาก และสเกลได้ไม่ว่ากี่ BU
# ══════════════════════════════════════════════════════════════════

# ── พจนานุกรมหัวข้อสเปก ────────────────────────────────────────────
# แต่ละ BU สะกดหัวข้อไม่ตรงกัน ('Display Mornitor' / 'Display Monitor' / 'Monitor')
# ถ้าไม่ยุบให้เป็นหัวข้อเดียว ตารางเทียบจะแตกเป็น 3 แถว แถวละมีค่าอยู่ช่องเดียว
SPEC_FIELDS = [
    ('cpu',     'CPU',            ('cpu', 'processor', 'ซีพียู', 'หน่วยประมวลผล')),
    ('ram',     'RAM',            ('ram', 'memory', 'หน่วยความจำ')),
    ('storage', 'Storage',        ('storage', 'harddisk', 'harddrive', 'hdd', 'ssd',
                                   'disk', 'ฮาร์ดดิสก์')),
    ('gpu',     'การ์ดจอ',         ('graphiccard', 'graphic', 'graphics', 'gpu', 'vga',
                                   'videocard', 'การ์ดจอ')),
    ('display', 'จอภาพ',           ('displaymonitor', 'monitor', 'display', 'displaysize',
                                   'screen', 'จอ', 'จอภาพ', 'ขนาดจอ')),
    ('os',      'ระบบปฏิบัติการ',   ('operatingsystem', 'os', 'ระบบปฏิบัติการ', 'windows')),
]
_FIELD_LABEL = {k: lbl for k, lbl, _ in SPEC_FIELDS}
_FIELD_RANK  = {k: i for i, (k, _, _) in enumerate(SPEC_FIELDS)}

_ALNUM_RE   = re.compile(r'[^0-9a-zก-๙]+')
_VARIANT_RE = re.compile(r'^spec\s*#?\s*(\d+)\s*[:.]?\s*$', re.I)
_CONT_RE    = re.compile(r'^\s+|^#')          # บรรทัดต่อจากหัวข้อเดิม เช่น '  #2 2TB'


def _key_norm(s):
    return _ALNUM_RE.sub('', (s or '').lower())


def _near(a, b):
    """ต่างกันไม่เกิน 1 ตัวอักษร — กันสะกดผิด เช่น mornitor/monitor"""
    if abs(len(a) - len(b)) > 1 or not a or not b:
        return False
    if len(a) > len(b):
        a, b = b, a
    i = 0
    while i < len(a) and a[i] == b[i]:
        i += 1
    if i == len(a):
        return True                      # b มีตัวเกินท้ายตัวเดียว
    if len(a) == len(b):
        return a[i + 1:] == b[i + 1:]    # แทนที่ 1 ตัว
    return a[i:] == b[i + 1:]            # แทรก 1 ตัว


def _field_key(label):
    """ชื่อหัวข้อที่ BU พิมพ์มา → คีย์มาตรฐาน (None = นอกพจนานุกรม)"""
    k = _key_norm(label)
    if not k:
        return None
    for key, _, syns in SPEC_FIELDS:
        for s in syns:
            if k == s or _near(k, s) or (len(k) > 4 and len(s) > 3 and (s in k or k in s)):
                return key
    return None


def _clean(s):
    """เก็บกวาดข้อความก่อนขึ้นเอกสารทางการ — '#' ที่ท้ายคำคือ ® ที่เพี้ยนตอน copy
    ('Intel# Core# i5' → 'Intel® Core® i5') แต่ '#1 512 GB' ต้องไม่โดน"""
    s = re.sub(r'(?<=[A-Za-z])#(?=\s|$|,)', '®', s or '')
    return ' '.join(s.split())


def _spec_parse(text):
    """แยกสเปกที่ BU กรอกเป็นทางเลือก (variant) → หัวข้อ → ค่า

    รองรับ 'CPU: i7', 'CPU - i7', หัวข้อว่าง 'CPU :' (นับว่าตั้งหัวข้อไว้แล้ว)
    บาง BU กรอกหลายทางเลือกในช่องเดียวด้วยหัวข้อ 'Spec #1 / Spec#2' → แยกเป็น variant
    (ของเดิมใช้ setdefault ทำให้ #2 #3 หายไปเงียบๆ)
    บรรทัดที่ย่อหน้าหรือขึ้นต้นด้วย '#' = ค่าต่อจากหัวข้อก่อนหน้า เช่น Storage 2 ลูก

    → [ {'title', 'fields': {key: (label, value)}, 'order': [key], 'free': [str]} ]
    """
    variants = []

    def new_variant(title=None):
        v = {'title': title, 'fields': {}, 'order': [], 'free': []}
        variants.append(v)
        return v

    cur, last_key = new_variant(), None
    for raw in (text or '').splitlines():
        line = ' '.join(raw.split())
        if not line:
            continue
        m = _VARIANT_RE.match(line)
        if m:
            # ขึ้นทางเลือกใหม่ — ถ้าทางเลือกแรกยังว่าง ใช้ตัวเดิม (แค่ใส่ชื่อให้)
            cur = cur if not cur['fields'] and not cur['free'] else new_variant()
            cur['title'], last_key = 'Spec #%s' % m.group(1), None
            continue

        key = val = None
        for sep in (':', ' - ', '–', '='):
            if sep in line:
                k, v = line.split(sep, 1)
                if k.strip() and len(k.strip()) <= 30:
                    key, val = k.strip(), _clean(v)
                break
        if key:
            fk = _field_key(key) or 'x:' + _key_norm(key)
            if fk in cur['fields']:                 # หัวข้อซ้ำในทางเลือกเดียวกัน
                lbl, old = cur['fields'][fk]
                cur['fields'][fk] = (lbl, (old + ' / ' + val).strip(' /'))
            else:
                cur['fields'][fk] = (_clean(key), val)
                cur['order'].append(fk)
            last_key = fk
        elif last_key and _CONT_RE.match(raw):
            lbl, old = cur['fields'][last_key]
            cur['fields'][last_key] = (lbl, (old + ' + ' + _clean(line)).strip(' +'))
        else:
            # 'Display Size' ที่ลืมใส่ ':' คือหัวข้อที่ยังไม่ใส่ค่า ไม่ใช่ข้อความอิสระ
            # ถ้านับเป็นข้อความ ช่องนั้นจะถูกมองว่า 'กรอกค่าแล้ว' ทั้งที่ยังว่าง
            fk = _field_key(line) if len(line) <= 30 else None
            if fk and fk not in cur['fields']:
                cur['fields'][fk] = (_clean(line), '')
                cur['order'].append(fk)
                last_key = fk
            else:
                cur['free'].append(_clean(line))
                last_key = None
    return variants


def _spec_fields(variants):
    """หัวข้อ→ค่า ของทางเลือกหลัก (variant แรก) — ใช้เทียบข้าม BU"""
    return variants[0]['fields'] if variants else {}


def _field_order(cols_fields):
    """ลำดับแถวมาตรฐาน: หัวข้อในพจนานุกรมมาก่อนตามลำดับตายตัว (ทุกหน้าเรียงเหมือนกัน)
    หัวข้อนอกพจนานุกรมต่อท้ายตามลำดับที่พบ"""
    seen, extra = set(), []
    for f in cols_fields:
        for k in f:
            if k not in seen:
                seen.add(k)
                if k not in _FIELD_RANK:
                    extra.append(k)
    known = sorted((k for k in seen if k in _FIELD_RANK), key=lambda k: _FIELD_RANK[k])
    return known + extra


def _val_key(v):
    return _ALNUM_RE.sub('', (v or '').lower())


def _group_values(pairs, weight=None):
    """จัดกลุ่มค่าที่ 'ตรงกันในสาระสำคัญ' — BU เขียนคนละสไตล์แต่หมายถึงของเดียวกัน
    ('16GB: 1x16GB,DDR5,5600MT/s' กับ '16 GB, 1 x 16 GB, DDR5')
    ถือว่าตรงกันเมื่อข้อความที่ตัดสัญลักษณ์แล้วเท่ากัน หรือฝ่ายหนึ่งเป็นส่วนหนึ่งของอีกฝ่าย
    (ฝ่ายที่ยาวกว่า = ระบุละเอียดกว่า ใช้เป็นตัวแทนกลุ่ม)
    weight = จำนวนเครื่องที่ BU นั้นใช้อยู่จริง — ใช้ตัดสินเมื่อจำนวน BU เท่ากัน
    (ฝั่งที่มีเครื่องใช้งานอยู่มากกว่าคือฝั่งที่ควรเป็นข้อกำหนดกลาง)
    → [[(bu, value), ...], ...] กลุ่มใหญ่สุดขึ้นก่อน"""
    weight = weight or {}
    groups = []
    for bu, v in pairs:
        k = _val_key(v)
        for g in groups:
            gk = _val_key(g[0][1])
            if k == gk or (len(k) > 8 and len(gk) > 8 and (k in gk or gk in k)):
                g.append((bu, v))
                break
        else:
            groups.append([(bu, v)])
    groups.sort(key=lambda g: (-len(g), -sum(weight.get(bu, 0) for bu, _ in g)))
    return groups


def _rep(group):
    """ตัวแทนกลุ่ม = ข้อความที่ละเอียดที่สุด"""
    return max((v for _, v in group), key=len)


def _spec_year_text(h):
    """ปีที่เริ่มเช่าของรุ่นนั้น — 2024, 2024–25 หรือ 2020, 2023"""
    ys = h.get('years') or []
    if not ys:
        return '—'
    if len(ys) == 1:
        return str(ys[0])
    if ys[-1] - ys[0] == len(ys) - 1:
        return '%d–%s' % (ys[0], str(ys[-1])[-2:])
    return ', '.join(str(y) for y in ys)


# ── chip: รหัส BU บนพื้นสีอ่อนของ BU นั้น ───────────────────────────
def _hexs(c):
    return '#%02x%02x%02x' % (int(c.red * 255), int(c.green * 255), int(c.blue * 255))


def _dark(hex_color, f=.72):
    c = colors.HexColor(hex_color)
    return colors.Color(c.red * f, c.green * f, c.blue * f)


def _chip(code, hex_color, size=6.8):
    return ('<font size="%s" color="%s" backColor="%s"><b>&nbsp;%s&nbsp;</b></font>&nbsp;'
            % (size, _hexs(_dark(hex_color)), _hexs(_tint(hex_color, .18)), _esc(code)))


def _chips(codes, hue, size=6.8):
    return ''.join(_chip(c, hue[c], size) for c in codes)


def _sec_head(title, note='', W=None):
    """หัวข้อหลัก — แถบสีซ้าย + เส้นใต้บาง (แทนพื้นหลังเต็มแถบ)"""
    cells = [Paragraph(title, _style('sh', 10.5, INK, bold=True))]
    if note:
        cells.append(Paragraph(note, _style('shn', 7, MUTED, align=TA_RIGHT)))
    return Table([cells], colWidths=([W * .5, W * .5] if note and W else None),
                 hAlign='LEFT', style=TableStyle([
                     ('VALIGN', (0, 0), (-1, -1), 'BOTTOM'),
                     ('LEFTPADDING', (0, 0), (0, 0), 6),
                     ('RIGHTPADDING', (-1, 0), (-1, 0), 0),
                     ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
                     ('LINEBEFORE', (0, 0), (0, 0), 3, BRAND),
                     ('LINEBELOW', (0, 0), (-1, -1), .8, LINE),
                 ]))


# ── โครงตาราง: เส้นนอนอย่างเดียว ไม่ตีกรอบทุกช่อง ───────────────────
def _table_base(ncols, header=True):
    st = [('VALIGN', (0, 0), (-1, -1), 'TOP'),
          ('TOPPADDING', (0, 0), (-1, -1), 4),
          ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
          ('LEFTPADDING', (0, 0), (-1, -1), 5),
          ('RIGHTPADDING', (0, 0), (-1, -1), 5),
          ('LINEBELOW', (0, 0), (-1, -2), .4, LINE)]
    if header:
        st += [('BACKGROUND', (0, 0), (-1, 0), BRAND),
               ('VALIGN', (0, 0), (-1, 0), 'MIDDLE'),
               ('TOPPADDING', (0, 0), (-1, 0), 3.5),
               ('BOTTOMPADDING', (0, 0), (-1, 0), 3.5),
               ('LINEBELOW', (0, 0), (-1, 0), .4, BRAND)]
    return st


def _hcell(t, align=TA_LEFT):
    return Paragraph(t, _style('th', 7.5, WHITE, bold=True, align=align))


# ══════════════════════════════════════════════════════════════════
#  โครงเรื่อง
# ══════════════════════════════════════════════════════════════════

def _spec_story(data, W):
    types, bus = data['types'], data['bus']
    specs, hist = data['specs'], data['history']
    year_th = datetime.now().year + 543
    hue = {b['bu_code']: CAT[i % len(CAT)] for i, b in enumerate(bus)}
    name_of = {b['bu_code']: b['bu'] for b in bus}
    codes = [b['bu_code'] for b in bus]

    def raw_of(mt, bu):
        return ((specs.get(mt) or {}).get(bu) or {}).get('spec', '').strip()

    def updated_of(mt, bu):
        return ((specs.get(mt) or {}).get(bu) or {}).get('updated_at') or ''

    def hist_of(mt, bu):
        return (hist.get(mt) or {}).get(bu) or []

    def units(mt, bu=None):
        src = codes if bu is None else [bu]
        return sum(h['count'] for c in src for h in hist_of(mt, c))

    # parse ครั้งเดียว ใช้ทั้งเล่ม
    P = {t['name']: {c: _spec_parse(raw_of(t['name'], c)) for c in codes} for t in types}

    def has_val(mt, bu):
        """กรอกค่าจริงแล้ว — ต่างจาก 'ตั้งหัวข้อไว้เฉยๆ' (CPU : ที่ยังไม่ใส่ค่า)"""
        return any(val for v in P[mt][bu] for _, val in v['fields'].values()) or \
               any(v['free'] for v in P[mt][bu])

    def state(mt, bu):
        if has_val(mt, bu):
            return 'val'
        return 'hdr' if raw_of(mt, bu) else 'none'

    ready   = [t for t in types if any(state(t['name'], c) == 'val' for c in codes)]
    hdr_only = [t for t in types if t not in ready and any(raw_of(t['name'], c) for c in codes)]
    bu_ready = [c for c in codes if any(state(t['name'], c) == 'val' for t in types)]

    # ── ปก / สรุปผู้บริหาร ─────────────────────────────────────────
    story = [Table([[Paragraph('คุณสมบัติเครื่องคอมพิวเตอร์ที่จะเช่า/ซื้อ ปี %d' % year_th,
                               _style('t1', 19, INK, bold=True, leading=23))],
                    [Paragraph('สรุปสำหรับผู้บริหาร — เปรียบเทียบข้อกำหนดของ %d หน่วยธุรกิจ '
                               '(BU) เพื่อรวมเป็นสเปกกลางในการจัดหา' % len(bus),
                               _style('t2', 9, SLATE, leading=13))]],
                   colWidths=[W], hAlign='LEFT', style=TableStyle([
                       ('LEFTPADDING', (0, 0), (-1, -1), 8),
                       ('TOPPADDING', (0, 0), (-1, 0), 0),
                       ('BOTTOMPADDING', (0, 0), (0, 0), 1),
                       ('TOPPADDING', (0, 1), (-1, 1), 0),
                       ('LINEBEFORE', (0, 0), (0, -1), 4, BRAND),
                   ])),
             Spacer(1, 4.5 * mm)]

    n_cells  = len(types) * len(bus)
    n_val    = sum(1 for t in types for c in codes if state(t['name'], c) == 'val')
    n_diff   = 0
    decisions = []          # (type, [หัวข้อที่ยังไม่ตรงกัน], เครื่องที่ใช้อยู่)
    for t in ready:
        mt   = t['name']
        cols = [c for c in codes if state(mt, c) == 'val']
        F    = [_spec_fields(P[mt][c]) for c in cols]
        wt   = {c: units(mt, c) for c in cols}
        diffs = []
        for k in _field_order(F):
            pairs = [(c, f[k][1]) for c, f in zip(cols, F) if f.get(k) and f[k][1]]
            if len(_group_values(pairs, wt)) > 1:
                diffs.append(_FIELD_LABEL.get(k) or (F[0].get(k) or ('', ''))[0] or k)
        n_diff += len(diffs)
        decisions.append((t, diffs, units(mt)))

    kpis = [('BU ที่กรอกแล้ว',        '%d / %d' % (len(bu_ready), len(bus)),   CAT[0]),
            ('ประเภทเครื่องที่พร้อม',  '%d / %d' % (len(ready), len(types)),    CAT[2]),
            ('ช่องที่กรอกค่าแล้ว',     '%d / %d' % (n_val, n_cells),           CAT[3]),
            ('หัวข้อที่ยังไม่ตรงกัน',  '%d หัวข้อ' % n_diff,
             CAT[3] if n_diff else CAT[5])]
    kpi = Table([[Paragraph(l, _style('kl', 7.5, SLATE, align=TA_CENTER)) for l, _, _ in kpis],
                 [Paragraph(v, _style('kv', 15, _dark(c, .9), bold=True, align=TA_CENTER))
                  for _, v, c in kpis]],
                colWidths=[W / len(kpis)] * len(kpis))
    ks = [('VALIGN', (0, 0), (-1, -1), 'MIDDLE'), ('TOPPADDING', (0, 0), (-1, 0), 4),
          ('BOTTOMPADDING', (0, 1), (-1, 1), 5), ('INNERGRID', (0, 0), (-1, -1), 2.5, WHITE)]
    for i, (_, _, c) in enumerate(kpis):
        ks += [('BACKGROUND', (i, 0), (i, -1), _tint(c, .09)),
               ('LINEABOVE', (i, 0), (i, 0), 2.2, colors.HexColor(c))]
    kpi.setStyle(TableStyle(ks))
    story += [kpi, Spacer(1, 5.5 * mm)]

    # ── 1. ความพร้อมของข้อมูล ─────────────────────────────────────
    story += [_sec_head('1.&nbsp;&nbsp;ความพร้อมของข้อมูล — ประเภทเครื่อง × BU',
                        '■ กรอกค่าแล้ว&nbsp;&nbsp;· •&nbsp;ตั้งหัวข้อไว้ ยังไม่ใส่ค่า&nbsp;&nbsp;· ·&nbsp;ยังไม่กรอก'
                        '&nbsp;&nbsp;|&nbsp;&nbsp;ตัวเลข = เครื่องที่เช่าอยู่', W),
              Spacer(1, 1.5 * mm)]

    head = [_hcell('ประเภทเครื่อง')] + \
           [Paragraph('<b>%s</b>' % _esc(c), _style('mh', 8, WHITE, bold=True, align=TA_CENTER))
            for c in codes] + [_hcell('พร้อม', TA_CENTER)]
    mrows, mtints = [head], []
    for ti, t in enumerate(types, 1):
        mt, cells, done = t['name'], [], 0
        for bi, c in enumerate(codes, 1):
            s, n = state(mt, c), units(mt, c)
            if s == 'val':
                done += 1
                txt, col = '<b>■</b>' + ('&nbsp;&nbsp;%d' % n if n else ''), GREEN
                mtints.append((bi, ti, _tint(CAT[2], .14)))
            elif s == 'hdr':
                txt, col = '•' + ('&nbsp;&nbsp;%d' % n if n else ''), AMBER
                mtints.append((bi, ti, _tint(CAT[3], .10)))
            else:
                txt, col = (str(n) if n else '·'), (SLATE if n else MUTED)
            cells.append(Paragraph(txt, _style('mc', 8, col, align=TA_CENTER)))
        mrows.append([Paragraph('<font color="#94a3b8">%d</font>&nbsp;&nbsp;%s'
                                % (ti, _esc(t['name'])), _style('mn', 8, INK))] + cells +
                     [Paragraph('%d/%d' % (done, len(bus)),
                                _style('mt', 7.5, GREEN if done == len(bus) else MUTED,
                                       bold=True, align=TA_CENTER))])
    mw = [W * .30] + [(W * .70 - 16 * mm) / max(1, len(bus))] * len(bus) + [16 * mm]
    mtbl = Table(mrows, colWidths=mw, repeatRows=1, hAlign='LEFT')
    ms = _table_base(len(codes) + 2)
    ms += [('LINEBELOW', (0, 0), (-1, -1), .4, LINE),
           ('TOPPADDING', (0, 1), (-1, -1), 3), ('BOTTOMPADDING', (0, 1), (-1, -1), 3)]
    ms += [('BACKGROUND', (c, r), (c, r), t) for c, r, t in mtints]
    mtbl.setStyle(TableStyle(ms))
    story += [mtbl, Spacer(1, 5 * mm)]

    # ── 2. ประเด็นที่ต้องตัดสินใจ ───────────────────────────────────
    story += [CondPageBreak(45 * mm),
              _sec_head('2.&nbsp;&nbsp;ประเด็นที่ต้องตัดสินใจ',
                        'เรียงตามจำนวนหัวข้อที่ยังไม่ตรงกัน แล้วตามจำนวนเครื่องที่ใช้อยู่', W),
              Spacer(1, 1.5 * mm)]
    if decisions:
        drows = [[_hcell('ประเภทเครื่อง'), _hcell('สถานะ', TA_CENTER),
                  _hcell('หัวข้อที่แต่ละ BU ขอไม่ตรงกัน'), _hcell('BU ที่กรอกแล้ว'),
                  _hcell('เครื่องที่ใช้อยู่', TA_RIGHT)]]
        dstyle = []
        for t, diffs, n in sorted(decisions, key=lambda d: (-len(d[1]), -d[2])):
            mt = t['name']
            ok = not diffs
            drows.append([
                Paragraph('<font color="#94a3b8">%d</font>&nbsp;&nbsp;%s'
                          % (t['no'], _esc(mt)), _style('dn', 8.5, INK)),
                Paragraph('<b>■ ตรงกัน</b>' if ok else '<b>◆ ต่าง %d</b>' % len(diffs),
                          _style('ds', 8, GREEN if ok else AMBER, align=TA_CENTER)),
                Paragraph(_esc(', '.join(diffs)) if diffs else
                          '<font color="#94a3b8">— รวมเป็นสเปกกลางชุดเดียวได้ —</font>',
                          _style('dd', 8, INK if diffs else MUTED)),
                Paragraph(_chips([c for c in codes if state(mt, c) == 'val'], hue),
                          _style('db', 8, SLATE, leading=11)),
                Paragraph('{:,}'.format(n) if n else '—',
                          _style('du', 8.5, SLATE, bold=True, align=TA_RIGHT))])
            dstyle.append(('BACKGROUND', (0, len(drows) - 1), (-1, len(drows) - 1),
                           _tint(CAT[2] if ok else CAT[3], .09)))
        dt = Table(drows, colWidths=[W * .27, 17 * mm, W * .30, W * .21, 20 * mm],
                   repeatRows=1, hAlign='LEFT')
        dt.setStyle(TableStyle(_table_base(5) + dstyle +
                               [('LINEBELOW', (0, 0), (-1, -1), .4, LINE)]))
        story.append(dt)
    if hdr_only:
        story += [Spacer(1, 2.5 * mm),
                  Paragraph('<b>ตั้งหัวข้อไว้แล้วแต่ยังไม่มี BU ใดใส่ค่า:</b> ' +
                            _esc(' · '.join('%d. %s' % (t['no'], t['name']) for t in hdr_only)),
                            _style('ho', 8, AMBER, leading=12))]
    rest = [t for t in types if t not in ready and t not in hdr_only]
    if rest:
        story += [Spacer(1, 1.5 * mm),
                  Paragraph('<b>ยังไม่มี BU ใดกรอก:</b> ' +
                            _esc(' · '.join('%d. %s' % (t['no'], t['name']) for t in rest)),
                            _style('rs', 8, MUTED, leading=12))]

    if not ready:
        return story

    # ── 3. ข้อกำหนดกลางที่เสนอ (หน้าเดียวจบ + ช่องลงนาม) ─────────────
    story += [PageBreak(),
              _sec_head('3.&nbsp;&nbsp;ข้อกำหนดกลางที่เสนอ — ทุกประเภทเครื่อง',
                        'ค่าที่ BU ส่วนใหญ่ตรงกัน · ◆ = ยังมี BU ขอต่าง ดูรายละเอียดรายประเภท', W),
              Spacer(1, 1.5 * mm)]

    keys_all = _field_order([_spec_fields(P[t['name']][c])
                             for t in ready for c in codes if state(t['name'], c) == 'val'])
    keys_all = keys_all[:6]
    brows = [[_hcell('ประเภทเครื่อง')] +
             [_hcell(_FIELD_LABEL.get(k, k.replace('x:', ''))) for k in keys_all]]
    bstyle = []
    for t in ready:
        mt   = t['name']
        cols = [c for c in codes if state(mt, c) == 'val']
        F    = {c: _spec_fields(P[mt][c]) for c in cols}
        row  = [Paragraph('<font color="#94a3b8">%d</font>&nbsp;&nbsp;<b>%s</b>'
                          % (t['no'], _esc(mt)), _style('bn', 8, INK, leading=10.5))]
        for k in keys_all:
            pairs = [(c, F[c][k][1]) for c in cols if F[c].get(k) and F[c][k][1]]
            if not pairs:
                row.append(Paragraph('<font color="#cbd5e1">—</font>',
                                     _style('bv', 7.5, MUTED)))
                continue
            g = _group_values(pairs, {c: units(mt, c) for c in cols})
            txt = _esc(_rep(g[0]))
            if len(g) > 1:
                txt += '&nbsp;<font color="#b45309" size="7"><b>◆%d</b></font>' % len(g)
                bstyle.append(('BACKGROUND', (keys_all.index(k) + 1, len(brows)),
                               (keys_all.index(k) + 1, len(brows)), _tint(CAT[3], .10)))
            row.append(Paragraph(txt, _style('bv', 7.5, INK, leading=9.5)))
        brows.append(row)
    bw = [W * .21] + [(W * .79) / len(keys_all)] * len(keys_all)
    bt = Table(brows, colWidths=bw, repeatRows=1, hAlign='LEFT')
    bt.setStyle(TableStyle(_table_base(len(keys_all) + 1) + bstyle +
                           [('LINEBELOW', (0, 0), (-1, -1), .4, LINE),
                            ('LINEAFTER', (0, 0), (0, -1), .4, LINE)]))
    story += [bt, Spacer(1, 8 * mm)]

    # ช่องลงนาม — ให้ผู้บริหารเซ็นได้จากตัวรายงานเลย ไม่ต้องทำใบปะหน้าอีกใบ
    sign = [['', '', ''], ['', '', ''], ['', '', '']]
    for i, role in enumerate(['ผู้จัดทำ / ฝ่ายเทคโนโลยีสารสนเทศ', 'ผู้ตรวจสอบ', 'ผู้อนุมัติ']):
        sign[0][i] = Paragraph('&nbsp;', _style('sg0', 8))
        sign[1][i] = Paragraph('ลงชื่อ ..............................................'
                               '&nbsp;&nbsp;&nbsp;วันที่ ................',
                               _style('sg1', 8, SLATE))
        sign[2][i] = Paragraph(role, _style('sg2', 7.5, MUTED))
    stbl = Table(sign, colWidths=[W / 3] * 3, hAlign='LEFT')
    stbl.setStyle(TableStyle([('TOPPADDING', (0, 0), (-1, -1), 2),
                              ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
                              ('TOPPADDING', (0, 1), (-1, 1), 10)]))
    story.append(stbl)

    # ── 4+. รายประเภท — ประเภทละ 1 หน้า ────────────────────────────
    LBL_W  = 24 * mm
    CONS_W = (W - LBL_W) * .44
    DIFF_W = W - LBL_W - CONS_W

    for t in ready:
        mt      = t['name']
        cols    = [c for c in codes if state(mt, c) == 'val']
        pending = [c for c in codes if state(mt, c) != 'val']
        F       = {c: _spec_fields(P[mt][c]) for c in cols}
        wt      = {c: units(mt, c) for c in cols}
        labels  = {}
        for c in cols:
            for k, (lbl, _) in F[c].items():
                labels.setdefault(k, _FIELD_LABEL.get(k, lbl))

        rows_t = [[_hcell('หัวข้อ'), _hcell('ข้อกำหนดกลางที่เสนอ'),
                   _hcell('BU ที่ขอต่างจากข้อกำหนดกลาง')]]
        tints, diff_labels = [], []
        for k in _field_order([F[c] for c in cols]):
            pairs = [(c, F[c][k][1]) for c in cols if F[c].get(k) and F[c][k][1]]
            lbl   = labels.get(k, k)
            if not pairs:
                rows_t.append([Paragraph(_esc(lbl), _style('fk', 8, SLATE, bold=True)),
                               Paragraph('<font color="#b6c2cf">— ยังไม่มี BU ใดระบุค่า —</font>',
                                         _style('fv', 8, MUTED)),
                               Paragraph('', _style('fd', 8))])
                tints.append((len(rows_t) - 1, colors.HexColor('#f8fafc')))
                continue
            g    = _group_values(pairs, wt)
            main = g[0]
            cons = ('<font size="9">%s</font><br/>%s'
                    '<font size="6.5" color="#94a3b8">%d/%d BU</font>'
                    % (_esc(_rep(main)), _chips([c for c, _ in main], hue), len(main), len(cols)))
            if len(g) > 1:
                diff_labels.append(lbl)
                dtxt = '<br/>'.join('%s<font size="8">%s</font>'
                                    % (_chips([c for c, _ in grp], hue), _esc(_rep(grp)))
                                    for grp in g[1:])
            elif len(cols) > 1:
                dtxt = '<font color="#008300"><b>■ ทุก BU ที่กรอกตรงกัน</b></font>'
            else:
                dtxt = ''        # มี BU เดียว — บอกครั้งเดียวใต้ตาราง ไม่ต้องซ้ำทุกแถว
            rows_t.append([Paragraph(_esc(lbl), _style('fk', 8, SLATE, bold=True)),
                           Paragraph(cons, _style('fv', 8, INK, leading=11)),
                           Paragraph(dtxt, _style('fd', 8, INK, leading=11))])
            tints.append((len(rows_t) - 1, _tint(CAT[3] if len(g) > 1 else CAT[2], .10)))

        # ข้อความอิสระ (บรรทัดที่ไม่ได้เขียนเป็น 'หัวข้อ: ค่า')
        free = [(c, ' · '.join(P[mt][c][0]['free'])) for c in cols if P[mt][c][0]['free']]
        if free:
            rows_t.append([Paragraph('หมายเหตุจาก BU', _style('fk', 8, SLATE, bold=True)),
                           Paragraph('<br/>'.join('%s%s' % (_chip(c, hue[c]), _esc(v))
                                                  for c, v in free),
                                     _style('fv', 8, INK, leading=11)),
                           Paragraph('', _style('fd', 8))])
            tints.append((len(rows_t) - 1, colors.HexColor('#fbfcfe')))

        ft = Table(rows_t, colWidths=[LBL_W, CONS_W, DIFF_W], repeatRows=1, hAlign='LEFT')
        fs = _table_base(3) + [('LINEBELOW', (0, 0), (-1, -1), .4, LINE),
                               ('LINEAFTER', (1, 1), (1, -1), .4, LINE)]
        fs += [('BACKGROUND', (0, r), (-1, r), c) for r, c in tints]
        ft.setStyle(TableStyle(fs))

        # ทางเลือกอื่นที่ BU เสนอไว้ในช่องเดียวกัน (Spec #2, #3)
        alts = [(c, len(P[mt][c])) for c in cols if len(P[mt][c]) > 1]

        # แถบอ้างอิง — รุ่นที่เช่าอยู่จริง (จาก eDevice/Sheets ไม่ใช่สิ่งที่ BU กรอก)
        ref = [[_hcell('BU'), _hcell('รุ่นที่เช่าอยู่ (ล่าสุด)'), _hcell('ปีที่เริ่มเช่า', TA_CENTER),
                _hcell('ค่าเช่า/เครื่อง/เดือน', TA_RIGHT), _hcell('รุ่นนี้', TA_RIGHT),
                _hcell('รวมทุกรุ่น', TA_RIGHT)]]
        for c in codes:
            lst = hist_of(mt, c)
            if not lst:
                continue
            h = lst[0]
            ref.append([Paragraph(_chip(c, hue[c]), _style('rb', 8)),
                        Paragraph(_esc(h['model']) +
                                  ('<font size="6.5" color="#94a3b8">&nbsp;&nbsp;+อีก %d รุ่น</font>'
                                   % (len(lst) - 1) if len(lst) > 1 else ''),
                                  _style('rm', 8, INK)),
                        Paragraph(_spec_year_text(h), _style('ry', 8, SLATE, align=TA_CENTER)),
                        Paragraph('—' if h.get('monthly') is None
                                  else '{:,} ฿'.format(int(h['monthly'])),
                                  _style('rc', 8, SLATE, align=TA_RIGHT)),
                        Paragraph('{:,}'.format(h['count']),
                                  _style('rn', 8, SLATE, align=TA_RIGHT)),
                        Paragraph('{:,}'.format(units(mt, c)),
                                  _style('rt', 8, INK, bold=True, align=TA_RIGHT))])
        rt = None
        if len(ref) > 1:
            ref.append([Paragraph('', _style('rz', 8)),
                        Paragraph('รวมทุก BU', _style('rz', 8, SLATE, bold=True)),
                        Paragraph('', _style('rz', 8)), Paragraph('', _style('rz', 8)),
                        Paragraph('', _style('rz', 8)),
                        Paragraph('{:,}'.format(units(mt)),
                                  _style('rz', 8.5, INK, bold=True, align=TA_RIGHT))])
            rt = Table(ref, colWidths=[16 * mm, W - 16 * mm - 112 * mm,
                                       28 * mm, 34 * mm, 24 * mm, 26 * mm],
                       hAlign='LEFT')
            rt.setStyle(TableStyle(_table_base(6) + [
                ('LINEABOVE', (0, -1), (-1, -1), .8, SLATE),
                ('BACKGROUND', (0, -1), (-1, -1), WHITE),
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#64748b')),
                ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#f6f8fb')),
                ('TOPPADDING', (0, 1), (-1, -1), 2.5), ('BOTTOMPADDING', (0, 1), (-1, -1), 2.5),
                ('LINEBELOW', (0, 0), (-1, -1), .4, LINE)]))

        if diff_labels:
            note = ('<font color="#b45309"><b>◆ ต้องตัดสินใจ %d หัวข้อ:</b> %s</font>'
                    % (len(diff_labels), _esc(', '.join(diff_labels))))
        elif len(cols) > 1:
            note = ('<font color="#008300"><b>■ ทุก BU ที่กรอกกำหนดตรงกัน — '
                    'รวมเป็นสเปกกลางชุดเดียวได้ทันที</b></font>')
        else:
            note = ('<font color="#94a3b8">มี BU เดียวที่กำหนดไว้ — '
                    'ยังไม่มีข้อมูลเทียบจาก BU อื่น</font>')
        if alts:
            note += ('&nbsp;&nbsp;<font color="#475569">· มีทางเลือกอื่นที่เสนอไว้: %s '
                     '(ดูภาคผนวก)</font>'
                     % _esc(', '.join('%s %d ทางเลือก' % (c, n) for c, n in alts)))
        if pending:
            note += ('<br/><font color="#94a3b8">ยังไม่กรอก: %s</font>'
                     % _esc(' · '.join(pending)))

        story += [PageBreak(),
                  _sec_head('%d.&nbsp;&nbsp;%s' % (t['no'], _esc(mt)),
                            'กรอกแล้ว %d/%d BU&nbsp;&nbsp;|&nbsp;&nbsp;เครื่องที่ใช้อยู่ %s เครื่อง'
                            % (len(cols), len(bus), '{:,}'.format(units(mt))), W),
                  Spacer(1, .8 * mm),
                  Paragraph(_esc(t['full_name']), _style('fn', 7.5, MUTED)),
                  Spacer(1, 2.5 * mm), ft,
                  Spacer(1, 1.5 * mm), Paragraph(note, _style('nt', 8, SLATE, leading=11.5))]
        if rt is not None:
            story += [Spacer(1, 4 * mm),
                      Paragraph('ข้อมูลอ้างอิง — รุ่นที่แต่ละ BU เช่าอยู่ในปัจจุบัน',
                                _style('rh', 8, SLATE, bold=True)),
                      Spacer(1, 1 * mm), rt]

    # ── ภาคผนวก — ข้อความต้นฉบับที่แต่ละ BU กรอก ────────────────────
    story += [PageBreak(),
              _sec_head('ภาคผนวก&nbsp;&nbsp;ก.&nbsp;&nbsp;ข้อความที่แต่ละ BU กรอก (ตามต้นฉบับ)',
                        'ใช้อ้างอิงเมื่อมีข้อโต้แย้ง — รวมทางเลือกที่ยังไม่ได้ยกขึ้นตารางเทียบ', W),
              Spacer(1, 1.5 * mm)]
    arows = [[_hcell('ประเภทเครื่อง'), _hcell('BU'), _hcell('ข้อความที่กรอก'),
              _hcell('แก้ไขล่าสุด', TA_RIGHT)]]
    astyle = []
    for t in types:
        mt = t['name']
        for c in codes:
            raw = raw_of(mt, c)
            if not raw:
                continue
            arows.append([
                Paragraph('<font color="#94a3b8">%d</font>&nbsp;&nbsp;%s'
                          % (t['no'], _esc(mt)), _style('an', 7.5, INK, leading=10)),
                Paragraph(_chip(c, hue[c]), _style('ab', 7.5)),
                Paragraph('<br/>'.join(_esc(x) for x in
                                       (' '.join(l.split()) for l in raw.splitlines()) if x),
                          _style('av', 7.5, INK, leading=10)),
                Paragraph(_esc((updated_of(mt, c) or '—')[:16]),
                          _style('au', 7, MUTED, align=TA_RIGHT))])
            if state(mt, c) != 'val':
                astyle.append(('TEXTCOLOR', (2, len(arows) - 1), (2, len(arows) - 1), MUTED))
    at = Table(arows, colWidths=[W * .24, 16 * mm, W - W * .24 - 16 * mm - 26 * mm, 26 * mm],
               repeatRows=1, hAlign='LEFT')
    at.setStyle(TableStyle(_table_base(4) + astyle +
                           [('LINEBELOW', (0, 0), (-1, -1), .4, LINE),
                            ('ROWBACKGROUNDS', (0, 1), (-1, -1),
                             [WHITE, colors.HexColor('#fafcff')])]))
    story.append(at)

    story += [Spacer(1, 3 * mm),
              Paragraph('BU ทั้งหมด: ' + ' '.join(_chip(c, hue[c]) + _esc(name_of[c]) + '&nbsp;&nbsp;'
                                                  for c in codes),
                        _style('leg', 7.5, SLATE, leading=12))]
    return story


def build_spec_report(data):
    """data = payload เดียวกับ /api/machine-specs (types, bus, specs, history)

    1 = ความพร้อมของข้อมูล · 2 = ประเด็นที่ต้องตัดสินใจ · 3 = ข้อกำหนดกลาง + ช่องลงนาม
    4+ = รายประเภท (ประเภทละหน้า, ข้อกำหนดกลาง + เฉพาะ BU ที่ขอต่าง) · ภาคผนวก ก = ต้นฉบับ

    build 2 รอบ — รอบแรกเพื่อนับจำนวนหน้าทั้งหมด ไว้พิมพ์ 'หน้า x / y'
    """
    _ensure_fonts()
    year_th      = datetime.now().year + 543
    generated_at = datetime.now().strftime('%d/%m/%Y %H:%M น.')
    bus    = data.get('bus') or []
    scope  = bus[0]['bu_code'] if len(bus) == 1 else 'ทุก BU'
    header = 'คุณสมบัติเครื่องคอมพิวเตอร์ที่จะเช่า/ซื้อ ปี %d — %s' % (year_th, scope)
    title  = 'คุณสมบัติเครื่องคอมพิวเตอร์ที่จะเช่า/ซื้อ ปี %d' % year_th
    foot   = 'ฉบับร่างเพื่อพิจารณา — ข้อมูลจากระบบ Amarin Employee Database'

    scratch = _doc(io.BytesIO(), generated_at, header_title=header, title=title, footer_note=foot)
    scratch.build(_spec_story(data, scratch.width))

    buf = io.BytesIO()
    doc = _doc(buf, generated_at, header_title=header, title=title, footer_note=foot)
    doc._total_pages = getattr(scratch, '_pages', 0)
    doc.build(_spec_story(data, doc.width))
    buf.seek(0)
    return buf
