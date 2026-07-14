# -*- coding: utf-8 -*-
"""주간 리포트 생성 (P1 지사/매장 + P2 개인 심화). 토요일 마감 후 호출.

- 데이터: data/close_*.json(일별 매장 누적), data/reports_*.json(개인 포함 상세)
- 차트: Pillow 자체 렌더 (추가 의존성 없음)
- 시사점: Claude 1회 호출로 [매장]/[개인] 주간 시사점 생성 (실패 시 생략)
"""
import json
import os
from datetime import date, datetime, timedelta
from pathlib import Path

import requests
from PIL import Image, ImageDraw, ImageFont

FB = "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"
FR = "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"
WEEKDAY = "월화수목금토일"
NAVY = (31, 78, 121)


def _F(p, s):
    return ImageFont.truetype(p, s)


def _load(p):
    try:
        return json.loads(Path(p).read_text(encoding="utf-8"))
    except Exception:
        return None


# ──────────────────────────── 데이터 수집 ────────────────────────────
def week_window(now, start):
    monday = now.date() - timedelta(days=now.weekday())
    week_no = (monday - start).days // 7 + 1
    return monday, week_no


def collect_week(data_dir, now, stores_cfg):
    data_dir = Path(data_dir)
    start = date.fromisoformat(stores_cfg["캠페인"]["시작"])
    end = date.fromisoformat(stores_cfg["캠페인"]["종료"])
    monday, week_no = week_window(now, start)

    # 이번 주 일별 (월~오늘) 지사 누적/증분
    days, prev_total = [], None
    prev_sat = monday - timedelta(days=2)  # 지난주 토
    pc = _load(data_dir / f"close_{prev_sat.strftime('%Y%m%d')}.json")
    if pc:
        prev_total = sum(pc.values())
    for i in range((now.date() - monday).days + 1):
        d = monday + timedelta(days=i)
        c = _load(data_dir / f"close_{d.strftime('%Y%m%d')}.json")
        if not c:
            continue
        total = sum(c.values())
        inc = total - prev_total if prev_total is not None else total
        days.append({"label": f"{d.month}/{d.day}({WEEKDAY[d.weekday()]})",
                     "inc": inc, "cum": total, "close": c})
        prev_total = total

    prev_week_close = pc or {}
    prev_week_reports = _load(
        data_dir / f"reports_{prev_sat.strftime('%Y%m%d')}.json") or {}

    biz_elapsed = sum(1 for i in range((now.date() - start).days + 1)
                      if (start + timedelta(days=i)).weekday() != 6)
    biz_remain = sum(1 for i in range(1, (end - now.date()).days + 1)
                     if (now.date() + timedelta(days=i)).weekday() != 6)
    return {"week_no": week_no, "monday": monday, "days": days,
            "prev_close": prev_week_close, "prev_reports": prev_week_reports,
            "biz_elapsed": max(1, biz_elapsed), "biz_remain": biz_remain,
            "end": end}


