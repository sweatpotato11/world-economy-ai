# 세계경제 AI 🌏

AI가 매일 아침 세계 경제 뉴스를 읽고, 이슈별로 묶고, 쉽게 정리해서 대시보드 사이트에 올려 주는 프로그램이에요.

```
[뉴스 RSS] ─┐
            ├─▶ collect.py ─▶ Gemini AI 분석 (무료) ─▶ site/data/today.json ─▶ 사이트 (GitHub Pages)
[경제 지표] ─┘        ▲
                     └── GitHub Actions가 매일 오전 6시에 자동 실행
```

## 기능

| 화면 | 내용 |
|---|---|
| **오늘** (`index.html`) | AI 브리핑, 핵심 이슈, 지역·분야별 분위기, 읽은 기사 전체, 날짜 고르기 |
| **한국** (`korea.html`) | 한국 경제 핵심, 세계 이슈가 한국에 주는 영향, 산업별 분위기, 원/엔·원/위안 등 한국 지표 |
| **주간 정리** (`weekly.html`) | 매주 일요일, 지난 7일을 AI가 정리한 리포트와 이번 주 숫자 |
| **용어 사전** (`glossary.html`) | 매일 뉴스에 나온 어려운 용어가 쌓이는 사전. 본문에 밑줄 친 용어를 누르면 바로 설명이 나와요 |
| **큰 그래프** | 지표 카드를 누르면 1개월~1년 그래프 |
| **앱 설치** | 휴대폰에서 '홈 화면에 추가'하면 앱처럼 열려요 |

## 폴더 구성

| 파일 | 하는 일 |
|---|---|
| `scripts/collect.py` | 뉴스·지표 수집 → AI 분석 → 데이터 저장 (프로그램의 핵심) |
| `scripts/ai.py` | Gemini(무료)·Claude 를 부르는 도우미 |
| `scripts/korea.py` | 한국 집중 분석 |
| `scripts/glossary.py` | 경제 용어 사전 |
| `scripts/weekly.py` | 주간 정리 (일요일) |
| `config/feeds.json` | 뉴스를 가져올 언론사 RSS 주소 목록 |
| `config/indicators.json` | 맨 위에 보여줄 경제 지표 목록 |
| `site/` | 사이트 화면 (`index.html` 홈, `issue.html` 이슈 상세) |
| `site/data/today.json` | 오늘의 분석 결과 (자동으로 만들어져요) |
| `site/data/archive/` | 날짜별 기록 (매일 하나씩 쌓여요) |
| `site/data/weekly/` | 주간 정리 기록 |
| `site/data/glossary.json` | 지금까지 모은 용어 사전 |
| `site/data/indicators.json` | 큰 그래프용 1년 치 지표 |
| `.github/workflows/update.yml` | 매일 자동 실행 설정 |

---

## 설치하기 (처음 한 번만)

> 🙋 **3단계(구글 AI 키)는 부모님과 같이 하는 게 좋아요.** 돈은 안 들어요.

