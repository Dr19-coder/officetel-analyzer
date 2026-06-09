"""오피스텔 에어비앤비 투자 판정 도구 (3탭 구조).

탭1. 시세 둘러보기 - 실측 지역 + TOP10 랭킹
탭2. 내 매물 판정 - 입력 → 추천/신중/비추천
탭3. 민감도·리스크 - 히트맵 + 법적 리스크
"""

import streamlit as st
import inspect
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime
from dateutil.relativedelta import relativedelta

from calculations import (
    calculate_str_noi,
    calculate_ltr_noi,
    calculate_dcf_irr,
    run_sensitivity_analysis,
)
from mortgage import cpm_schedule, annual_debt_service
from data_fetcher import fetch_officetel_trade, fetch_officetel_rent
from judge_property import judge_property

# ── 한글 폰트 설정 (Windows: Malgun Gothic / Linux·Cloud: NanumGothic) ──
import platform
import matplotlib.font_manager as fm

def _setup_korean_font():
    if platform.system() == "Windows":
        plt.rcParams["font.family"] = "Malgun Gothic"
        return
    # Linux(Streamlit Cloud): 파일 직접 로드 후 등록
    import os
    nanum_path = "/usr/share/fonts/truetype/nanum/NanumGothic.ttf"
    if os.path.exists(nanum_path):
        fm.fontManager.addfont(nanum_path)
        plt.rcParams["font.family"] = fm.FontProperties(fname=nanum_path).get_name()
    else:
        # 폰트 매니저 캐시 무시하고 재탐색
        fm._load_fontmanager(try_read_cache=False)
        names = {f.name for f in fm.fontManager.ttflist}
        if "NanumGothic" in names:
            plt.rcParams["font.family"] = "NanumGothic"

_setup_korean_font()
plt.rcParams["axes.unicode_minus"] = False

# ── 페이지 설정 ─────────────────────────────────────────────
st.set_page_config(
    page_title="오피스텔 투자 판정 도구",
    page_icon="🏢",
    layout="wide",
)
st.title("🏢 오피스텔 에어비앤비 투자 판정 도구")
st.caption("📊 실측 데이터 기반 단기임대 vs 장기임대 수익성 비교")

# ── 지역 데이터 로드 ─────────────────────────────────────────
@st.cache_data
def load_markets():
    """markets.csv 로드 (실측 지역)."""
    return pd.read_csv("./data/markets.csv")

markets_df = load_markets()
market_count = len(markets_df)

# 계산 모듈 호환성 확인: 예전 Streamlit 서버가 낡은 calculations.py를 물면
# deposit/setup_cost 인자를 못 받아 판정 버튼에서 TypeError가 난다.
dcf_signature = inspect.signature(calculate_dcf_irr)
if "deposit" not in dcf_signature.parameters or "setup_cost" not in dcf_signature.parameters:
    st.error(
        "계산 모듈이 예전 버전으로 로드되어 있습니다. "
        "터미널에서 Ctrl+C로 Streamlit을 끈 뒤 `streamlit run app.py`로 다시 실행하세요."
    )
    st.stop()

# ── 실거래가 조회 함수 (캐싱) ───────────────────────────────
@st.cache_data(ttl=3600)
def fetch_recent_data(lawd_cd: str, months: int = 6):
    """최근 N개월 실거래가를 조회한다."""
    results = []

    for i in range(months):
        target_date = datetime.now() - relativedelta(months=i)
        deal_ymd = target_date.strftime("%Y%m")

        try:
            trade_df = fetch_officetel_trade(lawd_cd, deal_ymd, num_of_rows=100)
            rent_df = fetch_officetel_rent(lawd_cd, deal_ymd, num_of_rows=100, monthly_only=True)
            results.append({"trade": trade_df, "rent": rent_df})
        except Exception:
            continue

    all_trade = pd.concat([r["trade"] for r in results if len(r["trade"]) > 0], ignore_index=True) if results else pd.DataFrame()
    all_rent = pd.concat([r["rent"] for r in results if len(r["rent"]) > 0], ignore_index=True) if results else pd.DataFrame()

    return {
        "trade_df": all_trade,
        "rent_df": all_rent,
        "trade_count": len(all_trade),
        "rent_count": len(all_rent),
        "avg_trade_price": int(all_trade["dealAmount"].mean()) if len(all_trade) > 0 else 0,
        "avg_deposit": int(all_rent["deposit"].mean()) if len(all_rent) > 0 else 0,
        "avg_monthly_rent": int(all_rent["monthlyRent"].mean()) if len(all_rent) > 0 else 0,
    }


