# -*- coding: utf-8 -*-
"""매일 20시 실행: 텔레그램 보고 수집 → 공지 이미지 게시 → 엑셀 메일 발송.
 
필요 환경변수 (GitHub Actions secrets):
  TELEGRAM_BOT_TOKEN   봇 토큰
  REPORT_CHAT_ID       매장 보고방 chat_id (보고 수집)
  ANNOUNCE_CHAT_ID     공지방 chat_id (이미지 게시, 보고방과 같아도 됨)
  GMAIL_USER           발신 Gmail 주소
  GMAIL_APP_PASSWORD   Gmail 앱 비밀번호
  MAIL_TO              수신 회사메일 (콤마 구분 복수 가능)
 
상태 파일 (레포에 커밋해서 유지):
  data/offset.json          텔레그램 getUpdates offset
  data/reports_YYYYMMDD.json  당일 수집된 매장별 보고 (누적 병합)
  data/close_YYYYMMDD.json    당일 마감 누적치 → 다음날 '전일마감'으로 사용
"""
import json
import os
import smtplib
import sys
from datetime import datetime, timedelta, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.mime.text import MIMEText
from email import encoders
from pathlib import Path
 
import requests
 
BASE = Path(__file__).parent
DATA = BASE / "data"
DATA.mkdir(exist_ok=True)
sys.path.insert(0, str(BASE))
 
from report_parser import load_stores, parse_all
from build_excel import aggregate, build_workbook
from render_image import render, build_rows, build_footnote
 
KST = timezone(timedelta(hours=9))
TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
API = f"https://api.telegram.org/bot{TOKEN}"
WEEKDAY = "월화수목금토일"
 
 
def load_json(p, default):
    try:
        return json.loads(Path(p).read_text(encoding="utf-8"))
    except Exception:
        return default
 
 
def save_json(p, obj):
    Path(p).write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")
 
 
def collect_messages(report_chat_id):
    """getUpdates로 보고방 신규 메시지 수집 (offset 상태 유지)."""
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
            if m and str(m["chat"]["id"]) == str(report_chat_id) and m.get("text"):
                msgs.append(m["text"])
        if len(r["result"]) < 100:
            break
    state["offset"] = offset
    save_json(DATA / "offset.json", state)
    return msgs
 
 
def send_photo(chat_id, path, caption=""):
    with open(path, "rb") as f:
        r = requests.post(f"{API}/sendPhoto",
                          data={"chat_id": chat_id, "caption": caption},
                          files={"photo": f}, timeout=60)
    r.raise_for_status()
 
 
def send_document(chat_id, path, caption=""):
    with open(path, "rb") as f:
        requests.post(f"{API}/sendDocument",
                      data={"chat_id": chat_id, "caption": caption},
                      files={"document": f}, timeout=60)
 
 
def send_mail(subject, body, attachments):
    user = os.environ["GMAIL_USER"]
    pw = os.environ["GMAIL_APP_PASSWORD"]
    to = [a.strip() for a in os.environ["MAIL_TO"].split(",")]
    msg = MIMEMultipart()
    msg["From"], msg["To"], msg["Subject"] = user, ", ".join(to), subject
    msg.attach(MIMEText(body, "plain", "utf-8"))
    for p in attachments:
        part = MIMEBase("application", "octet-stream")
        part.set_payload(Path(p).read_bytes())
        encoders.encode_base64(part)
        part.add_header("Content-Disposition", "attachment",
                        filename=("utf-8", "", Path(p).name))
        msg.attach(part)
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
        s.login(user, pw)
        s.sendmail(user, to, msg.as_string())
 
 
def main(mode="report"):
    stores_cfg = load_stores()
    now = datetime.now(KST)
    ymd = now.strftime("%Y%m%d")
    yesterday = (now - timedelta(days=1)).strftime("%Y%m%d")
    date_str = f"{now.month}/{now.day}({WEEKDAY[now.weekday()]}) {now.hour}시 기준"
    title = f"■ {stores_cfg['지사명']} {stores_cfg['모델명']} 매장별 예약현황"
 
    # 리마인드 모드 (19시): 취합 안내 공지만 발송, 메시지 수집 없음
    if mode == "remind":
        txt = (f"📢 {stores_cfg['모델명']} 예약현황 취합 안내\n\n"
               f"금일 예약현황을 20시까지 보고 양식으로 올려주시기 바랍니다.\n"
               f"20시 10분에 자동 마감 집계되며, 미제출 매장은 전일 보고값으로 이월됩니다.")
        requests.post(f"{API}/sendMessage",
                      data={"chat_id": os.environ["REPORT_CHAT_ID"], "text": txt})
        return
 
    # 1) 수집 + 파싱 (당일 기존 수집분과 병합 → 하루 여러 번 실행해도 안전)
    msgs = collect_messages(os.environ["REPORT_CHAT_ID"])
    reports = load_json(DATA / f"reports_{ymd}.json", {})
    new_reports, errors = parse_all(msgs, stores_cfg)
    reports.update(new_reports)
    save_json(DATA / f"reports_{ymd}.json", reports)
 
    missing = [s["조직"] for s in stores_cfg["매장"] if s["조직"] not in reports]
 
    # 2) 집계 (전일마감 = 전일 close 파일, 미제출은 전일 보고 이월)
    prev_close = load_json(DATA / f"close_{yesterday}.json", {})
    prev_reports = load_json(DATA / f"reports_{yesterday}.json", {})
    agg = aggregate(reports, stores_cfg, prev_close=prev_close,
                    prev_reports=prev_reports)
 
    # 3) 산출물 생성
    out_img = BASE / f"예약현황_{ymd}.png"
    out_xlsx = BASE / f"{stores_cfg['지사명']}_{stores_cfg['모델명']}_예약현황_{ymd}.xlsx"
    render(build_rows(agg), title, date_str, out_img, footnote=build_footnote(agg))
    build_workbook(agg, date_str, out_xlsx, title=title)
 
    # 4) 텔레그램 공지
    t = agg["지사계"]
    cap = (f"📱 {stores_cfg['모델명']} 예약현황 ({date_str})\n"
           f"지사 계 {t['예약누적']:,}건 / 목표 {t['목표']:,}건 "
           f"(달성률 {t['예약누적']/t['목표']*100:.1f}%, 증분 +{t['증분']})")
    if missing:
        cap += f"\n※ 미제출: {', '.join(missing)}"
    send_photo(os.environ["ANNOUNCE_CHAT_ID"], out_img, cap)
 
    # 5) 메일 발송 (CRM 포함 엑셀)
    body = cap + "\n\n상세 내역은 첨부 엑셀(raw 시트에 CRM 현황 포함) 참고 바랍니다."
    send_mail(f"[{stores_cfg['지사명']}] {stores_cfg['모델명']} 예약현황 ({now.month}/{now.day})",
              body, [out_xlsx])
 
    # 6) 당일 마감치/보고 저장 → 익일 전일마감·이월용
    close = {s["조직"]: s["예약누적"] for s in agg["매장"] if s["데이터있음"]}
    for name, v in prev_close.items():
        close.setdefault(name, v)
    save_json(DATA / f"close_{ymd}.json", close)
    # 미제출 매장의 이월분도 reports 파일에 병합 저장 (다음날 재이월 가능)
    merged = dict(prev_reports)
    merged.update(reports)
    save_json(DATA / f"reports_{ymd}.json", merged)
 
    if errors:
        print("매장명 인식 실패:", errors)
 
 
if __name__ == "__main__":
    main(mode=sys.argv[1] if len(sys.argv) > 1 else "report")
 
