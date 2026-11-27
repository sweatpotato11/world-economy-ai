"""
🇰🇷 한국 집중 분석 — 오늘 뉴스와 세계 이슈가 한국 경제에 어떤 영향을 주는지 AI가 따로 분석해요.
"""

import re

from ai import call_ai, pick, text_list

IMPACTS = ["긍정", "부정", "중립"]
KOREA_SECTORS = ["반도체", "자동차", "배터리", "조선", "철강·화학", "바이오", "인터넷·게임", "금융", "부동산·건설",
                 "유통·소비", "에너지", "항공·여행"]

KOREA_WORDS = re.compile(r"한국|국내|코스피|코스닥|원화|원/달러|원·달러|환율|한은|한국은행|기준금리|수출|삼성|SK|현대|LG|"
                         r"서울|부동산|아파트|금융위|기재부|Korea|KOSPI|Seoul|Samsung|Hyundai|won", re.I)

SCHEMA = {
    "type": "object",
    "required": ["summary", "mood", "key_points", "world_to_korea", "sectors", "watch", "article_ids"],
    "properties": {
        "summary": {"type": "string", "description": "오늘 한국 경제 흐름 2~3문장"},
        "mood": {"type": "string", "enum": IMPACTS},
        "key_points": {
            "type": "array", "minItems": 3, "maxItems": 6,
            "description": "오늘 한국 경제에서 가장 중요한 일들, 중요한 순서",
            "items": {"type": "object", "required": ["title", "detail", "impact", "easy"],
                      "properties": {
                          "title": {"type": "string", "description": "30자 이내 제목"},
                          "detail": {"type": "string", "description": "무슨 일인지와 의미 2~3문장"},
                          "easy": {"type": "string", "description": "중학생도 이해하는 쉬운 설명 1~2문장 (우리 생활과 연결)"},
                          "impact": {"type": "string", "enum": IMPACTS}}},
        },
        "world_to_korea": {
            "type": "array", "maxItems": 6,
            "description": "세계 이슈가 한국에 주는 영향. world_issue 는 주어진 세계 이슈 제목 그대로",
            "items": {"type": "object", "required": ["world_issue", "effect", "impact", "who"],
                      "properties": {
                          "world_issue": {"type": "string"},
                          "effect": {"type": "string", "description": "한국에 어떤 영향인지 2문장"},
                          "who": {"type": "string", "description": "특히 영향을 받는 곳 (예: 수출 기업, 해외여행 가는 사람, 대출 있는 집)"},
                          "impact": {"type": "string", "enum": IMPACTS}}},
        },
        "sectors": {
            "type": "array", "maxItems": 8,
            "description": "오늘 뉴스에서 근거가 있는 한국 산업만",
            "items": {"type": "object", "required": ["name", "outlook", "reason"],
                      "properties": {"name": {"type": "string", "enum": KOREA_SECTORS},
                                     "outlook": {"type": "string", "enum": IMPACTS},
                                     "reason": {"type": "string", "description": "이유 한 줄"}}},
        },
        "watch": {"type": "array", "items": {"type": "string"}, "maxItems": 4,
                  "description": "앞으로 지켜볼 일정이나 포인트 (기사에 근거가 있는 것만)"},
        "article_ids": {"type": "array", "items": {"type": "string"}, "description": "근거 기사 id (주어진 id만)"},
    },
}

SYSTEM = """당신은 한국 경제를 전문으로 분석하는 애널리스트예요.
오늘의 한국 관련 기사, 세계 경제 이슈, 한국 경제 지표를 보고 '한국 입장에서' 분석하세요.

규칙
- 모든 글은 한국어로, 쉽고 정확하게 써요.
- 기사에 없는 사실이나 숫자를 지어내지 마세요.
- 기사 문장을 그대로 베끼지 말고 자기 말로 요약해요.
- 투자 추천(사라/팔아라)은 하지 마세요.
- world_issue 에는 주어진 세계 이슈 제목을 글자 그대로 써요.
- article_ids 에는 반드시 주어진 기사 id 만 넣어요."""


def korea_articles(articles, limit=120):
    """한국 관련 기사를 먼저 고르고, 모자라면 나머지로 채워요."""
    hangul = re.compile(r"[가-힣]")
    picked = [a for a in articles if hangul.search(a["title"]) or KOREA_WORDS.search(a["title"] + " " + a["snippet"])]
    return picked[:limit]


def analyze_korea(articles, world_issues, indicators):
    chosen = korea_articles(articles)
    lines = [f"[{a['id']}] ({a['source']}) {a['title']} — {a['snippet'][:160]}" for a in chosen]
    issues = [f"- {i['title']} ({i['region']}, {i['sector']}): {i['what']}" for i in world_issues]
    inds = [f"{i['name']}: {i['value']} ({i['change']})" for i in indicators]
    user = ("## 한국 경제 지표\n" + "\n".join(inds) +
            "\n\n## 오늘의 세계 경제 이슈\n" + "\n".join(issues) +
            "\n\n## 한국 관련 기사\n" + "\n".join(lines))
    return normalize(call_ai("한국 분석", SYSTEM, user, SCHEMA), articles, world_issues)


def normalize(r, articles, world_issues):
    by_id = {a["id"]: a for a in articles}
    titles = {i["title"]: i["id"] for i in world_issues}
    linked = sorted((by_id[i] for i in (r.get("article_ids") or []) if i in by_id),
                    key=lambda a: a["published"], reverse=True)
    return {
        "summary": str(r.get("summary", "")),
        "mood": pick(r.get("mood"), IMPACTS, "중립"),
        "key_points": [{"title": str(k.get("title", "")), "detail": str(k.get("detail", "")),
                        "easy": str(k.get("easy", "")), "impact": pick(k.get("impact"), IMPACTS, "중립")}
                       for k in (r.get("key_points") or [])[:6] if isinstance(k, dict) and k.get("title")],
        "world_to_korea": [{"world_issue": str(w.get("world_issue", "")),
                            "issue_id": titles.get(w.get("world_issue")),
                            "effect": str(w.get("effect", "")), "who": str(w.get("who", "")),
                            "impact": pick(w.get("impact"), IMPACTS, "중립")}
                           for w in (r.get("world_to_korea") or [])[:6] if isinstance(w, dict) and w.get("effect")],
        "sectors": [{"name": s["name"], "outlook": pick(s.get("outlook"), IMPACTS, "중립"), "reason": str(s.get("reason", ""))}
                    for s in (r.get("sectors") or [])[:8] if isinstance(s, dict) and s.get("name") in KOREA_SECTORS],
        "watch": text_list(r.get("watch"), 4),
        "articles": [{k: a[k] for k in ("title", "source", "link", "published")} for a in linked[:15]],
    }
