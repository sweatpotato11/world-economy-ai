"""
세계경제 AI — 뉴스·지표를 모으고 AI로 분석해서 site/data/today.json 을 만드는 프로그램

실행 방법
  진짜 실행 (인터넷 + API 키 필요):  python scripts/collect.py
  샘플 실행 (인터넷·API 키 없이 테스트): python scripts/collect.py --sample

하는 일 (순서대로)
  1. config/feeds.json 의 RSS 주소에서 경제 기사 제목·짧은 설명을 가져와요
  2. config/indicators.json 의 경제 지표(환율, 주가 등)를 가져와요
  3. Claude API 에게 기사 목록을 주고 이슈로 묶어서 분석해 달라고 해요
  4. 결과를 site/data/today.json 과 site/data/archive/날짜.json 에 저장해요
"""

import argparse
import hashlib
import html
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "config"
DATA = ROOT / "site" / "data"
KST = timezone(timedelta(hours=9))

# 사용할 Claude 모델. 더 싸게 하고 싶으면 GitHub 설정에서 CLAUDE_MODEL=claude-haiku-5-5 로 바꿔요.
MODEL = os.environ.get("CLAUDE_MODEL", "claude-sonnet-5-5")

REGIONS = ["미국", "중국", "유럽", "한국", "일본", "아시아", "중동", "기타"]
SECTORS = ["금리", "물가", "무역", "에너지", "기술", "환율", "증시", "고용", "부동산", "기타"]
IMPACTS = ["긍정", "부정", "중립"]


# ─────────────────────────────── 1. 뉴스 수집 ───────────────────────────────

def clean_text(text, limit=300):
    """HTML 태그를 지우고 길이를 줄여요. (기사 원문을 통째로 쓰지 않기 위해 짧게만 써요)"""
    text = html.unescape(re.sub(r"<[^>]+>", " ", text or ""))
    text = re.sub(r"\s+", " ", text).strip()
    return text[:limit]


def fetch_articles(cfg):
    import feedparser  # 필요할 때만 불러와요

    now = datetime.now(timezone.utc)
    max_age = timedelta(hours=cfg.get("max_age_hours", 36))
    per_feed = cfg.get("max_articles_per_feed", 15)
    articles, seen_titles = [], set()

    for feed in cfg["feeds"]:
        try:
            parsed = feedparser.parse(feed["url"], agent="Mozilla/5.0 (world-economy-ai)")
        except Exception as e:  # 피드 하나가 실패해도 나머지는 계속해요
            print(f"  ! {feed['name']} 실패: {e}")
            continue

        count = 0
        for entry in parsed.entries:
            if count >= per_feed:
                break
            title = clean_text(entry.get("title", ""), 200)
            link = entry.get("link", "")
            if not title or not link.startswith("http"):
                continue

            key = re.sub(r"\W", "", title.lower())[:60]
            if key in seen_titles:  # 같은 기사 중복 제거
                continue

            published = None
            for field in ("published_parsed", "updated_parsed"):
                if entry.get(field):
                    published = datetime(*entry[field][:6], tzinfo=timezone.utc)
                    break
            if published and now - published > max_age:
                continue

            seen_titles.add(key)
            count += 1
            articles.append({
                "id": "a" + hashlib.md5(link.encode()).hexdigest()[:8],
                "title": title,
                "snippet": clean_text(entry.get("summary", "")),
                "source": feed["name"],
                "link": link,
                "published": (published or now).isoformat(),
            })
        print(f"  - {feed['name']}: {count}개")

    return articles


# ─────────────────────────────── 2. 지표 수집 ───────────────────────────────

def sparkline(values, width=70, height=20):
    """숫자 목록을 작은 그래프용 좌표 문자열로 바꿔요 (사이트의 SVG에서 사용)"""
    if len(values) < 2:
        return ""
    lo, hi = min(values), max(values)
    span = (hi - lo) or 1
    step = width / (len(values) - 1)
    pts = [f"{2 + i * step:.1f},{2 + height - (v - lo) / span * height:.1f}" for i, v in enumerate(values)]
    return " ".join(pts)


def fetch_indicators(cfg):
    import yfinance as yf

    result = []
    for ind in cfg["indicators"]:
        try:
            hist = yf.Ticker(ind["symbol"]).history(period="1mo")["Close"].dropna().tolist()
        except Exception as e:
            print(f"  ! {ind['name']} 실패: {e}")
            hist = []
        if len(hist) < 2:
            result.append({"name": ind["name"], "value": "—", "change": "—", "direction": "flat", "points": ""})
            continue

        last, prev = hist[-1], hist[-2]
        d = ind.get("decimals", 2)
        if ind.get("suffix") == "%":  # 금리는 %p 차이로 보여줘요
            diff = last - prev
            change = f"{diff:+.{d}f}%p"
        else:
            diff = (last - prev) / prev * 100
            change = f"{diff:+.2f}%"
        result.append({
            "name": ind["name"],
            "value": f"{last:,.{d}f}{ind.get('suffix', '')}",
            "change": change,
            "direction": "up" if diff > 0 else "down" if diff < 0 else "flat",
            "points": sparkline(hist[-20:]),
        })
        print(f"  - {ind['name']}: {result[-1]['value']} ({change})")
    return result


