# 🏢 오피스텔 에어비앤비 투자 판정 도구

> 중앙대학교 부동산금융론 개인 프로젝트  
> 오피스텔 단기임대(에어비앤비) vs 장기임대 수익성을 실거래 데이터 기반으로 비교하고 **"해도 될까?"를 판정**하는 Streamlit 웹앱

[![Streamlit App](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://officetel-analyzer.streamlit.app/)

**👉 [바로 실행하기 → officetel-analyzer.streamlit.app](https://officetel-analyzer.streamlit.app/)**

---

## 📌 프로젝트 개요

사업자가 점찍은 오피스텔 매물에 **매입가·ADR·예약률**을 입력하면,  
단기임대(STR) vs 장기임대(LTR)의 **IRR·NPV·손익분기**를 자동 계산하고  
**추천 / 신중 / 비추천** 판정을 내려줍니다.

- 추정치 없음 — 전부 실측 데이터 (국토부 실거래가 + airbtics + 한국은행 ECOS)
- 한국형 보증금 모델 적용 (초기 실투자금 차감, 매각 시 rollover)
- 교수님 수업 예제 (Parker Road Plaza)로 계산 엔진 교차검증 완료

---

## 🖥️ 화면 구성 (3탭)

| 탭 | 기능 |
|----|------|
| 📊 **시세 둘러보기** | airbtics 실측 13개 지역 ADR·점유율 + IRR 기준 TOP10 랭킹 |
| 🎯 **내 매물 판정** | 매입가·ADR·예약률 입력 → 추천/신중/비추천 판정 + 리스크 히트맵 |
| ⚖️ **법적 리스크** | 오피스텔 단기임대 합법 요건·위반 리스크·합법 대안 안내 |

---

## 🧮 핵심 계산 모델

```
[단기임대 STR]                        [장기임대 LTR]
PGI  = ADR × 365                      PGI  = 월세 × 12
EGI  = PGI × 점유율 - 플랫폼수수료    EGI  = PGI × (1 - 공실률 5%)
NOI  = EGI - 청소비 - 고정운영비       NOI  = EGI × (1 - 운영비율 12%)
         ↓                                      ↓
BTCF = NOI - 연간원리금(CPM)          BTCF = NOI - 연간원리금(CPM)
ATCF = BTCF - 소득세                  ATCF = BTCF - 소득세
         ↓                                      ↓
    IRR / NPV / Equity Multiple            IRR / NPV / Equity Multiple
```

**한국형 핵심:**
- 실투자금(STR) = 매입가 × (1-LTV) + 셋업비
- 실투자금(LTR) = 매입가 × (1-LTV) − 보증금  ← 보증금이 초기투자금을 줄임
- 매각 시 보증금은 신규 임차인 보증금으로 반환 → 순현금유출 0

**손익분기 일수:**
```
월 최소 예약일 = (LTR_NOI + 고정운영비) ÷ (ADR × 0.9 − 청소비) ÷ 12
```

---

## 📊 주요 가정값

| 항목 | 값 | 출처 |
|------|-----|------|
| 대출금리 | **BOK ECOS 실측** (예: 4.20%) | 한국은행 예금은행 대출금리 |
| Cap Rate | 5.0% | 수업 기준 한국 오피스텔 시장 통상값 |
| NOI 성장률 | 2.0% / 년 | 장기 물가상승률 근사치 |
| 종합소득세율 | 35% | 중간 구간 추정 |
| LTR 공실률 | 5% | 오피스텔 일반 가정 |
| LTR 운영비율 | 12% | 관리비·수선비 기준 |
| 건물 비중 | 80% | 건물 80% / 토지 20% (감가상각) |
| STR 플랫폼 수수료 | 10% | 에어비앤비 호스트 수수료 |
| STR 셋업비 기본값 | 700만원 | 인테리어·가구·가전 (탭2에서 수정 가능) |

---

## 📡 데이터 출처

| 데이터 | 출처 | 링크 |
|--------|------|------|
| 오피스텔 **매매** 실거래가 | 국토부 실거래가 공개 API | [🔗 공공데이터포털](https://www.data.go.kr/data/15126475/openapi.do) |
| 오피스텔 **전월세** 실거래가 | 국토부 실거래가 공개 API | [🔗 공공데이터포털](https://www.data.go.kr/data/15126464/openapi.do) |
| **금리** (기준금리·대출금리·국고채 등) | 한국은행 ECOS Open API | [🔗 ECOS API](https://ecos.bok.or.kr/api/#/) |
| **ADR·점유율** (13개 지역 실측) | airbtics 2025-2026 | [🔗 airbtics 부산](https://airbtics.com/annual-airbnb-revenue-in-busan-south-korea/-ko) |

> airbtics는 유료 서비스라 API/크롤링 없이 정적 데이터로 박제 (`data/markets.csv`)

---

## 🗂️ 파일 구조

```
officetel_analyzer/
│
├── app.py                  # Streamlit 메인 (3탭 UI)
├── calculations.py         # NOI · ATCF · DCF · IRR · 민감도 분석 (순수 함수)
├── mortgage.py             # CPM 원리금균등 상환표
├── data_fetcher.py         # 국토부 실거래가 API 호출 (XML 파싱)
├── bok_fetcher.py          # 한국은행 ECOS API 호출 (JSON 파싱)
├── judge_property.py       # 판정 로직 (추천/신중/비추천)
├── breakeven_analysis.py   # 손익분기·지역 랭킹 보조 계산
├── verify_parker_road.py   # Parker Road Plaza 교차검증 스크립트
│
├── data/
│   ├── markets.csv         # airbtics 13개 지역 실측 + 국토부 실거래 컬럼
│   └── region_codes.csv    # 지역명 ↔ LAWD_CD 매핑
│
├── reference/
│   └── link_reference.txt  # 프로젝트 관련 링크 모음
│
├── .streamlit/
│   └── secrets.toml.example  # Streamlit Cloud 시크릿 설정 예시
│
├── .env                    # API 키 (gitignore됨 — 절대 커밋 금지)
├── packages.txt            # Streamlit Cloud 시스템 패키지 (NanumGothic 폰트)
├── requirements.txt        # Python 패키지 목록
└── CLAUDE.md               # 프로젝트 명세 (개발 가이드)
```

---

## ⚙️ 로컬 실행 방법

### 1. 패키지 설치
```bash
pip install -r requirements.txt
```

### 2. API 키 설정
프로젝트 루트에 `.env` 파일 생성:
```
DATA_GO_KR_KEY=공공데이터포털_인증키
BOK_API_KEY=한국은행_ECOS_API키
```

- 국토부 키 발급: [data.go.kr](https://www.data.go.kr/data/15126475/openapi.do) 에서 활용신청
- 한국은행 키 발급: [ecos.bok.or.kr](https://ecos.bok.or.kr/api/#/) 에서 회원가입 후 발급

### 3. 실행
```bash
streamlit run app.py
```

---

## ☁️ Streamlit Cloud 배포

Streamlit Cloud → App settings → Secrets에 아래 형식으로 등록:
```toml
DATA_GO_KR_KEY = "공공데이터포털_인증키"
BOK_API_KEY    = "한국은행_ECOS_API키"
```

API 키 로딩은 환경에 따라 자동 분기됩니다:
```python
# 배포 환경: st.secrets 사용
# 로컬 환경: .env 파일 사용 (코드 변경 불필요)
```

---

## ✅ 계산 엔진 검증

수업 예제 **Parker Road Plaza**로 계산 로직을 교차검증합니다:

```bash
python verify_parker_road.py
```

```
=== Parker Road Plaza: loan engine ===
[OK] annual debt service: diff=3.5e-10
[OK] loan balance after year 1~5: diff<1e-9

=== Parker Road Plaza: IRR engine ===
[OK] BTCF IRR: 29.64%  (expected=29.64%)
[OK] ATCF IRR: 30.10%  (expected=30.10%)

=== Project rules regression ===
[OK] 보증금 초기투자금 차감
[OK] STR 셋업비 초기투자금 가산
[OK] LTR 운영비율 12% 적용
[OK] IRR >= 15% → 추천
[OK] IRR 5~15% → 신중
[OK] IRR < 5% → 비추천

All Parker Road and project rule checks passed.
```

---

## 🔗 관련 링크

| 링크 | 설명 |
|------|------|
| [🌐 라이브 앱](https://officetel-analyzer.streamlit.app/) | Streamlit Cloud 배포 주소 |
| [📁 GitHub 저장소](https://github.com/Dr19-coder/officetel-analyzer) | 소스코드 |
| [🏛️ 국토부 API (매매)](https://www.data.go.kr/data/15126475/openapi.do) | 오피스텔 매매 실거래가 |
| [🏛️ 국토부 API (전월세)](https://www.data.go.kr/data/15126464/openapi.do) | 오피스텔 전월세 실거래가 |
| [🏦 한국은행 ECOS API](https://ecos.bok.or.kr/api/#/) | 기준금리·대출금리 등 실시간 금융지표 |
| [📊 airbtics 부산](https://airbtics.com/annual-airbnb-revenue-in-busan-south-korea/-ko) | 에어비앤비 ADR·점유율 실측 데이터 |
