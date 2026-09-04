# -*- coding: utf-8 -*-
"""아이폰18 일일 성과 점검 리포트 (1920x1080 · 표지/지사/상권/매장).

폴더블8 '출시 전 최종 점검' 양식 이식.
  · 모델 18P / 18PM
  · 연계 8칸 = 120K·2nd·삼/디/가전·제휴카드 / 라이프·MIT·모두의 행복·MNP
  · 중간점검 없음, 중간 밴드는 2분할(모델 비중 · 잔여 실행 계획)
"""
import json
from datetime import date, timedelta
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

BASE = Path(__file__).parent
FB = "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"
FR = "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"
F = lambda p, s: ImageFont.truetype(p, s)

W, H = 1920, 1080
NAVY = (31, 53, 87); TEAL = (14, 124, 123); RED = (192, 57, 43)
GREEN = (46, 125, 50); GOLD = (176, 132, 30); INK = (26, 34, 48)
GRAY = (110, 122, 138); LINE = (216, 221, 228); LIGHT = (247, 248, 250)

MODELS = [("18P", "18P누적"), ("18PM", "18PM누적")]
MCOL = [(31, 53, 87), (14, 124, 123)]
LINKS = [("120K", "120K"), ("2nd", "2nd"), ("삼/디/가전", "삼디가전"),
         ("제휴카드", "제휴카드"), ("라이프", "라이프"), ("MIT", "MIT"),
         ("모두의 행복", "모두의행복"), ("MNP", "MNP")]
REGIONS = ["광진/구리", "경기북부", "강원"]
GROUPS = [("대형", 45, 999, "목표 45건↑"), ("중형", 30, 44, "목표 30~44건"),
          ("소형", 0, 29, "목표 29건↓")]


def load(data_dir=None, cfg_path=None):
    d = Path(data_dir or BASE / "data")
    cfg = json.loads(Path(cfg_path or BASE / "stores.json").read_text(encoding="utf-8"))
    tgt = {s["조직"]: s["목표"] for s in cfg["매장"]}
    reg = {s["조직"]: s["상권"] for s in cfg["매장"]}
    series = {f.stem.split("_")[1]: json.loads(f.read_text(encoding="utf-8"))
              for f in sorted(d.glob("close_*.json"))}
    reports = {f.stem.split("_")[1]: json.loads(f.read_text(encoding="utf-8"))
               for f in sorted(d.glob("reports_*.json"))}
    return tgt, reg, series, reports, cfg


def remain_days(now, cfg):
    end = date.fromisoformat(cfg["캠페인"]["종료"])
    n, d = 0, now.date()
    while d < end:
        d += timedelta(days=1)
        if d.weekday() != 6:
            n += 1
    return max(n, 1), end


def elapsed(now, cfg):
    return max((now.date() - date.fromisoformat(cfg["캠페인"]["시작"])).days + 1, 1)


def sect(d, x, y, title, sub=""):
    d.rectangle([x, y, x + 8, y + 22], fill=NAVY)
    d.text((x + 16, y - 2), title, font=F(FB, 20), fill=NAVY)
    if sub:
        d.text((x + 16 + d.textlength(title, font=F(FB, 20)) + 12, y + 4), sub,
               font=F(FR, 14), fill=GRAY)
    return y + 34