# ─────────────────────────────── 3. AI 분석 ───────────────────────────────

REPORT_TOOL = {
    "name": "publish_report",
    "description": "오늘의 세계 경제 분석 결과를 사이트에 올려요.",
    "input_schema": {
        "type": "object",
        "required": ["briefing", "issues", "regions", "sectors"],
        "properties": {
            "briefing": {
                "type": "object",
                "required": ["summary", "top_issue", "focus_region", "mood"],
                "properties": {
                    "summary": {"type": "string", "description": "오늘 세계 경제 흐름 2~3문장 요약"},
                    "top_issue": {"type": "string", "description": "가장 큰 이슈 이름 (짧게)"},
                    "focus_region": {"type": "string", "description": "오늘 가장 주목할 지역"},
                    "mood": {"type": "string", "enum": IMPACTS},
                },
            },
            "issues": {
                "type": "array",
                "minItems": 1,
                "maxItems": 8,
                "description": "중요한 순서대로 정렬한 이슈 목록. 비슷한 기사는 한 이슈로 묶어요.",
                "items": {
                    "type": "object",
                    "required": ["title", "region", "sector", "impact", "importance", "what", "why",
                                 "effect", "easy_summary", "pro_summary", "why_important",
                                 "market_effects", "article_ids"],
                    "properties": {
                        "title": {"type": "string", "description": "한국어 이슈 제목, 30자 이내"},
                        "region": {"type": "string", "enum": REGIONS},
                        "sector": {"type": "string", "enum": SECTORS},
                        "impact": {"type": "string", "enum": IMPACTS, "description": "세계 경제·시장에 긍정/부정/중립"},
                        "importance": {"type": "integer", "minimum": 1, "maximum": 5},
                        "what": {"type": "string", "description": "무슨 일인지 한 줄"},
                        "why": {"type": "string", "description": "왜 중요한지 한 줄"},
                        "effect": {"type": "string", "description": "어떤 시장에 영향이 가는지 한 줄"},
                        "easy_summary": {"type": "array", "items": {"type": "string"}, "minItems": 3, "maxItems": 3,
                                         "description": "중학생도 이해할 수 있는 쉬운 3줄 요약"},
                        "pro_summary": {"type": "array", "items": {"type": "string"}, "minItems": 3, "maxItems": 3,
                                        "description": "용어와 수치를 포함한 자세한 3줄 요약"},
                        "why_important": {"type": "string", "description": "이 이슈가 왜 중요한지 3~4문장"},
                        "market_effects": {
                            "type": "array", "maxItems": 4,
                            "items": {
                                "type": "object", "required": ["name", "direction", "reason"],
                                "properties": {
                                    "name": {"type": "string", "description": "예: 달러 가치, 원/달러 환율, 미국 주식, 유가"},
                                    "direction": {"type": "string", "enum": ["up", "down", "flat"]},
                                    "reason": {"type": "string", "description": "이유 한 줄"},
                                },
                            },
                        },
                        "article_ids": {"type": "array", "items": {"type": "string"},
                                        "description": "이 이슈의 근거가 된 기사 id 목록 (주어진 id만)"},
                    },
                },
            },
            "regions": {
                "type": "array",
                "items": {"type": "object", "required": ["name", "mood"],
                          "properties": {"name": {"type": "string", "enum": REGIONS},
                                         "mood": {"type": "string", "enum": IMPACTS}}},
            },
            "sectors": {
                "type": "array",
                "items": {"type": "object", "required": ["name", "positive_percent"],
                          "properties": {"name": {"type": "string", "enum": SECTORS},
                                         "positive_percent": {"type": "integer", "minimum": 0, "maximum": 100}}},
            },
        },
    },
}

SYSTEM_PROMPT = """당신은 세계 경제 뉴스를 분석하는 애널리스트예요.
아래 기사 목록(제목과 짧은 설명)만 근거로 오늘의 세계 경제 이슈를 정리하세요.

규칙
- 모든 글은 한국어로, 쉽고 정확하게 써요.
- 비슷한 기사는 하나의 이슈로 묶고, 중요한 순서대로 5~8개를 골라요.
- 기사에 없는 사실이나 숫자를 지어내지 마세요. 모르면 "기사에 나오지 않았어요"라고 써요.
- 기사 문장을 그대로 베끼지 말고 자기 말로 요약해요.
- market_effects 는 '예상'이에요. 확실하지 않으면 direction 을 flat 으로 해요.
- 투자 추천(사라/팔아라)은 하지 마세요.
- article_ids 에는 반드시 주어진 기사 id 만 넣어요.
- 결과는 반드시 publish_report 도구로 제출해요."""


