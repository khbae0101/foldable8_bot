# -*- coding: utf-8 -*-
"""당일 실적 기반 시사점 생성 (매장 3줄 + 개인 3줄).

- 파이썬이 전일 스냅샷과 비교해 '변화'(순위 변동·연속 기록·마일스톤)를 계산하고,
  Claude는 그 사실만 근거로 문장을 작성 (숫자 오류 방지).
- 전일 멘트를 프롬프트에 넣어 같은 소재 반복을 금지.
- 실패 시 None 반환 — 본 공지는 영향 없음.
"""
import json
import os
from datetime import timedelta
from pathlib import Path

import requests

BIZ_RULES = (
    "업무 규칙(반드시 준수):\n"
    "- 120K는 110K보다 상위 요금제라 120K 유치율이 높을수록 좋음.\n"
    "- 삼/디초와 가전구독은 서로 배타적 상품이라 둘의 '합산' 유치율로 평가.\n"
    "- 2nd, 제휴카드, 라이프, MIT 등 연계판매는 모두 높을수록 좋음 "
    "(단순 예약만 받는 것보다 결합 유치가 우수한 영업).")


def _load(p):
    try:
        return json.loads(Path(p).read_text(encoding="utf-8"))
    except Exception:
        return None


def load_prev(data_dir, now, prefix, max_back=7):
    for i in range(1, max_back + 1):
        d = (now - timedelta(days=i)).strftime("%Y%m%d")
        obj = _load(Path(data_dir) / f"{prefix}_{d}.json")
        if obj:
            return obj
    return None


def make_snapshot(agg):
    """오늘 집계 → 비교용 스냅샷 (연속기록은 compute_facts에서 갱신)."""
    snap = {"지사누적": agg["지사계"]["예약누적"],
            "매장": {}, "개인": {}, "상권": {}}
    for s in agg["매장_정렬"]:
        if s.get("데이터있음"):
            snap["매장"][s["조직"]] = {
                "누적": s["예약누적"], "순위": s.get("순위"),
                "증분": s["증분"] or 0, "plus": 0, "zero": 0}
    for g, r in agg["상권"].items():
        snap["상권"][g] = {"누적": r["예약누적"], "순위": r.get("순위")}
    for p in agg.get("개인", []):
        key = f"{p['조직']}|{p['이름']}"
        snap["개인"][key] = {"실적": p["실적"], "목표": p["목표"],
                             "순위": p.get("순위")}
    return snap