# ═══════════════════════════════════════════════════════════
# 탭 구성 (3개)
# ═══════════════════════════════════════════════════════════

tab1, tab2, tab3 = st.tabs(["📊 시세 둘러보기", "🎯 내 매물 판정", "⚖️ 법적 리스크"])


# ═══════════════════════════════════════════════════════════
# 탭1: 시세 둘러보기
# ═══════════════════════════════════════════════════════════

with tab1:
    st.subheader(f"📊 전국 {market_count}개 실측 지역 시세 (airbtics 2025-2026)")

    # 실측 지역 테이블
    display_df = markets_df[["region", "group", "airbnb_adr", "occupancy", "source"]].copy()
    display_df["airbnb_adr"] = display_df["airbnb_adr"].apply(lambda x: f"{x/10000:.1f}만원")
    display_df["occupancy"] = display_df["occupancy"].apply(lambda x: f"{x*100:.0f}%")
    display_df.columns = ["지역", "그룹", "ADR", "점유율", "출처"]

    st.dataframe(display_df, width="stretch", height=500)

    st.markdown("---")

    # TOP10 랭킹
    st.subheader("🏆 TOP10 랭킹 (실측 지역만)")

    # 공통 가정으로 실측 지역 계산
    @st.cache_data
    def calculate_all_regions_ranking():
        """실측 지역의 IRR과 손익분기를 계산하여 랭킹용 DataFrame 반환."""
        results = []

        # 공통 가정
        ltv = 0.60
        loan_rate = 0.045
        loan_years = 20
        hold_years = 5
        tax_rate = 0.35
        cap_rate = 0.05
        building_ratio = 0.80
        setup_cost = 7_000_000
        opex_fixed = 2_000_000
        vacancy_rate = 0.05
        opex_ratio = 0.12

        for _, region_row in markets_df.iterrows():
            region_name = region_row["region"]
            r_adr = float(region_row["airbnb_adr"])
            r_occupancy = float(region_row["occupancy"])
            r_cleaning = float(region_row["cleaning_fee"])
            r_platform = float(region_row["platform_fee"])
            r_purchase = float(region_row["purchase_price"])
            r_monthly_rent = float(region_row["monthly_rent"])
            r_deposit = float(region_row["deposit"])

            # STR NOI
            r_str_noi_result = calculate_str_noi(r_adr, r_occupancy, r_cleaning, r_platform, opex_fixed)
            r_str_noi = r_str_noi_result["noi"]

            # LTR NOI
            r_ltr_noi_result = calculate_ltr_noi(r_monthly_rent, vacancy_rate, opex_ratio)
            r_ltr_noi = r_ltr_noi_result["noi"]

            # 대출 조건
            r_loan_principal = r_purchase * ltv
            r_mortgage = {
                "principal": r_loan_principal,
                "annual_rate": loan_rate,
                "loan_years": loan_years,
            }

            r_params = {
                "purchase_price": r_purchase,
                "ltv": ltv,
                "hold_years": hold_years,
                "tax_rate": tax_rate,
                "cap_rate": cap_rate,
                "building_ratio": building_ratio,
            }
            r_str_params = {**r_params, "setup_cost": setup_cost}

            # STR IRR (인테리어·집기 셋업비 반영)
            try:
                r_str_dcf = calculate_dcf_irr(r_str_noi, r_str_params, r_mortgage)
                r_str_irr = r_str_dcf["irr"]
            except Exception:
                r_str_irr = None

            # LTR IRR (보증금 반영)
            try:
                r_ltr_dcf = calculate_dcf_irr(
                    r_ltr_noi,
                    r_params,
                    r_mortgage,
                    deposit=r_deposit,
                )
                r_ltr_irr = r_ltr_dcf["irr"]
            except Exception:
                r_ltr_irr = None

            # 손익분기
            r_net_per_night = r_adr * (1 - r_platform) - r_cleaning
            if r_net_per_night > 0:
                r_occupied_nights_breakeven = (r_ltr_noi + opex_fixed) / r_net_per_night
                r_breakeven_days_per_month = r_occupied_nights_breakeven / 12
            else:
                r_breakeven_days_per_month = 999

            results.append({
                "지역": region_name,
                "그룹": region_row["group"],
                "평균매입가": r_purchase,
                "월세": r_monthly_rent,
                "보증금": r_deposit,
                "ADR": r_adr,
                "점유율": r_occupancy * 100,
                "STR IRR": r_str_irr,
                "LTR IRR": r_ltr_irr,
                "손익분기": r_breakeven_days_per_month,
            })

        return pd.DataFrame(results)

    ranking_df = calculate_all_regions_ranking()

    # 정렬 기준 선택
    sort_col1, sort_col2 = st.columns(2)

    with sort_col1:
        sort_by = st.selectbox(
            "정렬 기준",
            ["STR IRR", "손익분기", "ADR", "점유율", "평균매입가", "LTR IRR"],
            index=0,
        )

    with sort_col2:
        top_n = st.slider("표시 개수", 5, market_count, min(10, market_count))

    # 정렬
    ascending = True if sort_by in ["손익분기", "평균매입가"] else False
    top_df = ranking_df.sort_values(sort_by, ascending=ascending, na_position="last").head(top_n)

    # 표시
    display_top = top_df.copy()
    display_top["평균매입가"] = display_top["평균매입가"].apply(lambda x: f"{x/100_000_000:.2f}억")
    display_top["월세"] = display_top["월세"].apply(lambda x: f"{x/10000:.0f}만원")
    display_top["보증금"] = display_top["보증금"].apply(lambda x: f"{x/10000:.0f}만원")
    display_top["ADR"] = display_top["ADR"].apply(lambda x: f"{x/10000:.1f}만원")
    display_top["점유율"] = display_top["점유율"].apply(lambda x: f"{x:.0f}%")
    display_top["STR IRR"] = display_top["STR IRR"].apply(
        lambda x: "N/A" if pd.isna(x) else ("전손실" if x == -100.0 else f"{x:.1f}%")
    )
    display_top["LTR IRR"] = display_top["LTR IRR"].apply(
        lambda x: "N/A" if pd.isna(x) else ("전손실" if x == -100.0 else f"{x:.1f}%")
    )
    display_top["손익분기"] = display_top["손익분기"].apply(lambda x: f"{x:.1f}일")

    st.dataframe(display_top, width="stretch")

    st.caption(
        f"💡 {sort_by} 기준 상위 {top_n}개 지역 "
        "(airbtics ADR·점유율 + 국토부 실거래 매입가·월세·보증금, 공통 가정: LTV 60%, 금리 4.5%, 보유 5년, STR 셋업비 700만원)"
    )


