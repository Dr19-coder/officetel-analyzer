# 프로젝트: 오피스텔 에어비앤비 투자 판정 도구

중앙대학교 **부동산금융론** 개인 프로젝트.
사업자가 점찍은 오피스텔 매물에 대해 **"에어비앤비(단기임대) 해도 될까?"를
판정**해주는 Streamlit 웹앱. 단기임대 vs 장기임대 수익성을 실거래가 기반으로
비교하고, 사용자가 직접 조사한 시세를 입력하면 추천/신중/비추천을 판정한다.

> 이 문서는 대화로 확정된 최신 방향을 담은 살아있는 명세서다.
> 방향이 바뀌면 이 파일을 먼저 갱신할 것.

---

## 앱의 정체성 (중요 - 여기서 헷갈리지 말 것)

초기엔 "지역 4개 비교 도구"였으나, **"내 매물 판정 도구"로 전환**했다.
- 시세(airbtics 실측) = 객관적 벤치마크 ("이 동네 시세는 이렇다")
- 사용자 직접 입력 ADR + 예상 점유율 = 본인의 시나리오/가정
- 판정 = 그 가정이 손익분기를 넘고 목표 수익률을 충족하는가
- "추정치 금지"는 숨은 임의 추정으로 데이터를 대체하지 말라는 뜻이다.
  탭2의 사용자 입력 ADR·예상 점유율은 삭제할 추정치가 아니라, 사용자가 직접
  조사·판단한 투자 시나리오로 명확히 표시한다.

---

## 교수님 채점 기준 (반드시 준수)

1. **로직 정확도 최우선.** NOI·IRR·민감도·손익분기 계산이 정확해야 함.
   계산이 틀리면 UI가 화려해도 감점.
2. **실제 데이터("Bloody Cash") 필수.** 추정치 금지 원칙 - 전부 실측 사용.
   매매·월세는 국토부 API, ADR·점유율은 airbtics 실측값.
3. **가산점:** GitHub 배포, .exe, 창의적 기능(전국 TOP10 랭킹, 판정 도구).
4. **발표:** 코드 한 줄씩이 아니라 전체 기능·작업 과정·기본 구조 설명.

---

## 화면 구조 (3개 탭)

```
탭1. 시세 둘러보기   - airbtics 13개 실측 지역 ADR·점유율 + TOP10 랭킹 (참고용)
탭2. 내 매물 판정    - 직접 입력 → 해라/마라 판정 (핵심 기능)
탭3. 민감도·리스크   - 점유율×ADR 히트맵 + 오피스텔 법적 리스크
```

- 탭1 TOP10 랭킹: markets.csv의 실거래 기반 `purchase_price`, `monthly_rent`,
  `deposit` 컬럼과 airbtics ADR·점유율을 사용한다. ADR로 매입가·월세를
  역산하는 숨은 추정은 쓰지 않는다.
- 탭2 내 매물 판정: 사용자가 입력한 매입가·월세·보증금·ADR·예상 점유율을
  "내 시나리오"로 계산한다. airbtics는 비교 기준선으로만 표시한다.

---

## 핵심 결론 (발표 강조점)

대화 중 정한 2대 결론:
1. **손익분기 일수**: "월 며칠 채우면 장기임대 수익을 추월하는가"
2. **리스크**: 점유율 하락 시 손해 + 오피스텔 원룸의 법적 리스크

---

## 데이터 출처 (전부 실측, 추정치 제외)

### 국토부 실거래가 API (.env의 DATA_GO_KR_KEY)
- 매매: RTMSDataSvcOffiTrade — 평균 매입가
- 전월세: RTMSDataSvcOffiRent — 월세(monthlyRent>0만 필터), 보증금
- 파라미터 LAWD_CD, DEAL_YMD, serviceKey / 응답 XML
- 보증금·월세는 '만원' 단위 → ×10000 변환 필수
- 캐싱(st.cache_data) 필수, 일일 1만 건 한도 모니터링

### airbtics 실측 ADR·점유율 (2025-2026)
점유율까지 공개된 13개 지역만 사용 (점유율 잠긴 서울 구는 제외):

[전국 도시] (10개)
제주 50110 / ADR 111,542 / 55%
부산(해운대) 26350 / 96,394 / 65%
인천(중구) 28110 / 77,115 / 43%
강릉 51150 / 118,428 / 48%
경주 47130 / 130,821 / 45%
여수 46130 / 95,017 / 35%
속초 51210 / 96,394 / 40%
대구(중구) 27110 / 71,607 / 51%
거제 48310 / 128,067 / 32%
대전(유성) 30200 / 72,984 / 56%

[서울 구] (3개)
홍대(마포) 11440 / 117,050 / 85%
종로명동(중구) 11140 / 123,936 / 83%
강남 11680 / 99,149 / 72%

