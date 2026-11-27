"""
📅 주간 정리 리포트 — 매주 일요일, 지난 7일 치 기록을 모아 AI가 '이번 주 세계 경제'를 정리해요.
결과: site/data/weekly/날짜.json, site/data/weekly/index.json
"""

import json
from datetime import date, timedelta

from ai import call_ai, pick, text_list

IMPACTS = ["긍정", "부정", "중립"]

SCHEMA = {
    "type": "object",
    "required": ["title", "summary", "mood", "top_stories", "korea", "next_week"],
    "properties": {
        "title": {"type": "string", "description": "이번 주를 한 줄로 표현하는 제목, 30자 이내"},
        "summary": {"type": "string", "description": "이번 주 세계 경제 흐름 4~6문장"},
        "mood": {"type": "string", "enum": IMPACTS},
        "top_stories": {
            "type": "array", "minItems": 3, "maxItems": 6,
            "description": "이번 주 가장 중요했던 이야기, 중요한 순서",
            "items": {"type": "object", "required": ["title", "region", "story", "days", "impact"],
                      "properties": {
                          "title": {"type": "string"},
                          "region": {"type": "string"},
                          "story": {"type": "string", "description": "한 주 동안 어떻게 흘러갔는지 3~4문장 (처음 → 변화 → 지금)"},
                          "days": {"type": "array", "items": {"type": "string"}, "description": "관련 날짜 YYYY-MM-DD (주어진 날짜만)"},
                          "impact": {"type": "string", "enum": IMPACTS}}},
        },
        "korea": {"type": "string", "description": "이번 주 한국 경제 정리 3~4문장"},
        "next_week": {"type": "array", "items": {"type": "string"}, "maxItems": 5, "description": "다음 주에 지켜볼 것"},
    },
}

SYSTEM = """당신은 세계 경제 주간 리포트를 쓰는 애널리스트예요.
지난 7일 동안 매일 정리한 분석을 읽고 '이번 주 세계 경제'를 정리하세요.

규칙
- 모든 글은 한국어로, 중학생도 읽을 수 있게 쉽고 정확하게 써요.
- 주어진 기록에 없는 사실이나 숫자를 지어내지 마세요.
- 여러 날에 걸쳐 이어진 이야기는 하나로 묶어서 흐름을 보여줘요.
- 투자 추천은 하지 마세요."""


def load_week(archive_dir, end):
    days = []
    for n in range(6, -1, -1):
        d = (end - timedelta(days=n)).isoformat()
        p = archive_dir / f"{d}.json"
        if p.exists():
            days.append(json.loads(p.read_text(encoding="utf-8")))
    return days


def week_numbers(history, start, end):
    """지표 1년 기록에서 이번 주 시작~끝 변화를 계산해요 (AI가 아니라 계산)."""
    out = []
    for name, h in history.items():
        pts = [(d, c) for d, c in zip(h["dates"], h["closes"]) if start.isoformat() <= d <= end.isoformat()]
        before = [(d, c) for d, c in zip(h["dates"], h["closes"]) if d < start.isoformat()]
        if before:
            pts = [before[-1]] + pts  # 지난주 마지막 값부터 비교
        if len(pts) < 2:
            continue
        first, last = pts[0][1], pts[-1][1]
        if h.get("suffix") == "%":
            change, diff = f"{last - first:+.2f}%p", last - first
        else:
            diff = (last - first) / first * 100
            change = f"{diff:+.2f}%"
        out.append({"name": name, "value": f"{last:,.{h.get('decimals', 2)}f}{h.get('suffix', '')}", "change": change,
                    "direction": "up" if diff > 0 else "down" if diff < 0 else "flat"})
    return out


def make_weekly(data_dir, today, history):
    end = today
    start = end - timedelta(days=6)
    days = load_week(data_dir / "archive", end)
    if len(days) < 3:
        print(f"  - 주간 정리: 기록이 {len(days)}일 치뿐이라 건너뛰어요 (3일 이상 필요)")
        return None

    blocks = []
    for d in days:
        lines = [f"### {d['date']}", f"브리핑: {d['briefing'].get('summary', '')}"]
        lines += [f"- {i['title']} ({i['region']}, {i['impact']}): {i['what']}" for i in d["issues"][:10]]
        if d.get("korea"):
            lines.append(f"한국: {d['korea'].get('summary', '')}")
        blocks.append("\n".join(lines))
    r = call_ai("주간 정리", SYSTEM, "\n\n".join(blocks), SCHEMA, max_tokens=8000)

    valid_days = {d["date"] for d in days}
    report = {
        "week_start": start.isoformat(),
        "week_end": end.isoformat(),
        "day_count": len(days),
        "title": str(r.get("title", "")),
        "summary": str(r.get("summary", "")),
        "mood": pick(r.get("mood"), IMPACTS, "중립"),
        "top_stories": [{"title": str(s.get("title", "")), "region": str(s.get("region", "")),
                         "story": str(s.get("story", "")), "impact": pick(s.get("impact"), IMPACTS, "중립"),
                         "days": sorted(x for x in (s.get("days") or []) if x in valid_days)}
                        for s in (r.get("top_stories") or [])[:6] if isinstance(s, dict) and s.get("title")],
        "korea": str(r.get("korea", "")),
        "next_week": text_list(r.get("next_week"), 5),
        "numbers": week_numbers(history, start, end),
    }

    wdir = data_dir / "weekly"
    wdir.mkdir(exist_ok=True)
    (wdir / f"{end.isoformat()}.json").write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    weeks = sorted((p.stem for p in wdir.glob("????-??-??.json")), reverse=True)
    (wdir / "index.json").write_text(json.dumps({"weeks": weeks}), encoding="utf-8")
    print(f"  - 주간 정리 저장: weekly/{end.isoformat()}.json")
    return report


def is_weekly_day(today: date):
    return today.weekday() == 6  # 일요일
