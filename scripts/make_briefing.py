#!/usr/bin/env python3
"""수집한 뉴스로 일일 브리핑 생성: Gemini 무료 API를 시도하고, 실패하면 규칙 기반 틀로 대체."""
import json, os, re, sys, time, urllib.error, urllib.request
from datetime import datetime, timedelta, timezone

KST = timezone(timedelta(hours=9))
BASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")
NEWS, OUT = os.path.join(BASE, "news.json"), os.path.join(BASE, "briefing.json")
# 모델 이름은 바뀔 수 있음. 저장소 Settings > Variables 에 GEMINI_MODEL을 넣으면 그 모델을 먼저 시도.
MODELS = [m for m in [os.environ.get("GEMINI_MODEL"), "gemini-flash-latest", "gemini-flash-lite-latest",
                      "gemini-2.5-flash"] if m]
KEEP = 60

TYPES = [("fx", ["환율", "원달러", "원·달러"]), ("freight", ["운임", "SCFI", "KCCI", "컨테이너"]),
         ("tariff", ["관세", "통상", "FTA", "보호무역"]), ("export", ["수출", "무역수지"]),
         ("port", ["항만", "혼잡", "선사", "결항", "수에즈", "선박"])]
TEMPL = {
    "fx": ("환율 변동은 수출 대금의 원화 환산액과 수출 마진에 영향을 줍니다.",
           "견적 환율 기준, 결제 통화, 환율 변동 조항을 바이어와 미리 점검해야 합니다."),
    "freight": ("운임은 선복 공급과 물동량, 지정학 변수에 따라 달라집니다.",
                "운임 부담 주체(Incoterms)에 따라 원가와 납기 협상이 달라집니다."),
    "tariff": ("관세·통상 정책은 수출 가격경쟁력과 시장 선택에 영향을 줍니다.",
               "HS Code와 FTA 적용 여부를 확인하고 바이어와 비용 분담을 협의해야 합니다."),
    "export": ("수출 통계는 품목·지역별 수요 흐름을 보여줍니다.",
               "담당 품목과 시장의 증감률을 따로 확인해 영업 기회를 찾아야 합니다."),
    "port": ("항로·항만 상황은 선박 회전과 가용 선복에 영향을 줍니다.",
             "납기 지연 가능성을 바이어에게 미리 알리고 대체 일정을 준비해야 합니다."),
    "other": ("공급망 변화는 비용과 납기에 영향을 줍니다.",
              "담당 업무에서 어떤 비용·납기 변수가 생기는지 확인해야 합니다."),
}
QTEMPL = {
    "fx": [("환율이 내려가면 수출 마진에 어떤 영향이 있고 어떻게 대응하나요?", "견적 환율 기준, 환율 변동 조항, 환헤지 협의를 언급"),
           ("환율 변동이 큰 시기에 바이어와 가격은 어떻게 협의하나요?", "견적 유효기간 단축, 결제 통화·조건 조정 제안")],
    "freight": [("운임이 오르내릴 때 영업에는 어떤 영향이 있나요?", "Incoterms에 따른 운임 부담 주체와 원가·납기 영향 설명"),
                ("운임 정보는 어디서 확인하나요?", "SCFI·KCCI·포워더 견적을 함께 확인한다고 답변")],
    "tariff": [("관세가 오르면 수출 가격은 어떻게 대응하나요?", "HS Code·FTA 확인, 비용 분담 협의, 시장 다변화"),
               ("관세 이슈를 어떻게 모니터링하나요?", "관세청·무역협회·KOTRA 등 신뢰 출처 언급")],
    "export": [("최근 수출 통계에서 눈에 띈 점과 그 이유는?", "품목·지역별 증감과 원인을 근거와 함께 설명"),
               ("수출이 좋은데 담당 품목은 부진하다면?", "품목별 수요·단가 차이를 확인하고 원인 분석")],
    "port": [("납기 지연이 예상되면 어떻게 대응하나요?", "원인 파악, 대체 항로·선사 확인, 바이어에 조기 통보"),
             ("항로 변경은 비용과 납기에 어떤 영향을 주나요?", "운송 기간·연료비 변화를 설명")],
    "other": [("이 이슈가 담당 업무에 미칠 영향은?", "원인, 영향 대상, 대응 방안 순서로 답변"),
              ("관련 정보를 어떻게 꾸준히 확인하나요?", "신뢰 출처와 점검 주기를 구체적으로 설명")],
}
CONCEPTS = [
    {"title": "SCFI와 KCCI", "body": "SCFI는 상하이거래소가 발표하는 중국 출발 컨테이너 운임 지수이고, KCCI는 한국해양진흥공사가 발표하는 한국 출발 운임 지수입니다. 둘의 방향과 항로별 차이를 같이 보면 시황 흐름을 읽을 수 있습니다.", "tip": "면접에서 지수 이름과 방향을 함께 말하면 시황을 챙긴다는 인상을 줍니다."},
    {"title": "HS Code", "body": "무역 상품을 분류하는 국제 번호로, 관세율·FTA 적용·수입 규제가 이 번호로 정해집니다. 분류를 잘못하면 추징이나 통관 지연이 생길 수 있습니다.", "tip": "관세 이슈가 나오면 HS Code 기준으로 영향 품목부터 확인하겠다고 답하세요."},
    {"title": "Incoterms (FOB·CIF)", "body": "운임·보험료와 위험 부담이 매도인과 매수인 사이 어디서 넘어가는지 정하는 규칙입니다. FOB는 선적 시점에 위험이 넘어가고 운임은 매수인이 부담하며, CIF는 매도인이 목적항까지 운임과 보험료를 부담합니다.", "tip": "운임 변동 이야기에 FOB·CIF에 따른 부담 주체 차이를 덧붙이세요."},
    {"title": "해운 얼라이언스와 선복 교환", "body": "여러 선사가 노선과 선복(선박의 적재 공간)을 나눠 쓰며 공동 운항하는 협력 구조입니다. 직접 배를 투입하지 않은 노선도 선복 교환으로 서비스할 수 있습니다.", "tip": "선사가 항로망을 넓히는 방식을 설명하면 산업 이해도를 보여줄 수 있습니다."},
    {"title": "주간 정리 연습", "body": "이번 주 가장 눈에 띈 이슈 3개를 골라 무슨 일 → 왜 → 내 직무에 미치는 영향 순서로 정리해 보세요.", "tip": "소리 내어 60초 안에 말해 보는 연습이 가장 효과적입니다."},
]


