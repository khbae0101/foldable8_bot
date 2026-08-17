# -*- coding: utf-8 -*-
"""미개통 현황 + 부족재고 보고 파서.
 
자동 보정 규칙 (매장 보고 오류가 잦아 파서 단에서 흡수):
  1) 모델별 유형칸이 비고 '계'만 있는 경우  →  기변으로 배정
     예) 폴드8 : 0 / 0 / 0 / 4   →  0 / 0 / 4 / 4
  2) 모델별 010+MNP+기변 ≠ 계        →  유형 합을 신뢰, 계를 재계산
  3) '합계' 줄이 0이거나 모델합과 불일치 →  모델합으로 재계산 (합계 줄은 참고만)
  4) 부족재고 수량 공란/누락          →  0 처리
  5) '모두 개통 완료' 류 문구          →  전 항목 0 으로 인식
보정이 일어나면 fixes 리스트에 기록해 공지에 함께 안내한다.
"""
import json
import re
from pathlib import Path
 
MODELS = ["울트라", "폴드8", "플립8"]      # 파싱은 3종, 표기는 collect 쪽에서 결정
TYPES = ["010", "MNP", "기변"]
LACK_COLORS = ["블랙", "크림", "라벤더"]
 
# 모델 표기 흔들림 흡수
MODEL_ALIAS = {
    "울트라": "울트라", "폴드8 울트라": "울트라", "폴드8울트라": "울트라",
    "폴드8": "폴드8", "폴드": "폴드8", "폴드 8": "폴드8",
    "플립8": "플립8", "플립": "플립8", "플립 8": "플립8",
}
DONE_PAT = re.compile(r"(모두|전부|전량)\s*개통\s*(완료|됨|끝)|개통\s*완료")
 
 
def load_stores(path=None):
    p = Path(path or Path(__file__).parent / "stores.json")
    return json.loads(p.read_text(encoding="utf-8"))
 
 
def _match_store(text, cfg):
    """제목/본문에서 매장명 추출. 정식명 → 별칭 순으로 최장일치."""
    names = [s["조직"] for s in cfg["매장"]]
    alias = cfg.get("매장명_별칭", {})
    head = text.split("\n")[0]
    for scope in (head, text):
        for n in sorted(names, key=len, reverse=True):
            if n in scope:
                return n
        for a in sorted(alias, key=len, reverse=True):
            if a in scope:
                return alias[a]
    return None
 
 
def _nums(s):
    return [int(x) for x in re.findall(r"\d+", s)]
 
 
def parse_report(text, cfg):
    """단일 매장 보고 → dict. 대상 아니면 None."""
    if "미개통" not in text and not DONE_PAT.search(text):
        return None
    store = _match_store(text, cfg)
    if not store:
        return None
 
    res = {m: [0, 0, 0, 0] for m in MODELS}
    lack = {c: 0 for c in LACK_COLORS}
    fixes = []
 
    # '모두 개통 완료' 형태 → 전부 0
    if DONE_PAT.search(text) and "미개통 건" not in text:
        return {"매장": store, **{m: [0, 0, 0, 0] for m in MODELS},
                "부족": lack, "fixes": ["개통 완료 보고 → 0건 처리"]}
 
    # 모델별 라인
    for line in text.split("\n"):
        t = line.strip().lstrip("*·-ㄴ•").strip()
        m = re.match(r"^(울트라|폴드8\s*울트라|폴드8|폴드|플립8|플립)\s*[:：]\s*(.+)$", t)
        if not m:
            continue
        key = MODEL_ALIAS.get(re.sub(r"\s+", " ", m.group(1)).strip())
        if not key:
            continue
        v = _nums(m.group(2))
        if len(v) < 4:
            v += [0] * (4 - len(v))
        a, b, c, tot = v[0], v[1], v[2], v[3]
        if a + b + c == 0 and tot > 0:              # 규칙 1
            c = tot
            fixes.append(f"{key} 유형 미기재 → 기변 {tot}건 배정")
        elif a + b + c != tot:                       # 규칙 2
            if tot != a + b + c:
                fixes.append(f"{key} 계 {tot} → {a+b+c} 재계산")
            tot = a + b + c
        res[key] = [a, b, c, a + b + c]
 
    # 부족재고 라인
    sec = text.split("부족재고")[-1] if "부족재고" in text else ""
    for line in sec.split("\n"):
        t = line.strip().lstrip("*·-ㄴ•").strip()
        m = re.match(r"^(?:폴드8|플립8|울트라)?\s*(블랙|크림|라벤더|퍼플|핑크)\s*[:：]\s*(.*)$", t)
        if not m:
            continue
        color = m.group(1)
        if color not in LACK_COLORS:
            continue
        n = _nums(m.group(2))
        if not n:
            lack[color] = 0
            fixes.append(f"부족재고 {color} 미기재 → 0 처리")
        else:
            lack[color] = n[0]
 
    return {"매장": store, **res, "부족": lack, "fixes": fixes}
 
 
def parse_all(messages, cfg):
    """여러 메시지 → {매장: dict}. 같은 매장 재보고 시 뒤엣것으로 갱신."""
    out = {}
    for msg in messages:
        # 한 메시지에 여러 매장이 붙어 온 경우 '■' 기준 분리
        blocks = re.split(r"(?=■)", msg)
        for b in blocks:
            if not b.strip():
                continue
            r = parse_report(b, cfg)
            if r:
                out[r["매장"]] = r
    return out
 
 
def totals(rec, models):
    """매장 1곳의 유형별/계 합계."""
    return [sum(rec[m][i] for m in models) for i in range(4)]
 