def compute_facts(agg, snap, prev):
    """오늘 스냅샷 + 전일 스냅샷 → 변화·마일스톤 사실 목록. snap의 연속기록 갱신."""
    t = agg["지사계"]
    facts = {"기본": [], "매장변화": [], "개인변화": [], "마일스톤": []}

    facts["기본"].append(
        f"지사계: 목표 {t['목표']} / 누적 {t['예약누적']} / 당일증분 {t['증분']} "
        f"/ 달성률 {t['예약누적']/t['목표']*100:.1f}%")
    for g in agg["상권순서"]:
        r = agg["상권"][g]
        facts["기본"].append(
            f"{g}: 누적 {r['예약누적']} / 증분 {r['증분']} "
            f"/ 달성률 {r['예약누적']/r['목표']*100:.1f}% / 상권순위 {r.get('순위')}")
    if t["예약누적"]:
        combo = t["삼디초"] + t["가전구독"]
        facts["기본"].append(
            f"유치율(누적): 120K {t['120K']/t['예약누적']*100:.0f}%, "
            f"110K {t['110K']/t['예약누적']*100:.0f}%, "
            f"삼/디초+가전 합산 {combo/t['예약누적']*100:.0f}%, "
            f"2nd {t['2nd']/t['예약누적']*100:.0f}%, "
            f"제휴카드 {t['제휴카드']/t['예약누적']*100:.0f}%")
    miss = [s["조직"] for s in agg["매장_정렬"] if not s.get("데이터있음")]
    if miss:
        facts["기본"].append("미제출: " + ", ".join(miss))

    live = [s for s in agg["매장_정렬"] if s.get("데이터있음")]
    inc = sorted(live, key=lambda x: x["증분"] or 0, reverse=True)
    top_inc = [f"{s['조직']} +{s['증분']}(누적 {s['예약누적']})"
               for s in inc[:3] if (s["증분"] or 0) > 0]
    if top_inc:
        facts["매장변화"].append("당일 증분 상위: " + ", ".join(top_inc))

    pm = (prev or {}).get("매장", {})
    for s in live:
        n = s["조직"]
        cur = snap["매장"][n]
        pv = pm.get(n)
        d = cur["증분"]
        cur["plus"] = (pv["plus"] + 1 if pv and d > 0 else (1 if d > 0 else 0)) \
            if pv is not None else (1 if d > 0 else 0)
        cur["zero"] = (pv["zero"] + 1 if pv and d <= 0 else (1 if d <= 0 else 0)) \
            if pv is not None else (1 if d <= 0 else 0)
        if pv:
            jump = (pv.get("순위") or 99) - (cur.get("순위") or 99)
            if jump >= 3:
                facts["매장변화"].append(
                    f"{n} 순위 {pv['순위']}위→{cur['순위']}위 ({jump}계단 상승)")
            if pv.get("누적", 0) == 0 and cur["누적"] > 0:
                facts["마일스톤"].append(f"{n} 첫 예약 발생 ({cur['누적']}건)")
    streak_p = [f"{n} {v['plus']}일 연속 증분" for n, v in snap["매장"].items()
                if v["plus"] >= 2]
    streak_z = [f"{n} {v['zero']}일 연속 증분 0" for n, v in snap["매장"].items()
                if v["zero"] >= 2]
    if streak_p:
        facts["매장변화"].append("연속 상승: " + ", ".join(sorted(streak_p)[:4]))
    if streak_z:
        facts["매장변화"].append("연속 정체: " + ", ".join(sorted(streak_z)[:4]))

    # 개인 변화
    pp = (prev or {}).get("개인", {})
    persons = agg.get("개인", [])
    deltas = []
    for p in persons:
        key = f"{p['조직']}|{p['이름']}"
        pv = pp.get(key)
        d = p["실적"] - pv["실적"] if pv else p["실적"]
        if d > 0:
            deltas.append((d, p))
        if pv:
            jump = (pv.get("순위") or 999) - (p.get("순위") or 999)
            if jump >= 10:
                facts["개인변화"].append(
                    f"{p['조직']} {p['이름']} 개인순위 {pv['순위']}위→{p['순위']}위")
            if pv["실적"] < pv.get("목표", 10**9) and p["실적"] >= p["목표"] > 0:
                facts["마일스톤"].append(
                    f"{p['조직']} {p['이름']} 개인 목표({p['목표']}건) 달성!")
        elif p["목표"] and p["실적"] >= p["목표"]:
            facts["마일스톤"].append(
                f"{p['조직']} {p['이름']} 개인 목표({p['목표']}건) 달성!")
    deltas.sort(key=lambda x: -x[0])
    if deltas:
        facts["개인변화"].append("당일 개인 증분 상위: " + ", ".join(
            f"{p['조직']} {p['이름']} +{d}(누적 {p['실적']})" for d, p in deltas[:3]))
    zero_p = [p for p in persons if p["실적"] == 0]
    if zero_p:
        facts["개인변화"].append(
            f"누적 실적 0 인원 {len(zero_p)}명: " + ", ".join(
                f"{p['조직']} {p['이름']}" for p in zero_p[:6])
            + (" 외" if len(zero_p) > 6 else ""))
    ach = [p for p in persons if p["목표"] and p["실적"] >= p["목표"]]
    if ach:
        facts["개인변화"].append(f"개인 목표 달성 누적 {len(ach)}명")
    if persons:
        top = persons[0]
        facts["개인변화"].append(
            f"개인 1위: {top['조직']} {top['이름']} "
            f"({top['실적']}/{top['목표']}건, {top['실적']/top['목표']*100:.0f}%)"
            if top["목표"] else f"개인 1위: {top['조직']} {top['이름']}")
        pt = (prev or {}).get("개인1위")
        cur1 = f"{top['조직']}|{top['이름']}"
        if pt and pt != cur1:
            facts["마일스톤"].append(f"개인 1위 교체: {pt.split('|')[-1]} → {top['이름']}")
        snap["개인1위"] = cur1

    # 지사/매장 마일스톤
    if prev:
        if prev.get("지사누적", 0) // 100 < t["예약누적"] // 100:
            facts["마일스톤"].append(
                f"지사 누적 {t['예약누적']//100*100}건 돌파 (현재 {t['예약누적']}건)")
        p1 = min(pm, key=lambda n: pm[n].get("순위") or 99) if pm else None
        c_live = [s for s in live if s.get("순위") == 1]
        if p1 and c_live and c_live[0]["조직"] != p1:
            facts["마일스톤"].append(f"매장 1위 교체: {p1} → {c_live[0]['조직']}")
        for g, r in snap["상권"].items():
            pg = (prev.get("상권") or {}).get(g)
            if pg and pg.get("순위") and r["순위"] and r["순위"] < pg["순위"]:
                facts["마일스톤"].append(f"{g} 상권 순위 {pg['순위']}위→{r['순위']}위 역전")
        if not miss and (prev.get("미제출수", 1) or 0) > 0:
            facts["마일스톤"].append("전 매장 정시 제출 달성")
    snap["미제출수"] = len(miss)
    return facts


