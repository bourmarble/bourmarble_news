#!/usr/bin/env python3
"""RSS로 물류·해운·무역 뉴스를 모아 data/news.json에 저장 (표준 라이브러리만 사용, 무료)."""
import hashlib, json, os, re, sys, urllib.parse, urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

KST = timezone(timedelta(hours=9))
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "news.json")
KEEP_DAYS = 90

# 구글 뉴스 RSS 검색어 (자유롭게 추가/수정)
QUERIES = ["해운 컨테이너 운임", "물류 공급망 SCM", "국제물류 포워더", "수출 무역 통계",
           "원달러 환율 수출", "관세 통상 수출기업", "KOTRA 해외시장"]
# 매체 자체 RSS를 추가하려면: ("매체명", "RSS 주소")
EXTRA_FEEDS = []

SALES = ["수출", "환율", "관세", "무역", "FTA", "통상", "해외영업", "KOTRA", "바이어"]
LOG = ["물류", "해운", "운임", "컨테이너", "SCFI", "KCCI", "항만", "포워", "공급망", "SCM", "선사", "선박", "해상"]
COMPANIES = ["HMM", "현대글로비스", "CJ대한통운", "한진", "팬오션", "대한해운", "KSS해운", "흥아해운",
             "머스크", "MSC", "쿠팡", "삼성SDS", "롯데글로벌로지스"]
INDUSTRIES = {"반도체": ["반도체", "HBM"], "자동차": ["자동차", "완성차", "PCTC"], "배터리": ["배터리", "이차전지"],
              "컨테이너 해운": ["컨테이너", "SCFI", "KCCI", "운임"], "항만": ["항만", "부두"],
              "국제물류(포워딩)": ["포워", "국제물류"], "외환": ["환율", "원달러", "원·달러"],
              "관세·통상": ["관세", "FTA", "통상"]}


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (news-collector)"})
    with urllib.request.urlopen(req, timeout=25) as r:
        return r.read()


def parse(xml_bytes):
    root = ET.fromstring(xml_bytes)
    out = []
    for it in root.iter("item"):
        src = it.find("source")
        out.append({"title": (it.findtext("title") or "").strip(), "link": (it.findtext("link") or "").strip(),
                    "pub": it.findtext("pubDate") or "", "source": (src.text or "").strip() if src is not None else ""})
    return out


def classify(title):
    cats = [c for c, kws in (("sales", SALES), ("log", LOG)) if any(k in title for k in kws)]
    tags = [c for c in COMPANIES if c in title] + [n for n, kws in INDUSTRIES.items() if any(k in title for k in kws)]
    return cats, tags


def norm(t):
    return re.sub(r"[^0-9a-z가-힣]", "", t.lower())[:40]


def to_item(raw, fallback_source=""):
    title, src = raw["title"], raw["source"] or fallback_source
    if src and title.endswith(" - " + src):
        title = title[: -len(src) - 3]
    if not title or not raw["link"]:
        return None
    try:
        d = parsedate_to_datetime(raw["pub"]).astimezone(KST)
    except Exception:
        d = datetime.now(KST)
    cats, tags = classify(title)
    if not cats:
        return None
    key = norm(title)
    return {"id": hashlib.md5(key.encode()).hexdigest()[:10], "date": d.strftime("%Y-%m-%d"), "title": title,
            "link": raw["link"], "source": src, "cats": cats, "tags": tags}


def main():
    feeds = [("구글뉴스", "https://news.google.com/rss/search?q=" + urllib.parse.quote(q + " when:2d") +
              "&hl=ko&gl=KR&ceid=KR:ko") for q in QUERIES] + EXTRA_FEEDS
    try:
        old = json.load(open(OUT, encoding="utf-8")).get("items", [])
    except Exception:
        old = []
    items = {i["id"]: i for i in old}
    ok = 0
    for name, url in feeds:
        try:
            raws = parse(fetch(url))
            ok += 1
            n = 0
            for r in raws:
                it = to_item(r, name)
                if it and it["id"] not in items:
                    items[it["id"]] = it
                    n += 1
            print(f"OK   {name} +{n} ({len(raws)}건 중)")
        except Exception as e:
            print(f"FAIL {name}: {e}", file=sys.stderr)
    if ok == 0:
        sys.exit("모든 피드 수집 실패")
    limit = (datetime.now(KST) - timedelta(days=KEEP_DAYS)).strftime("%Y-%m-%d")
    result = sorted((i for i in items.values() if i["date"] >= limit), key=lambda i: i["date"], reverse=True)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump({"updated": datetime.now(KST).strftime("%Y-%m-%d %H:%M"), "items": result},
              open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"저장 {len(result)}건")


if __name__ == "__main__":
    main()