def analyze(articles, indicators):
    import anthropic

    client = anthropic.Anthropic()  # ANTHROPIC_API_KEY 환경변수를 자동으로 읽어요
    lines = [f"[{a['id']}] ({a['source']}, {a['published'][:16]}) {a['title']} — {a['snippet']}" for a in articles]
    ind_lines = [f"{i['name']}: {i['value']} ({i['change']})" for i in indicators]
    user_msg = (
        f"오늘 날짜: {datetime.now(KST):%Y-%m-%d}\n\n"
        "## 오늘의 경제 지표\n" + "\n".join(ind_lines) +
        "\n\n## 기사 목록\n" + "\n".join(lines)
    )

    for attempt in range(2):  # 한 번 실패하면 한 번 더 시도해요
        resp = client.messages.create(
            model=MODEL,
            max_tokens=16000,
            system=SYSTEM_PROMPT,
            tools=[REPORT_TOOL],
            messages=[{"role": "user", "content": user_msg}],
        )
        for block in resp.content:
            if block.type == "tool_use" and block.name == "publish_report":
                print(f"  - 토큰 사용량: 입력 {resp.usage.input_tokens}, 출력 {resp.usage.output_tokens}")
                return block.input
        print(f"  ! AI가 결과를 도구로 내지 않았어요 (시도 {attempt + 1})")
    raise RuntimeError("AI 분석 결과를 받지 못했어요")


# ─────────────────────────────── 4. 결과 정리·저장 ───────────────────────────────

def build_output(articles, indicators, report, sample=False):
    """AI 결과에 실제 기사 링크를 붙여요. (링크는 AI가 아니라 RSS에서 온 진짜 주소만 써요)"""
    by_id = {a["id"]: a for a in articles}
    issues = []
    for n, issue in enumerate(report.get("issues", []), start=1):
        linked = [by_id[i] for i in issue.get("article_ids", []) if i in by_id]
        linked.sort(key=lambda a: a["published"], reverse=True)
        issue = dict(issue)
        issue["id"] = f"issue-{n}"
        issue["rank"] = n
        issue["importance"] = max(1, min(5, int(issue.get("importance", 3))))
        issue["articles"] = [{k: a[k] for k in ("title", "source", "link", "published")} for a in linked]
        issue.pop("article_ids", None)
        issues.append(issue)

    now = datetime.now(KST)
    return {
        "generated_at": now.isoformat(timespec="minutes"),
        "date": now.strftime("%Y-%m-%d"),
        "sample": sample,
        "model": "샘플 데이터" if sample else MODEL,
        "article_count": len(articles),
        "briefing": report.get("briefing", {}),
        "indicators": indicators,
        "issues": issues,
        "regions": report.get("regions", []),
        "sectors": report.get("sectors", []),
    }


def save(output):
    DATA.mkdir(parents=True, exist_ok=True)
    (DATA / "archive").mkdir(exist_ok=True)
    text = json.dumps(output, ensure_ascii=False, indent=2)
    (DATA / "today.json").write_text(text, encoding="utf-8")
    if not output["sample"]:
        (DATA / "archive" / f"{output['date']}.json").write_text(text, encoding="utf-8")
    print(f"저장 완료: site/data/today.json (이슈 {len(output['issues'])}개)")


# ─────────────────────────────── 샘플 모드 ───────────────────────────────

def sample_data():
    """인터넷과 API 키 없이 사이트가 잘 나오는지 확인하기 위한 가짜 데이터예요."""
    sample = json.loads((ROOT / "scripts" / "sample_report.json").read_text(encoding="utf-8"))
    return sample["articles"], sample["indicators"], sample["report"]


# ─────────────────────────────── 실행 ───────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="세계경제 AI 데이터 만들기")
    parser.add_argument("--sample", action="store_true", help="인터넷·API 없이 샘플 데이터로 실행")
    args = parser.parse_args()

    if args.sample:
        print("샘플 모드로 실행해요")
        articles, indicators, report = sample_data()
        save(build_output(articles, indicators, report, sample=True))
        return

    if not os.environ.get("ANTHROPIC_API_KEY"):
        sys.exit("ANTHROPIC_API_KEY 가 없어요. README 의 '3단계'를 확인해 주세요.")

    print("1) 뉴스 수집")
    articles = fetch_articles(json.loads((CONFIG / "feeds.json").read_text(encoding="utf-8")))
    if len(articles) < 3:
        sys.exit(f"기사가 너무 적어요 ({len(articles)}개). 피드 주소를 확인해 주세요. 기존 데이터는 그대로 둬요.")

    print("2) 경제 지표 수집")
    indicators = fetch_indicators(json.loads((CONFIG / "indicators.json").read_text(encoding="utf-8")))

    print(f"3) AI 분석 (기사 {len(articles)}개, 모델 {MODEL})")
    report = analyze(articles, indicators)

    print("4) 저장")
    save(build_output(articles, indicators, report))


if __name__ == "__main__":
    main()
