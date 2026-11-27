"""
📖 경제 용어 사전 — 오늘 분석 글에 나온 어려운 경제 용어를 AI가 골라서 쉽게 설명해요.
매일 새 용어가 site/data/glossary.json 에 쌓여서 나만의 경제 사전이 돼요.
"""

import json

from ai import call_ai

SCHEMA = {
    "type": "object",
    "required": ["terms"],
    "properties": {
        "terms": {
            "type": "array", "minItems": 3, "maxItems": 12,
            "items": {
                "type": "object", "required": ["term", "easy", "example"],
                "properties": {
                    "term": {"type": "string", "description": "본문에 나온 글자 그대로의 용어 (예: 기준금리, 사이드카)"},
                    "english": {"type": "string", "description": "영어 표현 (있으면)"},
                    "easy": {"type": "string", "description": "중학생도 이해하는 설명 2문장. 비유를 써도 좋아요"},
                    "example": {"type": "string", "description": "오늘 뉴스와 연결한 예시 한 문장"},
                },
            },
        }
    },
}

SYSTEM = """당신은 중학생에게 경제를 가르치는 친절한 선생님이에요.
아래 글에서 중학생이 어려워할 만한 경제 용어를 6~12개 골라 쉽게 설명하세요.

규칙
- term 은 본문에 나온 글자 그대로 써요 (사이트에서 그 글자에 밑줄을 쳐요).
- 사람 이름, 회사 이름, 나라 이름은 고르지 마세요. 경제 개념만 골라요.
- 이미 아는 사람이 많은 쉬운 단어(돈, 가격, 회사)는 빼요.
- 설명은 정확해야 하고, 지어낸 숫자는 쓰지 마세요."""


def collect_text(issues, korea):
    parts = []
    for i in issues:
        parts += [i["title"], i["what"], i["why"], i["effect"], i["why_important"], *i["easy_summary"], *i["pro_summary"]]
    if korea:
        parts.append(korea["summary"])
        for k in korea["key_points"]:
            parts += [k["title"], k["detail"], k["easy"]]
        for w in korea["world_to_korea"]:
            parts.append(w["effect"])
    return "\n".join(p for p in parts if p)


def make_glossary(issues, korea):
    text = collect_text(issues, korea)
    result = call_ai("용어 사전", SYSTEM, "## 오늘의 분석 글\n" + text[:20000], SCHEMA, max_tokens=4000)
    terms, seen = [], set()
    for t in result.get("terms") or []:
        term = str(t.get("term", "")).strip()
        if not term or len(term) > 20 or term in seen or term not in text:
            continue  # 본문에 실제로 나온 용어만 남겨요
        seen.add(term)
        terms.append({"term": term, "english": str(t.get("english") or "").strip(),
                      "easy": str(t.get("easy", "")).strip(), "example": str(t.get("example", "")).strip()})
    return terms


def update_dictionary(path, terms, date):
    """오늘 용어를 전체 사전(glossary.json)에 더해요. 같은 용어는 설명을 최신으로 바꾸고 처음 본 날짜는 남겨요."""
    try:
        book = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, ValueError):
        book = {"terms": {}}
    for t in terms:
        old = book["terms"].get(t["term"], {})
        book["terms"][t["term"]] = {
            **t,
            "first_seen": old.get("first_seen", date),
            "last_seen": date,
            "count": old.get("count", 0) + 1,
        }
    path.write_text(json.dumps(book, ensure_ascii=False, indent=1), encoding="utf-8")
    return len(book["terms"])
