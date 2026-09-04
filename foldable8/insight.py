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

# ── 날짜별 마무리 독려 멘트 (출시 8/4, 잔여 영업일 = 오늘 제외 일요일 뺀 값) ──
CLOSING = {
    # 9/5(토) ~ 9/10(수) : 사전 준비 기간
    "20260905": "🚀 아이폰18 예약 대장정의 첫날입니다\n"
                "오늘부터 9/17까지, 13일간의 여정을 함께 시작합니다. "
                "첫 단추가 중요합니다. 내일도 좋은 흐름 이어가요!",
    "20260908": "💪 D-9, 한 주의 시작입니다\n"
                "공식 사전예약(9/11)까지 사흘 남았습니다. "
                "지금 확보한 대기 고객이 개시일의 실적이 됩니다. 오늘도 고생하셨습니다.",
    "20260910": "⚡ 내일이면 공식 사전예약 개시입니다\n"
                "그동안 쌓아온 대기 고객, 내일 한 번에 접수될 수 있도록 "
                "오늘 밤 최종 점검 부탁드립니다. 내일 뵙겠습니다!",
    # 9/11(목) ~ 9/17(수) : 공식 사전예약
    "20260911": "🔥 공식 사전예약 첫날, 정말 고생 많으셨습니다\n"
                "눈코 뜰 새 없이 바쁜 하루였을 겁니다. "
                "오늘의 기세, 남은 엿새 동안 이어가 봅시다.",
    "20260912": "👏 사전예약 이틀째, 흐름이 잡혀갑니다\n"
                "내일은 주말 첫날입니다. 오늘 상담만 하고 가신 고객,"
                " 내일 방문 약속으로 연결해 주세요.",
    "20260913": "🌟 주말 첫날 수고하셨습니다\n"
                "내방 고객이 몰리는 시기입니다. "
                "내일도 한 분 한 분 놓치지 않도록 함께 힘내요.",
    "20260914": "🌈 주말 마무리, 정말 애쓰셨습니다\n"
                "이제 사흘 남았습니다. 남은 대기 고객 리스트,"
                " 내일부터 최종 컨택 부탁드립니다.",
    "20260915": "💫 D-2, 마지막 스퍼트 구간입니다\n"
                "미결정 고객에게 오늘 연락 한 번 더. "
                "작은 한 건이 순위를 바꿉니다.",
    "20260916": "❤️‍🔥 내일이면 예약 마감입니다\n"
                "오늘 하루도 끝까지 붙잡아 주셔서 감사합니다. "
                "마지막 하루, 후회 없이 달려봅시다!",
    "20260917": "🎉 예약 대장정이 마무리됐습니다\n"
                "13일간 정말 고생 많으셨습니다. 이른 아침부터 늦은 저녁까지, "
                "여러분의 하루하루가 모여 오늘의 강동소매를 만들었습니다.\n"
                "내일은 그 결실을 만나는 날입니다. 마지막까지, 우리답게. 🎊",
}


def closing_message(now):
    """오늘 날짜에 해당하는 마무리 멘트 (없으면 None)."""
    return CLOSING.get(now.strftime("%Y%m%d"))


BIZ_RULES = (
    "업무 규칙(반드시 준수):\n"
    "- 120K는 상위 요금제라 유치율이 높을수록 좋음.\n"
    "- 삼/디/가전은 삼성케어·디바이스초기화·가전구독 합산 항목.\n"
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


def make_snapshot(agg, now=None, cfg=None):
    """오늘 집계 → 비교용 스냅샷 (연속기록은 compute_facts에서 갱신)."""
    snap = {"지사누적": agg["지사계"]["예약누적"],
            "매장": {}, "개인": {}, "상권": {}}
    # 캠페인 경과일수 (달성 예상 계산용)
    if now and cfg:
        try:
            from datetime import date
            st = date.fromisoformat(cfg["캠페인"]["시작"])
            snap["경과일수"] = max((now.date() - st).days + 1, 1)
        except Exception:
            snap["경과일수"] = 1
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
    if prev and prev.get("무실적인원") is not None:
        snap["무실적인원_전일"] = prev["무실적인원"]
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
        combo = t["삼디가전"]
        facts["기본"].append(
            f"유치율(누적): 120K {t['120K']/t['예약누적']*100:.0f}%, "
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
            "💬 오늘의 포인트\n\n[매장]\n• (최대 5줄)\n\n[개인]\n• (최대 5줄)\n\n"
            "규칙:\n"
            "- 매장·개인 각 최대 5줄. 각 줄은 한 문장 40자 이내.\n"
            "- 짧고 담백하게. 수식어·부연 설명 없이 핵심만.\n"
            "- 소재가 부족하면 줄 수를 줄여도 됨 (억지로 5줄 채우지 말 것).\n"
            "- 마일스톤이 있으면 우선 반영 (🎉 사용 가능).\n"
            "- 잘한 곳은 구체적으로 칭찬, 정체·부진은 매장명/이름 명시해 독려 "
            "(비난 아닌 코칭 톤).\n"
            "- 특이사항 없는 줄을 억지로 만들지 말고 데이터가 있는 소재만.\n"
            "- 숫자는 데이터에 있는 것만 사용, 추측·과장 금지, 존댓말.")


def generate(agg, stores_cfg, date_str, data_dir, now):
    """시사점 텍스트 생성 + 스냅샷/멘트 저장. 실패 시 (None, 이유)."""
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        return None, None, "API 키 없음"
    data_dir = Path(data_dir)
    prev = load_prev(data_dir, now, "snapshot")
    prev_insight = (load_prev(data_dir, now, "insight") or {}).get("text")

    snap = make_snapshot(agg, now, stores_cfg)
    facts = compute_facts(agg, snap, prev)
    prompt = build_prompt(facts, date_str, stores_cfg["모델명"], prev_insight)
    try:
        r = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={"x-api-key": key, "anthropic-version": "2023-06-01",
                     "content-type": "application/json"},
            json={"model": "claude-sonnet-4-6", "max_tokens": 1100,
                  "messages": [{"role": "user", "content": prompt}]},
            timeout=60)
        r.raise_for_status()
        text = "".join(b.get("text", "") for b in r.json()["content"]).strip()
    except Exception as e:
        return None, None, f"API 호출 실패: {e}"

    closing = closing_message(now)
    full = text + ("\n\n─────────────\n" + closing if closing else "")

    ymd = now.strftime("%Y%m%d")
    (data_dir / f"snapshot_{ymd}.json").write_text(
        json.dumps(snap, ensure_ascii=False, indent=1), encoding="utf-8")
    (data_dir / f"insight_{ymd}.json").write_text(
        json.dumps({"text": text}, ensure_ascii=False, indent=1), encoding="utf-8")
    return text, closing, None


