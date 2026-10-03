# 물류·해외영업 뉴스 + 자동 브리핑 (무료)

매일 한국시간 06:00에 GitHub Actions가 다음을 자동 실행합니다.
1. `scripts/fetch_news.py` : 구글 뉴스 RSS에서 뉴스 수집 → `data/news.json`
2. `scripts/make_briefing.py` : 무슨 일/왜/영향 분석, 면접 답변, 필수 개념 생성 → `data/briefing.json`
   - Gemini 무료 API 키가 있으면 AI가 작성, 없거나 실패하면 규칙 기반 틀로 자동 대체
3. `index.html` 이 두 파일을 읽어 보여줍니다 (탭: 전체 / 해외영업 / 물류·해운 / 브리핑 / 저장함)

## 처음 설정
1. 저장소에 파일 업로드 (`.github` 폴더 포함) → Settings → Pages → Branch `main`, `/ (root)`
2. Settings → Actions → General → Workflow permissions → "Read and write permissions"
3. (선택, AI 분석) Google AI Studio(aistudio.google.com)에서 API 키 발급 → 결제 설정은 켜지 마세요
   → 저장소 Settings → Secrets and variables → Actions → New repository secret
   → 이름 `GEMINI_API_KEY`, 값에 키 붙여넣기. 키는 코드나 index.html에 절대 넣지 마세요.
4. Actions 탭 → Daily news → Run workflow 로 한 번 실행
5. 실행 로그의 "Briefing" 단계에서 `브리핑 저장(ai)` 또는 `(rule)`을 확인

## 모델 이름이 바뀌었을 때
Settings → Secrets and variables → Actions → Variables 탭에 `GEMINI_MODEL`을 만들고 AI Studio에 표시된 모델 이름을 넣으세요.
(비워 두면 gemini-flash-latest → gemini-flash-lite-latest → gemini-2.5-flash 순으로 시도)

## 알아둘 점
- 브리핑 화면 상단에 `AI 자동 생성` 또는 `규칙 기반` 표시가 나옵니다. AI 분석은 기사 제목만 보고 쓰므로 수치는 원문에서 확인하세요.
- Gemini 무료 요금제는 입력 내용이 Google 제품 개선에 쓰일 수 있습니다. 여기서는 공개 뉴스 제목만 보냅니다.
- 무료 한도와 모델은 바뀔 수 있으니 AI Studio에서 현재 조건을 확인하세요.
- 공개 저장소에 60일 이상 활동이 없으면 예약 실행이 멈출 수 있어 가끔 Actions 탭을 확인하세요.

## 문제 해결
- Actions 탭에 "Daily news"가 안 보임: `.github/workflows/daily.yml`이 빠진 것입니다. Add file → Create new file에서
  파일명 `.github/workflows/daily.yml` 입력 후 `workflow-copy/daily.yml` 내용을 붙여넣고 Commit 하세요.
- 사이트가 비어 있음: Actions 실행 로그의 FAIL 줄을 확인하세요.
- 브리핑 탭이 비어 있음: Actions를 한 번 실행하세요 (데이터가 있어야 생성됩니다).
