# -*- coding: utf-8 -*-
"""폴더블8 미개통·부족재고 취합 봇 (예약 시스템과 독립 트랙).
 
MODE
  remind : 18시 — 보고 요청 공지
  report : 20시 — 수집 → 자동보정 → 이미지 1장 + 텍스트 1장 게시
 
환경변수
  TELEGRAM_BOT_TOKEN / REPORT_CHAT_ID / ANNOUNCE_CHAT_ID
 
상태 파일 (레포 커밋으로 유지)
  data/offset.json                  텔레그램 getUpdates offset (예약봇과 분리)
  data/unopened_YYYYMMDD.json       당일 확정 데이터 (전일 대비 계산용)
"""
import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
 
import requests
 
BASE = Path(__file__).parent
DATA = BASE / "data"
DATA.mkdir(exist_ok=True)
sys.path.insert(0, str(BASE))
 
from parser import load_stores, parse_all, MODELS
from render import render, build_text, MOD
 
KST = timezone(timedelta(hours=9))
TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
API = f"https://api.telegram.org/bot{TOKEN}"
WD = "월화수목금토일"
 
 
def load_json(p, default):
    try:
        return json.loads(Path(p).read_text(encoding="utf-8"))
    except Exception:
        return default
 
 
def save_json(p, obj):
    Path(p).write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")
 
 
def load_latest(now, max_back=7, include_today=False):
    """직전 영업일 확정 데이터 (없으면 최대 7일 소급).
    include_today=True 면 당일 파일부터 확인 (remind 용)."""
    for i in range(0 if include_today else 1, max_back + 1):
        d = (now - timedelta(days=i)).strftime("%Y%m%d")
        data = load_json(DATA / f"unopened_{d}.json", None)
        if data:
            if i > 1:
                print(f"전일 파일 없음 → {i}일 전({d}) 사용")
            return data
    return {}
 
 
def collect_messages(chat_id):
    state = load_json(DATA / "offset.json", {"offset": 0})
    msgs, offset = [], state["offset"]
    while True:
        r = requests.get(f"{API}/getUpdates",
                         params={"offset": offset, "timeout": 0, "limit": 100},
                         timeout=30).json()
        if not r.get("ok") or not r["result"]:
            break
        for u in r["result"]:
            offset = u["update_id"] + 1
            m = u.get("message") or u.get("edited_message")
            if m and str(m["chat"]["id"]) == str(chat_id) and m.get("text"):
                msgs.append(m["text"])
        if len(r["result"]) < 100:
            break
    state["offset"] = offset
    save_json(DATA / "offset.json", state)
    return msgs
 
 
def send_text(chat_id, text):
    requests.post(f"{API}/sendMessage",
                  data={"chat_id": chat_id, "text": text}, timeout=(15, 60))
 
 
def send_photo(chat_id, path, caption="", retries=3):
    last = None
    for a in range(1, retries + 1):
        try:
            with open(path, "rb") as f:
                r = requests.post(f"{API}/sendPhoto",
                                  data={"chat_id": chat_id, "caption": caption},
                                  files={"photo": f}, timeout=(15, 180))
            r.raise_for_status()
            return
        except Exception as e:
            last = e
            print(f"send_photo 재시도 {a}/{retries}: {e}")
            if a < retries:
                time.sleep(15)
    raise last
 
 
def zero_rec():
    return {**{m: [0, 0, 0, 0] for m in MODELS},
            "부족": {"블랙": 0, "크림": 0, "라벤더": 0}}
 
 
