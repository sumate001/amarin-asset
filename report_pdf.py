"""สร้างรายงาน PDF การใช้งานเครื่อง IT — ประเภทเครื่อง × ตำแหน่งงาน × รุ่นเครื่อง

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
from reportlab.platypus import (BaseDocTemplate, Frame, PageBreak, PageTemplate,
                                Paragraph, Spacer, Table, TableStyle)

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
    canvas.drawRightString(w - 11 * mm, 7 * mm, 'หน้า %d' % doc.page)
    canvas.restoreState()


def _doc(buf, generated_at,
         header_title='รายงานการใช้งานเครื่อง IT — ประเภทเครื่อง × ตำแหน่งงาน',
         title='รายงานการใช้งานเครื่อง IT'):
    doc = BaseDocTemplate(buf, pagesize=landscape(A4),
                          leftMargin=11 * mm, rightMargin=11 * mm,
                          topMargin=19 * mm, bottomMargin=11 * mm,
                          title=title,
                          author='Amarin Employee Database')
    doc._generated_at  = generated_at
    doc._header_title  = header_title
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
# ══════════════════════════════════════════════════════════════════

def _spec_parse(text):
    """แยกสเปกเป็นหัวข้อ → ค่า สำหรับเทียบข้าม BU
    รับรูปแบบ 'CPU: i7-1355U' และ 'CPU - i7' — บรรทัดที่ไม่มีตัวคั่นถือเป็นข้อความอิสระ
    'CPU :' ที่ยังไม่ใส่ค่า ก็นับเป็นหัวข้อ (ค่าว่าง) เพื่อให้เห็นว่า BU นี้ตั้งหัวข้อไว้แล้ว
    → ({key_norm: (label, value)}, [บรรทัดอิสระ])"""
    fields, free = {}, []
    for raw in (text or '').splitlines():
        line = ' '.join(raw.split())
        if not line:
            continue
        key = val = None
        for sep in (':', ' - ', '–', '='):
            if sep in line:
                k, v = line.split(sep, 1)
                if k.strip() and len(k.strip()) <= 30:
                    key, val = k.strip(), v.strip()
                break
        if key:
            fields.setdefault(key.lower().replace(' ', ''), (key, val))
        else:
            free.append(line)
    return fields, free


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


def _spec_story(data, W):
    types, bus = data['types'], data['bus']
    specs, hist = data['specs'], data['history']
    hue = {b['bu_code']: CAT[i % len(CAT)] for i, b in enumerate(bus)}

    def spec_of(mt, bu):
        return ((specs.get(mt) or {}).get(bu) or {}).get('spec', '').strip()

    def hist_of(mt, bu):
        return (hist.get(mt) or {}).get(bu) or []

    filled_types = [t for t in types if any(spec_of(t['name'], b['bu_code']) for b in bus)]
    n_cells      = len(types) * len(bus)
    n_filled     = sum(1 for t in types for b in bus if spec_of(t['name'], b['bu_code']))
    bu_done      = [b for b in bus if any(spec_of(t['name'], b['bu_code']) for t in types)]

    # ── KPI ────────────────────────────────────────────────────────
    kpis = [('BU ที่กรอกแล้ว',        '%d / %d BU' % (len(bu_done), len(bus)),      CAT[0]),
            ('ประเภทเครื่องที่ขอ',    '%d / %d ประเภท' % (len(filled_types), len(types)), CAT[2]),
            ('ช่องที่กรอกครบ',        '%d / %d' % (n_filled, n_cells),              CAT[3]),
            ('รุ่นที่เคยเช่าอ้างอิง',  '%d รุ่น' % len({(mt, h['model'])
                                                        for mt in hist
                                                        for b in bus
                                                        for h in hist_of(mt, b['bu_code'])}), CAT[6])]
    kpi = Table([[Paragraph(l, _style('kl', 7.5, SLATE, align=TA_CENTER)) for l, _, _ in kpis],
                 [Paragraph(v, _style('kv', 14, colors.HexColor(c), bold=True, align=TA_CENTER))
                  for _, v, c in kpis]],
                colWidths=[W / len(kpis)] * len(kpis))
    ks = [('VALIGN', (0, 0), (-1, -1), 'MIDDLE'), ('TOPPADDING', (0, 0), (-1, 0), 4),
          ('BOTTOMPADDING', (0, 1), (-1, 1), 5), ('INNERGRID', (0, 0), (-1, -1), 2, WHITE)]
    for i, (_, _, c) in enumerate(kpis):
        ks += [('BACKGROUND', (i, 0), (i, -1), _tint(c, .10)),
               ('LINEABOVE', (i, 0), (i, 0), 2.2, colors.HexColor(c))]
    kpi.setStyle(TableStyle(ks))

    story = [kpi, Spacer(1, 5 * mm),
             _heading('1.', 'ความพร้อมของข้อมูล — ประเภทเครื่อง × BU',
                      '■ = BU กำหนดคุณสมบัติแล้ว · ตัวเลข = จำนวนเครื่องที่ BU นั้นเคยเช่าประเภทนี้'),
             Spacer(1, 1.5 * mm)]

    # ── 1. ตารางไขว้ความพร้อม ──────────────────────────────────────
    head = [Paragraph('ประเภทเครื่อง', _style('mh', 7.5, SLATE, bold=True))] + \
           [Paragraph(_esc(b['bu_code']), _style('mh', 8, WHITE, bold=True, align=TA_CENTER))
            for b in bus] + \
           [Paragraph('กรอกแล้ว', _style('mh', 7.5, SLATE, bold=True, align=TA_CENTER))]
    mrows, mtints = [head], []
    for ti, t in enumerate(types, 1):
        cells, done = [], 0
        for bi, b in enumerate(bus, 1):
            sp = spec_of(t['name'], b['bu_code'])
            n  = sum(h['count'] for h in hist_of(t['name'], b['bu_code']))
            if sp:
                done += 1
                txt = '<b>■</b>' + ('&nbsp;&nbsp;%d' % n if n else '')
                col, tint = GREEN, _tint(CAT[2], .16)
            elif n:
                txt, col, tint = str(n), AMBER, _tint(CAT[3], .10)
            else:
                txt, col, tint = '·', MUTED, None
            cells.append(Paragraph(txt, _style('mc', 8, col, align=TA_CENTER)))
            if tint:
                mtints.append((bi, ti, tint))
        mrows.append([Paragraph('<b>%d</b>&nbsp; %s' % (ti, _esc(t['name'])),
                                _style('mn', 8, INK))] + cells +
                     [Paragraph('%d/%d' % (done, len(bus)),
                                _style('mt', 7.5, GREEN if done == len(bus) else SLATE,
                                       bold=True, align=TA_CENTER))])
    mw = [W * .30] + [(W * .70 - 18 * mm) / max(1, len(bus))] * len(bus) + [18 * mm]
    mt_tbl = Table(mrows, colWidths=mw, repeatRows=1, hAlign='LEFT')
    ms = [('GRID', (0, 0), (-1, -1), .4, LINE),
          ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
          ('TOPPADDING', (0, 0), (-1, -1), 3), ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
          ('BACKGROUND', (0, 0), (0, 0), colors.HexColor('#f1f5f9')),
          ('BACKGROUND', (-1, 0), (-1, 0), colors.HexColor('#f1f5f9'))]
    for bi, b in enumerate(bus, 1):
        ms.append(('BACKGROUND', (bi, 0), (bi, 0), colors.HexColor(hue[b['bu_code']])))
    ms += [('BACKGROUND', (c, r), (c, r), t) for c, r, t in mtints]
    mt_tbl.setStyle(TableStyle(ms))
    story.append(mt_tbl)

    # ── 2. คุณสมบัติที่ขอ — ประเภทเครื่องละ 1 หน้า ─────────────────
    sec2_head = [_heading('2.', 'คุณสมบัติที่แต่ละ BU กำหนด (เทียบข้าม BU)',
                          'แถวเขียว = ทุก BU ตรงกัน (รวมเป็นสเปกกลางได้) · '
                          'แถวส้ม = ต่างกัน ต้องตัดสินใจ · เทา = ข้อมูลรุ่นที่เช่าอยู่ ใช้อ้างอิง'),
                 Spacer(1, 2.5 * mm)]

    if not filled_types:
        story += [Spacer(1, 6 * mm)] + sec2_head
        story.append(Paragraph('— ยังไม่มี BU ใดกำหนดคุณสมบัติ —',
                               _style('none', 9, MUTED, align=TA_CENTER)))
        return story

    LBL_W = 30 * mm
    for t in filled_types:
        mt   = t['name']
        cols = [b for b in bus if spec_of(mt, b['bu_code'])]
        skip = [b['bu_code'] for b in bus if not spec_of(mt, b['bu_code'])]
        parsed = {b['bu_code']: _spec_parse(spec_of(mt, b['bu_code'])) for b in cols}

        # หัวข้อทั้งหมดที่ BU ใช้ — เรียงตามลำดับที่ BU แรกเขียนไว้
        keys, labels = [], {}
        for b in cols:
            for k, (label, _) in parsed[b['bu_code']][0].items():
                if k not in labels:
                    labels[k] = label
                    keys.append(k)

        hdr = [Paragraph('หัวข้อ', _style('sh', 7.5, SLATE, bold=True))] + \
              [Paragraph('<b>%s</b><br/><font size="6.5">%s</font>'
                         % (_esc(b['bu_code']), _esc(b['bu'])),
                         _style('sh', 8.5, WHITE, bold=True, leading=10))
               for b in cols]
        rows_t, tints, diff_keys = [hdr], [], []

        if keys:
            for ri, k in enumerate(keys, 1):
                vals = [parsed[b['bu_code']][0].get(k, (None, None))[1] for b in cols]
                if not any(vals):
                    tint = colors.HexColor('#f8fafc')      # ตั้งหัวข้อไว้ แต่ยังไม่มีใครใส่ค่า
                elif len(set(vals)) == 1:
                    tint = _tint(CAT[2], .13)              # ทุก BU ตรงกัน
                else:
                    tint = _tint(CAT[3], .13)              # ต่างกัน — ต้องตัดสินใจ
                    diff_keys.append(labels[k])
                tints.append((ri, tint))
                rows_t.append([Paragraph(_esc(labels[k]), _style('sk', 8, SLATE, bold=True))] +
                              [Paragraph(_esc(v) if v else
                                         '<font color="#b6c2cf">— ไม่ระบุ —</font>',
                                         _style('sv', 8.5, INK)) for v in vals])
            free_rows = [parsed[b['bu_code']][1] for b in cols]
            if any(free_rows):
                rows_t.append([Paragraph('อื่นๆ', _style('sk', 8, SLATE, bold=True))] +
                              [Paragraph('<br/>'.join(_esc(x) for x in f) or '—',
                                         _style('sv', 8, INK, leading=10)) for f in free_rows])
                tints.append((len(rows_t) - 1, colors.HexColor('#fcfdff')))
        else:
            # BU ไม่ได้เขียนเป็น 'หัวข้อ: ค่า' — เทียบทีละหัวข้อไม่ได้ แสดงข้อความเต็ม
            rows_t.append([Paragraph('คุณสมบัติที่ขอ', _style('sk', 8, SLATE, bold=True))] +
                          [Paragraph('<br/>'.join(_esc(x) for x in
                                                  spec_of(mt, b['bu_code']).splitlines() if x.strip()),
                                     _style('sv', 8.5, INK, leading=11)) for b in cols])
            tints.append((1, WHITE))

        # แถบอ้างอิง — รุ่นล่าสุดที่ BU นั้นเช่าอยู่ (จาก eDevice/Sheets ไม่ใช่สิ่งที่กรอก)
        ref_start = len(rows_t)
        for label, fn in [
            ('รุ่นที่เช่าล่าสุด', lambda h: _esc(h['model'])),
            ('ปีที่เริ่มเช่า',    lambda h: _spec_year_text(h)),
            ('ค่าเช่า/เครื่อง/ด.', lambda h: '—' if h.get('monthly') is None
                                   else '{:,} ฿'.format(int(h['monthly']))),
            ('จำนวนที่ถืออยู่',   lambda h: '{:,} เครื่อง'.format(h['count'])),
        ]:
            cells = []
            for b in cols:
                lst = hist_of(mt, b['bu_code'])
                cells.append(Paragraph(fn(lst[0]) if lst else '—',
                                       _style('rv', 8, SLATE)))
            rows_t.append([Paragraph(label, _style('rk', 7.5, MUTED, bold=True))] + cells)

        cw = [LBL_W] + [(W - LBL_W) / len(cols)] * len(cols)
        st = Table(rows_t, colWidths=cw, repeatRows=1, hAlign='LEFT')
        ss = [('GRID', (0, 0), (-1, -1), .4, LINE),
              ('VALIGN', (0, 0), (-1, -1), 'TOP'),
              ('TOPPADDING', (0, 0), (-1, -1), 3), ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
              ('BACKGROUND', (0, 0), (0, 0), colors.HexColor('#f1f5f9')),
              ('BACKGROUND', (0, ref_start), (-1, -1), colors.HexColor('#f6f8fb')),
              ('LINEABOVE', (0, ref_start), (-1, ref_start), 1, BRAND)]
        for ci, b in enumerate(cols, 1):
            ss.append(('BACKGROUND', (ci, 0), (ci, 0), colors.HexColor(hue[b['bu_code']])))
        ss += [('BACKGROUND', (1, r), (-1, r), tint) for r, tint in tints]
        st.setStyle(TableStyle(ss))

        has_val = any(v for b in cols for _, v in parsed[b['bu_code']][0].values())
        if diff_keys:
            note = '<font color="#b45309"><b>◆ ต่างกันที่:</b> %s</font>' % _esc(', '.join(diff_keys))
        elif keys and has_val:
            note = ('<font color="#008300"><b>◆ ทุก BU กำหนดตรงกันทุกหัวข้อ — '
                    'รวมเป็นสเปกกลางชุดเดียวได้</b></font>')
        elif keys:
            note = '<font color="#94a3b8">◆ ตั้งหัวข้อไว้แล้ว แต่ยังไม่มี BU ใดใส่ค่า</font>'
        else:
            note = ('<font color="#94a3b8">◆ กรอกเป็นข้อความอิสระ — เทียบรายหัวข้อไม่ได้ '
                    '(ใช้รูปแบบ "หัวข้อ: ค่า" จะเทียบให้อัตโนมัติ)</font>')
        if skip:
            note += '&nbsp;&nbsp;<font color="#94a3b8">· ยังไม่กรอก: %s</font>' % _esc(', '.join(skip))

        # ประเภทเครื่องละ 1 หน้าเสมอ — เอาไปเทียบ/สั่งพิมพ์แยกแผ่นต่อประเภทได้
        story += [PageBreak()]
        story += (sec2_head if t is filled_types[0] else [])
        story += [_heading('%d.' % t['no'], t['name'], _esc(t['full_name'])),
                  Spacer(1, 1.2 * mm), st,
                  Spacer(1, 1.2 * mm), Paragraph(note, _style('nt', 8, SLATE, leading=11))]

    # ── ประเภทที่ยังไม่มีใครกรอก ───────────────────────────────────
    rest = [t for t in types if t not in filled_types]
    if rest:
        story += [Spacer(1, 4 * mm),
                  Paragraph('<b>ยังไม่มี BU ใดกำหนดคุณสมบัติ:</b> ' +
                            _esc(' · '.join('%d. %s' % (t['no'], t['name']) for t in rest)),
                            _style('rest', 8.5, AMBER, leading=12))]
    return story


def build_spec_report(data):
    """data = payload เดียวกับ /api/machine-specs (types, bus, specs, history)

    ข้อ 1 = ความพร้อมของข้อมูล ประเภทเครื่อง × BU
    ข้อ 2 = คุณสมบัติที่แต่ละ BU กำหนด วางเทียบกันรายหัวข้อ + รุ่นที่เช่าอยู่เป็นฐานอ้างอิง
    """
    _ensure_fonts()
    year_th      = datetime.now().year + 543
    generated_at = datetime.now().strftime('%d/%m/%Y %H:%M น.')
    buf = io.BytesIO()
    doc = _doc(buf, generated_at,
               header_title='คุณสมบัติเครื่องคอมพิวเตอร์ที่จะเช่า/ซื้อ ปี %d — ทุก BU' % year_th,
               title='คุณสมบัติเครื่องคอมพิวเตอร์ที่จะเช่า/ซื้อ ปี %d' % year_th)
    doc.build(_spec_story(data, doc.width))
    buf.seek(0)
    return buf
