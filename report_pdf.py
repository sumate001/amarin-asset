"""สร้างรายงาน PDF การใช้งานเครื่อง IT — ประเภทเครื่อง × ตำแหน่งงาน (หน้าเดียว)

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
from reportlab.platypus import (BaseDocTemplate, Frame, PageTemplate, Paragraph,
                                Spacer, Table, TableStyle)

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


def _fmt_baht(n):
    return '฿{:,.0f}'.format(n or 0)


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
    canvas.drawString(11 * mm, h - 10 * mm,
                      'รายงานการใช้งานเครื่อง IT — ประเภทเครื่อง × ตำแหน่งงาน')
    canvas.setFont(FONT, 8)
    canvas.drawRightString(w - 11 * mm, h - 10 * mm, 'Amarin Employee Database')

    canvas.setFillColor(MUTED)
    canvas.setFont(FONT, 7)
    canvas.drawString(11 * mm, 7 * mm, 'ออกรายงานเมื่อ ' + doc._generated_at)
    canvas.drawRightString(w - 11 * mm, 7 * mm, 'หน้า %d' % doc.page)
    canvas.restoreState()


def _doc(buf, generated_at):
    doc = BaseDocTemplate(buf, pagesize=landscape(A4),
                          leftMargin=11 * mm, rightMargin=11 * mm,
                          topMargin=19 * mm, bottomMargin=11 * mm,
                          title='รายงานการใช้งานเครื่อง IT',
                          author='Amarin Employee Database')
    doc._generated_at = generated_at
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
    monthly  = sum(r.get('monthly_charge') or 0 for r in rows)
    machines = Counter(_machine_of(r) for r in rows)
    spec_cnt = total - machines.get(UNSPEC_MACHINE, 0)
    n_pos    = len({_position_of(r) for r in rows})
    pct      = (spec_cnt / total * 100) if total else 0

    story = [Paragraph(
        'ตัวกรอง: ' + (' · '.join(filter_labels) if filter_labels else 'ไม่มี (ข้อมูลทั้งหมด)'),
        _style('flt', 8, SLATE)), Spacer(1, 2.5 * mm)]

    # ── KPI ──────────────────────────────────────────────────────
    kpis = [('เครื่องทั้งหมด', '{:,}'.format(total), CAT[0]),
            ('ค่าเช่ารวม / เดือน', _fmt_baht(monthly), CAT[2]),
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

    # เรียงประเภทเครื่องตามลำดับมาตรฐาน (MACHINE_ORDER) — นอกลิสต์ต่อท้ายตามจำนวน
    cols = sorted([m for m in machines if m != UNSPEC_MACHINE],
                  key=lambda m: (_machine_rank(m), -machines[m], m))
    hue = {m: CAT[i % len(CAT)] for i, m in enumerate(cols)}
    if UNSPEC_MACHINE in machines:
        cols.append(UNSPEC_MACHINE)
        hue[UNSPEC_MACHINE] = NEUTRAL

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
               'ค่าเช่า/เดือน', 'ตำแหน่งงานที่ใช้มากที่สุด (3 อันดับแรก)', 'BU หลัก']]
    m_body, m_style = [], []
    top_n = max([machines[m] for m in cols if m != UNSPEC_MACHINE] or [1])
    for i, m in enumerate(cols, 1):
        sub = [r for r in rows if _machine_of(r) == m]
        n   = len(sub)
        rank = _machine_rank(m)
        no   = str(rank + 1) if rank < len(MACHINE_ORDER) else '—'
        full = _full_name(m)
        # ช่องแรก: ชื่อในระบบ (ตัวหนา) + ชื่อเต็มบรรทัดล่าง (สีจาง)
        name_cell = ('<b>%s</b>' % m) + ('<br/><font size="6" color="#94a3b8">%s</font>' % full if full else '')
        bar = Table([['']], colWidths=[min(max(BAR * n / top_n, 1.2), BAR)], rowHeights=[5],
                    style=TableStyle([('BACKGROUND', (0, 0), (-1, -1), colors.HexColor(hue[m])),
                                      ('LEFTPADDING', (0, 0), (-1, -1), 0),
                                      ('RIGHTPADDING', (0, 0), (-1, -1), 0)]))
        m_body.append([
            Paragraph(no, _style('mno', 7.6, SLATE, bold=True, align=TA_CENTER)),
            Paragraph(name_cell, _style('m', 7.4, INK if m != UNSPEC_MACHINE else MUTED, leading=8.6)),
            Paragraph('{:,}'.format(n), _style('m', 8, INK, bold=True, align=TA_CENTER)),
            bar,
            Paragraph(_fmt_baht(sum(r.get('monthly_charge') or 0 for r in sub)),
                      _style('m', 7.6, SLATE, align=TA_CENTER)),
            Paragraph(' · '.join('%s (%d)' % (p, c) for p, c in
                                 Counter(_position_of(r) for r in sub).most_common(3)) or '—',
                      _style('m', 7.2, SLATE, leading=8.6)),
            Paragraph(' · '.join('%s (%d)' % (b, c) for b, c in
                                 Counter((r.get('emp_bu_code') or '—') for r in sub).most_common(3)) or '—',
                      _style('m', 7.2, SLATE)),
        ])
        m_style.append(('LINEBEFORE', (1, i), (1, i), 2.5, colors.HexColor(hue[m])))
    mt = Table([m_head] + m_body,
               colWidths=[W * .035, W * .275, W * .06, BAR, W * .10, W * .29,
                          W - (W * .76) - BAR],
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
    return story


def build_asset_report(rows, filter_labels):
    """rows = asset dict ที่ผ่าน filter แล้ว

    ข้อ 1 = สรุปรายประเภทเครื่อง · ข้อ 2 = ตารางไขว้ตำแหน่งงาน × ประเภทเครื่อง
    (แสดงทุกตำแหน่ง — กี่หน้าก็ได้ ตารางแตกหน้าเองพร้อมหัวตารางซ้ำ)
    """
    _ensure_fonts()
    generated_at = datetime.now().strftime('%d/%m/%Y %H:%M น.')
    buf = io.BytesIO()
    doc = _doc(buf, generated_at)
    doc.build(_story(rows, filter_labels, doc.width))
    buf.seek(0)
    return buf