def kind(title):
    for k, kws in TYPES:
        if any(w in title for w in kws):
            return k
    return "other"


def rule_briefing(sel):
    issues, used = [], set()
    for cat in ("sales", "log"):
        n = 0
        for it in sel:
            if cat in it["cats"] and it["id"] not in used and n < 3:
                why, imp = TEMPL[kind(it["title"])]
                used.add(it["id"]); n += 1
                issues.append({"cat": cat, "title": it["title"], "summary": it["title"], "what": it["title"], "why": why, "impact": imp,
                               "questions": [{"q": q, "hint": h} for q, h in QTEMPL[kind(it["title"])]], "unverified": [],
                               "tags": it["tags"][:5], "sources": [{"name": it["source"] or "원문", "url": it["link"]}]})
    iv = []
    for cat, label in (("sales", "해외영업"), ("log", "물류·해운")):
        i = next((x for x in issues if x["cat"] == cat), None)
        if i:
            iv.append({"topic": i["title"], "script": [f"최근 '{i['title']}' 소식에 관심을 갖고 있습니다.", i["why"],
                       f"{label} 관점에서 보면 {i['impact']}", "그래서 관련 지표와 뉴스를 꾸준히 확인하고 업무에 반영하는 습관을 들이고 있습니다."],
                       "followups": ["이 이슈가 우리 회사에 미칠 영향은? → 원인, 영향 대상, 대응 방안 순서로 답변",
                                     "관련 정보는 어디서 확인하나요? → 신뢰할 출처와 지표 이름을 들어 설명"]})
    return {"issues": issues, "interview": iv, "concept": CONCEPTS[datetime.now(KST).weekday() % 5]}


def build_prompt(sel):
    lines = "\n".join(f'{i["id"]}|{"해외영업" if "sales" in i["cats"] else "물류"}|{i["title"]}|{i["source"]}' for i in sel)
    return f"""너는 해외영업·물류·SCM 신입 지원자를 돕는 한국어 뉴스 코치다. 아래는 오늘 수집한 기사 제목 목록이다(형식: id|분류|제목|매체).
규칙:
- 제목에 없는 수치·사실·기업 정보를 지어내지 마라. 불확실하면 일반적인 해석으로 쓰고 단정하지 마라.
- 이슈 4~6개를 골라 해외영업(sales) 중심으로 분석하되 물류(log)도 포함하라. 비슷한 기사는 하나로 묶어라.
- 각 이슈 필드: cat("sales" 또는 "log"), title(짧은 제목), summary(기사 제목에서 확인되는 내용만으로 2문장 이내 요약), what(무슨 일), why(왜), impact(누구에게 어떤 영향, 해외영업 직무 관점), tags(관련 산업·기업 이름 0~5개), ids(근거 기사 id 1~3개), questions(이 이슈로 면접관이 물을 만한 예상 질문 2개: 각각 q(질문), hint(답변 방향 한 줄)).
- interview: 2개(해외영업 1, 물류 1). 각각 topic, script(4문장: 요약/원인/직무 연결/내 생각), followups(꼬리질문과 답변 방향 2개).
- concept: 신입이 알아둘 무역·물류 개념 1개(title, body, tip).
- JSON만 출력. 스키마: {{"issues":[...],"interview":[...],"concept":{{...}}}}
기사:
{lines}"""


def parse_json(txt):
    txt = re.sub(r"^```(?:json)?|```$", "", txt.strip(), flags=re.M).strip()
    try:
        return json.loads(txt)
    except Exception:
        return json.loads(txt[txt.index("{"): txt.rindex("}") + 1])