def build_prompt(facts, date_str, model_name, prev_insight):
    parts = []
    for k in ("기본", "매장변화", "개인변화", "마일스톤"):
        if facts[k]:
            parts.append(f"[{k}]\n" + "\n".join("- " + x for x in facts[k]))
    prev_block = f"\n\n어제 멘트(같은 매장·인물·관점 반복 금지):\n{prev_insight}" \
        if prev_insight else ""
    return (f"KT 강동소매지사 {model_name} 예약 캠페인 {date_str} 실적 데이터야.\n\n"
            + "\n\n".join(parts) + "\n\n" + BIZ_RULES + prev_block + "\n\n"
            "위 데이터에 있는 사실만 근거로 지사장 관점의 시사점을 작성해줘.\n"
            "형식(그대로):\n"
            "💬 오늘의 포인트\n\n[매장]\n• (3줄)\n\n[개인]\n• (3줄)\n\n"
            "규칙:\n"
            "- 매장 3줄, 개인 3줄. 각 줄은 한 문장, 전체 600자 이내.\n"
            "- 마일스톤이 있으면 우선 반영 (🎉 사용 가능).\n"
            "- 잘한 곳은 구체적으로 칭찬, 정체·부진은 매장명/이름 명시해 독려 "
            "(비난 아닌 코칭 톤).\n"
            "- 특이사항 없는 줄을 억지로 만들지 말고 데이터가 있는 소재만.\n"
            "- 숫자는 데이터에 있는 것만 사용, 추측·과장 금지, 존댓말.")


def generate(agg, stores_cfg, date_str, data_dir, now):
    """시사점 텍스트 생성 + 스냅샷/멘트 저장. 실패 시 (None, 이유)."""
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        return None, "API 키 없음"
    data_dir = Path(data_dir)
    prev = load_prev(data_dir, now, "snapshot")
    prev_insight = (load_prev(data_dir, now, "insight") or {}).get("text")

    snap = make_snapshot(agg)
    facts = compute_facts(agg, snap, prev)
    prompt = build_prompt(facts, date_str, stores_cfg["모델명"], prev_insight)
    try:
        r = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={"x-api-key": key, "anthropic-version": "2023-06-01",
                     "content-type": "application/json"},
            json={"model": "claude-sonnet-4-6", "max_tokens": 900,
                  "messages": [{"role": "user", "content": prompt}]},
            timeout=60)
        r.raise_for_status()
        text = "".join(b.get("text", "") for b in r.json()["content"]).strip()
    except Exception as e:
        return None, f"API 호출 실패: {e}"

    ymd = now.strftime("%Y%m%d")
    (data_dir / f"snapshot_{ymd}.json").write_text(
        json.dumps(snap, ensure_ascii=False, indent=1), encoding="utf-8")
    (data_dir / f"insight_{ymd}.json").write_text(
        json.dumps({"text": text}, ensure_ascii=False, indent=1), encoding="utf-8")
    return text, None
