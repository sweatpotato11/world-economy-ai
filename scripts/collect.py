"""
세계경제 AI — 뉴스·지표를 모으고 AI로 분석해서 site/data/today.json 을 만드는 프로그램

실행 방법
  진짜 실행 (인터넷 + API 키 필요):  python scripts/collect.py
  샘플 실행 (인터넷·API 키 없이 테스트): python scripts/collect.py --sample

하는 일 (순서대로)
  1. config/feeds.json 의 RSS 주소에서 경제 기사 제목·짧은 설명을 가져와요
  2. config/indicators.json 의 경제 지표(환율, 주가 등)를 가져와요
  3. AI(Gemini 무료 또는 Claude)에게 기사를 주고 이슈로 묶어서 분석해요
  4. 🇰🇷 한국 집중 분석 (scripts/korea.py)
  5. 📖 오늘의 경제 용어 사전 (scripts/glossary.py)
  6. 결과를 site/data/today.json 과 site/data/archive/날짜.json 에 저장해요
  7. 일요일이면 📅 주간 정리도 만들어요 (scripts/weekly.py)
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

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ai  # noqa: E402  (AI 부르는 도우미)
from glossary import make_glossary, update_dictionary  # noqa: E402
from korea import analyze_korea  # noqa: E402
from weekly import is_weekly_day, make_weekly  # noqa: E402

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

    articles.sort(key=lambda a: a["published"], reverse=True)  # 최신 기사부터
    return articles[: cfg.get("max_total_articles", 250)]


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


def fetch_one(yf, ind):
    """지표 하나의 1년 치 하루 종가를 가져와요. (날짜 목록, 값 목록)"""
    try:
        h = yf.Ticker(ind["symbol"]).history(period="1y")["Close"].dropna()
    except Exception as e:
        print(f"  ! {ind['name']} 실패: {e}")
        return [], []
    mult = ind.get("multiplier", 1)
    return [d.strftime("%Y-%m-%d") for d in h.index], [round(float(v) * mult, 4) for v in h.tolist()]


def summarize_indicator(ind, closes):
    if len(closes) < 2:
        return {"name": ind["name"], "value": "—", "change": "—", "direction": "flat", "points": ""}
    last, prev = closes[-1], closes[-2]
    d = ind.get("decimals", 2)
    if ind.get("suffix") == "%":  # 금리는 %p 차이로 보여줘요
        diff = last - prev
        change = f"{diff:+.{d}f}%p"
    else:
        diff = (last - prev) / prev * 100
        change = f"{diff:+.2f}%"
    return {
        "name": ind["name"],
        "value": f"{last:,.{d}f}{ind.get('suffix', '')}",
        "change": change,
        "direction": "up" if diff > 0 else "down" if diff < 0 else "flat",
        "points": sparkline(closes[-20:]),
    }


def fetch_indicators(cfg):
    """세계 지표와 한국 지표를 가져와요. 큰 그래프용 1년 기록(history)도 같이 돌려줘요."""
    import yfinance as yf

    groups, history = {}, {}
    for group in ("indicators", "korea_indicators"):
        groups[group] = []
        for ind in cfg.get(group, []):
            if ind["name"] not in history:
                dates, closes = fetch_one(yf, ind)
                history[ind["name"]] = {"symbol": ind["symbol"], "suffix": ind.get("suffix", ""),
                                        "decimals": ind.get("decimals", 2), "dates": dates, "closes": closes}
            summary = summarize_indicator(ind, history[ind["name"]]["closes"])
            groups[group].append(summary)
            print(f"  - {ind['name']}: {summary['value']} ({summary['change']})")
    return groups["indicators"], groups["korea_indicators"], history


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
                "maxItems": 15,
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
- 비슷한 기사는 하나의 이슈로 묶고, 중요한 순서대로 10~15개를 골라요. 미국·중국·유럽·한국·일본·중동 등 여러 지역과 분야가 골고루 들어가게 해요.
- 기사에 없는 사실이나 숫자를 지어내지 마세요. 모르면 "기사에 나오지 않았어요"라고 써요.
- 기사 문장을 그대로 베끼지 말고 자기 말로 요약해요.
- market_effects 는 '예상'이에요. 확실하지 않으면 direction 을 flat 으로 해요.
- 투자 추천(사라/팔아라)은 하지 마세요.
- article_ids 에는 반드시 주어진 기사 id 만 넣어요."""


