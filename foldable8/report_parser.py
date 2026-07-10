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
 
    # 모델별: 'ㄴ' 줄 순서 기준 집계 (1번째=폴드8 울트라, 2번째=와이드, 3번째=플립8)
    # → 라벨이 구양식('폴드8')이든 신양식('폴드8 울트라')이든 순서로 인식
    model_keys = ["울트라", "와이드", "플립8"]
    sub_lines = re.findall(r"^\s*ㄴ\s*(.+)$", text, re.MULTILINE)[:3]
    for i, key in enumerate(model_keys):
        if i < len(sub_lines):
            p = _pair(sub_lines[i], r"")
            d[f"{key}당일"], d[f"{key}누적"] = p if p else (0, 0)
        else:
            d[f"{key}당일"], d[f"{key}누적"] = 0, 0
 
    d["모두의행복"] = _single(text, r"모두의\s*행복")
    d["소규모법인"] = _single(text, r"소규모\s*/?\s*법인\s*특판")
 
    # Quality
    for key, pat in [("120K", r"120\s*K"), ("110K", r"110\s*K"), ("2nd", r"2\s*nd"),
                     ("삼디초", r"삼\s*/?\s*디초"), ("가전구독", r"가전\s*구독"),
                     ("제휴카드", r"제휴\s*카드"), ("라이프", r"라이프"), ("MIT", r"MIT")]:
        d[key] = _single(text, pat)
 
    # 검증: 모델별 누적 합 = 예약누적
    model_sum = d["울트라누적"] + d["와이드누적"] + d["플립8누적"]
    d["검증오류"] = []
    if model_sum != d["예약누적"]:
        d["검증오류"].append(f"모델별 합({model_sum}) ≠ 예약누적({d['예약누적']})")
 
    # 개인별 실적 (고정 순서 12필드: 목표/실적/모행/특판/120K/110K/2nd/삼디초/가전/카드/라이프/MIT)
    d["개인별"] = []
    psec = re.search(r"ㅇ\s*개인별[^\n]*\n(.*?)(?=\nㅇ|\Z)", text, re.DOTALL)
    if psec:
        person_keys = ["목표", "실적", "모행", "특판",
                       "120K", "110K", "2nd", "삼디초", "가전구독",
                       "제휴카드", "라이프", "MIT"]
        for line in psec.group(1).split("\n"):
            m = re.match(r"\s*[-ㄴ]\s*([^:：/\d][^:：]*?)\s*[:：]\s*([\d\s/,·.]+)", line)
            if not m:
                continue
            name = m.group(1).strip()
            nums = [_num(x) for x in re.split(r"[/·]", m.group(2)) if x.strip()]
            p = {"이름": name}
            if len(nums) != 12:
                d["검증오류"].append(f"개인별 '{name}' 숫자 {len(nums)}개 (12개 필요)")
            for i, k in enumerate(person_keys):
                p[k] = nums[i] if i < len(nums) else 0
            d["개인별"].append(p)
        # 개인 합 = 매장 값 대사
        if d["개인별"]:
            checks = [("실적", "예약누적"), ("모행", "모두의행복"), ("특판", "소규모법인")] + \
                     [(k, k) for k in ["120K", "110K", "2nd", "삼디초",
                                       "가전구독", "제휴카드", "라이프", "MIT"]]
            for pk, sk in checks:
                psum = sum(p[pk] for p in d["개인별"])
                if psum != d[sk]:
                    d["검증오류"].append(f"개인 {pk} 합({psum}) ≠ 매장 {sk}({d[sk]})")
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
 