# ═══════════════════════════════════════════════════════════
# 탭2: 내 매물 판정
# ═══════════════════════════════════════════════════════════

with tab2:
    st.subheader("🎯 내 매물 판정 - 에어비앤비 해도 될까?")

    with st.expander("💬 용어가 헷갈린다면? (처음이신 분 필독)"):
        st.markdown("""
| 용어 | 쉬운 설명 |
|------|-----------|
| **1박 요금 (ADR)** | 에어비앤비에 올릴 1박 가격. 인근 유사 매물을 검색해 참고하세요. |
| **예약률 (점유율)** | 1년 365일 중 실제 예약이 차는 날의 비율. 예: 60% = 연 219일, 월 평균 18일 예약. 제주 55%, 홍대 85% 수준. |
| **에어비앤비 연수익률 (STR IRR)** | 내가 투자한 돈(자기자본) 대비 1년 평균 수익률. **15% 이상이면 우수**, 5% 미만이면 그냥 예금이 낫습니다. |
| **일반임대 연수익률 (LTR IRR)** | 같은 매물을 월세로 놓을 때의 연수익률. 비교 기준입니다. |
| **월 최소 예약일 (손익분기)** | 한 달에 며칠 이상 예약이 차야 일반임대보다 더 버는지. 이 날수를 못 채우면 그냥 월세를 받는 게 낫습니다. |
| **LTV** | 매입가 대비 대출 비율. LTV 60% = 3억짜리 오피스텔이면 1.8억 대출. |
""")

    # 그룹 선택
    st.markdown("### 1️⃣ 비교 지역 선택")
    group_choice = st.radio(
        "지역 그룹",
        ["전국 도시", "서울 구"],
        horizontal=True,
    )

    # 그룹별 지역 필터링
    filtered_regions = markets_df[markets_df["group"] == group_choice]
    region_names = filtered_regions["region"].tolist()

    selected_region = st.selectbox("비교 기준 지역 (시세 참고용)", region_names, index=0)
    region_info = markets_df[markets_df["region"] == selected_region].iloc[0]
    lawd_cd = str(region_info["lawd_cd"])

    # airbtics 링크
    airbtics_urls = {
        "홍대": "https://www.airbtics.com/listing-neighborhood/kr/seoul/mapo-gu/",
        "종로명동": "https://www.airbtics.com/listing-neighborhood/kr/seoul/jung-gu/",
        "강남": "https://www.airbtics.com/listing-neighborhood/kr/seoul/gangnam-gu/",
        "제주": "https://www.airbtics.com/listing-neighborhood/kr/jeju/jeju-si/",
        "부산": "https://www.airbtics.com/listing-neighborhood/kr/busan/haeundae-gu/",
        "인천": "https://www.airbtics.com/listing-neighborhood/kr/incheon/jung-gu/",
        "강릉": "https://www.airbtics.com/listing-neighborhood/kr/gangwon-do/gangneung-si/",
        "경주": "https://www.airbtics.com/listing-neighborhood/kr/gyeongsangbuk-do/gyeongju-si/",
    }

    if selected_region in airbtics_urls:
        st.link_button(
            f"🔍 {selected_region} airbtics 최신 데이터 확인",
            airbtics_urls[selected_region],
        )

    # 시세 정보 표시
    ref_col1, ref_col2 = st.columns(2)
    with ref_col1:
        st.metric("🏘️ 시세 ADR", f"{region_info['airbnb_adr']/10000:.1f}만원")
    with ref_col2:
        st.metric("📊 시세 점유율", f"{region_info['occupancy']*100:.0f}%")

    st.caption(f"출처: {region_info['source']}")

    st.markdown("---")

    # 2. 내 매물 입력
    st.markdown("### 2️⃣ 내 매물 정보 입력")

    input_col1, input_col2 = st.columns(2)

    with input_col1:
        st.markdown("#### 📝 기본 정보")
        user_purchase_price = st.number_input(
            "매입가 (원)",
            min_value=50_000_000,
            max_value=2_000_000_000,
            value=300_000_000,
            step=10_000_000,
            format="%d",
            help="5천만원~20억원 범위에서 입력하세요. 국토부 평균 매입가나 실제 매물가 기준입니다.",
        )
        user_ltv = st.slider(
            "LTV (%)",
            40,
            80,
            60,
            help="40~80% 범위. LTV가 높을수록 자기자본은 줄지만 원리금 부담이 커집니다.",
        ) / 100
        user_loan_rate = st.slider(
            "대출금리 (%)",
            2.0,
            8.0,
            4.5,
            0.1,
            help="2.0~8.0% 범위. 현재 금리 또는 보수적 시나리오를 입력하세요.",
        ) / 100
        user_loan_years = st.number_input(
            "대출기간 (년)",
            value=20,
            min_value=1,
            max_value=40,
            help="1~40년 범위. CPM 원리금균등 상환 기준입니다.",
        )
        user_hold_years = st.number_input(
            "보유기간 (년)",
            value=5,
            min_value=1,
            max_value=30,
            help="1~30년 범위. IRR 계산의 보유기간입니다.",
        )

    with input_col2:
        st.markdown("#### 🏠 단기임대 시나리오")
        user_adr = st.number_input(
            "1박 숙박 요금 (원)",
            min_value=30_000,
            max_value=300_000,
            value=int(region_info["airbnb_adr"]),
            step=5_000,
            format="%d",
            help="ADR: 에어비앤비에 올릴 1박 가격. 인근 유사 매물 검색 또는 위 airbtics 시세 버튼을 참고하세요.",
        )
        user_occupancy = st.slider(
            "연간 예약률 (%)",
            30,
            95,
            int(region_info["occupancy"] * 100),
            help="1년 365일 중 예약이 차는 날의 비율. 예: 60% = 연 219일, 월 18일. 처음이라면 지역 평균보다 10%p 낮게 잡는 게 안전합니다.",
        ) / 100
        user_cleaning_fee = st.number_input(
            "건당 청소비 (원)",
            min_value=0,
            max_value=100_000,
            value=int(region_info["cleaning_fee"]),
            step=5_000,
            format="%d",
            help="0~10만원 범위. 숙박 1박당 청소비로 계산합니다.",
        )
        user_setup_cost = st.number_input(
            "인테리어·집기 셋업비 (원)",
            min_value=0,
            max_value=30_000_000,
            value=7_000_000,
            step=1_000_000,
            format="%d",
            help="0~3천만원 범위. STR 초기투자금에 더하고 매각 시 회수하지 않습니다.",
        )

    # 3. 장기임대 정보 (실거래가 or 수동)
    st.markdown("---")
    st.markdown("### 3️⃣ 장기임대 비교 (실거래가 or 수동)")

    use_api = st.checkbox(f"📊 {selected_region} 실거래가 불러오기 (최근 6개월)", value=False)
    max_safe_deposit = int(max(user_purchase_price * (1 - user_ltv) - 1, 0))

    if use_api:
        with st.spinner(f"{selected_region} 실거래가 조회 중..."):
            try:
                api_data = fetch_recent_data(lawd_cd, months=6)
                if api_data["trade_count"] > 0 or api_data["rent_count"] > 0:
                    st.success(f"✅ 조회 완료: 매매 {api_data['trade_count']}건, 월세 {api_data['rent_count']}건")
                    user_monthly_rent = api_data["avg_monthly_rent"]
                    user_deposit = api_data["avg_deposit"]
                else:
                    st.warning("해당 지역의 최근 거래 데이터가 없습니다. 수동 입력하세요.")
                    user_monthly_rent = 1_000_000
                    user_deposit = 50_000_000
            except Exception as e:
                st.error(f"❌ API 호출 실패: {e}")
                user_monthly_rent = 1_000_000
                user_deposit = 50_000_000
    else:
        user_monthly_rent = st.number_input(
            "월세 (원)",
            min_value=0,
            max_value=5_000_000,
            value=1_000_000,
            step=50_000,
            format="%d",
            help="0~500만원 범위. 국토부 월세 실거래 또는 직접 조사한 월세를 입력하세요.",
        )
        user_deposit = st.number_input(
            "보증금 (원)",
            min_value=0,
            max_value=max_safe_deposit,
            value=min(50_000_000, max_safe_deposit),
            step=5_000_000,
            format="%d",
            help="0원부터 자기자본(매입가×(1-LTV)) 미만까지 입력하세요. 보증금은 LTR 초기 실투자금에서 차감됩니다.",
        )

    st.session_state["user_purchase_price"] = user_purchase_price
    st.session_state["user_ltv"] = user_ltv
    st.session_state["user_loan_rate"] = user_loan_rate
    st.session_state["user_loan_years"] = user_loan_years
    st.session_state["user_hold_years"] = user_hold_years
    st.session_state["user_adr"] = user_adr
    st.session_state["user_occupancy"] = user_occupancy
    st.session_state["user_cleaning_fee"] = user_cleaning_fee
    st.session_state["user_setup_cost"] = user_setup_cost

    st.markdown("---")

    # 4. 판정 버튼
    if st.button("🎯 판정하기", type="primary", width="stretch"):
        validation_errors = []
        equity_before_deposit = user_purchase_price * (1 - user_ltv)
        if user_deposit >= equity_before_deposit:
            validation_errors.append(
                f"보증금은 자기자본({equity_before_deposit/10000:,.0f}만원)보다 작아야 합니다. "
                "보증금이 자기자본 이상이면 초기 투자금이 0 이하가 되어 IRR 판정이 왜곡됩니다."
            )
        if user_adr * 0.9 <= user_cleaning_fee:
            validation_errors.append(
                "ADR×(1-플랫폼수수료)가 청소비보다 커야 합니다. "
                "현재 값이면 1박을 팔 때마다 영업손실이 납니다."
            )

        if validation_errors:
            for error in validation_errors:
                st.error(error)
            st.stop()

        # 계산
        loan_principal = user_purchase_price * user_ltv
        mortgage_info = {
            "principal": loan_principal,
            "annual_rate": user_loan_rate,
            "loan_years": user_loan_years,
        }

        common_params = {
            "purchase_price": user_purchase_price,
            "ltv": user_ltv,
            "hold_years": user_hold_years,
            "tax_rate": 0.35,
            "cap_rate": 0.05,
            "building_ratio": 0.80,
        }
        str_params = {**common_params, "setup_cost": user_setup_cost}

        # STR NOI
        str_noi_result = calculate_str_noi(
            user_adr,
            user_occupancy,
            user_cleaning_fee,
            0.10,  # 플랫폼 수수료 10%
            2_000_000,  # 고정 운영비
        )
        str_noi = str_noi_result["noi"]

        # LTR NOI
        ltr_noi_result = calculate_ltr_noi(user_monthly_rent, 0.05, 0.12)
        ltr_noi = ltr_noi_result["noi"]

        # DCF / IRR
        try:
            str_dcf = calculate_dcf_irr(str_noi, str_params, mortgage_info)
            ltr_dcf = calculate_dcf_irr(
                ltr_noi,
                common_params,
                mortgage_info,
                deposit=user_deposit,
            )
        except TypeError as e:
            if "deposit" in str(e) or "setup_cost" in str(e):
                st.error(
                    "계산 모듈이 예전 버전으로 로드되어 있습니다. "
                    "터미널에서 Ctrl+C로 Streamlit을 완전히 종료한 뒤 "
                    "`streamlit run app.py`로 다시 실행하세요."
                )
            else:
                st.error(f"입력값 조합을 계산할 수 없습니다: {e}")
            st.stop()
        except Exception as e:
            st.error(f"입력값 조합을 계산할 수 없습니다: {e}")
            st.stop()

        str_irr = str_dcf["irr"]

        # 손익분기
        net_per_night = user_adr * 0.9 - user_cleaning_fee
        if net_per_night > 0:
            occupied_nights_breakeven = (ltr_noi + 2_000_000) / net_per_night
            breakeven_occupancy = occupied_nights_breakeven / 365
        else:
            breakeven_occupancy = 1.0

        # 판정
        judgment = judge_property(
            str_irr,
            breakeven_occupancy,
            user_occupancy,
            str_noi,
            ltr_noi,
        )

        # 판정 결과 표시
        st.markdown("---")
        st.markdown("## 📋 판정 결과")

        if judgment["color"] == "success":
            st.success(f"{judgment['emoji']} **{judgment['verdict']}**")
        elif judgment["color"] == "warning":
            st.warning(f"{judgment['emoji']} **{judgment['verdict']}**")
        else:
            st.error(f"{judgment['emoji']} **{judgment['verdict']}**")

        st.write(judgment["reason"])

        # 핵심 수치 (평어)
        st.markdown("---")
        st.markdown("### 📊 핵심 수치")

        ltr_irr = ltr_dcf["irr"]
        breakeven_days_month = breakeven_occupancy * 365 / 12

        mc1, mc2, mc3 = st.columns(3)
        with mc1:
            irr_display = f"{str_irr:.1f}%" if str_irr not in [None, -100.0] else "전손실"
            st.metric("에어비앤비 연수익률", irr_display)
            st.caption("내 투자금 대비 연평균 수익률. 15% 이상이면 우수")
        with mc2:
            st.metric("월 최소 예약일", f"{breakeven_days_month:.1f}일")
            st.caption(f"한 달에 이 날수 이상 예약이 차야 일반임대보다 이득")
        with mc3:
            ltr_display = f"{ltr_irr:.1f}%" if ltr_irr not in [None, -100.0] else "전손실"
            st.metric("일반임대 연수익률", ltr_display)
            st.caption("같은 매물을 월세로 놓을 때의 수익률 (비교용)")

        # 시세 비교
        st.markdown("---")
        adr_diff = (user_adr / region_info["airbnb_adr"] - 1) * 100
        occ_diff = (user_occupancy / region_info["occupancy"] - 1) * 100

        comp_col1, comp_col2 = st.columns(2)
        with comp_col1:
            if adr_diff > 0:
                st.info(f"📈 입력 요금이 {selected_region} 시세보다 {adr_diff:.1f}% 높습니다.")
            elif adr_diff < -10:
                st.warning(f"📉 입력 요금이 {selected_region} 시세보다 {abs(adr_diff):.1f}% 낮습니다. 경쟁력을 점검하세요.")
            else:
                st.success(f"✓ 입력 요금이 {selected_region} 시세와 비슷합니다.")
        with comp_col2:
            if occ_diff > 0:
                st.info(f"📈 예상 예약률이 {selected_region} 평균보다 {occ_diff:.1f}%p 높습니다.")
            elif occ_diff < -10:
                st.warning(f"📉 예상 예약률이 {selected_region} 평균보다 {abs(occ_diff):.1f}%p 낮습니다.")
            else:
                st.success(f"✓ 예상 예약률이 {selected_region} 평균과 비슷합니다.")

        # 리스크 지형도 (히트맵 + ★ 내 시나리오)
        st.markdown("---")
        st.markdown("### 📍 리스크 지형도 — 예약률·요금이 달라지면?")
        st.caption(
            "가로축: 내 1박 요금 기준 ±범위 시나리오 | "
            "세로축: 연 예약률 | "
            "숫자: 에어비앤비 연수익률(%) | "
            "**흰 테두리 = 내 시나리오**"
        )

        _sens_params = {
            "adr": user_adr,
            "cleaning_fee": user_cleaning_fee,
            "platform_fee": 0.10,
            "opex_fixed": 2_000_000,
            "purchase_price": user_purchase_price,
            "ltv": user_ltv,
            "hold_years": user_hold_years,
            "tax_rate": 0.35,
            "cap_rate": 0.05,
            "building_ratio": 0.80,
            "setup_cost": user_setup_cost,
        }
        _sens_mortgage = {
            "principal": user_purchase_price * user_ltv,
            "annual_rate": user_loan_rate,
            "loan_years": user_loan_years,
        }

        try:
            import matplotlib.patches as mpatches
            _sensitivity_df = run_sensitivity_analysis(_sens_params, _sens_mortgage, mode="str")

            # 내 시나리오 위치 계산
            _occ_range = np.arange(0.30, 1.00, 0.05)
            _row_idx = int(np.argmin(np.abs(_occ_range - user_occupancy)))
            _col_idx = 4  # base ADR = 100% 열 (adr*0.6부터 시작해 5번째)

            with plt.style.context("dark_background"):
                fig_risk = plt.figure(figsize=(7, 5))
                gs = fig_risk.add_gridspec(2, 1, height_ratios=[12, 1], hspace=0.55)
                ax_risk = fig_risk.add_subplot(gs[0])
                ax_cbar = fig_risk.add_subplot(gs[1])
                fig_risk.patch.set_facecolor("#0e1117")
                ax_risk.set_facecolor("#0e1117")
                ax_cbar.set_facecolor("#0e1117")
                sns.heatmap(
                    _sensitivity_df.astype(float),
                    annot=True,
                    fmt=".1f",
                    cmap="RdYlGn",
                    center=10,
                    vmin=-10,
                    vmax=30,
                    cbar=False,
                    annot_kws={"size": 8},
                    ax=ax_risk,
                )
                ax_risk.add_patch(mpatches.Rectangle(
                    (_col_idx, _row_idx), 1, 1,
                    fill=False, edgecolor="white", lw=2.5, zorder=5,
                ))
                ax_risk.set_xlabel("1박 요금 시나리오")
                ax_risk.set_ylabel("연 예약률", rotation=0, labelpad=40, va="center")
                ax_risk.set_title("리스크 지형도 (흰 테두리 = 내 시나리오)", pad=10)
                ax_risk.set_yticklabels(ax_risk.get_yticklabels(), rotation=0)
                # 가로 컬러바 — 빨강(손실) 왼쪽, 초록(수익) 오른쪽
                cb = fig_risk.colorbar(
                    ax_risk.collections[0], cax=ax_cbar, orientation="horizontal"
                )
                cb.set_label(
                    "← 손실 (빨강)          연수익률(IRR) %          수익 (초록) →",
                    color="white", fontsize=8,
                )
                ax_cbar.xaxis.set_tick_params(labelcolor="white", labelsize=7)

            st.pyplot(fig_risk)
            plt.close(fig_risk)
            irr_str = f"{str_irr:.1f}%" if str_irr not in [None, -100.0] else "전손실"
            st.caption(
                f"내 시나리오: 요금 {user_adr/10000:.1f}만원, 예약률 {user_occupancy*100:.0f}% → 연수익률 {irr_str}  |  "
                f"초록 영역이 넓을수록 웬만큼 빗나가도 수익이 나는 안전한 투자입니다."
            )
        except Exception as e:
            st.warning(f"리스크 지형도 계산 실패: {e}")