def build_user_message(articles, indicators):
    lines = [f"[{a['id']}] ({a['source']}, {a['published'][:16]}) {a['title']} — {a['snippet']}" for a in articles]
    ind_lines = [f"{i['name']}: {i['value']} ({i['change']})" for i in indicators]
    return (
        f"오늘 날짜: {datetime.now(KST):%Y-%m-%d}\n\n"
        "## 오늘의 경제 지표\n" + "\n".join(ind_lines) +
        "\n\n## 기사 목록\n" + "\n".join(lines)
    )


def analyze(articles, indicators):
    raw = ai.call_ai("세계 분석", SYSTEM_PROMPT, build_user_message(articles, indicators), REPORT_TOOL["input_schema"])
    return normalize_report(raw)


def normalize_report(report):
    """AI 답이 조금 틀려도 사이트가 깨지지 않게 값을 정리해요."""
    def pick(value, allowed, default):
        return value if value in allowed else default

    b = report.get("briefing") or {}
    report["briefing"] = {
        "summary": str(b.get("summary", "")),
        "top_issue": str(b.get("top_issue", "")),
        "focus_region": str(b.get("focus_region", "")),
        "mood": pick(b.get("mood"), IMPACTS, "중립"),
    }
    issues = []
    for i in (report.get("issues") or [])[:15]:
        if not isinstance(i, dict) or not i.get("title"):
            continue
        try:
            importance = int(i.get("importance", 3))
        except (TypeError, ValueError):
            importance = 3

        def three(lines):
            lines = [str(x) for x in (lines or []) if x][:3]
            return lines or ["(요약 없음)"]

        issues.append({
            "title": str(i["title"]),
            "region": pick(i.get("region"), REGIONS, "기타"),
            "sector": pick(i.get("sector"), SECTORS, "기타"),
            "impact": pick(i.get("impact"), IMPACTS, "중립"),
            "importance": importance,
            "what": str(i.get("what", "")),
            "why": str(i.get("why", "")),
            "effect": str(i.get("effect", "")),
            "easy_summary": three(i.get("easy_summary")),
            "pro_summary": three(i.get("pro_summary")),
            "why_important": str(i.get("why_important", "")),
            "market_effects": [
                {"name": str(m.get("name", "")), "direction": pick(m.get("direction"), ["up", "down", "flat"], "flat"),
                 "reason": str(m.get("reason", ""))}
                for m in (i.get("market_effects") or [])[:4] if isinstance(m, dict)
            ],
            "article_ids": [str(x) for x in (i.get("article_ids") or [])],
        })
    report["issues"] = issues
    report["regions"] = [{"name": r.get("name"), "mood": pick(r.get("mood"), IMPACTS, "중립")}
                         for r in (report.get("regions") or []) if isinstance(r, dict) and r.get("name") in REGIONS]
    sectors = []
    for s in report.get("sectors") or []:
        if isinstance(s, dict) and s.get("name") in SECTORS:
            try:
                p = max(0, min(100, int(s.get("positive_percent", 50))))
            except (TypeError, ValueError):
                p = 50
            sectors.append({"name": s["name"], "positive_percent": p})
    report["sectors"] = sectors
    if not issues:
        raise RuntimeError("AI가 이슈를 하나도 만들지 못했어요")
    return report


# ─────────────────────────────── 4. 결과 정리·저장 ───────────────────────────────

def build_output(articles, indicators, report, sample=False, korea=None, korea_indicators=None, glossary=None):
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
        "model": "샘플 데이터" if sample else (ai.used_model or "AI"),
        "article_count": len(articles),
        "briefing": report.get("briefing", {}),
        "indicators": indicators,
        "issues": issues,
        "all_articles": [{k: a[k] for k in ("title", "source", "link", "published")} for a in articles],
        "regions": report.get("regions", []),
        "sectors": report.get("sectors", []),
        "korea": korea,
        "korea_indicators": korea_indicators or [],
        "glossary": glossary or [],
    }


