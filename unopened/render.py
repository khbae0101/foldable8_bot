# -*- coding: utf-8 -*-
"""미개통 현황 + 부족재고 이미지 렌더."""
from PIL import Image, ImageDraw, ImageFont
 
FB = "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"
FR = "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"
F = lambda p, s: ImageFont.truetype(p, s)
 
NAVY = (31, 53, 87); RED = (192, 57, 43); GREEN = (46, 125, 50)
GOLD = (176, 132, 30); INK = (26, 34, 48); GRAY = (110, 122, 138)
LINE = (216, 221, 228); LIGHT = (245, 247, 250); REGBG = (228, 234, 244)
M_TONE = {"폴드8": (24, 96, 112), "플립8": (150, 106, 32)}
M_TINT = {"폴드8": (238, 247, 247), "플립8": (253, 248, 238)}
STOCK_TONE = (150, 60, 46); STOCK_TINT = (253, 242, 240)
 
MOD = ["폴드8", "플립8"]
TYPES = ["010", "MNP", "기변"]
LACK = ["블랙", "크림", "라벤더"]
REGIONS = ["광진/구리", "경기북부", "강원"]
W = 1300
 
 
def render(cur, prev, stores, reg, date_label, carry, out_path):
    """cur/prev: {매장: {모델:[010,MNP,기변,계], '부족':{색:수}}}"""
    def un(names, m=None, t=None):
        s = 0
        for n in names:
            for mm in ([m] if m else MOD):
                for i, tt in enumerate(TYPES):
                    if t and tt != t:
                        continue
                    s += cur[n][mm][i]
        return s
 
    def pun(names):
        return sum(sum(prev[n][mm][3] for mm in MOD) for n in names if n in prev)
 
    def lk(names, c=None):
        return sum(cur[n]["부족"].get(c, 0) if c else sum(cur[n]["부족"].values())
                   for n in names)
 
    def plk(names):
        return sum(sum(prev[n]["부족"].values()) for n in names if n in prev)
 
    allst = [n for n, _ in stores]
    n_rows = 1 + len(REGIONS) + len(allst)
    H = 76 + 98 + 34 + 48 + n_rows * 30 + 84
    img = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(img)
 
    d.rectangle([0, 0, W, 76], fill=(38, 38, 38))
    d.rectangle([0, 0, W, 5], fill=(14, 124, 123))
    d.text((28, 20), "폴더블8 사전예약 미개통 현황", font=F(FB, 28), fill="white")
    d.text((W - 28, 28), date_label, font=F(FB, 20), fill=(255, 217, 102), anchor="ra")
 
    y = 88
    d1 = un(allst) - pun(allst); d2 = lk(allst) - plk(allst)
    cards = [("미개통 총계", f"{un(allst)}건", NAVY, f"전일 대비 {d1:+d}"),
             ("신규(010+MNP)", f"{un(allst,t='010')+un(allst,t='MNP')}건",
              (14, 124, 123), ""),
             ("기변", f"{un(allst,t='기변')}건", GOLD, ""),
             ("부족재고", f"{lk(allst)}대", RED, f"전일 대비 {d2:+d}")]
    cw = (W - 56 - 3 * 10) // 4
    for i, (a, b, col, sub) in enumerate(cards):
        x = 28 + i * (cw + 10)
        d.rounded_rectangle([x, y, x + cw, y + 82], radius=10, fill=LIGHT,
                            outline=LINE, width=2)
        d.text((x + cw // 2, y + 12), a, font=F(FB, 15), fill=GRAY, anchor="ma")
        d.text((x + cw // 2, y + 32), b, font=F(FB, 28), fill=col, anchor="ma")
        if sub:
            d.text((x + cw // 2, y + 66), sub, font=F(FB, 14),
                   fill=GREEN if "-" in sub else GRAY, anchor="ma")
    y += 98
 
    d.rectangle([28, y, 37, y + 20], fill=NAVY)
    d.text((45, y - 3), "매장별 미개통 · 부족재고", font=F(FB, 19), fill=NAVY)
    d.text((W - 28, y + 3), "모델 × 개통유형 / 부족재고 색상별 · 전일 대비 감소=초록",
           font=F(FR, 13), fill=GRAY, anchor="ra")
    y += 30
 
    colw = [104, 158] + [62] * 6 + [76] + [84] + [92] * 3 + [82] + [78]
    tw = sum(colw)
    hh, rh = 48, 30
    d.rectangle([28, y, 28 + tw, y + hh], fill=NAVY)
    xa = 28
    for i, h in enumerate(["상권", "매장"]):
        d.text((xa + colw[i] // 2, y + hh // 2), h, font=F(FB, 17), fill="white",
               anchor="mm")
        xa += colw[i]
    for mi, m in enumerate(MOD):
        gw = colw[2 + mi * 3] * 3
        d.rectangle([xa, y, xa + gw, y + 21], fill=M_TONE[m])
        d.text((xa + gw // 2, y + 10), m, font=F(FB, 16), fill="white", anchor="mm")
        for ti, t in enumerate(TYPES):
            d.text((xa + colw[2] * ti + colw[2] // 2, y + 33), t, font=F(FB, 15),
                   fill="white", anchor="mm")
            if ti:
                d.line([xa + colw[2] * ti, y + 23, xa + colw[2] * ti, y + hh - 4],
                       fill=(92, 116, 150), width=1)
        d.line([xa, y, xa, y + hh], fill="white", width=2)
        xa += gw
    d.line([xa, y, xa, y + hh], fill="white", width=2)
    d.rectangle([xa, y, xa + colw[8], y + hh], fill=(64, 64, 64))
    d.text((xa + colw[8] // 2, y + hh // 2), "계", font=F(FB, 18), fill="white",
           anchor="mm")
    xa += colw[8]
    d.rectangle([xa, y, xa + colw[9], y + hh], fill=(88, 88, 88))
    d.text((xa + colw[9] // 2, y + 15), "전일", font=F(FB, 14), fill="white", anchor="mm")
    d.text((xa + colw[9] // 2, y + 31), "대비", font=F(FB, 14), fill="white", anchor="mm")
    xa += colw[9]
    d.line([xa, y, xa, y + hh], fill="white", width=3)
    gw = sum(colw[10:13])
    d.rectangle([xa, y, xa + gw, y + 21], fill=STOCK_TONE)
    d.text((xa + gw // 2, y + 10), "부족재고 (폴드8)", font=F(FB, 16), fill="white",
           anchor="mm")
    for ci, c in enumerate(LACK):
        d.text((xa + colw[10] * ci + colw[10] // 2, y + 33), c, font=F(FB, 15),
               fill="white", anchor="mm")
        if ci:
            d.line([xa + colw[10] * ci, y + 23, xa + colw[10] * ci, y + hh - 4],
                   fill=(196, 140, 128), width=1)
    xa += gw
    d.rectangle([xa, y, xa + colw[13], y + hh], fill=(110, 44, 34))
    d.text((xa + colw[13] // 2, y + hh // 2), "계", font=F(FB, 18), fill="white",
           anchor="mm")
    xa += colw[13]
    d.rectangle([xa, y, xa + colw[14], y + hh], fill=(140, 70, 58))
    d.text((xa + colw[14] // 2, y + 15), "전일", font=F(FB, 14), fill="white", anchor="mm")
    d.text((xa + colw[14] // 2, y + 31), "대비", font=F(FB, 14), fill="white", anchor="mm")
    y += hh
    top = y
 
    def row(cells, kind):
        nonlocal y
        bg = {"total": (38, 38, 38), "region": REGBG}.get(kind)
        if bg:
            d.rectangle([28, y, 28 + tw, y + rh], fill=bg)
        fg = "white" if kind == "total" else INK
        xa = 28
        for i, c in enumerate(cells):
            if kind == "store":
                if 2 <= i <= 7:
                    d.rectangle([xa, y + 1, xa + colw[i], y + rh - 1],
                                fill=M_TINT[MOD[(i - 2) // 3]])
                elif 10 <= i <= 12:
                    d.rectangle([xa, y + 1, xa + colw[i], y + rh - 1], fill=STOCK_TINT)
            if i in (9, 14):
                txt = f"{c:+d}" if c else "-"
            else:
                txt = str(c) if (c or i < 2) else "-"
            if kind == "store" and i == 1 and cells[1] in carry:
                txt += "＊"
            f_ = FB if (kind != "store" or i in (1, 8, 9, 13, 14)) else FR
            col = fg
            if i in (9, 14):
                col = GREEN if c < 0 else (RED if c > 0 else
                                           ((176, 184, 196) if kind == "store" else fg))
            elif kind == "store":
                if not c and i >= 2:
                    col = (176, 184, 196)
                elif i == 13:
                    col = RED
                elif i == 8:
                    col = INK
                elif 10 <= i <= 12 and c >= 5:
                    col = RED
            d.text((xa + colw[i] // 2, y + rh // 2), txt, font=F(f_, 17), fill=col,
                   anchor="mm")
            xa += colw[i]
        for b in (2, 5, 8, 9, 10, 13, 14):
            bx = 28 + sum(colw[:b])
            d.line([bx, y, bx, y + rh], fill=(150, 162, 178),
                   width=3 if b == 10 else 2)
        d.line([28, y + rh, 28 + tw, y + rh], fill=(234, 238, 243), width=1)
        y += rh
 
    def cells(names):
        out = []
        for m in MOD:
            for t in TYPES:
                out.append(un(names, m, t))
        out.append(un(names))
        out.append(un(names) - pun(names))
        for c in LACK:
            out.append(lk(names, c))
        out.append(lk(names))
        out.append(lk(names) - plk(names))
        return out
 
    row(["", "지사 계"] + cells(allst), "total")
    for g in REGIONS:
        ms = [n for n, gg in stores if gg == g]
        ms.sort(key=lambda n: -un([n]))
        row(["", g] + cells(ms), "region")
        for n in ms:
            row([g, n] + cells([n]), "store")
    d.rectangle([28, top - hh, 28 + tw, y], outline=(120, 130, 145), width=2)
 
    y += 10
    d.text((28, y), "※ 미개통 = 예약 접수 후 미개통 건 (개통유형별)  ·  "
           "부족재고 5대 이상 빨간색  ·  '-'는 해당 없음  ·  미개통 많은 순",
           font=F(FR, 13), fill=GRAY)
    if carry:
        d.text((28, y + 22), f"＊ 미보고 매장(전일값 이월, {len(carry)}개) : "
               + ", ".join(carry), font=F(FB, 13), fill=RED)
    else:
        z = [n for n in allst if sum(cur[n][m][3] for m in MOD) == 0]
        d.text((28, y + 22), f"※ 전 매장 보고 완료  ·  미개통 0건 완료 {len(z)}개 매장",
               font=F(FB, 13), fill=GREEN)
    img = img.crop((0, 0, W, y + 52))
    img.save(out_path, optimize=True)
    return out_path
 
 
def build_text(cur, prev, allst, date_label):
    """텔레그램 텍스트 요약."""
    def s(data, m=None, i=3):
        if m:
            return sum(data[n][m][i] for n in allst if n in data)
        return sum(sum(data[n][mm][i] for mm in MOD) for n in allst if n in data)
 
    lines = [f"■ 강동소매 미개통 현황({date_label})",
             " ㅇ 모델 / 010 / MNP / 기변 / 계 (전일대비)", ""]
    for m in ["플립8", "폴드8"]:
        v = [s(cur, m, i) for i in range(4)]
        dv = v[3] - s(prev, m, 3)
        lines.append(f"* {m} : {v[0]}건 / {v[1]}건 / {v[2]}건 / {v[3]}건 ({dv:+d})")
    t = [s(cur, None, i) for i in range(4)]
    dt = t[3] - s(prev, None, 3)
    lines.append(f"* 합계 : {t[0]}건 / {t[1]}건 / {t[2]}건 / {t[3]}건 ({dt:+d})")
    return "\n".join(lines)
 