# ═══════════════════════════════════════════════════════════
# 탭3: 법적 리스크
# ═══════════════════════════════════════════════════════════

with tab3:
    st.subheader("⚖️ 오피스텔 단기임대 법적 리스크")

    st.warning(
        "⚠️ **핵심 요약**: 오피스텔은 법적으로 '업무시설'입니다. "
        "현행법상 에어비앤비 영업은 상당수가 불법입니다. "
        "서울 불법 공유숙소 추정 약 1.3만 개."
    )

    st.markdown("#### 왜 문제가 되나?")
    st.markdown(
        "- 오피스텔 = 건축법상 업무시설 → 공중위생관리법상 숙박업 등록 **불가**\n"
        "- 월세 계약 후 에어비앤비 운영 = '실제 거주' 요건 위반 (전대 금지)\n"
        "- 적발 시: 과태료·영업정지·임대차 계약 해지 가능"
    )

    st.markdown("#### 합법으로 운영하려면?")
    st.info(
        "1. **ICT 규제 샌드박스 특례** — 위홈 등 등록 플랫폼 이용, 연 180일 이내, 내국인 한정\n"
        "2. **시간제 공간대여업** — 침구류를 제공하지 않는 형태로 운영\n\n"
        "출처: 관광진흥법 시행령, 공중위생관리법"
    )

    st.markdown("#### 투자 전 체크리스트")
    st.info(
        "- 임대차 계약서에 **전대 금지 조항**이 있는지 확인\n"
        "- 건물주(임대인)에게 단기임대 허용 여부 **사전 협의**\n"
        "- 일반 주택보험은 미적용 → 숙박업 전용 보험 별도 가입 필요\n"
        "- 서울·제주는 단속 강화 추세 — 지자체별 리스크 상이"
    )
