# -*- coding: utf-8 -*-
"""폴더블8 예약현황 텔레그램 보고 메시지 파서.
 
보고 양식:
■ ㅇㅇ점 폴더블8 예약현황 보고
 
ㅇ CRM 현황
- CRM 확보모수 : 0,000건
- 컨택완료 : 00/00/00건 (성공/보류/실패)
 
ㅇ 예약현황
 - 예약 계 : 00/00건 (당일/누적)
   ㄴ 폴드8 : 00/00건
   ㄴ 폴드8 와이드 : 00/00건
   ㄴ 플립8 : 00/00건
 - 모두의 행복 : 0건 (누적)
 - 소규모/법인 특판 : 0건 (누적)
 
ㅇ Quality (누적)
  - 120K : 00건
  - 110K : 00건
  - 2nd : 00건
  - 삼/디초 : 00건
  - 가전구독 : 00건
  - 제휴카드 : 00건
  - 라이프 : 00건
  - MIT : 00건 (M 기준)
"""
import json
import re
from pathlib import Path
 
BASE = Path(__file__).parent
 
 
def load_stores(path=None):
    with open(path or BASE / "stores.json", encoding="utf-8") as f:
        return json.load(f)
 
 
def _num(s):
    """'1,234건' -> 1234"""
    if s is None:
        return 0
    m = re.search(r"-?[\d,]+", str(s))
    return int(m.group().replace(",", "")) if m else 0
 
 
def _pair(text, label_pattern):
    """'- 예약 계 : 02/28건' -> (2, 28). 단일값이면 (0, 값)."""
    m = re.search(label_pattern + r"\s*[:：]\s*([\d,]+)\s*/\s*([\d,]+)", text)
    if m:
        return _num(m.group(1)), _num(m.group(2))
    m = re.search(label_pattern + r"\s*[:：]\s*([\d,]+)", text)
    if m:
        return 0, _num(m.group(1))
    return None
 
 
def _single(text, label_pattern):
    m = re.search(label_pattern + r"\s*[:：]\s*([\d,]+)", text)
    return _num(m.group(1)) if m else 0
 
 
def match_store(name_raw, stores_cfg):
    """보고 메시지의 매장명을 마스터의 정식 조직명으로 매핑."""
    name = re.sub(r"(점|매장)$", "", name_raw.strip())
    names = [s["조직"] for s in stores_cfg["매장"]]
    if name in names:
        return name
    alias = stores_cfg.get("매장명_별칭", {})
    if name in alias:
        return alias[name]
    # 부분일치 (유일할 때만)
    hits = [n for n in names if name in n or n in name]
    if len(hits) == 1:
        return hits[0]
    return None
 
 
def parse_report(text, stores_cfg):
    """보고 메시지 1건 파싱. 실패 시 None, 성공 시 dict 반환."""
    # 보고 판별: 제목 줄에 '예약현황' + 본문에 '예약 계' 항목이 있어야 함
    first = text.strip().split("\n")[0]
    if "예약현황" not in first or not re.search(r"예약\s*계\s*[:：]", text):
        return None
    m = re.search(r"■?\s*(.+?)\s*(?:폴더블8)?\s*예약현황\s*보고", first)
    if not m:
        return None
    store = match_store(m.group(1), stores_cfg)
    if not store:
        return {"error": f"매장명 인식 실패: '{m.group(1)}'", "원문제목": first}
 
    d = {"조직": store}
 
    # CRM
    d["CRM모수"] = _single(text, r"CRM\s*확보?모수")
    m = re.search(r"컨택\s*완료\s*[:：]\s*([\d,]+)\s*/\s*([\d,]+)\s*/\s*([\d,]+)", text)
    if m:
        d["컨택성공"], d["컨택보류"], d["컨택실패"] = (_num(m.group(i)) for i in (1, 2, 3))
    else:
        d["컨택성공"] = d["컨택보류"] = d["컨택실패"] = 0
    d["컨택완료"] = d["컨택성공"] + d["컨택보류"] + d["컨택실패"]
 
    # 예약현황 (당일/누적)
    total = _pair(text, r"예약\s*계")
    d["예약당일"], d["예약누적"] = total if total else (0, 0)
    for key, pat in [("폴드8", r"ㄴ?\s*폴드\s*8(?!\s*와이드)"),
                     ("와이드", r"(?:폴드\s*8\s*)?와이드"),
                     ("플립8", r"플립\s*8")]:
        p = _pair(text, pat)
        d[f"{key}당일"], d[f"{key}누적"] = p if p else (0, 0)
 
    d["모두의행복"] = _single(text, r"모두의\s*행복")
    d["소규모법인"] = _single(text, r"소규모\s*/?\s*법인\s*특판")
 
    # Quality
    for key, pat in [("120K", r"120\s*K"), ("110K", r"110\s*K"), ("2nd", r"2\s*nd"),
                     ("삼디초", r"삼\s*/?\s*디초"), ("가전구독", r"가전\s*구독"),
                     ("제휴카드", r"제휴\s*카드"), ("라이프", r"라이프"), ("MIT", r"MIT")]:
        d[key] = _single(text, pat)
 
    # 검증: 모델별 누적 합 = 예약누적
    model_sum = d["폴드8누적"] + d["와이드누적"] + d["플립8누적"]
    d["검증오류"] = []
    if model_sum != d["예약누적"]:
        d["검증오류"].append(f"모델별 합({model_sum}) ≠ 예약누적({d['예약누적']})")
    return d
 
 
def parse_all(messages, stores_cfg):
    """메시지 목록 → 매장별 최신 보고 dict. (같은 매장 중복 보고 시 마지막 것 사용)"""
    reports, errors = {}, []
    for msg in messages:
        r = parse_report(msg, stores_cfg)
        if r is None:
            continue
        if "error" in r:
            errors.append(r)
        else:
            reports[r["조직"]] = r
    return reports, errors
 