- airbtics ADR은 연평균값 → 평일/주말 보정 불필요 (effective_adr direct 모드)
- airbtics는 유료 서비스라 API/크롤링 금지. 정적 데이터로 박제 + 링크 버튼만.

---

## 파일 구조

```
officetel_analyzer/
├── .env                  # API 키 (gitignore됨, 절대 커밋 금지)
├── .gitignore
├── app.py                # Streamlit 메인 (3탭)
├── calculations.py       # NOI, ATCF, DCF, IRR, effective_adr, breakeven
├── mortgage.py           # CPM 상환표 (검증 완료)
├── data_fetcher.py       # 국토부 API 호출
├── breakeven_analysis.py # 손익분기·지역 랭킹
├── verify_parker_road.py # Parker Road Plaza + 확정 규칙 회귀검증
├── data/
│   ├── markets.csv       # 13개 실측 지역 (전주 제외 - 실거래 데이터 없음)
│   └── region_codes.csv  # LAWD_CD 매칭
├── reference/            # 수업자료(Parker Road 등) + 국토부 HWP 기술문서
├── requirements.txt
├── README.md
└── CLAUDE.md             # 이 파일
```

---

## 핵심 함수 (계약)

```python
# mortgage.py (검증 완료)
cpm_schedule(principal, annual_rate, years, round_output=True) -> DataFrame
loan_balance_at(principal, annual_rate, years, after_year) -> float

# calculations.py
calculate_str_noi(adr, occupancy, cleaning_fee, platform_fee, opex_fixed) -> dict
calculate_ltr_noi(monthly_rent, vacancy_rate, opex_ratio) -> dict
effective_adr(row, mode)   # "direct"=airbtics 연평균 / "weekday"=평일ADR 보정
calculate_dcf_irr(..., setup_cost=0) -> dict   # STR/LTR 동일 기준으로 IRR·NPV
breakeven_occupancy(...) -> dict # 월 손익분기 일수 역산

# 판정 (탭2)
judge_property(...) -> verdict   # 추천/신중/비추천
```

---

## 검증된 로직 규칙 (대화 중 확정 - 절대 어기지 말 것)

1. **보증금 처리 (한국형 핵심):** 실투자금 = 매입가×(1-LTV) - 보증금.
   매각 시 신규 임차인 보증금으로 기존 보증금 반환(순현금유출 0).
2. **이자/원금 분리:** 연도별 세금 계산 시 그 해 이자는 cpm_schedule의
   해당 12개월 이자 합으로. 추정 금지.
   DCF 내부계산에서는 `round_output=False`로 무반올림 상환표를 사용하고,
   UI/표시용 상환표만 원 단위 반올림한다.
3. **운영비율:** 오피스텔 1호실 장기임대 운영비율 = 12% (관리비·수선 수준).
   30%는 과다 - 쓰지 말 것.
4. **STR/LTR 동일 기준:** 두 IRR은 같은 매입가·LTV·대출·보증금 기준으로
   비교. STR 초기투자엔 인테리어·가구·가전 셋업비를 추가한다.
   현재 공통 가정은 700만원이며, 탭2에서는 사용자가 직접 수정 가능하다.
5. **IRR 전손실 처리:** 전 기간 음수 현금흐름이면 IRR=-100%("전손실")로
   명시 표시. nan 방치 금지.
6. **매각 잔액:** loan_balance_at()으로 정확히.
7. **셋업비 처리:** setup_cost는 t=0 실투자금에 더하고, 매각 시 회수하지 않는다.

---

## 사용자 가정과 민감도 연결

- 탭2의 매입가, LTV, 금리, 대출기간, 보유기간, ADR, 청소비, 셋업비 입력값은
  `st.session_state`에 저장한다.
- 탭3 점유율×ADR 민감도 히트맵은 위 탭2 입력값을 기준으로 계산한다.
  탭2를 건드리지 않은 경우에는 기본값(매입가 3억원, ADR 10만원, 셋업비
  700만원 등)을 사용한다.
- 민감도 분석에서도 STR 셋업비는 DCF 초기투자금에 반영된다.

## 입력값 검증 및 오류 방지

- 탭2 입력창에는 명시적 입력 범위와 help 문구를 둔다.
  - 매입가: 5천만원~20억원
  - ADR: 3만원~30만원
  - 예상 점유율: 30~95%
  - 청소비: 0~10만원
  - STR 셋업비: 0~3천만원
  - 월세: 0~500만원
  - 보증금: 0원~자기자본(매입가×(1-LTV)) 미만
- 보증금이 자기자본 이상이면 초기 투자금이 0 이하가 되어 IRR이 왜곡되므로
  판정 전에 `st.error`로 막는다.