def write_archive_index():
    """지난 날짜 목록(archive/index.json)을 만들어요. 사이트의 날짜 고르기에서 써요."""
    archive = DATA / "archive"
    dates = sorted((p.stem for p in archive.glob("*.json") if re.fullmatch(r"\d{4}-\d{2}-\d{2}", p.stem)),
                   reverse=True)
    (archive / "index.json").write_text(json.dumps({"dates": dates}, ensure_ascii=False), encoding="utf-8")


def save(output):
    DATA.mkdir(parents=True, exist_ok=True)
    (DATA / "archive").mkdir(exist_ok=True)
    text = json.dumps(output, ensure_ascii=False, indent=2)
    (DATA / "today.json").write_text(text, encoding="utf-8")
    if not output["sample"]:
        (DATA / "archive" / f"{output['date']}.json").write_text(text, encoding="utf-8")
    write_archive_index()
    if output.get("glossary") and not output["sample"]:
        total = update_dictionary(DATA / "glossary.json", output["glossary"], output["date"])
        print(f"  - 용어 사전: 오늘 {len(output['glossary'])}개, 전체 {total}개")
    print(f"저장 완료: site/data/today.json (이슈 {len(output['issues'])}개)")


# ─────────────────────────────── 샘플 모드 ───────────────────────────────

def sample_data():
    """인터넷과 API 키 없이 사이트가 잘 나오는지 확인하기 위한 가짜 데이터예요."""
    return json.loads((ROOT / "scripts" / "sample_report.json").read_text(encoding="utf-8"))


# ─────────────────────────────── 실행 ───────────────────────────────

def step(name, fn, *args):
    """추가 기능(한국 분석, 용어 사전, 주간 정리)은 실패해도 오늘 분석은 저장되게 해요."""
    try:
        return fn(*args)
    except Exception as e:
        print(f"  ! {name} 실패 (건너뛰고 계속해요): {e}")
        return None


def main():
    parser = argparse.ArgumentParser(description="세계경제 AI 데이터 만들기")
    parser.add_argument("--sample", action="store_true", help="인터넷·API 없이 샘플 데이터로 실행")
    parser.add_argument("--weekly", action="store_true", help="요일과 상관없이 주간 정리도 만들기")
    args = parser.parse_args()

    if args.sample:
        print("샘플 모드로 실행해요")
        s = sample_data()
        save(build_output(s["articles"], s["indicators"], normalize_report(s["report"]), sample=True,
                          korea=s.get("korea"), korea_indicators=s.get("korea_indicators"), glossary=s.get("glossary")))
        return

    if not ai.provider():
        sys.exit("AI 키가 없어요. GEMINI_API_KEY(무료) 또는 ANTHROPIC_API_KEY 를 넣어 주세요. README 의 '3단계'를 확인해 주세요.")

    print("1) 뉴스 수집")
    articles = fetch_articles(json.loads((CONFIG / "feeds.json").read_text(encoding="utf-8")))
    if len(articles) < 3:
        sys.exit(f"기사가 너무 적어요 ({len(articles)}개). 피드 주소를 확인해 주세요. 기존 데이터는 그대로 둬요.")

    print("2) 경제 지표 수집")
    indicators, korea_indicators, history = fetch_indicators(
        json.loads((CONFIG / "indicators.json").read_text(encoding="utf-8")))
    DATA.mkdir(parents=True, exist_ok=True)
    if any(h["closes"] for h in history.values()):
        (DATA / "indicators.json").write_text(json.dumps(history, ensure_ascii=False), encoding="utf-8")

    print(f"3) 세계 분석 (기사 {len(articles)}개, {ai.provider()})")
    report = analyze(articles, indicators)
    world = build_output(articles, indicators, report)  # 이슈 id·기사 연결이 된 상태

    print("4) 한국 집중 분석")
    korea = step("한국 분석", analyze_korea, articles, world["issues"], korea_indicators)

    print("5) 경제 용어 사전")
    glossary = step("용어 사전", make_glossary, world["issues"], korea) or []

    print("6) 저장")
    output = build_output(articles, indicators, report, korea=korea, korea_indicators=korea_indicators, glossary=glossary)
    save(output)

    today = datetime.now(KST).date()
    if args.weekly or os.environ.get("FORCE_WEEKLY") == "true" or is_weekly_day(today):
        print("7) 주간 정리")
        step("주간 정리", make_weekly, DATA, today, history)


if __name__ == "__main__":
    main()
