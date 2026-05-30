# API 키 발급 가이드

이 문서는 경쟁사 모니터링 시스템에서 사용하는 각 API 키의 단계별 발급 방법을 설명합니다.  
발급한 키는 모두 `.env` 파일에 저장합니다. **`.env` 파일은 절대 Git에 커밋하지 마세요.**

---

## 목차

1. [META_ACCESS_TOKEN — Instagram Business Discovery](#1-meta_access_token--instagram-business-discovery)
2. [YOUTUBE_API_KEY — YouTube Data API v3](#2-youtube_api_key--youtube-data-api-v3)
3. [NAVER_CLIENT_ID / NAVER_CLIENT_SECRET — Naver Open API](#3-naver_client_id--naver_client_secret--naver-open-api)
4. [ANTHROPIC_API_KEY — Claude API (선택)](#4-anthropic_api_key--claude-api-선택)
5. [보안 주의 사항](#5-보안-주의-사항)

---

## 1. `META_ACCESS_TOKEN` — Instagram Business Discovery

**포털:** [https://developers.facebook.com](https://developers.facebook.com)

Instagram Business Discovery API를 사용하려면 Facebook 앱, Facebook 페이지, 그리고 그 페이지에 연결된 Instagram Business/Creator 계정이 모두 필요합니다.

### 1-1. 사전 요건 확인

- **본인 Facebook 계정**이 있어야 합니다.
- **본인 소유의 Facebook 페이지**가 있어야 합니다 (브랜드 페이지).
- **본인 소유의 Instagram Business 또는 Creator 계정**이 있어야 하며, 위 Facebook 페이지와 연결되어 있어야 합니다.
  - Instagram 앱 → 설정 및 활동 → 계정 종류 및 도구 → 비즈니스 계정으로 전환 (또는 크리에이터 계정)
  - Instagram 앱 → 설정 → 계정 → Facebook 페이지와 연결

### 1-2. Facebook 앱 생성

1. [https://developers.facebook.com](https://developers.facebook.com) 에 로그인 → 우측 상단 **"내 앱"** → **"앱 만들기"** 클릭.
2. 사용 목적: **"기타"** 선택 → **다음**.
3. 앱 유형: **"비즈니스"** 선택 → **다음**.
4. 앱 이름 입력 (예: `my-brand-monitor`) → 비즈니스 계정 선택 (없으면 "없음" 가능) → **"앱 만들기"** 클릭.
5. 앱 대시보드가 열리면 왼쪽 메뉴에서 **"제품 추가"** → **"Instagram Graph API"** 항목에서 **"설정"** 클릭.

### 1-3. Instagram 비즈니스 계정 연결

1. 앱 대시보드 왼쪽 메뉴 → **Instagram Graph API → 설정**.
2. **"Instagram 비즈니스 계정 추가"** → Facebook 페이지를 선택해 연결합니다.
3. 연결이 완료되면 해당 Facebook 페이지에 연결된 Instagram 비즈니스 계정이 앱에 등록됩니다.

### 1-4. IG User ID 확인 (`config.yaml`의 `instagram.ig_user_id`)

1. [Graph API Explorer](https://developers.facebook.com/tools/explorer/) 접속.
2. 우측 상단 "Meta 앱" 드롭다운에서 방금 만든 앱 선택.
3. **"사용자 또는 페이지"** 드롭다운에서 **"페이지 액세스 토큰 받기"** → 본인 Facebook 페이지 선택.
4. Graph API 입력창에 `me/accounts` 입력 → **"쿼리 제출"**.
5. 응답 JSON에서 해당 페이지의 `id` 확인 후, 다시 입력창에 `{PAGE_ID}?fields=instagram_business_account` 입력.
6. 응답에서 `instagram_business_account.id` 값이 **IG User ID**입니다.
7. 이 값을 `config.yaml`의 `instagram.ig_user_id`에 입력하세요.

```yaml
# config.yaml
instagram:
  ig_user_id: "17841400000000000"   # <- 여기에 입력
```

### 1-5. 장기 액세스 토큰(Long-lived Token) 발급

단기 토큰(1시간)은 운영 용도로 적합하지 않습니다. 장기 토큰(약 60일)을 발급받으세요.

1. Graph API Explorer에서 **"액세스 토큰 생성"** → **"사용자 액세스 토큰"** 선택.
2. 권한(Permissions) 선택 시 다음을 반드시 체크하세요:
   - `instagram_basic`
   - `pages_read_engagement`
   - `pages_show_list`
3. **"액세스 토큰 생성"** → 팝업에서 앱 승인.
4. 발급된 단기 토큰을 장기 토큰으로 교환합니다. 터미널에서 아래 명령 실행:
   ```
   curl "https://graph.facebook.com/v19.0/oauth/access_token
     ?grant_type=fb_exchange_token
     &client_id={APP_ID}
     &client_secret={APP_SECRET}
     &fb_exchange_token={SHORT_LIVED_TOKEN}"
   ```
   - `APP_ID` / `APP_SECRET` : 앱 대시보드 → **설정 → 기본 설정** 에서 확인.
5. 응답의 `access_token` 값을 `.env`의 `META_ACCESS_TOKEN`에 입력하세요.

```dotenv
# .env
META_ACCESS_TOKEN=EAAxxxxxxxxxxxxxxxx...
```

### 1-6. Business Discovery 동작 원리 및 제한

- **조회 대상 계정이 반드시 Instagram 비즈니스 또는 크리에이터 계정**이어야 합니다. 개인 계정은 조회 불가합니다.
- `config.yaml`의 `competitors[].instagram_username`에 입력하는 핸들이 비즈니스/크리에이터 계정인지 먼저 확인하세요.
- 장기 토큰도 **약 60일** 후 만료됩니다. 만료 전 Graph API Explorer에서 동일 절차로 재발급하거나, Meta Business Suite의 시스템 사용자(System User) 토큰(만료 없음)을 사용하는 것을 장기적으로 권장합니다.

---

## 2. `YOUTUBE_API_KEY` — YouTube Data API v3

**포털:** [https://console.cloud.google.com](https://console.cloud.google.com)

### 2-1. Google Cloud 프로젝트 생성

1. [Google Cloud Console](https://console.cloud.google.com) 에 Google 계정으로 로그인.
2. 상단 프로젝트 선택 드롭다운 → **"새 프로젝트"** → 프로젝트 이름 입력 (예: `competitor-monitor`) → **"만들기"**.

### 2-2. YouTube Data API v3 활성화

1. 왼쪽 메뉴 → **"API 및 서비스"** → **"라이브러리"**.
2. 검색창에 `YouTube Data API v3` 입력 → 결과 클릭.
3. **"사용 설정"** 클릭.

### 2-3. API 키 생성

1. 왼쪽 메뉴 → **"API 및 서비스"** → **"사용자 인증 정보"**.
2. 상단 **"+ 사용자 인증 정보 만들기"** → **"API 키"** 선택.
3. 키가 생성되면 **"키 제한"** 클릭 (보안 강화 권장):
   - "API 제한" → "키 제한" → `YouTube Data API v3` 선택.
   - **"저장"** 클릭.
4. 생성된 키를 복사해 `.env`의 `YOUTUBE_API_KEY`에 입력하세요.

```dotenv
# .env
YOUTUBE_API_KEY=AIzaSyxxxxxxxxxxxxxxxxxxxxxxx
```

### 2-4. 채널 ID 확인 (`config.yaml`의 `youtube_channel_id`)

`youtube_channel_id`는 `UC`로 시작하는 채널 고유 ID입니다. 채널 핸들(`@channelname`)과 다릅니다.

확인 방법:
- 채널 페이지 → 채널 이름 아래 **"채널 공유"** → 링크에 포함된 `/channel/UCxxxxxxxxxx` 부분.
- 또는 채널 페이지 → **"정보"** 탭 → "채널 공유" → 링크에서 확인.
- 핸들만 알고 ID를 모를 경우: [https://www.youtube.com/@핸들/about](https://www.youtube.com) 접속 후 페이지 소스에서 `"channelId"` 값 검색.

```yaml
# config.yaml
competitors:
  - name: "New Balance Kids"
    youtube_channel_id: "UCxxxxxxxxxxxxxxxxxxxxxx"   # <- UC로 시작하는 채널 ID
```

### 2-5. 할당량 안내

- 기본 할당량: **10,000 유닛/일** (무료).
- 채널 통계 조회 1회 ≈ 1~3 유닛. 최신 영상 목록 조회 1회 ≈ 100 유닛.
- 경쟁사가 10개 이하이면 일반적으로 충분합니다.
- 할당량 초과 시 Google Cloud Console → API 및 서비스 → 할당량에서 증가 요청 가능 (유료 심사).

---

## 3. `NAVER_CLIENT_ID` / `NAVER_CLIENT_SECRET` — Naver Open API

**포털:** [https://developers.naver.com](https://developers.naver.com)

### 3-1. Naver 개발자 센터 가입 및 로그인

1. [https://developers.naver.com](https://developers.naver.com) 접속 → Naver 계정으로 로그인.
2. 상단 메뉴 **"Application"** → **"애플리케이션 등록"** 클릭.

### 3-2. 애플리케이션 등록

1. **애플리케이션 이름** 입력 (예: `competitor-monitor`).
2. **사용 API** 항목에서 아래 두 가지를 모두 추가하세요:
   - **검색** — 블로그, 카페글, 뉴스 건수 수집에 사용 (`NaverSearchCount` 레코드).
   - **데이터랩(검색어 트렌드)** — 상대 트렌드 지수 수집에 사용 (`NaverDataLabPoint` 레코드).
3. **비로그인 오픈 API 서비스 환경** → **"WEB 설정"** → 웹 서비스 URL에 `http://localhost` 입력 (로컬 테스트용; CI에서는 사용하지 않음).
4. **"등록하기"** 클릭.

### 3-3. Client ID / Secret 확인

1. 등록 완료 후 애플리케이션 목록에서 해당 앱 클릭.
2. **Client ID**와 **Client Secret** 값을 복사해 `.env`에 입력하세요.

```dotenv
# .env
NAVER_CLIENT_ID=xxxxxxxxxxxxxxxx
NAVER_CLIENT_SECRET=xxxxxxxxxxxxxxxx
```

### 3-4. 각 API별 역할 및 제한

**검색 API (`naver.search_sources`)**

- `config.yaml`의 `naver.search_sources`에 지정한 소스(`blog`, `cafearticle`, `news`)별로 키워드 검색 결과 총 건수를 수집합니다.
- 일 할당량 약 **25,000건**. 경쟁사 수 × 키워드 수 × 소스 수가 많을수록 소진이 빠릅니다.
- 할당량 절약 팁: `search_sources`를 `["blog", "news"]`로 줄이거나, 경쟁사 수를 단계적으로 늘리세요.

**DataLab (검색어 트렌드) API (`naver.datalab_keyword_groups`)**

- `config.yaml`의 `naver.datalab_keyword_groups`에 정의된 그룹별 상대 검색량 트렌드를 수집합니다.
- 반환 `ratio` 값은 **절대 검색량이 아닌 0–100 상대 지수**입니다. 조회 기간 내 최대 검색량을 100으로 정규화한 값으로, "이번 주 검색 N회" 같은 절대 수치를 알 수는 없습니다.
- 비교 기간 내 트렌드 방향 및 브랜드 간 상대적 관심도 비교에 활용하세요.

```yaml
# config.yaml
naver:
  search_sources: ["blog", "cafearticle", "news"]
  datalab_keyword_groups:
    - groupName: "뉴발란스 키즈"            # keyword_group 컬럼의 식별자
      keywords: ["뉴발란스 키즈", "뉴발란스키즈"]
```

---

## 4. `ANTHROPIC_API_KEY` — Claude API (선택)

**포털:** [https://console.anthropic.com](https://console.anthropic.com)

`ANTHROPIC_API_KEY`는 `config.yaml`에서 `analysis.llm.enabled: true`로 설정했을 때만 사용됩니다. 기본값은 `false`이므로 이 키 없이도 수집·분석·리포트가 모두 동작합니다.

### 4-1. Anthropic Console 가입 및 로그인

1. [https://console.anthropic.com](https://console.anthropic.com) 접속 → 회원가입 또는 Google 계정으로 로그인.
2. 결제 수단(신용카드)을 등록하거나 크레딧을 구매해야 API를 사용할 수 있습니다.  
   **Claude API는 유료입니다.** 사용량에 따라 과금됩니다.

### 4-2. API 키 생성

1. 콘솔 좌측 메뉴 → **"API Keys"** → **"Create Key"**.
2. 키 이름 입력 (예: `competitor-monitor`) → **"Create Key"**.
3. 생성 즉시 표시되는 키 값을 복사하세요. **이후 다시 조회할 수 없습니다.**
4. `.env`의 `ANTHROPIC_API_KEY`에 입력하세요.

```dotenv
# .env
ANTHROPIC_API_KEY=sk-ant-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

### 4-3. config.yaml에서 LLM 활성화

```yaml
# config.yaml
analysis:
  llm:
    enabled: true                  # false → 키 없어도 동작, true → Claude 요약 활성화
    model: "claude-sonnet-4-6"     # 사용할 Claude 모델
```

### 4-4. 주의 사항

- LLM 기능은 **선택(optional)**입니다. 비용이 발생하므로 필요한 경우에만 활성화하세요.
- GitHub Actions에서 LLM을 사용하려면 저장소 시크릿에 `ANTHROPIC_API_KEY`를 등록하고 `config.yaml`에서 `enabled: true`로 설정하세요.

---

## 5. 보안 주의 사항

- **`.env` 파일은 절대 Git에 커밋하지 마세요.** `.gitignore`에 `.env`가 포함되어 있는지 반드시 확인하세요.
- API 키가 실수로 커밋되었다면 즉시 해당 키를 **폐기(revoke)하고 재발급**하세요. Git 이력에서 삭제해도 이미 노출된 것으로 간주해야 합니다.
- GitHub Actions에서는 키를 **저장소 시크릿(Settings → Secrets and variables → Actions)**에만 저장하세요. 워크플로우 로그에 키 값이 출력되지 않도록 `echo` 등을 사용하지 마세요.
- 최소 권한 원칙을 따르세요: YouTube API 키는 YouTube Data API v3만 허용, Meta 토큰은 필요한 권한(`instagram_basic`, `pages_read_engagement`, `pages_show_list`)만 부여하세요.
- 정기적으로 키를 교체하고, 특히 Meta 액세스 토큰은 약 60일 만료 전에 갱신하세요.