def call_gemini(prompt, key):
    last = None
    for m in MODELS:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent"
        body = json.dumps({"contents": [{"parts": [{"text": prompt}]}],
                           "generationConfig": {"responseMimeType": "application/json", "temperature": 0.3}}).encode()
        for attempt in range(3):  # 일시적 오류(503 등)는 쉬었다가 같은 모델로 재시도
            req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json", "x-goog-api-key": key})
            try:
                with urllib.request.urlopen(req, timeout=90) as r:
                    data = json.load(r)
                print("Gemini 모델:", m)
                return parse_json(data["candidates"][0]["content"]["parts"][0]["text"])
            except urllib.error.HTTPError as e:
                last = e
                print(f"모델 {m} 실패(시도 {attempt + 1}): {e}", file=sys.stderr)
                if e.code in (429, 500, 502, 503, 504) and attempt < 2:
                    time.sleep(8 * (attempt + 1))
                    continue
                break
            except Exception as e:
                last = e
                print(f"모델 {m} 실패: {e}", file=sys.stderr)
                break
    raise RuntimeError(last)


NUM = re.compile(r"\d[\d,]*\.?\d*")


def unverified_numbers(texts, base):
    base = base.replace(",", "")
    out = []
    for n in NUM.findall(" ".join(texts)):
        k = n.replace(",", "").rstrip(".")
        if len(k) >= 2 and k not in base and n.rstrip(".,") not in out:
            out.append(n.rstrip(".,"))
    return out[:5]


def s(v):
    return v.strip() if isinstance(v, str) else ""


def validate_ai(d, byid):
    issues = []
    for i in d.get("issues", []):
        if not (s(i.get("title")) and s(i.get("what")) and s(i.get("why")) and s(i.get("impact"))):
            continue
        src = [{"name": byid[x]["source"] or "원문", "url": byid[x]["link"]} for x in i.get("ids", []) if x in byid][:3]
        if not src:
            continue  # 근거 기사가 없는 이슈는 버림
        tags = [s(t) for t in i.get("tags", []) if s(t)][:5]
        qs = [{"q": s(q.get("q")), "hint": s(q.get("hint"))} for q in i.get("questions", []) if isinstance(q, dict) and s(q.get("q"))][:3]
        base = " ".join(byid[x]["title"] for x in i.get("ids", []) if x in byid)
        summary = s(i.get("summary")) or s(i["what"])
        issues.append({"cat": "sales" if i.get("cat") == "sales" else "log", "title": s(i["title"]), "summary": summary,
                       "what": s(i["what"]), "why": s(i["why"]), "impact": s(i["impact"]), "tags": tags, "sources": src,
                       "questions": qs, "unverified": unverified_numbers([summary, s(i["what"]), s(i["why"]), s(i["impact"])], base)})
    iv = [{"topic": s(x.get("topic")), "script": [s(t) for t in x["script"]][:4],
           "followups": [s(t) for t in x.get("followups", [])][:2]}
          for x in d.get("interview", []) if isinstance(x.get("script"), list) and len(x["script"]) >= 4 and s(x.get("topic"))]
    c = d.get("concept") if isinstance(d.get("concept"), dict) else {}
    concept = {"title": s(c.get("title")), "body": s(c.get("body")), "tip": s(c.get("tip"))} if s(c.get("title")) and s(c.get("body")) else {}
    return {"issues": issues, "interview": iv, "concept": concept}


def main():
    items = json.load(open(NEWS, encoding="utf-8")).get("items", [])
    if not items:
        print("뉴스가 없어 브리핑을 만들지 않습니다.")
        return
    today = datetime.now(KST).date()
    ok = {str(today), str(today - timedelta(days=1))}
    sel = [i for i in items if i["date"] in ok]
    sel = (sel if len(sel) >= 5 else items)[:40]
    byid = {i["id"]: i for i in sel}
    rb, res, mode = rule_briefing(sel), None, "rule"
    key = os.environ.get("GEMINI_API_KEY")
    if key:
        try:
            res = validate_ai(call_gemini(build_prompt(sel), key), byid)
            if res["issues"]:
                mode = "ai"
            else:
                print("AI 결과에 쓸 수 있는 이슈가 없어 규칙 기반으로 대체", file=sys.stderr)
                res = None
        except Exception as e:
            print("AI 실패, 규칙 기반으로 대체:", e, file=sys.stderr)
    else:
        print("GEMINI_API_KEY가 없어 규칙 기반으로 생성")
    if res is None:
        res = rb
    else:
        for k in res:
            res[k] = res[k] or rb[k]
    if not res["issues"]:
        print("만들 수 있는 이슈가 없습니다.")
        return
    try:
        days = json.load(open(OUT, encoding="utf-8")).get("days", [])
    except Exception:
        days = []
    days = [d for d in days if d["date"] != str(today)]
    days.append({"date": str(today), "mode": mode, **res})
    days = sorted(days, key=lambda d: d["date"], reverse=True)[:KEEP]
    json.dump({"updated": datetime.now(KST).strftime("%Y-%m-%d %H:%M"), "days": days},
              open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"브리핑 저장({mode}): 이슈 {len(res['issues'])}개")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:  # 브리핑 실패가 뉴스 수집을 막지 않도록
        print("브리핑 생성 오류:", e, file=sys.stderr)