def header(d, cfg, title, sub, rt, rb, badge=None):
    d.rectangle([0, 0, W, 78], fill=NAVY)
    d.rectangle([0, 0, W, 5], fill=TEAL)
    d.text((32, 9), f"{cfg['모델명']} 예약 캠페인 · 일일 성과 점검 리포트",
           font=F(FB, 16), fill=(150, 200, 215))
    d.text((32, 31), title, font=F(FB, 34), fill="white")
    tw = d.textlength(title, font=F(FB, 34))
    x = 32 + tw + 16
    if sub:
        d.text((x, 47), sub, font=F(FR, 17), fill=(178, 198, 222))
        x += d.textlength(sub, font=F(FR, 17)) + 18
    if badge:
        bw = int(F(FB, 14).getlength(badge)) + 24
        d.rounded_rectangle([x, 41, x + bw, 65], radius=8, fill=(56, 82, 122))
        d.text((x + bw // 2, 53), badge, font=F(FB, 14), fill=(205, 222, 242),
               anchor="mm")
    d.text((W - 32, 13), rt, font=F(FB, 25), fill="white", anchor="ra")
    d.text((W - 32, 47), rb, font=F(FB, 17), fill=(255, 217, 102), anchor="ra")


def kpi(d, y, cards):
    cw = (W - 64 - (len(cards) - 1) * 12) // len(cards)
    for i, (lab, val, sub, col) in enumerate(cards):
        x = 32 + i * (cw + 12)
        d.rounded_rectangle([x, y, x + cw, y + 66], radius=9, fill=LIGHT,
                            outline=LINE, width=2)
        d.text((x + 18, y + 33), lab, font=F(FB, 16), fill=GRAY, anchor="lm")
        d.text((x + 128, y + 33), val, font=F(FB, 28), fill=col, anchor="lm")
        if sub:
            d.text((x + cw - 16, y + 35), sub, font=F(FR, 13), fill=GRAY, anchor="rm")
    return y + 80


def trend(d, x, y, w, h, labels, cums, rate, avg, show_avg=True):
    d.rounded_rectangle([x, y, x + w, y + h], radius=10, fill="white",
                        outline=LINE, width=2)
    n = len(labels)
    if not n:
        return
    pl, pr, pt, pb = 46, 58, 38, 42
    gw, gh = w - pl - pr, h - pt - pb
    incs = [cums[0]] + [cums[i] - cums[i - 1] for i in range(1, n)]
    mx = max(max(incs), 1)
    bw = max(int(gw / n * 0.46), 6)
    step = gw / max(n - 1, 1)
    d.rectangle([x + 18, y + 13, x + 32, y + 25], fill=(160, 205, 225))
    d.text((x + 38, y + 11), "일별 증분", font=F(FR, 13), fill=GRAY)
    d.line([x + 112, y + 19, x + 140, y + 19], fill=TEAL, width=3)
    d.text((x + 146, y + 11), "우리 달성률", font=F(FR, 13), fill=GRAY)
    if show_avg:
        d.line([x + 238, y + 19, x + 266, y + 19], fill=(180, 188, 200), width=3)
        d.text((x + 272, y + 11), "지사 평균", font=F(FR, 13), fill=GRAY)
    base = y + pt + gh
    for i in range(n):
        cx = x + pl + step * i
        bh = int(gh * incs[i] / mx * 0.72)
        d.rectangle([cx - bw // 2, base - bh, cx + bw // 2, base],
                    fill=(160, 205, 225))
        if incs[i]:
            d.text((cx, base - bh - 16), str(incs[i]), font=F(FB, 12),
                   fill=(70, 110, 140), anchor="ma")
        d.text((cx, base + 7), labels[i], font=F(FR, 12), fill=GRAY, anchor="ma")
    rmax = max(max(rate), max(avg) if show_avg else 0, 0.15) * 1.18
    ser_list = ([(avg, (180, 188, 200), 3)] if show_avg else []) + [(rate, TEAL, 4)]
    for ser, col, wd in ser_list:
        pts = [(x + pl + step * i, base - gh * v / rmax) for i, v in enumerate(ser)]
        for a, b in zip(pts, pts[1:]):
            d.line([a, b], fill=col, width=wd)
        if col == TEAL:
            for px, py in pts:
                d.ellipse([px - 4, py - 4, px + 4, py + 4], fill=col)
            d.text((pts[-1][0] + 8, pts[-1][1] - 9), f"{rate[-1]*100:.0f}%",
                   font=F(FB, 16), fill=TEAL)
    for f in (0, 0.5, 1.0):
        yy = base - gh * f
        d.text((x + w - pr + 8, yy), f"{rmax*f*100:.0f}%", font=F(FR, 12),
               fill=GRAY, anchor="lm")


def link_grid(d, x, y, w, vals, dist, cum, judge=True):
    gw, gh = (w - 3 * 8) // 4, 100
    for i, (lab, key) in enumerate(LINKS):
        v = vals[key]
        mine = v / cum if cum else 0
        base = dist[key]
        if not judge:
            fill, outl, col, note = LIGHT, LINE, NAVY, ""
        else:
            tone = "good" if mine >= base else ("bad" if mine <= base * 0.6 else "mid")
            note = {"good": "▲ 우수", "bad": "▼ 개선", "mid": "△ 보통"}[tone]
            fill = {"good": (233, 245, 233), "bad": (253, 236, 234), "mid": LIGHT}[tone]
            outl = {"good": (175, 205, 175), "bad": (228, 182, 174), "mid": LINE}[tone]
            col = {"good": GREEN, "bad": RED, "mid": GRAY}[tone]
        cx = x + (i % 4) * (gw + 8)
        cy = y + (i // 4) * (gh + 12)
        d.rounded_rectangle([cx, cy, cx + gw, cy + gh], radius=10, fill=fill,
                            outline=outl, width=2)
        d.text((cx + 11, cy + 8), lab, font=F(FB, 14), fill=INK)
        if note:
            d.text((cx + gw - 11, cy + 9), note, font=F(FB, 12), fill=col, anchor="ra")
        d.text((cx + 11, cy + 31), f"{mine*100:.0f}%", font=F(FB, 30), fill=col)
        d.text((cx + gw - 11, cy + 40), f"{v:,}건", font=F(FB, 16), fill=INK,
               anchor="ra")
        if judge:
            d.text((cx + gw - 11, cy + 74), f"지사 {base*100:.0f}%", font=F(FR, 12),
                   fill=GRAY, anchor="ra")
    return y + 2 * gh + 12


def mid_band(d, y, vals, dm, cum, tgt_v, rem, pace, now):
    pw = (W - 64 - 14) // 2
    for i in range(2):
        d.rounded_rectangle([32 + i * (pw + 14), y, 32 + i * (pw + 14) + pw,
                             y + 122], radius=11, fill=(252, 253, 254),
                            outline=LINE, width=2)
    p1 = 32
    d.text((p1 + 16, y + 9), "모델별 예약 비중", font=F(FB, 16), fill=NAVY)
    d.text((p1 + pw - 16, y + 11), "지사 대비 (참고)", font=F(FR, 12), fill=GRAY,
           anchor="ra")
    rows = [("우리" if dm else "전체", [vals[k] for _, k in MODELS], cum)]
    if dm:
        rows.append(("지사", dm, sum(dm) or 1))
    for ri, (lbl, vs, tot) in enumerate(rows):
        yy = y + 40 + ri * 30
        d.text((p1 + 16, yy + 11), lbl, font=F(FB, 13), fill=INK, anchor="lm")
        xc, bw = p1 + 62, pw - 84
        for k2 in range(2):
            seg = int(bw * vs[k2] / (tot or 1))
            d.rectangle([xc, yy, xc + seg, yy + 23], fill=MCOL[k2])
            if seg > 40:
                d.text((xc + seg // 2, yy + 11), f"{vs[k2]/(tot or 1)*100:.0f}%",
                       font=F(FB, 13), fill="white", anchor="mm")
            xc += seg
    lx = p1 + 16
    for k2, (mn, _) in enumerate(MODELS):
        d.rectangle([lx, y + 102, lx + 14, y + 113], fill=MCOL[k2])
        d.text((lx + 20, y + 99), mn, font=F(FR, 13), fill=GRAY)
        lx += 20 + int(F(FR, 13).getlength(mn)) + 26

    p2 = 32 + pw + 14
    d.text((p2 + 16, y + 9), f"잔여 {rem}영업일 실행 계획", font=F(FB, 16), fill=NAVY)
    need = max(tgt_v - cum, 0) / rem
    d.text((p2 + pw - 16, y + 11), f"일 {need:.0f}건 필요 · 현 {pace:.0f}건",
           font=F(FR, 12), fill=RED if need > pace else GREEN, anchor="ra")
    proj = round(cum + pace * rem)
    gx, gw2, gy = p2 + 16, pw - 32, y + 42
    smax = max(tgt_v, proj) * 1.02
    d.rounded_rectangle([gx, gy, gx + gw2, gy + 20], radius=6, fill=(232, 236, 241))
    d.rounded_rectangle([gx, gy, gx + int(gw2 * proj / smax), gy + 20], radius=6,
                        fill=(168, 214, 205))
    d.rounded_rectangle([gx, gy, gx + int(gw2 * cum / smax), gy + 20], radius=6,
                        fill=TEAL)
    xt = gx + int(gw2 * tgt_v / smax)
    d.line([xt, gy - 6, xt, gy + 26], fill=RED, width=3)
    d.text((gx, gy + 28), f"현재 {cum:,}", font=F(FB, 13), fill=TEAL)
    d.text((min(gx + int(gw2 * proj / smax), gx + gw2 - 44), gy + 28),
           f"착지 {proj:,}", font=F(FB, 13), fill=(90, 150, 140), anchor="ma")
    d.text((xt, gy - 21), f"목표 {tgt_v:,}", font=F(FB, 13), fill=RED, anchor="ma")
    dl, dd = [], now.date()
    while len(dl) < min(rem, 5):
        dd += timedelta(days=1)
        if dd.weekday() != 6:
            dl.append((f"{dd.month}/{dd.day}", dd.weekday() == 5))
    bwd = (gw2 - (len(dl) - 1) * 7) // max(len(dl), 1)
    for j, (lb, sat) in enumerate(dl):
        xx = gx + j * (bwd + 7)
        d.rounded_rectangle([xx, y + 86, xx + bwd, y + 114], radius=6,
                            fill=(255, 244, 217) if sat else (243, 245, 248),
                            outline=(227, 199, 122) if sat else LINE, width=1)
        d.text((xx + bwd // 2, y + 89), lb + ("(토)" if sat else ""),
               font=F(FR, 11), fill=GRAY, anchor="ma")
        d.text((xx + bwd // 2, y + 100), f"{need:.0f}건", font=F(FB, 14),
               fill=GOLD if sat else INK, anchor="ma")
    return y + 136


def summary3(d, y, good, bad, task, bottom=H - 22):
    pw = (W - 64 - 2 * 14) // 3
    for i, (t, items, col, bg, ol) in enumerate([
            ("잘한 점 / 강점", good, GREEN, (238, 247, 239), (176, 208, 178)),
            ("아쉬운 점 / 과제", bad, RED, (253, 238, 236), (228, 182, 174)),
            ("잔여기간 중점 과제", task, (30, 62, 110), (238, 243, 250),
             (172, 192, 218))]):
        x = 32 + i * (pw + 14)
        d.rounded_rectangle([x, y, x + pw, bottom], radius=11, fill=bg,
                            outline=ol, width=2)
        d.text((x + 18, y + 12), t, font=F(FB, 17), fill=col)
        for j, it in enumerate([z for z in items if z][:3]):
            yy = y + 46 + j * 30
            d.ellipse([x + 20, yy + 2, x + 38, yy + 20], fill=col)
            d.text((x + 29, yy + 11), str(j + 1), font=F(FB, 12), fill="white",
                   anchor="mm")
            d.text((x + 46, yy + 1), it, font=F(FR, 14), fill=(58, 70, 90))


def _ctx(now, data_dir, cfg_path):
    tgt, reg, series, reports, cfg = load(data_dir, cfg_path)
    ymd = now.strftime("%Y%m%d")
    cur = reports.get(ymd) or reports[max(reports)]
    days = sorted(series)
    labels = [f"{int(k[4:6])}/{int(k[6:])}" for k in days]
    dtot = sum(x["예약누적"] for x in cur.values())
    dtgt = sum(tgt.values())
    dist = {k: sum(x[k] for x in cur.values()) / dtot for _, k in LINKS}
    rem, _ = remain_days(now, cfg)
    el = elapsed(now, cfg)
    return dict(tgt=tgt, reg=reg, series=series, cur=cur, cfg=cfg, days=days,
                labels=labels, dtot=dtot, dtgt=dtgt, dist=dist, rem=rem, el=el)


# ═══════════════════ 표지 ═══════════════════
def draw_cover(now, out, data_dir=None, cfg_path=None):
    c = _ctx(now, data_dir, cfg_path)
    cfg, cur, tgt = c["cfg"], c["cur"], c["tgt"]
    cum, G = c["dtot"], c["dtgt"]
    inc = sum(x.get("증분", 0) or 0 for x in cur.values())
    proj = round(cum + max(inc, cum / c["el"]) * c["rem"])
    end = date.fromisoformat(cfg["캠페인"]["종료"])
    launch = end + timedelta(days=1)

    img = Image.new("RGB", (W, H), (16, 30, 52))
    d = ImageDraw.Draw(img)
    for y in range(H):
        r = y / H
        d.line([(0, y), (W, y)],
               fill=(int(16 + 22 * r), int(30 + 40 * r), int(52 + 62 * r)))
    gl = Image.new("RGB", (W, H), (0, 0, 0))
    ImageDraw.Draw(gl).ellipse([W - 780, H - 620, W + 260, H + 300],
                               fill=(10, 92, 92))
    gl = gl.filter(ImageFilter.GaussianBlur(190))
    img = Image.blend(img, Image.blend(img, gl, 0.55), 0.85)
    d = ImageDraw.Draw(img)

    cums = [sum(c["series"][k].values()) for k in c["days"]]
    mx = max(cums) * 1.15 if cums else 1
    pts = [(120 + int((W - 240) * i / max(len(cums) - 1, 1)),
            H - 120 - int(340 * v / mx)) for i, v in enumerate(cums)]
    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    od = ImageDraw.Draw(ov)
    if len(pts) > 1:
        od.polygon(pts + [(pts[-1][0], H), (pts[0][0], H)], fill=(24, 150, 145, 46))
        for a, b in zip(pts, pts[1:]):
            od.line([a, b], fill=(64, 206, 196, 150), width=5)
    for p in pts:
        od.ellipse([p[0] - 6, p[1] - 6, p[0] + 6, p[1] + 6], fill=(120, 226, 216, 190))
    img = Image.alpha_composite(img.convert("RGBA"), ov).convert("RGB")
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, 14, H], fill=(14, 124, 123))

    d.text((110, 104), f"{cfg['지사명']}  ·  KT M&S", font=F(FB, 26),
           fill=(126, 208, 204))
    d.line([110, 148, 470, 148], fill=(40, 92, 110), width=2)
    d.text((108, 184), f"{cfg['모델명']} 예약 캠페인", font=F(FB, 92), fill="white")
    d.text((112, 306), "일일 성과 점검 리포트", font=F(FB, 56), fill=(150, 214, 210))
    dday = (launch - now.date()).days
    bt = f"출시 D-{dday}  ·  잔여 {c['rem']}영업일"
    bw = int(F(FB, 30).getlength(bt)) + 60
    d.rounded_rectangle([110, 396, 110 + bw, 456], radius=30, fill=(196, 122, 42))
    d.text((110 + bw // 2, 426), bt, font=F(FB, 30), fill=(255, 246, 232), anchor="mm")

    cards = [("누적 예약", f"{cum:,}", "건", f"목표 {G:,}건", (255, 255, 255)),
             ("달성률", f"{cum/G*100:.1f}", "%",
              f"{now.month}/{now.day} 마감 기준", (126, 226, 214)),
             ("달성 예상", f"{proj:,}", "건", f"목표 대비 {proj/G*100:.0f}%",
              (255, 209, 120)),
             ("금일 증분", f"+{inc}", "건", f"일평균 {cum/c['el']:.0f}건",
              (170, 226, 255))]
    cw, gap, y0 = 372, 22, 552
    for i, (lab, num, unit, sub, col) in enumerate(cards):
        x = 110 + i * (cw + gap)
        d.rounded_rectangle([x, y0, x + cw, y0 + 190], radius=18, fill=(26, 46, 74),
                            outline=(52, 82, 118), width=2)
        d.rectangle([x, y0, x + cw, y0 + 5], fill=col)
        d.text((x + 28, y0 + 30), lab, font=F(FB, 23), fill=(150, 176, 208))
        d.text((x + 28, y0 + 72), num, font=F(FB, 68), fill=col)
        d.text((x + 34 + F(FB, 68).getlength(num), y0 + 116), unit, font=F(FB, 26),
               fill=(170, 196, 224))
        d.text((x + 28, y0 + 152), sub, font=F(FR, 20), fill=(140, 168, 200))

    d.line([110, 822, W - 110, 822], fill=(46, 76, 108), width=2)
    lx = 110
    for i, (a, b) in enumerate([("지사 종합", "1장"), ("상권별", "3장"),
                                ("매장별", f"{len(cur)}장")]):
        d.text((lx, 854), a, font=F(FB, 26), fill=(210, 226, 244))
        wA = F(FB, 26).getlength(a)
        d.text((lx + wA + 12, 860), b, font=F(FR, 22), fill=(126, 208, 204))
        lx += wA + 12 + F(FR, 22).getlength(b) + 46
        if i < 2:
            d.text((lx - 26, 854), "·", font=F(FB, 26), fill=(70, 104, 140))
    st = date.fromisoformat(cfg["캠페인"]["시작"])
    d.text((110, 938), f"집계 기간  {st.year}. {st.month}. {st.day}  ~  "
           f"{now.month}. {now.day}   |   출시  {launch.month}. {launch.day}",
           font=F(FR, 24), fill=(132, 162, 196))
    d.text((W - 110, 938), f"{now.year}. {now.month}. {now.day}", font=F(FB, 26),
           fill=(160, 192, 226), anchor="ra")
    img.save(out, optimize=True)
    return out


# ═══════════════════ 지사 1P ═══════════════════
def draw_branch(now, out, data_dir=None, cfg_path=None):
    c = _ctx(now, data_dir, cfg_path)
    cfg, cur, tgt, reg = c["cfg"], c["cur"], c["tgt"], c["reg"]
    cum, G, rem, el = c["dtot"], c["dtgt"], c["rem"], c["el"]
    inc = sum(x.get("증분", 0) or 0 for x in cur.values())
    pace = max(inc, cum / el)
    proj = round(cum + pace * rem)
    npeople = sum(len(x.get("개인별", [])) for x in cur.values())
    end = date.fromisoformat(cfg["캠페인"]["종료"])

    img = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(img)
    header(d, cfg, cfg["지사명"], f"{len(cur)}개 매장 전체", f"목표 {G:,}건",
           f"{now.month}/{now.day} 마감 기준 · 출시 {(end+timedelta(days=1)).month}/"
           f"{(end+timedelta(days=1)).day}")
    y = kpi(d, 90, [
        ("누적 예약", f"{cum:,}건", f"목표 {G:,}건", NAVY),
        ("달성률", f"{cum/G*100:.1f}%", "전체 기준", TEAL),
        ("달성 예상", f"{proj:,}건", f"목표 대비 {proj/G*100:.0f}%",
         GREEN if proj >= G else (RED if proj / G < 0.6 else GOLD)),
        ("인당 실적", f"{cum/max(npeople,1):.1f}건", f"{npeople}명", INK),
        ("잔여 목표", f"{max(G-cum,0):,}건", f"잔여 {rem}영업일", GOLD)])

    y2 = sect(d, 32, y, "예약 추이", "막대=일별 증분(건) · 선=누적 달성률(%)")
    sect(d, 1160, y, "연계판매 성적표", "유치율 · 건수")
    cums = [sum(c["series"][k].values()) for k in c["days"]]
    rate = [v / G for v in cums]
    trend(d, 32, y2, 1096, 226, c["labels"], cums, rate, rate, show_avg=False)
    agg = {k: sum(x[k] for x in cur.values()) for _, k in LINKS}
    agg.update({k: sum(x[k] for x in cur.values()) for _, k in MODELS})
    link_grid(d, 1160, y2, W - 32 - 1160, agg, c["dist"], cum, judge=False)
    y = y2 + 240
    y = mid_band(d, y, agg, None, cum, G, rem, pace, now)

    # 하단 좌: 상권별 현황 / 우: TOP5·하위5
    ly = sect(d, 32, y, "상권별 현황", "달성률 순")
    sect(d, 1130, y, "매장 TOP 5 · 하위 5", "달성률")
    cw = [130, 92, 96, 96, 108, 108, 118]
    tw = sum(cw)
    d.rectangle([32, ly, 32 + tw, ly + 34], fill=NAVY)
    xa = 32
    for i, h in enumerate(["상권", "매장수", "목표", "누적", "달성률",
                           "달성예상", "예상 달성률"]):
        d.text((xa + cw[i] // 2, ly + 17), h, font=F(FB, 15), fill="white",
               anchor="mm")
        xa += cw[i]
    ly += 34
    rows = []
    for g in REGIONS:
        ms = [n for n in cur if reg[n] == g]
        gc = sum(cur[n]["예약누적"] for n in ms)
        gt = sum(tgt[n] for n in ms)
        gi = sum(cur[n].get("증분", 0) or 0 for n in ms)
        gp = round(gc + max(gi, gc / el) * rem)
        rows.append((g, len(ms), gt, gc, gc / gt, gp, gp / gt))
    rows.sort(key=lambda r: -r[4])
    for i, (g, n, gt, gc, ac, gp, pr) in enumerate(rows):
        d.rectangle([32, ly, 32 + tw, ly + 34],
                    fill="white" if i % 2 == 0 else (250, 251, 253))
        vals = [g, f"{n}개", f"{gt:,}", f"{gc:,}", f"{ac*100:.1f}%",
                f"{gp:,}", f"{pr*100:.0f}%"]
        xa = 32
        for j, v in enumerate(vals):
            col = INK
            if j == 4:
                col = GREEN if ac >= cum / G else RED
            elif j == 6:
                col = GREEN if pr >= 1 else (RED if pr < 0.6 else GOLD)
            d.text((xa + cw[j] // 2, ly + 17), v,
                   font=F(FB, 15) if j in (0, 4, 6) else F(FR, 15), fill=col,
                   anchor="mm")
            xa += cw[j]
        d.line([32, ly + 34, 32 + tw, ly + 34], fill=(234, 238, 243), width=1)
        ly += 34
    d.rectangle([32, ly - 34 * len(rows) - 34, 32 + tw, ly],
                outline=(120, 130, 145), width=2)

    rank = sorted(cur, key=lambda n: -(cur[n]["예약누적"] / tgt[n]))
    ry = ly - 34 * len(rows) - 34
    bw2 = (W - 32 - 1130 - 16) // 2
    for bi, (ttl, items, col, bg) in enumerate([
            ("TOP 5", rank[:5], GREEN, (240, 248, 241)),
            ("하위 5", rank[-5:], RED, (253, 240, 238))]):
        bx = 1130 + bi * (bw2 + 16)
        d.rounded_rectangle([bx, ry, bx + bw2, ry + 34], radius=6, fill=col)
        d.text((bx + bw2 // 2, ry + 17), ttl, font=F(FB, 16), fill="white",
               anchor="mm")
        yy = ry + 34
        for i, n in enumerate(items):
            ac = cur[n]["예약누적"] / tgt[n]
            d.rectangle([bx, yy, bx + bw2, yy + 34],
                        fill=bg if i % 2 == 0 else "white")
            d.text((bx + 16, yy + 17), f"{rank.index(n)+1}. {n}", font=F(FR, 15),
                   fill=INK, anchor="lm")
            d.text((bx + bw2 - 16, yy + 17), f"{ac*100:.0f}%", font=F(FB, 15),
                   fill=col, anchor="rm")
            d.line([bx, yy + 34, bx + bw2, yy + 34], fill=(234, 238, 243), width=1)
            yy += 34
        d.rectangle([bx, ry, bx + bw2, yy], outline=(120, 130, 145), width=2)

    # 총평
    y = max(ly, ry + 34 * 6) + 16
    y = sect(d, 32, y, "예약기간 총평 및 잔여기간 중점 과제", "데이터 근거 기반")
    best = max(cur, key=lambda n: cur[n]["예약누적"] / tgt[n])
    worst = min(cur, key=lambda n: cur[n]["예약누적"] / tgt[n])
    under = [n for n in cur if (cur[n]["예약누적"] +
             max(cur[n].get("증분", 0) or 0, cur[n]["예약누적"] / el) * rem)
             / tgt[n] < 1]
    wl = min(LINKS, key=lambda x: c["dist"][x[1]])
    bl = max(LINKS, key=lambda x: c["dist"][x[1]])
    need = max(G - cum, 0) / rem
    summary3(d, y,
             [f"누적 {cum:,}건 · 달성률 {cum/G*100:.1f}% (달성 예상 {proj/G*100:.0f}%)",
              f"{best} {cur[best]['예약누적']/tgt[best]*100:.0f}% 선두 · "
              f"{bl[0]} 유치율 {c['dist'][bl[1]]*100:.0f}%",
              f"금일 +{inc}건 · 일평균 {cum/el:.0f}건"],
             [f"최저 {worst} {cur[worst]['예약누적']/tgt[worst]*100:.0f}% — 매장 격차 큼",
              f"목표 미달 예상 {len(under)}개 매장 — 집중 관리 필요",
              f"{wl[0]} 유치율 {c['dist'][wl[1]]*100:.0f}%로 연계 중 최저"],
             [f"목표까지 {max(G-cum,0):,}건 — 잔여 {rem}일간 일 {need:.0f}건 필요 "
              f"(현 {pace:.0f}건)",
              f"미달 예상 {len(under)}개 매장 일일 점검 ({', '.join(under[:2])} 외)",
              f"{wl[0]} 유치 집중 — 현 {c['dist'][wl[1]]*100:.0f}%"])
    img.save(out, optimize=True)
    return out


# ═══════════════════ 상권 1P ═══════════════════
def draw_region(scope, now, out, data_dir=None, cfg_path=None):
    c = _ctx(now, data_dir, cfg_path)
    cfg, cur, tgt, reg = c["cfg"], c["cur"], c["tgt"], c["reg"]
    ms = [n for n in cur if reg[n] == scope]
    cum = sum(cur[n]["예약누적"] for n in ms)
    t = sum(tgt[n] for n in ms)
    inc = sum(cur[n].get("증분", 0) or 0 for n in ms)
    rem, el = c["rem"], c["el"]
    pace = max(inc, cum / el)
    proj = round(cum + pace * rem)
    npeople = sum(len(cur[n].get("개인별", [])) for n in ms)
    ranks = sorted(REGIONS, key=lambda g: -(
        sum(cur[n]["예약누적"] for n in cur if reg[n] == g) /
        sum(tgt[n] for n in tgt if reg[n] == g)))
    end = date.fromisoformat(cfg["캠페인"]["종료"])

    img = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(img)
    header(d, cfg, f"{scope} 상권", f"{len(ms)}개 매장",
           f"상권 {ranks.index(scope)+1}위 / {len(REGIONS)}개 상권",
           f"{now.month}/{now.day} 마감 기준 · 출시 "
           f"{(end+timedelta(days=1)).month}/{(end+timedelta(days=1)).day}")
    y = kpi(d, 90, [
        ("누적 예약", f"{cum:,}건", f"목표 {t:,}건", NAVY),
        ("달성률", f"{cum/t*100:.1f}%", f"지사 {c['dtot']/c['dtgt']*100:.1f}%", TEAL),
        ("달성 예상", f"{proj:,}건", f"목표 대비 {proj/t*100:.0f}%",
         GREEN if proj >= t else (RED if proj / t < 0.6 else GOLD)),
        ("인당 실적", f"{cum/max(npeople,1):.1f}건", f"{npeople}명", INK),
        ("잔여 목표", f"{max(t-cum,0):,}건", f"잔여 {rem}영업일", GOLD)])

    y2 = sect(d, 32, y, "예약 추이", "막대=일별 증분(건) · 선=누적 달성률(%)")
    sect(d, 1160, y, "연계판매 성적표", "유치율 · 건수 · 지사 대비")
    cums = [sum(c["series"][k].get(n, 0) for n in ms) for k in c["days"]]
    dcums = [sum(c["series"][k].values()) for k in c["days"]]
    trend(d, 32, y2, 1096, 226, c["labels"], cums,
          [v / t for v in cums], [v / c["dtgt"] for v in dcums])
    agg = {k: sum(cur[n][k] for n in ms) for _, k in LINKS}
    agg.update({k: sum(cur[n][k] for n in ms) for _, k in MODELS})
    link_grid(d, 1160, y2, W - 32 - 1160, agg, c["dist"], cum)
    y = y2 + 240
    dm = [sum(x[k] for x in cur.values()) for _, k in MODELS]
    y = mid_band(d, y, agg, dm, cum, t, rem, pace, now)

    # 소속 매장 현황
    y = sect(d, 32, y, "소속 매장 현황", "달성률 순")
    heads = ["매장", "목표", "누적", "달성률", "달성예상", "예상 달성률",
             "120K", "제휴카드", "모행"]
    cw = [172, 96, 96, 116, 116, 128, 112, 118, 100]
    tw = sum(cw)
    order = sorted(ms, key=lambda n: -(cur[n]["예약누적"] / tgt[n]))
    rh = max(24, min(34, (H - 210 - y) // (len(order) + 1)))
    d.rectangle([32, y, 32 + tw, y + rh], fill=NAVY)
    xa = 32
    for i, h in enumerate(heads):
        d.text((xa + cw[i] // 2, y + rh // 2), h, font=F(FB, 15), fill="white",
               anchor="mm")
        xa += cw[i]
    y += rh
    top = y
    for i, n in enumerate(order):
        v = cur[n]
        ac = v["예약누적"] / tgt[n]
        pj = (v["예약누적"] + max(v.get("증분", 0) or 0,
              v["예약누적"] / el) * rem) / tgt[n]
        g2 = v["예약누적"] or 1
        d.rectangle([32, y, 32 + tw, y + rh],
                    fill="white" if i % 2 == 0 else (250, 251, 253))
        vals = [n, tgt[n], v["예약누적"], f"{ac*100:.0f}%",
                round(pj * tgt[n]), f"{pj*100:.0f}%",
                f"{v['120K']/g2*100:.0f}%", f"{v['제휴카드']/g2*100:.0f}%",
                f"{v['모두의행복']/g2*100:.0f}%"]
        xa = 32
        for j, val in enumerate(vals):
            col = INK
            if j == 3:
                col = GREEN if ac >= c["dtot"] / c["dtgt"] else RED
            elif j == 5:
                col = GREEN if pj >= 1 else (RED if pj < 0.6 else GOLD)
            elif j >= 6:
                key = ["120K", "제휴카드", "모두의행복"][j - 6]
                r = v[key] / g2
                col = GREEN if r >= c["dist"][key] else (
                    RED if r <= c["dist"][key] * 0.6 else INK)
            d.text((xa + cw[j] // 2, y + rh // 2), str(val),
                   font=F(FB, 15) if j in (0, 3, 5) else F(FR, 15), fill=col,
                   anchor="mm")
            xa += cw[j]
        d.line([32, y + rh, 32 + tw, y + rh], fill=(234, 238, 243), width=1)
        y += rh
    d.rectangle([32, top - rh, 32 + tw, y], outline=(120, 130, 145), width=2)

    y += 14
    y = sect(d, 32, y, "예약기간 총평 및 잔여기간 중점 과제", "데이터 근거 기반")
    best, worst = order[0], order[-1]
    under = [n for n in ms if (cur[n]["예약누적"] +
             max(cur[n].get("증분", 0) or 0, cur[n]["예약누적"] / el) * rem)
             / tgt[n] < 1]
    wl = min(LINKS, key=lambda x: agg[x[1]] / cum / max(c["dist"][x[1]], .001))
    bl = max(LINKS, key=lambda x: agg[x[1]] / cum / max(c["dist"][x[1]], .001))
    need = max(t - cum, 0) / rem
    summary3(d, y,
             [f"달성 예상 {proj:,}건 ({proj/t*100:.0f}%) · 상권 "
              f"{ranks.index(scope)+1}위",
              f"{best} {cur[best]['예약누적']/tgt[best]*100:.0f}%로 상권 선두",
              f"{bl[0]} 유치율 {agg[bl[1]]/cum*100:.0f}% "
              f"(지사 {c['dist'][bl[1]]*100:.0f}%)"],
             [f"달성률 {cum/t*100:.1f}% (지사 {c['dtot']/c['dtgt']*100:.1f}%)",
              f"최저 {worst} {cur[worst]['예약누적']/tgt[worst]*100:.0f}% — 상권 내 격차",
              f"목표 미달 예상 {len(under)}개 매장"],
             [f"목표까지 {max(t-cum,0):,}건 — 잔여 {rem}일간 일 {need:.0f}건 필요 "
              f"(현 {pace:.0f}건)",
              f"미달 예상 {len(under)}개 매장 일일 점검 ({', '.join(under[:2])} 외)"
              if under else "전 매장 목표 달성 예상 — 페이스 유지",
              f"{wl[0]} 유치 집중 — 현 {agg[wl[1]]/cum*100:.0f}%"])
    img.save(out, optimize=True)
    return out


# ═══════════════════ 매장 1P ═══════════════════
def draw_store(store, now, out, data_dir=None, cfg_path=None):
    c = _ctx(now, data_dir, cfg_path)
    cfg, cur, tgt, reg = c["cfg"], c["cur"], c["tgt"], c["reg"]
    v = cur[store]
    cum, t = v["예약누적"], tgt[store]
    inc = v.get("증분", 0) or 0
    rem, el = c["rem"], c["el"]
    pace = max(inc, cum / el)
    proj = round(cum + pace * rem)
    persons = sorted(v.get("개인별", []), key=lambda p: -p["실적"])
    rank = sorted(cur, key=lambda n: -(cur[n]["예약누적"] / tgt[n]))
    reg_ms = sorted([n for n in cur if reg[n] == reg[store]],
                    key=lambda n: -(cur[n]["예약누적"] / tgt[n]))
    # 동급 그룹
    gname, lo, hi, glab = next(g for g in GROUPS if g[1] <= t <= g[2])
    peers = [n for n in cur if lo <= tgt[n] <= hi]
    prank = sorted(peers, key=lambda n: -(cur[n]["예약누적"] / tgt[n])).index(store) + 1
    end = date.fromisoformat(cfg["캠페인"]["종료"])

    img = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(img)
    header(d, cfg, f"{store}점", f"{reg[store]} 상권",
           f"지사 {rank.index(store)+1}위 / {len(rank)}개 매장",
           f"{reg[store]} {reg_ms.index(store)+1}위 / {len(reg_ms)}개점",
           badge=f"{gname}({glab}) 그룹 {prank}위 / {len(peers)}개")
    y = kpi(d, 90, [
        ("누적 예약", f"{cum}건", f"목표 {t}건", NAVY),
        ("달성률", f"{cum/t*100:.1f}%", f"지사 {c['dtot']/c['dtgt']*100:.1f}%", TEAL),
        ("달성 예상", f"{proj}건", f"목표 대비 {proj/t*100:.0f}%",
         GREEN if proj >= t else (RED if proj / t < 0.6 else GOLD)),
        ("인당 실적", f"{cum/max(len(persons),1):.1f}건",
         f"지사 {c['dtot']/max(sum(len(x.get('개인별',[])) for x in cur.values()),1):.1f}건",
         INK),
        ("잔여 목표", f"{max(t-cum,0)}건", f"잔여 {rem}영업일", GOLD)])

    y2 = sect(d, 32, y, "예약 추이", "막대=일별 증분(건) · 선=누적 달성률(%)")
    sect(d, 1160, y, "연계판매 성적표", "유치율 · 건수 · 지사 대비")
    cums = [c["series"][k].get(store, 0) for k in c["days"]]
    dcums = [sum(c["series"][k].values()) for k in c["days"]]
    trend(d, 32, y2, 1096, 226, c["labels"], cums,
          [x / t for x in cums], [x / c["dtgt"] for x in dcums])
    link_grid(d, 1160, y2, W - 32 - 1160, v, c["dist"], cum)
    y = y2 + 240
    dm = [sum(x[k] for x in cur.values()) for _, k in MODELS]
    y = mid_band(d, y, v, dm, cum, t, rem, pace, now)

    # 직원별
    y = sect(d, 32, y, "직원별 실적", "연계 = 건수(유치율) · 색상은 지사 평균 대비")
    heads = ["이름", "목표", "실적", "달성률"] + [l for l, _ in LINKS[:6]] + \
            ["모행", "MNP"]
    cw = [140, 82, 82, 104] + [166] * 6 + [96, 96]
    tw = sum(cw)
    rh = max(22, min(32, (H - 214 - y) // (len(persons) + 1)))
    d.rectangle([32, y, 32 + tw, y + rh], fill=NAVY)
    xa = 32
    for i, h in enumerate(heads):
        d.text((xa + cw[i] // 2, y + rh // 2), h, font=F(FB, 15), fill="white",
               anchor="mm")
        xa += cw[i]
    y += rh
    top = y
    for i, p in enumerate(persons):
        d.rectangle([32, y, 32 + tw, y + rh],
                    fill="white" if i % 2 == 0 else (250, 251, 253))
        ach = p["실적"] / p["목표"] * 100 if p["목표"] else 0
        xa = 32
        for j, val in enumerate([p["이름"], p["목표"], p["실적"], f"{ach:.0f}%"]):
            col = GREEN if (j == 3 and ach >= 100) else (
                RED if (j == 3 and ach < 50) else INK)
            d.text((xa + cw[j] // 2, y + rh // 2), str(val),
                   font=F(FB, 15) if j in (0, 3) else F(FR, 15), fill=col,
                   anchor="mm")
            xa += cw[j]
        for j, (lab, key) in enumerate(LINKS[:6]):
            r = p[key] / p["실적"] if p["실적"] else 0
            col = GREEN if r >= c["dist"][key] else (
                RED if r <= c["dist"][key] * 0.6 else INK)
            d.text((xa + cw[4 + j] // 2, y + rh // 2),
                   f"{p[key]} ({r*100:.0f}%)", font=F(FR, 15), fill=col, anchor="mm")
            xa += cw[4 + j]
        for j, key in enumerate(("모행", "MNP")):
            d.text((xa + cw[10 + j] // 2, y + rh // 2), str(p[key]),
                   font=F(FR, 15), fill=INK if p[key] else (185, 192, 202),
                   anchor="mm")
            xa += cw[10 + j]
        d.line([32, y + rh, 32 + tw, y + rh], fill=(234, 238, 243), width=1)
        y += rh
    d.rectangle([32, top - rh, 32 + tw, y], outline=(120, 130, 145), width=2)

    y += 14
    y = sect(d, 32, y, "예약기간 총평 및 잔여기간 중점 과제", "데이터 근거 기반")
    g2 = cum or 1
    wl = min(LINKS, key=lambda x: v[x[1]] / g2 / max(c["dist"][x[1]], .001))
    bl = max(LINKS, key=lambda x: v[x[1]] / g2 / max(c["dist"][x[1]], .001))
    zero = sum(1 for p in persons if p["실적"] == 0)
    low = sum(1 for p in persons if p["목표"] and p["실적"] / p["목표"] < 0.5)
    need = max(t - cum, 0) / rem
    good, bad = [], []
    if cum / t >= c["dtot"] / c["dtgt"]:
        good.append(f"달성률 {cum/t*100:.1f}%로 지사 평균({c['dtot']/c['dtgt']*100:.1f}%) 상회")
    else:
        bad.append(f"달성률 {cum/t*100:.1f}% — 지사 평균({c['dtot']/c['dtgt']*100:.1f}%) 미달")
    good.append(f"{bl[0]} 유치율 {v[bl[1]]/g2*100:.0f}% (지사 {c['dist'][bl[1]]*100:.0f}%) 우수")
    if persons and zero == 0:
        good.append(f"{len(persons)}명 전원 실적 발생")
    good.append(f"동급 {gname} 그룹 {prank}위 / {len(peers)}개")
    bad.append(f"{wl[0]} 유치율 {v[wl[1]]/g2*100:.0f}% — 지사({c['dist'][wl[1]]*100:.0f}%) 대비 부진")
    if zero:
        bad.append(f"실적 0건 {zero}명")
    if proj < t:
        bad.append(f"현 페이스 유지 시 {proj/t*100:.0f}% — 목표 미달 예상")
    summary3(d, y, good, bad,
             [f"목표까지 {max(t-cum,0)}건 — 잔여 {rem}일간 일 {need:.1f}건 필요 "
              f"(현 {pace:.1f}건)",
              f"{wl[0]} 유치 집중 — 현 {v[wl[1]]/g2*100:.0f}% (지사 {c['dist'][wl[1]]*100:.0f}%)",
              (f"달성률 50% 미만 {low}명 개별 코칭"
               f" ({', '.join(p['이름'] for p in persons if p['목표'] and p['실적']/p['목표']<0.5)[:18]} 외)"
               if low else "전원 달성률 50% 이상 — 상위 목표 재설정")])
    img.save(out, optimize=True)
    return out
