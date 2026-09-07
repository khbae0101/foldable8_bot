# -*- coding: utf-8 -*-
"""아이폰18 리포트 PPT 빌더 (이미지 삽입형 · 16:9).

발행 규칙
  · 지사 · 상권 : 매일
  · 매장별      : 화·목·토 (일요일 미발행)

구성
  전체(화·목·토) : 표지 · 지사 · 상권간지+상권 3세트 · 매장 28   → 36장
  요약(그 외)    : 표지 · 지사 · 상권 3                        → 5장
"""
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont
from pptx import Presentation
from pptx.util import Inches

BASE = Path(__file__).parent
sys.path.insert(0, str(BASE))
from report_1p import (F, FB, FR, GOLD, GREEN, H, LINKS, NAVY, RED, REGIONS,
                       TEAL, W, _ctx, draw_branch, draw_cover, draw_region,
                       draw_store, elapsed, remain_days)

STORE_WEEKDAYS = (1, 3, 5)      # 화 · 목 · 토


def is_store_day(now):
    return now.weekday() in STORE_WEEKDAYS


def next_store_day(now):
    d = now.date()
    for _ in range(14):
        d += timedelta(days=1)
        if d.weekday() in STORE_WEEKDAYS:
            return d
    return None


# ─────────────────────────── 상권 간지 ───────────────────────────
def draw_divider(scope, idx, now, out, data_dir=None, cfg_path=None):
    c = _ctx(now, data_dir, cfg_path)
    cur, tgt, reg = c["cur"], c["tgt"], c["reg"]
    ms = sorted([n for n in cur if reg[n] == scope],
                key=lambda n: -(cur[n]["예약누적"] / tgt[n]))
    cum = sum(cur[n]["예약누적"] for n in ms)
    t = sum(tgt[n] for n in ms)
    inc = sum(cur[n].get("증분", 0) or 0 for n in ms)
    proj = round(cum + max(inc, cum / c["el"]) * c["rem"])
    ranks = sorted(REGIONS, key=lambda g: -(
        sum(cur[n]["예약누적"] for n in cur if reg[n] == g) /
        sum(tgt[n] for n in tgt if reg[n] == g)))

    img = Image.new("RGB", (W, H), (16, 30, 52))
    d = ImageDraw.Draw(img)
    for y in range(H):
        r = y / H
        d.line([(0, y), (W, y)],
               fill=(int(16 + 20 * r), int(30 + 36 * r), int(52 + 58 * r)))
    gl = Image.new("RGB", (W, H), (0, 0, 0))
    ImageDraw.Draw(gl).ellipse([W - 900, -220, W + 200, 700], fill=(10, 92, 92))
    gl = gl.filter(ImageFilter.GaussianBlur(200))
    img = Image.blend(img, Image.blend(img, gl, 0.5), 0.85)
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, 14, H], fill=(14, 124, 123))

    d.text((110, 250), f"SECTION {idx}", font=F(FB, 30), fill=(110, 190, 188),
           anchor="ls")
    d.line([110, 276, 360, 276], fill=(46, 96, 112), width=2)
    d.text((108, 310), scope, font=F(FB, 118), fill="white")
    d.text((112, 470), f"상권 · 매장 {len(ms)}개", font=F(FB, 44),
           fill=(150, 214, 210))
    bt = f"지사 내 달성률 {ranks.index(scope)+1}위 / {len(REGIONS)}개 상권"
    bw = int(F(FB, 27).getlength(bt)) + 54
    d.rounded_rectangle([110, 552, 110 + bw, 606], radius=27, fill=(46, 78, 116))
    d.text((110 + bw // 2, 579), bt, font=F(FB, 27), fill=(198, 220, 244),
           anchor="mm")

    for i, (lab, num, sub, col) in enumerate([
            ("누적 예약", f"{cum:,}건", f"목표 {t:,}건", (255, 255, 255)),
            ("달성률", f"{cum/t*100:.1f}%",
             f"지사 {c['dtot']/c['dtgt']*100:.1f}%", (126, 226, 214)),
            ("달성 예상", f"{proj:,}건", f"목표 대비 {proj/t*100:.0f}%",
             (255, 209, 120))]):
        x = 110 + i * 362
        d.rounded_rectangle([x, 680, x + 340, 848], radius=16, fill=(26, 46, 74),
                            outline=(52, 82, 118), width=2)
        d.rectangle([x, 680, x + 340, 685], fill=col)
        d.text((x + 26, 708), lab, font=F(FB, 22), fill=(150, 176, 208))
        d.text((x + 26, 744), num, font=F(FB, 54), fill=col)
        d.text((x + 26, 812), sub, font=F(FR, 19), fill=(140, 168, 200))

    lx = 1220
    d.text((lx, 250), "수록 매장 (달성률 순)", font=F(FB, 24), fill=(126, 208, 204))
    d.line([lx, 288, W - 110, 288], fill=(46, 96, 112), width=2)
    col_n = (len(ms) + 1) // 2
    for i, n in enumerate(ms):
        cx = lx + (i // col_n) * 300
        cy = 316 + (i % col_n) * 46
        rt = cur[n]["예약누적"] / tgt[n] * 100
        rc = (150, 226, 170) if rt >= 100 else (
            (255, 205, 130) if rt >= 60 else (255, 160, 150))
        d.text((cx, cy), f"{i+1:2d}.", font=F(FR, 21), fill=(110, 140, 176))
        d.text((cx + 40, cy), n, font=F(FB, 22), fill=(224, 234, 246))
        d.text((cx + 262, cy), f"{rt:.0f}%", font=F(FB, 21), fill=rc, anchor="ra")
    img.save(out, optimize=True)
    return out


# ─────────────────────────── PPT 빌드 ───────────────────────────
def build(now, out_dir=None, data_dir=None, cfg_path=None, force_full=None):
    out_dir = Path(out_dir or BASE / "report_out")
    out_dir.mkdir(exist_ok=True)
    img_dir = out_dir / "img"
    img_dir.mkdir(exist_ok=True)
    c = _ctx(now, data_dir, cfg_path)
    cur, tgt, reg, cfg = c["cur"], c["tgt"], c["reg"], c["cfg"]
    full = is_store_day(now) if force_full is None else force_full
    ymd = now.strftime("%Y%m%d")

    pages = []
    pages.append(("표지", draw_cover(now, img_dir / "00_cover.png",
                                     data_dir, cfg_path)))
    pages.append(("지사 종합", draw_branch(now, img_dir / "01_branch.png",
                                         data_dir, cfg_path)))
    if not full:
        for i, g in enumerate(REGIONS, 1):
            f = img_dir / f"1{i}_region_{g.replace('/', '')}.png"
            pages.append((f"{g} 상권", draw_region(g, now, f, data_dir, cfg_path)))
    else:
        for i, g in enumerate(REGIONS, 1):
            gs = g.replace("/", "")
            pages.append((f"{g} 간지",
                          draw_divider(g, i, now, img_dir / f"2{i}_00_div_{gs}.png",
                                       data_dir, cfg_path)))
            pages.append((f"{g} 상권",
                          draw_region(g, now, img_dir / f"2{i}_01_region_{gs}.png",
                                      data_dir, cfg_path)))
            ms = sorted([n for n in cur if reg[n] == g],
                        key=lambda n: -(cur[n]["예약누적"] / tgt[n]))
            for j, n in enumerate(ms, 2):
                f = img_dir / f"2{i}_{j:02d}_{n}.png"
                pages.append((f"{n}점", draw_store(n, now, f, data_dir, cfg_path)))

    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)
    blank = prs.slide_layouts[6]
    for title, path in pages:
        s = prs.slides.add_slide(blank)
        s.shapes.add_picture(str(path), 0, 0, width=prs.slide_width,
                             height=prs.slide_height)
        s.notes_slide.notes_text_frame.text = title
    kind = "리포트" if full else "요약"
    out = out_dir / f"{cfg['모델명']}_{kind}_{now.month:02d}{now.day:02d}.pptx"
    prs.save(out)
    return str(out), len(pages), full


def mail_body(now, full, data_dir=None, cfg_path=None):
    """PPT 메일 본문."""
    c = _ctx(now, data_dir, cfg_path)
    cur, tgt, reg, cfg = c["cur"], c["tgt"], c["reg"], c["cfg"]
    cum, G, rem, el = c["dtot"], c["dtgt"], c["rem"], c["el"]
    inc = sum(x.get("증분", 0) or 0 for x in cur.values())
    proj = round(cum + max(inc, cum / el) * rem)
    WD = "월화수목금토일"
    lines = [f"안녕하세요, {cfg['지사명']}지사입니다.",
             f"{now.month}/{now.day}({WD[now.weekday()]}) 마감 기준 "
             f"예약현황 리포트를 공유드립니다.", "",
             "── 지사 현황 ──",
             f"누적 {cum:,}건 / 목표 {G:,}건 · 달성률 {cum/G*100:.1f}%",
             f"금일 +{inc}건 · 달성 예상 {proj:,}건 (목표 대비 {proj/G*100:.0f}%)",
             f"잔여 {rem}영업일 · 일 {max(G-cum,0)/rem:.0f}건 필요", "",
             "── 상권별 ──"]
    rows = []
    for g in REGIONS:
        ms = [n for n in cur if reg[n] == g]
        gc = sum(cur[n]["예약누적"] for n in ms)
        gt = sum(tgt[n] for n in ms)
        gi = sum(cur[n].get("증분", 0) or 0 for n in ms)
        gp = round(gc + max(gi, gc / el) * rem)
        rows.append((g, gc, gt, gc / gt, gp / gt))
    rows.sort(key=lambda r: -r[3])
    for g, gc, gt, ac, pr in rows:
        lines.append(f"{g:8s} {gc:>4,}건 / {gt:,}건  {ac*100:5.1f}%  "
                     f"(달성 예상 {pr*100:.0f}%)")
    n_store = len(cur)
    lines += ["", f"첨부: {cfg['모델명']}_{'리포트' if full else '요약'}_"
              f"{now.month:02d}{now.day:02d}.pptx "
              f"({36 if full else 5}장)"]
    lines.append("  · 표지 · 지사 종합 1장 · 상권별 3장"
                 + (f" · 매장별 {n_store}장" if full else ""))
    lines += ["", "※ 지사·상권 리포트는 매일, 매장별 리포트는 화·목·토 발행됩니다."]
    if not full:
        nd = next_store_day(now)
        if nd:
            lines.append(f"   (매장별 리포트 다음 발행일: {nd.month}/{nd.day})")
    subject = (f"[{cfg['지사명']}] {cfg['모델명']} 예약현황 리포트 "
               f"({now.month}/{now.day} 기준)")
    return subject, "\n".join(lines)


if __name__ == "__main__":
    from datetime import timezone
    KST = timezone(timedelta(hours=9))
    now = datetime.now(KST)
    p, n, full = build(now)
    print(f"{'전체' if full else '요약'} {n}장 → {p}")
