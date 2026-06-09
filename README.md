# 오피스텔 투자 전략 비교기

중앙대학교 부동산금융론 개인 프로젝트.
오피스텔 단기임대(에어비앤비) vs 장기임대 투자 수익성을 비교 분석하는 Streamlit 웹앱.

## 실행 방법

```bash
pip install -r requirements.txt
streamlit run app.py
```

## 주요 기능

- NOI 산출 (PGI → EGI → NOI)
- CPM 상환표 및 연도별 이자/원금 분리
- 세후현금흐름(ATCF) 기반 IRR · NPV · Equity Multiple 비교
- 2원 민감도 분석: 점유율×ADR → IRR, 대출금리×Cap Rate → NPV
- CSV 다운로드

## 파일 구조

| 파일 | 역할 |
|------|------|
| `app.py` | Streamlit 메인 UI |
| `calculations.py` | NOI, ATCF, DCF, IRR, 민감도 분석 |
| `mortgage.py` | CPM 상환표 |