# ─────────────────────────── 체크포인트 ───────────────────────────
LINK_KEYS = ["120K", "2nd", "삼디가전", "제휴카드", "라이프", "MIT"]


def build_checkpoint(agg, snap, remain_days, date_label):
    """규칙 기반 경보 블록. 시사점과 별개로 매일 발송."""
    t = agg["지사계"]
    live = [s for s in agg["매장_정렬"] if s.get("데이터있음")]
    days = max(snap.get("경과일수", 1), 1)

    def proj(s):
        pace = max(s["증분"] or 0, s["예약누적"] / days)
        return (s["예약누적"] + pace * remain_days) / s["목표"] * 100 if s["목표"] else 0

    L = [f"⚠ 오늘의 체크포인트 ({date_label} 기준)", ""]

    # 1) 2일 연속 예약 0건
    z = [n for n, v in snap["매장"].items() if v.get("zero", 0) >= 2]
    L += ["🔴 2일 연속 예약 0건", "   " + (", ".join(sorted(z)) if z else "없음"), ""]

    # 2) 달성 60% 미달 예상
    under = sorted(((s["조직"], proj(s)) for s in live if proj(s) < 60),
                   key=lambda x: x[1])
    if under:
        head = ", ".join(f"{n}({r:.0f}%)" for n, r in under[:5])
        more = f"  외 {len(under)-5}개점" if len(under) > 5 else ""
        L += ["🔴 달성 60% 미달 예상", f"   {head}{more}", ""]

    # 3) 연계 0건 매장수 ㅣ 항목별 1위
    L.append("🔴 연계 0건 매장수 ㅣ 항목별 1위")
    for k in LINK_KEYS:
        zc = sum(1 for s in live if s.get(k, 0) == 0)
        cand = [s for s in live if s["예약누적"] > 0]
        if cand:
            best = max(cand, key=lambda s: s[k] / s["예약누적"])
            br = best[k] / best["예약누적"] * 100
            L.append(f"   {k:8s}{zc:2d}개점  ㅣ {best['조직']} {br:.0f}%")
    L.append("")

    # 4) 무실적 인원
    persons = agg.get("개인", [])
    nz = sum(1 for p in persons if p["실적"] == 0)
    pz = snap.get("무실적인원_전일")
    tail = f" (전일 {pz}명)" if pz is not None else ""
    L += [f"🟡 무실적 인원 {nz}명{tail}", ""]

    # 5) 1인 의존 50%↑
    dep = []
    for s in live:
        if s["예약누적"] < 5:
            continue
        ps = [p for p in persons if p.get("조직") == s["조직"]]
        if not ps:
            continue
        top = max(ps, key=lambda p: p["실적"])
        r = top["실적"] / s["예약누적"] * 100
        if r >= 50:
            dep.append((s["조직"], r))
    dep.sort(key=lambda x: -x[1])
    if dep:
        L += ["🟡 1인 의존 50%↑",
              "   " + ", ".join(f"{n}({r:.0f}%)" for n, r in dep[:3]), ""]

    # 6) 달성 예상 100%↑
    over = sorted(((s["조직"], proj(s)) for s in live if proj(s) >= 100),
                  key=lambda x: -x[1])
    if over:
        L += ["🟢 달성 예상 (100%↑)",
              "   " + ", ".join(f"{n}({r:.0f}%)" for n, r in over[:4])]

    snap["무실적인원"] = nz
    return "\n".join(L).rstrip()