### 1단계. GitHub 계정 만들기
[github.com](https://github.com) 에서 가입해요. 이미 있으면 넘어가요.

### 2단계. 저장소 만들고 파일 올리기
1. 오른쪽 위 **+** → **New repository**
2. 이름: `world-economy-ai` / **Public** 선택 → **Create repository**
   - 무료 계정은 Public 저장소만 사이트(GitHub Pages)를 열 수 있어요. API 키는 따로 숨겨서 넣으니까 Public이어도 안전해요.
3. **uploading an existing file** 을 눌러서, 이 폴더 안의 파일과 폴더를 전부 끌어다 놓고 **Commit changes**
4. ⚠️ `.github` 폴더는 이름이 점(.)으로 시작해서 **끌어다 놓기로 안 올라가는 경우가 많아요.** 그럴 땐:
   - **Add file → Create new file**
   - 파일 이름 칸에 `.github/workflows/update.yml` 이라고 입력 (슬래시를 치면 폴더가 생겨요)
   - 내 컴퓨터의 `update.yml` 내용을 복사해서 붙여넣고 **Commit changes**

### 3단계. 무료 AI 키(Gemini) 만들고 넣기 — 돈 안 들어요
1. [aistudio.google.com](https://aistudio.google.com) 에 구글 계정으로 로그인
   - 나이 제한이 있을 수 있어서 **부모님 구글 계정**으로 만드는 게 안전해요. 카드 등록은 필요 없어요.
2. 왼쪽 메뉴 **Get API key** → **Create API key** → 나온 키(`AIza...`)를 복사
3. GitHub 저장소 → **Settings → Secrets and variables → Actions → New repository secret**
   - Name: `GEMINI_API_KEY`
   - Secret: 복사한 키 붙여넣기 → **Add secret**

> 🔒 API 키는 비밀번호예요. 코드 파일, 채팅, 사진에 절대 올리지 마세요. Secret에만 넣어요.

**비용은?** Gemini 무료 등급이라 0원이에요. 하루에 AI를 딱 한 번만 부르니까 무료 한도 안에 충분히 들어가요. (무료 등급은 보낸 내용이 구글 제품 개선에 쓰일 수 있는데, 우리는 공개된 뉴스 제목만 보내요.)

**나중에 Claude(유료)로 바꾸고 싶으면:** `GEMINI_API_KEY` Secret을 지우고 `ANTHROPIC_API_KEY` Secret을 넣으면 돼요. ([console.anthropic.com](https://console.anthropic.com) 에서 키 발급, 결제 필요, 한 달 몇 달러 정도)

### 4단계. 사이트 켜기
저장소 → **Settings → Pages** → Source를 **GitHub Actions** 로 선택

### 5단계. 첫 실행
1. 저장소 → **Actions** 탭 (처음이면 초록 버튼으로 활성화)
2. 왼쪽 **세계경제 AI 업데이트** → **Run workflow** → **Run workflow**
3. 2~3분 기다리면 초록 체크 ✅
4. 사이트 주소: `https://내아이디.github.io/world-economy-ai/`

이제 매일 새벽에 알아서 업데이트돼요! 🎉
(예약은 새벽 4시 17분인데, GitHub 사정에 따라 몇 시간 늦게 실행될 때도 있어요.)

**주간 정리를 지금 바로 만들고 싶으면:** Run workflow 를 누를 때 나오는 **"주간 정리도 지금 만들기"** 를 체크해요. (기록이 3일 이상 있어야 해요)

---

## 휴대폰에 앱처럼 설치하기

- **안드로이드(크롬):** 사이트 접속 → 오른쪽 위 ⋮ → **홈 화면에 추가** (또는 **앱 설치**)
- **아이폰(사파리):** 사이트 접속 → 아래 공유 버튼 → **홈 화면에 추가**
- **컴퓨터(크롬):** 사이트 오른쪽 위 **앱 설치** 버튼, 또는 주소창 오른쪽 설치 아이콘

## 내 컴퓨터에서 미리 보기

Python이 설치되어 있으면:

```bash
# 샘플 데이터로 테스트 (인터넷·API 키 없이)
python scripts/collect.py --sample

# 사이트 열기 → 브라우저에서 http://localhost:8000
python -m http.server 8000 -d site
```

`index.html` 을 더블클릭해서 열면 데이터가 안 보여요. 꼭 위 방법으로 열어요.

진짜 데이터로 내 컴퓨터에서 돌려보려면:
```bash
pip install -r requirements.txt
# Mac/Linux
export GEMINI_API_KEY=AIza...
# Windows (PowerShell)
$env:GEMINI_API_KEY="AIza..."
python scripts/collect.py
```

---

## 바꿔 보기

- **언론사 추가/삭제:** `config/feeds.json` 에 `{"name": "이름", "url": "RSS 주소"}` 추가
- **지표 추가:** `config/indicators.json` 에 야후 파이낸스 기호 추가 (예: 닛케이 `^N225`, 비트코인 `BTC-USD`). 한국 화면 지표는 `korea_indicators` 에
- **업데이트 시간:** `update.yml` 의 `cron: "17 19 * * *"` (UTC 기준이라 한국 시간에서 9시간 빼기. 정각(00분)은 GitHub가 바빠서 늦어지기 쉬워요)
- **모델 바꾸기:** Settings → Secrets and variables → Actions → **Variables** 탭 → `GEMINI_MODEL` 에 원하는 Gemini 모델 이름 (쉼표로 여러 개 쓰면 앞에서부터 시도). 기본값은 `gemini-3.6-flash,gemini-3.5-flash,gemini-3.5-flash-lite`
- **AI 분석 방식:** `scripts/collect.py` 의 `SYSTEM_PROMPT` 를 고치면 AI가 쓰는 글의 스타일이 바뀌어요

## 안 될 때

| 증상 | 해결 |
|---|---|
| Actions에서 빨간 X ❌ | 실패한 실행을 눌러서 빨간 단계의 로그를 확인해요. 그대로 Claude에게 보여주면 같이 고칠 수 있어요 |
| `AI 키가 없어요` | 3단계 Secret 이름(`GEMINI_API_KEY`) 철자 확인 |
| `HTTP 429` | 무료 한도 초과예요. 하루 지나면 풀려요. 계속되면 `GEMINI_MODEL` 을 `gemini-3.5-flash-lite` 로 |
| `HTTP 404` | 모델 이름이 바뀌었어요. aistudio.google.com 에서 지금 있는 Flash 모델 이름을 `GEMINI_MODEL` 에 넣어요 |
| `기사가 너무 적어요` | `feeds.json` 의 주소가 바뀌었을 수 있어요. 다른 RSS로 교체 |
| 사이트가 404 | 4단계 Pages 설정 확인, 첫 실행이 성공했는지 확인 |
| 지표가 `—` 로 나옴 | 야후 파이낸스 접속이 잠깐 막힌 거예요. 다음 날 보통 돌아와요 |

---

## 나중에 모든 사람에게 공개할 때 체크리스트

- [ ] **저작권:** 지금처럼 기사 원문은 올리지 않고 *AI 요약 + 원문 링크*만 유지하기
- [ ] **AI 안내:** "AI가 만든 분석이라 틀릴 수 있음", "투자 조언 아님" 문구 유지하기
- [ ] **데이터 출처:** 야후 파이낸스(yfinance)는 개인용 비공식 도구예요. 공개 서비스라면 공식 데이터(한국은행 ECOS, 미국 FRED 등)로 바꾸는 걸 검토하기
- [ ] **RSS 이용 조건:** 각 언론사 RSS 이용 약관 확인하기
- [ ] **비용:** 방문자가 늘어도 AI는 하루 한 번만 돌아서 그대로 무료예요. 업데이트 횟수를 많이 늘리면 무료 한도를 넘을 수 있어요
- [ ] **도메인:** 원하면 나만의 주소(예: `worldecon.ai`)를 사서 GitHub Pages에 연결할 수 있어요