- ADR×(1-플랫폼수수료)가 청소비 이하이면 1박당 영업손실이므로 판정 전에 막는다.
- `calculate_dcf_irr`가 `deposit`/`setup_cost`를 받지 못하는 TypeError가 나면
  raw traceback 대신 Streamlit 재시작 안내를 표시한다. 이는 대개 예전 서버가
  낡은 calculations.py를 물고 있을 때 발생한다.

---

## 판정 기준 (탭2)

- STR IRR >= 15% → 추천 (목표 수익률 충족)
- STR IRR 5~15% → 신중 (본전은 넘지만 목표 미달)
- STR IRR < 5% 또는 손익분기 점유율 > 예상 점유율 → 비추천
- 벤치마크 표시: 일반임대 4~7% / 에어비앤비 목표 15~20%
- 입력 ADR을 가까운 airbtics 지역 시세와 비교 (높음/낮음)

---

## 검증된 결과 (현재까지)

실거래가 + airbtics + STR 셋업비 700만원 기준 13개 지역 검증 결과:
- 월 손익분기일: 제주 8.2 / 홍대 9.4 / 종로명동 10.5 / 강남 14.6일
- STR IRR: 거제 56.0%(매입가 매우 낮음) / 강릉 45.8% / 경주 45.5% /
  제주 33.6% / 홍대 20.9% / 종로명동 19.9% / 강남 -1.8%
- LTR IRR: 거제 46.5%, 경주 24.3%, 강릉 17.7%, 속초 12.1%, 대구 11.6%,
  제주 9.8%, 인천 6.7%; 일부 지역은 음수/전손실
- 반전 인사이트: 강남은 점유율이 높아도 매입가와 실투자금이 커 STR 효율이 낮다.
  저가 매입가 지역(거제·강릉·경주·제주)이 IRR에서 유리하다.

---

## 법적 리스크 (탭3, 발표 핵심)

- 오피스텔은 법적으로 '업무시설'이라 외국인관광도시민박업 등록 대상 아님
- 월세 임차 후 전대 영업은 '실제 거주' 요건 위반 → 현행법상 상당수 불법
- 서울 불법 공유숙소(주로 오피스텔) 약 1.3만 개 추정
- 합법 대안: ICT 규제 샌드박스 특례(위홈, 연 180일 내국인) /
  침구류 제외 시간제 공간대여업
- 출처: 관광진흥법 시행령, 공중위생관리법

---

## 코딩 스타일

- 한글 주석으로 수업 개념(NOI, ATCF 등) 명시
- numpy_financial 사용
- 계산 함수는 순수 함수(입력→출력), UI와 분리
- 작업 후 streamlit run app.py로 실행 검증
- 계산 로직 변경 후 `python verify_parker_road.py`로 Parker Road Plaza 및
  확정 규칙 회귀검증

---

## 진행 상황

```
[완료]
- 계산 엔진(NOI/CPM/DCF/IRR) - Parker Road Plaza 교차검증
- 국토부 API 연동 - 13개 지역 실거래가 수집 완료
- airbtics 실데이터 반영, 보증금·운영비 로직 수정
- 손익분기·STR/LTR IRR 검증 (전손실 처리 포함)
- 13개 실측 지역 markets.csv 확장 + LAWD_CD 매칭 (전주는 실거래 없어 제외)
- 국토부 API로 실거래가 데이터 수집 (purchase_price, monthly_rent, deposit)
- 3탭 재구성 (시세참고 / 내매물판정 / 리스크)
- 탭2 판정 배너 (추천/신중/비추천)
- 전국 TOP10 랭킹 (정렬 기준 선택 가능, 실거래 컬럼 기반)
- STR 인테리어·집기 셋업비 700만원 반영 (탭2 사용자 수정 가능)
- 탭2 입력값을 탭3 민감도 분석에 session_state로 연결
- streamlit run app.py 기동 검증
- CPM 상환표 개선: 내부 DCF는 무반올림 이자/원금/잔액 사용,
  화면 표시용은 기존처럼 반올림 유지
- Parker Road Plaza 교차검증 스크립트 추가
  (`verify_parker_road.py`: PMT, 대출잔액, 연도별 이자, BTCF/ATCF IRR,
  보증금·셋업비·운영비 12%·판정 기준 회귀검증)
- requirements.txt에 openpyxl 추가
- 탭2 입력 범위/help 문구, 보증금·청소비 검증, 계산 모듈 버전 체크 추가
  (판정 버튼 raw traceback 방지)

[남은 것 - 가산점]
- GitHub + Streamlit Cloud 배포 (API 키는 st.secrets)
- 발표 자료
```

---

## 가산점 로드맵

1. GitHub → Streamlit Community Cloud 배포 (.env→st.secrets 분기)
2. 전국 TOP10 랭킹 (실측 지역만, 정렬 기준 선택)
3. PyInstaller .exe (선택)