# ──────────────────────────── PIL 차트 ────────────────────────────
def combo_chart(days, W=1480, H=440):
    img = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(img)
    if not days:
        return img
    L, R, T, B = 70, 70, 60, 60
    pw, ph = W - L - R, H - T - B
    n = len(days)
    maxb = max(max(x["inc"] for x in days), 1) * 1.4
    maxc = max(x["cum"] for x in days) * 1.3
    bw = int(pw / n * 0.5)
    d.text((W // 2, 26), "일별 예약 증분 및 누적 추이", font=_F(FB, 26),
           fill=(30, 30, 30), anchor="mm")
    d.line([L, H - B, W - R, H - B], fill=(120, 120, 120), width=2)
    pts = []
    for i, x in enumerate(days):
        cx = L + int(pw * (i + 0.5) / n)
        bh = int(ph * x["inc"] / maxb)
        d.rectangle([cx - bw // 2, H - B - bh, cx + bw // 2, H - B],
                    fill=(111, 168, 220))
        d.text((cx, H - B - bh - 16), str(x["inc"]), font=_F(FB, 21), anchor="mm")
        d.text((cx, H - B + 22), x["label"], font=_F(FR, 19), anchor="mm")
        cy = H - B - int(ph * x["cum"] / maxc)
        pts.append((cx, cy))
    for a, b in zip(pts, pts[1:]):
        d.line([a, b], fill=(224, 102, 102), width=4)
    for (cx, cy), x in zip(pts, days):
        d.ellipse([cx - 6, cy - 6, cx + 6, cy + 6], fill=(224, 102, 102))
        d.text((cx, cy - 22), str(x["cum"]), font=_F(FB, 21),
               fill=(192, 57, 43), anchor="mm")
    return img


def hist_chart(counts, W=1480, H=400):
    bins = ["0%", "1~25%", "26~50%", "51~75%", "76~99%", "100%+"]
    colors = [(204, 65, 37), (230, 145, 56), (241, 194, 50),
              (147, 196, 125), (106, 168, 79), (56, 118, 29)]
    img = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(img)
    L, R, T, B = 60, 40, 60, 50
    pw, ph = W - L - R, H - T - B
    mx = max(max(counts), 1) * 1.3
    n = len(bins)
    bw = int(pw / n * 0.55)
    total = sum(counts)
    d.text((W // 2, 26), f"개인 목표 달성률 분포 ({total}명)", font=_F(FB, 26),
           fill=(30, 30, 30), anchor="mm")
    d.line([L, H - B, W - R, H - B], fill=(120, 120, 120), width=2)
    for i, (b, c, col) in enumerate(zip(bins, counts, colors)):
        cx = L + int(pw * (i + 0.5) / n)
        bh = int(ph * c / mx)
        d.rectangle([cx - bw // 2, H - B - bh, cx + bw // 2, H - B], fill=col)
        d.text((cx, H - B - bh - 16), f"{c}명", font=_F(FB, 21), anchor="mm")
        d.text((cx, H - B + 20), b, font=_F(FR, 19), anchor="mm")
    return img


# ──────────────────────────── 공용 레이아웃 ────────────────────────────
W = 1560


def _title(d, img, text, right):
    d.rectangle([28, 28, W - 28, 118], fill=(38, 38, 38))
    d.text((52, 73), text, font=_F(FB, 38), fill="white", anchor="lm")
    d.text((W - 52, 73), right, font=_F(FB, 30), fill=(255, 220, 90), anchor="rm")


def _sect(d, y, label):
    d.rectangle([40, y, 52, y + 34], fill=NAVY)
    d.text((64, y + 17), label, font=_F(FB, 26), fill=NAVY, anchor="lm")
    return y + 56


def _cards(d, y, cards):
    cw = (W - 56 - 3 * 20) // 4
    for i, (t1, t2, t3, col) in enumerate(cards):
        x = 28 + i * (cw + 20)
        d.rounded_rectangle([x, y, x + cw, y + 150], radius=12,
                            fill=(246, 248, 250), outline=(200, 205, 210), width=2)
        d.text((x + cw // 2, y + 34), t1, font=_F(FB, 22), fill=(90, 95, 100), anchor="mm")
        d.text((x + cw // 2, y + 78), t2, font=_F(FB, 40), fill=col, anchor="mm")
        d.text((x + cw // 2, y + 122), t3, font=_F(FR, 17), fill=(110, 115, 120), anchor="mm")
    return y + 180


def _tipbox(d, y, tips):
    h = 44 + len(tips) * 38
    d.rounded_rectangle([40, y, W - 40, y + h], radius=12, fill=(255, 251, 235),
                        outline=(220, 200, 140), width=2)
    for i, t in enumerate(tips):
        d.text((60, y + 30 + i * 38), t, font=_F(FR, 22), anchor="lm")
    return y + h + 20


def _wrap(text, limit=68):
    out = []
    for raw in text.split("\n"):
        raw = raw.strip()
        while len(raw) > limit:
            out.append(raw[:limit])
            raw = "   " + raw[limit:]
        if raw:
            out.append(raw)
    return out


# ──────────────────────────── P1: 지사/매장 ────────────────────────────
def render_p1(agg, wk, stores_cfg, out_path, tips):
    img = Image.new("RGB", (W, 3000), "white")
    d = ImageDraw.Draw(img)
    t = agg["지사계"]
    monday = wk["monday"]
    rng = f"{monday.month}/{monday.day}~{wk['days'][-1]['label'].split('(')[0] if wk['days'] else ''}"
    _title(d, img, f"■ {stores_cfg['지사명']} {stores_cfg['모델명']} 주간 리포트",
           f"{wk['week_no']}주차 ({rng})")

    week_inc = sum(x["inc"] for x in wk["days"])
    avg = t["예약누적"] / wk["biz_elapsed"]
    landing = int(t["예약누적"] + avg * wk["biz_remain"])
    need = (t["목표"] - t["예약누적"]) / wk["biz_remain"] if wk["biz_remain"] else 0
    y = _cards(d, 150, [
        ("누적 예약", f"{t['예약누적']:,}건",
         f"목표 {t['목표']:,}건 · 달성률 {t['예약누적']/t['목표']*100:.1f}%", NAVY),
        ("주간 증분", f"+{week_inc:,}건", f"영업일 평균 {avg:.1f}건", (56, 118, 29)),
        ("착지 예측", f"약 {landing:,}건",
         f"현 페이스 유지 시 (달성률 {landing/t['목표']*100:.0f}%)", (191, 54, 12)),
        ("필요 페이스", f"일 {need:.0f}건",
         f"잔여 영업일 {wk['biz_remain']}일 기준", (127, 96, 0))])

    y = _sect(d, y + 10, "주간 추이")
    ch = combo_chart(wk["days"])
    img.paste(ch, (40, y)); y += ch.height + 30

    y = _sect(d, y, "상권별 현황")
    rows = [("상권", "주간 증분", "누적", "달성률", "상권 순위")]
    for g in agg["상권순서"]:
        r = agg["상권"][g]
        winc = r["예약누적"] - sum(v for k, v in wk["prev_close"].items()
                                   if any(s["상권"] == g and s["조직"] == k
                                          for s in stores_cfg["매장"]))
        rows.append((g, f"+{winc}", f"{r['예약누적']:,}",
                     f"{r['예약누적']/r['목표']*100:.1f}%", str(r.get("순위", ""))))
    tw = W - 80; cw5 = tw // 5; rh = 52
    for r, row in enumerate(rows):
        ry = y + r * rh
        if r == 0:
            d.rectangle([40, ry, 40 + tw, ry + rh], fill=(217, 217, 217))
        for c, v in enumerate(row):
            d.text((40 + c * cw5 + cw5 // 2, ry + rh // 2), v,
                   font=_F(FB if r == 0 else FR, 22), anchor="mm")
        d.line([40, ry + rh, 40 + tw, ry + rh], fill=(180, 180, 180), width=2)
    d.rectangle([40, y, 40 + tw, y + rh * len(rows)], outline=(120, 120, 120), width=2)
    y += rh * len(rows) + 40

    # 매장 주간 증분 TOP/하위
    y = _sect(d, y, "주간 매장 TOP 5 · 하위 5 (주간 증분)")
    live = [s for s in agg["매장_정렬"] if s.get("데이터있음")]
    wdelta = [(s["조직"], s["예약누적"] - wk["prev_close"].get(s["조직"], 0))
              for s in live]
    wdelta.sort(key=lambda x: -x[1])
    half = (W - 100) // 2

    def minitab(x0, title, data, col):
        d.rectangle([x0, y, x0 + half, y + 44], fill=col)
        d.text((x0 + half // 2, y + 22), title, font=_F(FB, 21), fill="white", anchor="mm")
        for i, (n, v) in enumerate(data):
            ry = y + 44 + i * 44
            d.text((x0 + 18, ry + 22), f"{i+1}. {n}", font=_F(FR, 21), anchor="lm")
            d.text((x0 + half - 18, ry + 22), f"+{v}", font=_F(FB, 21), anchor="rm")
            d.line([x0, ry + 44, x0 + half, ry + 44], fill=(210, 210, 210), width=1)
        d.rectangle([x0, y, x0 + half, y + 44 + 44 * 5], outline=(150, 150, 150), width=2)
    minitab(40, "TOP 5", wdelta[:5], (56, 118, 29))
    minitab(60 + half, "하위 5", wdelta[::-1][:5], (176, 58, 46))
    y += 44 + 44 * 5 + 40

    y = _sect(d, y, "Quality 유치율 (누적)")
    g = t["예약누적"] or 1
    quals = [("120K", t["120K"]), ("110K", t["110K"]),
             ("삼/디초+가전 합산", t["삼디초"] + t["가전구독"]),
             ("2nd", t["2nd"]), ("제휴카드", t["제휴카드"]),
             ("라이프·MIT", t["라이프"] + t["MIT"])]
    qw = (W - 80 - 5 * 14) // 6
    for i, (n, v) in enumerate(quals):
        x = 40 + i * (qw + 14)
        d.rounded_rectangle([x, y, x + qw, y + 108], radius=10, fill=(246, 248, 250),
                            outline=(200, 205, 210), width=2)
        d.text((x + qw // 2, y + 30), n, font=_F(FB, 18), fill=(90, 95, 100), anchor="mm")
        d.text((x + qw // 2, y + 74), f"{v/g*100:.0f}%", font=_F(FB, 32),
               fill=NAVY, anchor="mm")
    y += 140

    if tips:
        y = _sect(d, y, "주간 시사점")
        y = _tipbox(d, y, tips)

    img = img.crop((0, 0, W, y + 30))
    img.save(out_path, optimize=True)
    return out_path


# ──────────────────────────── P2: 개인 심화 ────────────────────────────
def render_p2(agg, wk, stores_cfg, out_path, tips):
    persons = agg.get("개인", [])
    img = Image.new("RGB", (W, 3200), "white")
    d = ImageDraw.Draw(img)
    monday = wk["monday"]
    rng = f"{monday.month}/{monday.day}~{wk['days'][-1]['label'].split('(')[0] if wk['days'] else ''}"
    _title(d, img, f"■ {stores_cfg['지사명']} {stores_cfg['모델명']} 주간 리포트 — 개인 실적",
           f"{wk['week_no']}주차 ({rng})  P.2")

    prev_p = {}
    for org, rpt in wk["prev_reports"].items():
        for p in rpt.get("개인별", []):
            prev_p[f"{org}|{p['이름']}"] = p.get("실적", 0)
    wdel = []
    for p in persons:
        key = f"{p['조직']}|{p['이름']}"
        wdel.append((p, p["실적"] - prev_p.get(key, 0)))
    active = [x for x in wdel if x[1] > 0]
    ach = [p for p in persons if p["목표"] and p["실적"] >= p["목표"]]
    new_ach = [p for p in ach
               if prev_p.get(f"{p['조직']}|{p['이름']}", 0) < p["목표"]]
    week_inc = sum(v for _, v in wdel)
    top1 = max(wdel, key=lambda x: x[1])[0] if wdel else None
    y = _cards(d, 150, [
        ("참여 인원", f"{len(persons)}명", f"{len(stores_cfg['매장'])}개 매장", NAVY),
        ("주간 실적 발생", f"{len(active)}명",
         f"참여율 {len(active)/len(persons)*100:.0f}%" if persons else "-", (56, 118, 29)),
        ("개인 목표 달성", f"{len(ach)}명", f"신규 {len(new_ach)} · 누적 {len(ach)}", (127, 96, 0)),
        ("1인당 주간 평균", f"{week_inc/len(persons):.2f}건" if persons else "-",
         f"최고 {max(v for _, v in wdel)}건" if wdel else "-", (102, 61, 142))])

    # 분포
    y = _sect(d, y + 10, "개인 목표 달성률 분포")
    cnt = [0] * 6
    for p in persons:
        r = p["실적"] / p["목표"] * 100 if p["목표"] else 0
        idx = 0 if p["실적"] == 0 else 1 if r <= 25 else 2 if r <= 50 \
            else 3 if r <= 75 else 4 if r < 100 else 5
        cnt[idx] += 1
    ch = hist_chart(cnt)
    img.paste(ch, (40, y)); y += ch.height + 34

    # 주간 개인 TOP10
    y = _sect(d, y, "주간 개인 TOP 10 (주간 증분 기준)")
    top10 = sorted(wdel, key=lambda x: -x[1])[:10]
    rows = [("순위", "매장", "이름", "주간 증분", "누적", "목표 달성률")]
    for i, (p, v) in enumerate(top10, 1):
        rows.append((str(i), p["조직"], p["이름"], f"+{v}", str(p["실적"]),
                     f"{p['실적']/p['목표']*100:.0f}%" if p["목표"] else "-"))
    tw = W - 80; colw = [90, 300, 260, 240, 200, tw - 1090]; rh = 46
    for r, row in enumerate(rows):
        ry = y + r * rh
        if r == 0:
            d.rectangle([40, ry, 40 + tw, ry + rh], fill=(217, 217, 217))
        elif r <= 3:
            d.rectangle([40, ry, 40 + tw, ry + rh], fill=(234, 244, 234))
        xacc = 40
        for c, v in enumerate(row):
            d.text((xacc + colw[c] // 2, ry + rh // 2), v,
                   font=_F(FB if r == 0 else FR, 21), anchor="mm")
            xacc += colw[c]
        d.line([40, ry + rh, 40 + tw, ry + rh], fill=(200, 200, 200), width=1)
    d.rectangle([40, y, 40 + tw, y + rh * len(rows)], outline=(120, 120, 120), width=2)
    y += rh * len(rows) + 40

    # 개인 의존도
    dep = []
    for s in agg["매장_정렬"]:
        if not s.get("데이터있음") or s["예약누적"] < 5:
            continue
        sp = [p for p in persons if p["조직"] == s["조직"]]
        if not sp:
            continue
        mx = max(sp, key=lambda p: p["실적"])
        share = mx["실적"] / s["예약누적"]
        if share >= 0.5:
            dep.append((s["조직"], mx["이름"], mx["실적"], s["예약누적"], share))
    if dep:
        y = _sect(d, y, "개인 의존도 주의 매장 (1인 실적 비중 50%↑)")
        for n, nm, pv, sv, sh in sorted(dep, key=lambda x: -x[4])[:5]:
            d.text((60, y + 16),
                   f"• {n} : {nm} {pv}건 / 매장 {sv}건 ({sh*100:.0f}%) — 나머지 인원 활동 점검 필요",
                   font=_F(FR, 22), anchor="lm")
            y += 44
        y += 24

    # 주간 실적 0 인원
    zero = [p for p, v in wdel if v == 0]
    if zero:
        y = _sect(d, y, f"주간 실적 0 인원 ({len(zero)}명)")
        by_reg = {}
        for p in zero:
            by_reg.setdefault(p["상권"], []).append(f"{p['조직']} {p['이름']}")
        for reg in agg["상권순서"]:
            if reg not in by_reg:
                continue
            names = by_reg[reg]
            line = f"{reg}({len(names)}) : " + ", ".join(names[:8]) + \
                   (f" 외 {len(names)-8}명" if len(names) > 8 else "")
            for ln in _wrap("• " + line, 74):
                d.text((60, y + 14), ln, font=_F(FR, 21), anchor="lm"); y += 38
        y += 24

    if tips:
        y = _sect(d, y, "개인 시사점")
        y = _tipbox(d, y, tips)

    img = img.crop((0, 0, W, y + 30))
    img.save(out_path, optimize=True)
    return out_path


# ──────────────────────────── 시사점 (Claude) ────────────────────────────
def weekly_insight(agg, wk, stores_cfg):
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        return [], []
    t = agg["지사계"]
    week_inc = sum(x["inc"] for x in wk["days"])
    avg = t["예약누적"] / wk["biz_elapsed"]
    landing = int(t["예약누적"] + avg * wk["biz_remain"])
    need = (t["목표"] - t["예약누적"]) / wk["biz_remain"] if wk["biz_remain"] else 0
    live = [s for s in agg["매장_정렬"] if s.get("데이터있음")]
    wdelta = sorted(((s["조직"], s["예약누적"] - wk["prev_close"].get(s["조직"], 0))
                     for s in live), key=lambda x: -x[1])
    persons = agg.get("개인", [])
    prev_p = {}
    for org, rpt in wk["prev_reports"].items():
        for p in rpt.get("개인별", []):
            prev_p[f"{org}|{p['이름']}"] = p.get("실적", 0)
    pdel = sorted(((p, p["실적"] - prev_p.get(f"{p['조직']}|{p['이름']}", 0))
                   for p in persons), key=lambda x: -x[1])
    zero_n = sum(1 for _, v in pdel if v == 0)
    top10_share = sum(v for _, v in pdel[:10]) / week_inc * 100 if week_inc else 0
    g = t["예약누적"] or 1
    daypat = ", ".join(f"{x['label']} +{x['inc']}" for x in wk["days"])
    facts = (
        f"주간: 증분 {week_inc}, 누적 {t['예약누적']}/{t['목표']} "
        f"({t['예약누적']/t['목표']*100:.1f}%), 착지예측 {landing}"
        f"({landing/t['목표']*100:.0f}%), 필요페이스 일{need:.0f}건, "
        f"잔여영업일 {wk['biz_remain']}\n"
        f"일별: {daypat}\n"
        f"매장 주간 TOP: " + ", ".join(f"{n} +{v}" for n, v in wdelta[:3]) + "\n"
        f"매장 주간 하위: " + ", ".join(f"{n} +{v}" for n, v in wdelta[-3:]) + "\n"
        f"유치율: 120K {t['120K']/g*100:.0f}%, 삼/디초+가전 합산 "
        f"{(t['삼디초']+t['가전구독'])/g*100:.0f}%, 제휴카드 {t['제휴카드']/g*100:.0f}%\n"
        f"개인: 참여 {len(persons)}명, 주간실적0 {zero_n}명, "
        f"상위10명 실적비중 {top10_share:.0f}%, "
        f"개인 주간 TOP: " + ", ".join(
            f"{p['조직']} {p['이름']} +{v}" for p, v in pdel[:3]))
    prompt = (f"KT {stores_cfg['지사명']} {stores_cfg['모델명']} 예약 캠페인 "
              f"{wk['week_no']}주차 주간 데이터야.\n{facts}\n\n"
              "업무 규칙: 120K는 110K보다 상위 요금제(높을수록 좋음), "
              "삼/디초와 가전구독은 배타적이라 합산으로 평가, 연계판매는 높을수록 좋음.\n\n"
              "상위 직책자 보고용 주간 시사점을 작성해줘. JSON만 출력:\n"
              '{"매장": ["문장1","문장2","문장3"], "개인": ["문장1","문장2","문장3"]}\n'
              "- 각 문장 60자 이내, 데이터 근거만 사용, 존댓말, 페이스/착지 평가 포함")
    try:
        r = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={"x-api-key": key, "anthropic-version": "2023-06-01",
                     "content-type": "application/json"},
            json={"model": "claude-sonnet-4-6", "max_tokens": 800,
                  "messages": [{"role": "user", "content": prompt}]},
            timeout=60)
        r.raise_for_status()
        import re
        text = "".join(b.get("text", "") for b in r.json()["content"])
        m = re.search(r"\{.*\}", text, re.DOTALL)
        obj = json.loads(m.group())
        wrap = lambda lst: sum((_wrap("• " + s, 72) for s in lst[:4]), [])
        return wrap(obj.get("매장", [])), wrap(obj.get("개인", []))
    except Exception as e:
        print("주간 시사점 생략:", e)
        return [], []


# ──────────────────────────── 엔트리 ────────────────────────────
def generate(agg, stores_cfg, data_dir, now, base_dir):
    """토요일 마감 후 호출. (p1, p2, 텔레그램 캡션, 메일제목, 메일본문) 반환."""
    wk = collect_week(data_dir, now, stores_cfg)
    tips1, tips2 = weekly_insight(agg, wk, stores_cfg)
    ymd = now.strftime("%Y%m%d")
    p1 = Path(base_dir) / f"주간리포트_P1_{ymd}.png"
    p2 = Path(base_dir) / f"주간리포트_P2_{ymd}.png"
    render_p1(agg, wk, stores_cfg, p1, tips1)
    render_p2(agg, wk, stores_cfg, p2, tips2)

    t = agg["지사계"]
    week_inc = sum(x["inc"] for x in wk["days"])
    avg = t["예약누적"] / wk["biz_elapsed"]
    landing = int(t["예약누적"] + avg * wk["biz_remain"])
    monday = wk["monday"]
    rng = f"{monday.month}/{monday.day}~{now.month}/{now.day}"
    summary = (f"누적 {t['예약누적']:,}건 ({t['예약누적']/t['목표']*100:.1f}%) / "
               f"주간 +{week_inc:,}건 / 착지 예측 약 {landing:,}건")
    cap = f"📈 {stores_cfg['모델명']} 주간 리포트 — {wk['week_no']}주차 ({rng})\n{summary}"
    subject = (f"[{stores_cfg['지사명']}] {stores_cfg['모델명']} 주간 리포트 — "
               f"{wk['week_no']}주차 ({rng})")
    body = (f"📈 {stores_cfg['모델명']} 예약 캠페인 {wk['week_no']}주차 결과를 보고드립니다.\n"
            f"{summary}\n상세 내용은 아래 리포트 2매 참고 바랍니다.")
    return p1, p2, cap, subject, body