def main(mode="report"):
    now = datetime.now(KST)
    cfg = load_stores()
    stores = [(s["조직"], s["상권"]) for s in cfg["매장"]]
    allst = [n for n, _ in stores]
    reg = {n: g for n, g in stores}
    prev = load_latest(now)
 
    # ── 18시 : 보고 요청 ──
    if mode == "remind":
        base = load_latest(now, include_today=True)
        pend = [n for n in allst
                if not base or sum(base.get(n, zero_rec())[m][3] for m in MOD) > 0]
        txt = (f"📢 폴더블8 미개통 현황 취합 안내\n\n"
               f"금일 미개통 건과 부족재고를 20시까지 공유 부탁드립니다.\n"
               f"※ 전일 0건 매장은 미보고해도 됩니다.\n"
               f"※ 전일 미개통 있었으나 금일 0건이 된 매장은 꼭 공유해 주세요.\n\n"
               f"[보고 양식]\n"
               f"■ ㅇㅇ점 폴더블8 사전예약 미개통 현황\n\n"
               f"ㅇ 미개통 건 (010 / MNP / 기변 / 계)\n"
               f" * 폴드8 : 0 / 0 / 0 / 0\n"
               f" * 플립8 : 0 / 0 / 0 / 0\n"
               f" * 합계 : 0 / 0 / 0 / 0\n\n"
               f"ㅇ 부족재고 현황\n"
               f" * 폴드8 블랙 : 0대\n"
               f" * 폴드8 크림 : 0대\n"
               f" * 폴드8 라벤더 : 0대")
        if base and pend:
            txt += f"\n\n※ 전일 잔량 보유 {len(pend)}개 매장 : " + ", ".join(pend)
        send_text(os.environ["REPORT_CHAT_ID"], txt)
        print(f"remind 발송 (잔량 매장 {len(pend)}개)")
        return
 
    # ── 20시 : 수집 → 보정 → 게시 ──
    msgs = collect_messages(os.environ["REPORT_CHAT_ID"])
    got = parse_all(msgs, cfg)
    print(f"수집 메시지 {len(msgs)}건 / 인식 매장 {len(got)}곳")
 
    cur, carry, fixes = {}, [], []
    for n in allst:
        if n in got:
            cur[n] = {k: v for k, v in got[n].items() if k != "매장"}
            for f in got[n].get("fixes", []):
                fixes.append(f"{n}: {f}")
        elif n in prev:
            p = prev[n]
            if sum(p[m][3] for m in MOD) > 0:
                carry.append(n)          # 잔량 있는데 미보고 → 이월 표기
            cur[n] = {**{m: list(p[m]) for m in MODELS}, "부족": dict(p["부족"])}
        else:
            cur[n] = zero_rec()
    for n in cur:
        cur[n].pop("fixes", None)
 
    ymd = now.strftime("%Y%m%d")
    label = f"{now.month}/{now.day}({WD[now.weekday()]})"
    img = str(BASE / f"unopened_{ymd}.png")
    render(cur, prev, stores, reg, f"{label} 기준", carry, img)
 
    tot = sum(sum(cur[n][m][3] for m in MOD) for n in allst)
    ptot = sum(sum(prev[n][m][3] for m in MOD) for n in allst if n in prev)
    cap = (f"📱 폴더블8 미개통 현황 ({label} 기준)\n"
           f"미개통 {tot}건" + (f" (전일 대비 {tot-ptot:+d})" if prev else ""))
    send_photo(os.environ["ANNOUNCE_CHAT_ID"], img, cap)
    send_text(os.environ["ANNOUNCE_CHAT_ID"], build_text(cur, prev, allst, label))
 
    if fixes:
        send_text(os.environ["ANNOUNCE_CHAT_ID"],
                  "⚠ 자동 보정 안내 (보고 형식 오류)\n"
                  + "\n".join(f"· {f}" for f in fixes[:12])
                  + ("\n· 외 " + str(len(fixes) - 12) + "건" if len(fixes) > 12 else "")
                  + "\n\n다음 보고 시 합계 줄과 유형칸을 확인해 주세요.")
 
    save_json(DATA / f"unopened_{ymd}.json", cur)
    print(f"완료 | 미개통 {tot}건 | 이월 {len(carry)}곳 | 보정 {len(fixes)}건")
 
 
if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "report")
 
