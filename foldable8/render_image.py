# -*- coding: utf-8 -*-
"""예약현황 요약표 이미지 생성 (텔레그램 공지용). CRM 항목은 제외."""
from PIL import Image, ImageDraw, ImageFont
 
FONT_R = "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"
FONT_B = "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"
 
# (헤더그룹, 서브, 폭)
COLS = [
    ("상권", "", 92), ("코드", "", 96), ("조직", "", 142),
    ("목표", "", 60), ("예약", "", 60), ("증분", "", 56), ("달성률", "", 82), ("순위", "", 52),
    ("모델별", "울트라", 58), ("모델별", "와이드", 58), ("모델별", "플립8", 58),
    ("모두의\n행복", "", 64), ("소규모\n/법인", "", 64),
    ("120K", "건", 54), ("120K", "유치율", 60),
    ("110K", "건", 54), ("110K", "유치율", 60),
    ("2nd", "건", 54), ("2nd", "유치율", 60),
    ("삼/디초", "건", 54), ("삼/디초", "유치율", 60),
    ("가전구독", "건", 54), ("가전구독", "유치율", 60),
    ("제휴카드", "건", 54), ("제휴카드", "유치율", 60),
    ("라이프", "건", 54), ("라이프", "유치율", 60),
    ("MIT", "건", 54), ("MIT", "유치율", 60),
    ("전일\n마감", "", 64),
]
 
C_TITLE_BG = (63, 63, 63)
C_HEAD_BG = (217, 217, 217)
C_TOTAL_BG = (38, 38, 38)
C_REGION_BG = (228, 223, 236)
C_TARGET_BG = (226, 239, 218)
C_PREV_BG = (255, 244, 176)
C_GRID = (160, 160, 160)
C_MISS = (150, 150, 150)
C_HL = {"good": ((198, 239, 206), (0, 97, 0)),
        "bad": ((255, 199, 206), (156, 0, 6))}
 
 
def _fmt_pct(v, dec=1):
    return f"{v*100:.{dec}f}%" if v is not None else ""
 
 
def _text(draw, xy, s, font, fill=(0, 0, 0), anchor="mm"):
    draw.text(xy, str(s), font=font, fill=fill, anchor=anchor)
 
 
