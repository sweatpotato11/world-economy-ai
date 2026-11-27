"""
AI 부르기 — Gemini(무료)와 Claude(유료) 둘 다 같은 방법으로 부를 수 있게 해 주는 도우미

call_ai(이름, 지시문, 내용, JSON 스키마) → 파이썬 딕셔너리
  - GEMINI_API_KEY 가 있으면 Gemini, 없고 ANTHROPIC_API_KEY 가 있으면 Claude 를 써요.
"""

import json
import os
import re
import time

CLAUDE_MODEL = os.environ.get("CLAUDE_MODEL") or "claude-sonnet-5-5"
# Gemini 모델: 앞에서부터 시도하고, 안 되면(없어졌거나 한도 초과) 다음 모델로 넘어가요.
GEMINI_MODELS = [m.strip() for m in (os.environ.get("GEMINI_MODEL") or
                 "gemini-3.6-flash,gemini-3.5-flash,gemini-3.5-flash-lite").split(",") if m.strip()]

used_model = None  # 마지막으로 실제 사용한 모델 이름 (사이트에 표시)
_last_call = 0.0


def provider():
    if os.environ.get("GEMINI_API_KEY"):
        return "gemini"
    if os.environ.get("ANTHROPIC_API_KEY"):
        return "claude"
    return None


def call_ai(name, system, user, schema, max_tokens=16000):
    """AI에게 묻고, schema 모양의 JSON 결과를 돌려받아요."""
    global _last_call
    # 무료 등급은 1분에 부를 수 있는 횟수가 정해져 있어서, 연달아 부를 땐 조금 쉬어요.
    wait = 8 - (time.time() - _last_call)
    if wait > 0:
        time.sleep(wait)
    try:
        if provider() == "gemini":
            return _gemini(name, system, user, schema)
        return _claude(name, system, user, schema, max_tokens)
    finally:
        _last_call = time.time()


def _gemini(name, system, user, schema):
    global used_model
    import urllib.error
    import urllib.request

    prompt = (system + "\n\n결과는 아래 JSON 스키마에 맞는 JSON 하나로만 답해요. 다른 글은 쓰지 마세요.\n\n## JSON 스키마\n"
              + json.dumps(schema, ensure_ascii=False))
    body = json.dumps({
        "systemInstruction": {"parts": [{"text": prompt}]},
        "contents": [{"role": "user", "parts": [{"text": user}]}],
        "generationConfig": {"responseMimeType": "application/json", "temperature": 0.3},
    }).encode()

    last_error = None
    for model in GEMINI_MODELS:
        for attempt in range(2):
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
            req = urllib.request.Request(url, data=body, method="POST", headers={
                "Content-Type": "application/json",
                "x-goog-api-key": os.environ["GEMINI_API_KEY"],
            })
            try:
                with urllib.request.urlopen(req, timeout=300) as resp:
                    data = json.loads(resp.read())
            except urllib.error.HTTPError as e:
                detail = e.read().decode(errors="replace")[:300]
                last_error = f"{model}: HTTP {e.code} {detail}"
                print(f"  ! [{name}] {last_error}")
                if e.code in (429, 500, 503) and attempt == 0:  # 잠깐 바쁘면 1분 쉬고 다시
                    time.sleep(60)
                    continue
                break  # 없는 모델(404) 등은 다음 모델로
            except Exception as e:
                last_error = f"{model}: {e}"
                print(f"  ! [{name}] {last_error}")
                continue

            try:
                text = "".join(p.get("text", "") for p in data["candidates"][0]["content"]["parts"])
                result = json.loads(re.sub(r"^```(?:json)?|```$", "", text.strip()).strip())
            except Exception as e:
                last_error = f"{model}: 답을 JSON으로 읽지 못했어요 ({e})"
                print(f"  ! [{name}] {last_error}")
                continue
            usage = data.get("usageMetadata", {})
            print(f"  - [{name}] {model}, 토큰 입력 {usage.get('promptTokenCount')} / 출력 {usage.get('candidatesTokenCount')}")
            used_model = model
            return result
    raise RuntimeError(f"[{name}] Gemini 실패: {last_error}")


def _claude(name, system, user, schema, max_tokens):
    global used_model
    import anthropic

    client = anthropic.Anthropic()
    tool = {"name": "submit", "description": "결과를 제출해요.", "input_schema": schema}
    for attempt in range(2):
        resp = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=max_tokens,
            system=system + "\n\n결과는 반드시 submit 도구로 제출해요.",
            tools=[tool],
            messages=[{"role": "user", "content": user}],
        )
        for block in resp.content:
            if block.type == "tool_use" and block.name == "submit":
                print(f"  - [{name}] {CLAUDE_MODEL}, 토큰 입력 {resp.usage.input_tokens} / 출력 {resp.usage.output_tokens}")
                used_model = CLAUDE_MODEL
                return block.input
        print(f"  ! [{name}] AI가 결과를 도구로 내지 않았어요 (시도 {attempt + 1})")
    raise RuntimeError(f"[{name}] Claude 결과를 받지 못했어요")


def pick(value, allowed, default):
    """AI 답이 정해진 값 중 하나가 아니면 기본값으로 바꿔요."""
    return value if value in allowed else default


def text_list(values, limit, fallback=None):
    out = [str(v).strip() for v in (values or []) if str(v).strip()][:limit]
    return out or ([fallback] if fallback else [])
