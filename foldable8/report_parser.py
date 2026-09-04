# -*- coding: utf-8 -*-
"""아이폰18 예약현황 텔레그램 보고 메시지 파서.

보고 양식:
■ ㅇㅇ점 아이폰18 예약현황 보고

ㅇ CRM 현황

CRM 확보모수 : 0건
컨택완료 : 0/0/0건 (성공/보류/실패)

ㅇ 예약현황

예약 계 : 0/0건 (당일/누적)
    ㄴ 18P : 0/0건
    ㄴ 18PM : 0/0건
MNP : 0건 (누적)
모두의 행복 : 0건 (누적)

ㅇ Quality (누적)

120K : 0건
2nd : 0건
삼/디/가전 : 0건
제휴카드 : 0건
라이프 : 0건
MIT : 0건 (M 기준)

ㅇ 개인별 (목표/실적/MNP/모행/120K/2nd/삼디가전/카드/라이프/MIT)

홍길동 : 10/4/2/0/4/4/4/3/4/2
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
    """보고 메시지의 매장명을 마스터의 정식 조직명으로 매핑.

    실제 보고에서 '건대직영점점', '도농로 직영점', '의점부로데오점'(오타) 등
    표기 흔들림이 잦아 접미사 제거 → 정식명 → 별칭 → 부분일치 순으로 시도한다.
    """
    names = [s["조직"] for s in stores_cfg["매장"]]
    alias = stores_cfg.get("매장명_별칭", {})

    raw = name_raw.strip()
    # 접미사·공백 정리 ('OO직영점점', 'OO 직영점', 'OO매장' 등)
    cands = [raw]
    n = re.sub(r"[\s]*(직영)?(점|매장)+\s*$", "", raw)
    cands.append(n)
    cands.append(n.replace(" ", ""))

    for c in cands:
        if c in names:
            return c
        if c in alias:
            return alias[c]

    # 부분일치 (유일할 때만)
    for c in cands:
        hits = [x for x in names if c and (c in x or x in c)]
        if len(hits) == 1:
            return hits[0]
        # 별칭 부분일치
        ah = {v for k, v in alias.items() if c and (c in k or k in c)}
        if len(ah) == 1:
            return ah.pop()

    # 오타 대응 : 한 글자 차이 이내면 동일 매장으로 간주
    def close(a, b):
        if abs(len(a) - len(b)) > 1 or not a or not b:
            return False
        diff = sum(1 for x, y in zip(a, b) if x != y) + abs(len(a) - len(b))
        return diff <= 1
    base = cands[1].replace(" ", "")
    hits = [x for x in names if close(base, x)] or \
           [v for k, v in alias.items() if close(base, k)]
    if len(set(hits)) == 1:
        return hits[0]
    return None


def parse_report(text, stores_cfg):
    """보고 메시지 1건 파싱. 실패 시 None, 성공 시 dict 반환."""
    # 보고 판별: 제목 줄에 '예약현황' + 본문에 '예약 계' 항목이 있어야 함
    first = text.strip().split("\n")[0]
    if "예약현황" not in first or not re.search(r"예약\s*계\s*[:：]", text):
        return None
    m = re.search(r"■?\s*(.+?)\s*(?:아이폰18|폴더블8)?\s*예약현황\s*보고", first)
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

    # 모델별: 'ㄴ' 줄 순서 기준 집계 (1번째=18P, 2번째=18PM)
    model_keys = ["18P", "18PM"]
    sub_lines = re.findall(r"^\s*ㄴ\s*(.+)$", text, re.MULTILINE)[:2]
    for i, key in enumerate(model_keys):
        if i < len(sub_lines):
            p = _pair(sub_lines[i], r"")
            d[f"{key}당일"], d[f"{key}누적"] = p if p else (0, 0)
        else:
            d[f"{key}당일"], d[f"{key}누적"] = 0, 0

    d["MNP"] = _single(text, r"MNP")
    d["모두의행복"] = _single(text, r"모두의\s*행복")

    # Quality
    for key, pat in [("120K", r"120\s*K"), ("2nd", r"2\s*nd"),
                     ("삼디가전", r"삼\s*/?\s*디\s*/?\s*가전"),
                     ("제휴카드", r"제휴\s*카드"), ("라이프", r"라이프"), ("MIT", r"MIT")]:
        d[key] = _single(text, pat)

    # 검증: 모델별 누적 합 = 예약누적
    model_sum = d["18P누적"] + d["18PM누적"]
    d["검증오류"] = []
    if model_sum != d["예약누적"]:
        d["검증오류"].append(f"모델별 합({model_sum}) ≠ 예약누적({d['예약누적']})")

    # 개인별 실적 (고정 순서 10필드: 목표/실적/MNP/모행/120K/2nd/삼디가전/카드/라이프/MIT)
    d["개인별"] = []
    psec = re.search(r"ㅇ\s*개인별[^\n]*\n(.*?)(?=\nㅇ|\Z)", text, re.DOTALL)
    if psec:
        person_keys = ["목표", "실적", "MNP", "모행",
                       "120K", "2nd", "삼디가전",
                       "제휴카드", "라이프", "MIT"]
        # 줄 병합: 이름만 있고 숫자가 다음 줄로 넘어간 경우 대응
        # (머리기호 -, ㄴ, ·, * 는 있어도 없어도 인식)
        def _is_head(t):
            return bool(re.match(r"^[-ㄴ·*•]\s*\S", t)) or \
                bool(re.match(r"^[가-힣A-Za-z][^:：\d]{0,14}\s*[:：]", t))

        merged, buf = [], ""
        for ln in psec.group(1).split("\n"):
            t = ln.strip()
            if not t or t.startswith("("):
                continue
            if _is_head(t):
                if buf:
                    merged.append(buf)
                buf = t
            elif buf:
                buf += " " + t
        if buf:
            merged.append(buf)
        for line in merged:
            # 머리기호 제거 후 '이름 [:] 숫자/숫자/...' 매칭 (콜론 생략 허용)
            line = re.sub(r"^[-ㄴ·*•]\s*", "", line)
            m = re.match(r"^([^\d:：/][^:：\d]*?)\s*[:：]?\s*([\d][\d\s/,·.]*)", line)
            if not m:
                continue
            # 숫자가 너무 적으면 개인 라인이 아님 (구분선·안내문 방어)
            if len([x for x in re.split(r"[/·]", m.group(2)) if x.strip()]) < 5:
                continue
            name = m.group(1).strip()
            nums = [_num(x) for x in re.split(r"[/·]", m.group(2)) if x.strip()]
            p = {"이름": name}
            if len(nums) != 10:
                d["검증오류"].append(f"개인별 '{name}' 숫자 {len(nums)}개 (10개 필요)")
            for i, k in enumerate(person_keys):
                p[k] = nums[i] if i < len(nums) else 0
            d["개인별"].append(p)
        # 개인 합 = 매장 값 대사
        if d["개인별"]:
            checks = [("실적", "예약누적"), ("MNP", "MNP"), ("모행", "모두의행복")] + \
                     [(k, k) for k in ["120K", "2nd", "삼디가전",
                                       "제휴카드", "라이프", "MIT"]]
            # 포함관계 검증 (모행 ≤ MNP ≤ 실적)
            if d["모두의행복"] > d["MNP"]:
                d["검증오류"].append(
                    f"모행({d['모두의행복']}) > MNP({d['MNP']}) — 포함관계 위배")
            if d["MNP"] > d["예약누적"]:
                d["검증오류"].append(
                    f"MNP({d['MNP']}) > 예약누적({d['예약누적']}) — 포함관계 위배")
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