def render(rows, title, date_str, out_path, footnote=None, scale=2,
           cols=None, target_col=3, prev_col=True):
    cols = cols or COLS
    """rows: dict 리스트. type: total|region|store|store_missing"""
    F = lambda p, s: ImageFont.truetype(p, int(s * scale))
    f_title = F(FONT_B, 26)
    f_head = F(FONT_B, 18)
    f_sub = F(FONT_B, 15)
    f_cell = F(FONT_R, 19)
    f_cellb = F(FONT_B, 19)
 
    pad = int(14 * scale)
    row_h = int(42 * scale)
    title_h = int(56 * scale)
    head_h = int(62 * scale)
    widths = [int(w * scale) for *_ , w in cols]
    W = sum(widths) + pad * 2
    n_rows = len(rows)
    foot_h = int(40 * scale) if footnote else int(10 * scale)
    H = pad + title_h + head_h + n_rows * row_h + foot_h + pad
 
    img = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(img)
 
    # 제목 바
    d.rectangle([pad, pad, W - pad, pad + title_h], fill=C_TITLE_BG)
    _text(d, (pad + int(12 * scale), pad + title_h // 2), title, f_title,
          fill="white", anchor="lm")
    _text(d, (W - pad - int(12 * scale), pad + title_h // 2), date_str, f_title,
          fill=(255, 220, 90), anchor="rm")
 
    xs = [pad]
    for w in widths:
        xs.append(xs[-1] + w)
    y0 = pad + title_h
 
    # 헤더 (그룹 병합)
    d.rectangle([pad, y0, W - pad, y0 + head_h], fill=C_HEAD_BG)
    i = 0
    while i < len(cols):
        g = cols[i][0]
        j = i
        while j < len(cols) and cols[j][0] == g:
            j += 1
        x1, x2 = xs[i], xs[j]
        has_sub = any(cols[k][1] for k in range(i, j))
        if has_sub:
            ymid = y0 + head_h // 2
            _text(d, ((x1 + x2) // 2, y0 + head_h // 4), g.replace("\n", " "), f_head)
            d.line([x1, ymid, x2, ymid], fill=C_GRID, width=scale)
            for k in range(i, j):
                _text(d, ((xs[k] + xs[k + 1]) // 2, y0 + 3 * head_h // 4),
                      cols[k][1], f_sub)
                if k > i:
                    d.line([xs[k], ymid, xs[k], y0 + head_h], fill=C_GRID, width=scale)
        else:
            _text(d, ((x1 + x2) // 2, y0 + head_h // 2), g, f_head)
        d.line([x2, y0, x2, y0 + head_h], fill=C_GRID, width=scale)
        i = j
    # 전일마감 헤더 노란 표시
    if prev_col:
        d.rectangle([xs[-2], y0, xs[-1], y0 + head_h], fill=C_PREV_BG, outline=C_GRID)
        _text(d, ((xs[-2] + xs[-1]) // 2, y0 + head_h // 2), "전일\n마감", f_sub)
 
    # 데이터 행
    y = y0 + head_h
    for r in rows:
        typ = r.get("type", "store")
        bg = {"total": C_TOTAL_BG, "region": C_REGION_BG}.get(typ)
        if bg:
            d.rectangle([pad, y, W - pad, y + row_h], fill=bg)
        fg = "white" if typ == "total" else (0, 0, 0)
        font = f_cellb if typ in ("total", "region") else f_cell
 
        vals = r["cells"]  # COLS 순서와 동일한 리스트
        hl = r.get("hl", {})
        for k, v in enumerate(vals):
            cx = (xs[k] + xs[k + 1]) // 2
            cy = y + row_h // 2
            cell_fg = fg
            if typ == "store":
                if k == target_col:  # 목표 열 배경
                    d.rectangle([xs[target_col], y, xs[target_col + 1], y + row_h],
                                fill=C_TARGET_BG)
                if prev_col and k == len(vals) - 1:
                    d.rectangle([xs[-2], y, xs[-1], y + row_h], fill=C_PREV_BG)
                if k in hl:
                    bgc, fgc = C_HL[hl[k]]
                    d.rectangle([xs[k], y, xs[k + 1], y + row_h], fill=bgc)
                    cell_fg = fgc
            if typ == "store_missing":
                cell_fg = C_MISS
            if v is None or v == "":
                continue
            _text(d, (cx, cy), v, font, fill=cell_fg)
        d.line([pad, y + row_h, W - pad, y + row_h], fill=C_GRID, width=scale)
        y += row_h
 
    # 세로 그리드
    for x in xs:
        d.line([x, y0, x, y], fill=C_GRID, width=scale)
    d.rectangle([pad, y0, W - pad, y], outline=(60, 60, 60), width=scale)
 
    if footnote:
        _text(d, (pad + int(2 * scale), y + int(12 * scale)), footnote,
              F(FONT_B, 18), fill=(200, 30, 30), anchor="lm")
 
    # 텔레그램 sendPhoto 제한(가로+세로 10000px) 대비 자동 축소
    if img.width + img.height > 9800:
        f = 9800 / (img.width + img.height)
        img = img.resize((int(img.width * f), int(img.height * f)),
                         Image.LANCZOS)
    img.save(out_path, optimize=True)
    return out_path
 
 
def build_rows(agg):
    """집계 결과(build_excel.aggregate 산출물) → 이미지 행 데이터."""
    from build_excel import QUAL_KEYS
 
    def cells(r, name_cols):
        g = r["예약누적"]
        def rate(k, dec=0):
            return _fmt_pct(r[k] / g, dec) if g else ""
        return name_cols + [
            f"{r['목표']:,}", f"{r['예약누적']:,}",
            (f"+{r['증분']}" if r["증분"] > 0 else str(r["증분"])) if r["증분"] is not None else "",
            _fmt_pct(r["예약누적"] / r["목표"]) if r["목표"] else "", r.get("순위", ""),
            r["울트라누적"], r["와이드누적"], r["플립8누적"],
            r["모두의행복"], r["소규모법인"],
            r["120K"], rate("120K"), r["110K"], rate("110K"),
            r["2nd"], rate("2nd"), r["삼디초"], rate("삼디초"),
            r["가전구독"], rate("가전구독"), r["제휴카드"], rate("제휴카드"),
            r["라이프"], rate("라이프"), r["MIT"], rate("MIT"),
            f"{r['전일마감']:,}" if r.get("전일마감") is not None else "",
        ]
 
    rows = [{"type": "total", "cells": cells(agg["지사계"], ["", "", "지사 계"])}]
    for reg in agg["상권순서"]:
        rows.append({"type": "region", "cells": cells(agg["상권"][reg], ["", "", reg])})
    for s in agg["매장_정렬"]:
        if not s.get("데이터있음"):
            continue
        name = s["조직"] + ("＊" if s.get("이월") else "")
        hl = {}
        if s.get("달성률HL"):
            hl[6] = hl[7] = s["달성률HL"]
        for idx, k in enumerate(QUAL_KEYS):
            h = s.get("유치율HL", {}).get(k)
            if h:
                hl[14 + 2 * idx] = h
        rows.append({"type": "store", "hl": hl,
                     "cells": cells(s, [s["상권"], s["코드"], name])})
    for s in agg["매장_정렬"]:
        if s.get("데이터있음"):
            continue
        c = [s["상권"], s["코드"], s["조직"], f"{s['목표']:,}", "미제출"] + [""] * 25
        rows.append({"type": "store_missing", "cells": c})
    return rows
 
 
def build_footnote(agg):
    """미제출/이월 매장 안내 문구."""
    carried = [s["조직"] for s in agg["매장_정렬"] if s.get("이월")]
    nodata = [s["조직"] for s in agg["매장_정렬"] if not s.get("데이터있음")]
    parts = []
    if carried:
        parts.append(f"＊ 미제출 매장(전일값 이월, {len(carried)}개) : {', '.join(carried)}")
    if nodata:
        parts.append(f"미제출({len(nodata)}개) : {', '.join(nodata)}")
    return "   /   ".join(parts) if parts else None
 
 
# ── 개인별 랭킹 이미지 ───────────────────────────────────────
PCOLS = [
    ("순위", "", 56), ("상권", "", 92), ("매장", "", 142), ("이름", "", 100),
    ("목표", "", 60), ("실적", "", 60), ("달성률", "", 82),
    ("모두의\n행복", "", 64), ("소규모\n/법인", "", 64),
    ("120K", "건", 54), ("120K", "유치율", 60),
    ("110K", "건", 54), ("110K", "유치율", 60),
    ("2nd", "건", 54), ("2nd", "유치율", 60),
    ("삼/디초", "건", 54), ("삼/디초", "유치율", 60),
    ("가전구독", "건", 54), ("가전구독", "유치율", 60),
    ("제휴카드", "건", 54), ("제휴카드", "유치율", 60),
    ("라이프", "건", 54), ("라이프", "유치율", 60),
    ("MIT", "건", 54), ("MIT", "유치율", 60),
]
P_QUAL = ["120K", "110K", "2nd", "삼디초", "가전구독", "제휴카드", "라이프", "MIT"]
 
 
def build_person_rows(agg):
    def cells(p, lead):
        g = p["실적"]
        def rate(k):
            return _fmt_pct(p[k] / g, 0) if g else ""
        out = lead + [f"{p['목표']:,}", f"{p['실적']:,}",
                      _fmt_pct(p["실적"] / p["목표"]) if p["목표"] else "",
                      p["모행"] if "모행" in p else p.get("모행", 0), p.get("특판", 0)]
        for k in P_QUAL:
            out += [p[k], rate(k)]
        return out
 
    t = agg["개인지사계"]
    rows = [{"type": "total",
             "cells": cells(t, ["", "", "", "지사 계"])}]
    for p in agg["개인"]:
        name = p["이름"] + ("＊" if p.get("이월") else "")
        hl = {}
        if p.get("달성률HL"):
            hl[0] = hl[6] = p["달성률HL"]
        for i, k in enumerate(P_QUAL):
            h = p.get("유치율HL", {}).get(k)
            if h:
                hl[10 + 2 * i] = h
        rows.append({"type": "store", "hl": hl,
                     "cells": cells(p, [p["순위"], p["상권"], p["조직"], name])})
    return rows
 
 
def render_persons(agg, title, date_str, out_path, scale=2):
    """전체 개인 1장 (분할 이미지 대신 필요 시 사용)."""
    foot = None
    miss = agg.get("개인미제출매장")
    if miss:
        foot = f"※ 개인별 미제출 매장({len(miss)}개) : " + ", ".join(miss)
    return render(build_person_rows(agg), title, date_str, out_path,
                  footnote=foot, scale=scale, cols=PCOLS,
                  target_col=4, prev_col=False)
 
 
def render_persons_split(agg, base, date_str, out_dir, prefix, scale=2, top_n=10):
    """개인별 분할 이미지: ①지사 상/하위 TOP N 1장 ②상권별 각 1장.
    반환: [(경로, 캡션제목), ...]"""
    from pathlib import Path
    out_dir = Path(out_dir)
    rows_all = build_person_rows(agg)
    total_row, person_rows = rows_all[0], rows_all[1:]
 
    def section(label):
        return {"type": "region", "cells": [label] + [""] * (len(PCOLS) - 1)}
 
    outs = []
    miss = agg.get("개인미제출매장")
    foot = (f"※ 개인별 미제출 매장({len(miss)}개) : " + ", ".join(miss)) if miss else None
 
    # ① 상/하위 TOP N (인원이 2N 이하이면 전체 1장)
    if len(person_rows) <= top_n * 2:
        rows1 = [total_row, section("전체 순위")] + person_rows
        t1 = f"{base} 개인별 전체 순위"
    else:
        rows1 = [total_row, section(f"상위 TOP {top_n}")] + person_rows[:top_n] +                 [section(f"하위 TOP {top_n}")] + person_rows[-top_n:]
        t1 = f"{base} 개인별 TOP{top_n}"
    p = out_dir / f"{prefix}_개인_TOP.png"
    render(rows1, f"■ {t1}", date_str, p, footnote=foot,
           scale=scale, cols=PCOLS, target_col=4, prev_col=False)
    outs.append((p, t1))
 
    # ② 상권별 (지사 전체 순위 번호 유지)
    for reg in agg["상권순서"]:
        idxs = [i for i, x in enumerate(agg["개인"]) if x["상권"] == reg]
        if not idxs:
            continue
        rows = [total_row] + [person_rows[i] for i in idxs]
        t = f"{base} 개인별 [{reg}]"
        pth = out_dir / f"{prefix}_개인_{reg.replace('/', '')}.png"
        render(rows, f"■ {t}", date_str, pth,
               scale=scale, cols=PCOLS, target_col=4, prev_col=False)
        outs.append((pth, t))
    return outs
 
