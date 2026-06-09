"""NOI · ATCF · DCF/IRR · 2원 민감도 분석 모듈.

수업 핵심 개념: PGI → EGI → NOI → BTCF → ATCF → IRR/NPV
"""

import numpy as np
import numpy_financial as npf
import pandas as pd

from mortgage import annual_debt_service, loan_balance_at, cpm_schedule


# ── 0. ADR 계산 (markets.csv 활용) ──────────────────────────

def effective_adr(market_row: dict, use_peak: bool = False, mode: str = "auto") -> float:
    """지역 데이터에서 실효 ADR을 계산한다.

    Parameters
    ----------
    market_row : dict
        markets.csv의 한 행 (pandas Series를 dict로 변환한 형태)
    use_peak : bool
        성수기 배율 적용 여부 (기본: False)
    mode : str
        - "auto": airbnb_adr 컬럼 존재 시 direct, 없으면 weekday
        - "direct": airbnb_adr을 그대로 사용 (airbtics 실측 연평균)
        - "weekday": weekday_adr × (5 + 2×weekend_mult)/7 계산

    Returns
    -------
    float
        실효 ADR (원)

    Examples
    --------
    # airbtics 실측값 (direct 모드)
    >>> effective_adr({"airbnb_adr": 117050, "peak_mult": 1.3}, use_peak=False)
    117050.0

    # 직접 조사값 (weekday 모드)
    >>> effective_adr({"weekday_adr": 100000, "weekend_mult": 1.4}, mode="weekday")
    111428.57
    """
    # 모드 자동 감지
    if mode == "auto":
        if "airbnb_adr" in market_row and pd.notna(market_row.get("airbnb_adr")):
            mode = "direct"
        elif "weekday_adr" in market_row and pd.notna(market_row.get("weekday_adr")):
            mode = "weekday"
        else:
            raise ValueError("market_row에 airbnb_adr 또는 weekday_adr 컬럼이 필요합니다")

    # direct 모드: airbtics 실측 연평균값
    if mode == "direct":
        base_adr = float(market_row["airbnb_adr"])

        # 성수기 배율 적용
        if use_peak and "peak_mult" in market_row:
            peak_mult = float(market_row["peak_mult"])
            return base_adr * peak_mult
        return base_adr

    # weekday 모드: 평일/주말 보정
    elif mode == "weekday":
        weekday_adr = float(market_row["weekday_adr"])
        weekend_mult = float(market_row["weekend_mult"])

        # 주간평균 = (평일5일 + 주말2일×배율) / 7
        weekly_avg = weekday_adr * (5 + 2 * weekend_mult) / 7

        # 성수기 배율 적용
        if use_peak and "peak_mult" in market_row:
            peak_mult = float(market_row["peak_mult"])
            return weekly_avg * peak_mult
        return weekly_avg

    else:
        raise ValueError(f"Unknown mode: {mode}. Use 'auto', 'direct', or 'weekday'.")


# ── 1. 단기임대 NOI ─────────────────────────────────────────

def calculate_str_noi(
    adr: float,
    occupancy: float,
    cleaning_fee: float,
    platform_fee: float,
    opex_fixed: float,
) -> dict:
    """단기임대(에어비앤비) 연간 NOI를 산출한다.

    PGI  = ADR × 365
    EGI  = ADR × (365 × 점유율) — 플랫폼 수수료
    NOI  = EGI - 고정운영비 - 청소비
    """
    occupied_nights = 365 * occupancy
    pgi = adr * 365                                    # 잠재총수입
    gross_revenue = adr * occupied_nights              # 실제 숙박 수입
    cleaning_total = cleaning_fee * occupied_nights    # 총 청소비
    platform_total = gross_revenue * platform_fee      # 플랫폼 수수료
    egi = gross_revenue - platform_total               # 유효총수입
    noi = egi - opex_fixed - cleaning_total            # 순영업소득

    return {
        "pgi": pgi,
        "occupied_nights": occupied_nights,
        "gross_revenue": gross_revenue,
        "cleaning_total": cleaning_total,
        "platform_total": platform_total,
        "egi": egi,
        "noi": noi,
    }


# ── 2. 장기임대 NOI ─────────────────────────────────────────

def calculate_ltr_noi(
    monthly_rent: float,
    vacancy_rate: float,
    opex_ratio: float,
) -> dict:
    """장기임대 연간 NOI를 산출한다.

    PGI = 월세 × 12
    EGI = PGI × (1 - 공실률)
    NOI = EGI × (1 - 운영비율)
    """
    pgi = monthly_rent * 12
    egi = pgi * (1 - vacancy_rate)
    opex = egi * opex_ratio
    noi = egi - opex  # = EGI × (1 - 운영비율)

    return {
        "pgi": pgi,
        "egi": egi,
        "opex": opex,
        "noi": noi,
    }


# ── 3. 세후현금흐름(ATCF) ───────────────────────────────────

def calculate_atcf(
    noi: float,
    debt_service: float,
    depreciation: float,
    interest: float,
    tax_rate: float,
) -> float:
    """단일 연도 세후현금흐름(ATCF)을 반환한다.

    로직 규칙 #1: 세금 = max(NOI - 감가상각 - 이자, 0) × 세율
    BTCF = NOI - DS
    ATCF = BTCF - Tax
    """
    btcf = noi - debt_service                               # 세전현금흐름
    taxable_income = noi - depreciation - interest           # 과세소득
    tax = max(taxable_income, 0) * tax_rate                  # 소득세
    atcf = btcf - tax                                        # 세후현금흐름
    return atcf


# ── 4. DCF / IRR 분석 ───────────────────────────────────────

def _annual_interest_from_schedule(
    schedule: pd.DataFrame, year: int
) -> float:
    """cpm_schedule() 결과에서 특정 연도(1-based)의 이자 합계를 구한다.

    로직 규칙 #1: 이자는 추정하지 말고, 상환표의 해당 12개월 합으로.
    """
    start = (year - 1) * 12 + 1
    end = year * 12
    mask = (schedule["회차"] >= start) & (schedule["회차"] <= end)
    return schedule.loc[mask, "이자"].sum()


def calculate_dcf_irr(
    noi_year1: float,
    params: dict,
    mortgage: dict,
    noi_growth: float = 0.02,
    deposit: float = 0.0,
    setup_cost: float = 0.0,
) -> dict:
    """보유기간 전체의 DCF 분석 결과를 반환한다.

    Parameters
    ----------
    noi_year1 : 1차년도 NOI
    params : {purchase_price, ltv, hold_years, tax_rate, cap_rate, building_ratio}
    mortgage : {principal, annual_rate, loan_years}
    noi_growth : NOI 연간 성장률 (기본 2 %)
    deposit : 보증금 (장기임대 시, 초기 투자금 차감 및 매각 시 반환)
    setup_cost : 초기 셋업비 (STR 인테리어·가구·가전 등, 초기 투자금에 가산)

    Returns
    -------
    dict with keys: irr, npv, equity_multiple, cashflows (DataFrame)

    로직 규칙:
    - #1 이자/원금 분리: cpm_schedule에서 연도별 이자 합산
    - #2 매각 잔액: loan_balance_at()으로 정확 계산
    - #3 감가상각: 건물분만 정액법 (토지 제외)
    - #4 IRR 부호: t=0 에쿼티 = 음수
    - #5 보증금: 초기 투자금 차감, 매각 시 반환 (한국형 모델)
    - #6 셋업비: STR 초기 투자금에 가산, 매각 시 회수하지 않음
    """
    purchase_price = params["purchase_price"]
    ltv = params["ltv"]
    hold_years = params["hold_years"]
    tax_rate = params["tax_rate"]
    cap_rate = params["cap_rate"]
    building_ratio = params.get("building_ratio", 0.8)  # 건물 비중 (기본 80%)
    setup_cost = float(params.get("setup_cost", setup_cost))

    loan_principal = mortgage["principal"]
    loan_rate = mortgage["annual_rate"]
    loan_years = mortgage["loan_years"]

    # 로직 규칙 #5~6: 보증금은 실투자금 차감, STR 셋업비는 실투자금 가산
    equity = purchase_price - loan_principal - deposit + setup_cost
    ds = annual_debt_service(loan_principal, loan_rate, loan_years)

    # 로직 규칙 #3: 건물분만 정액법 감가 (내용연수 40년)
    building_value = purchase_price * building_ratio
    annual_depreciation = building_value / 40

    # 상환 스케줄 — 연도별 이자 추출용 (로직 규칙 #1)
    # DCF 내부계산은 무반올림 값을 사용하고, 화면 표시에서만 반올림한다.
    schedule = cpm_schedule(loan_principal, loan_rate, loan_years, round_output=False)

    rows = []
    cf_list = [-equity]  # t=0 (로직 규칙 #4: 에쿼티 음수)

    for yr in range(1, hold_years + 1):
        noi_yr = noi_year1 * (1 + noi_growth) ** (yr - 1)

        # 로직 규칙 #1: 해당 연도의 실제 이자 합계
        annual_interest = _annual_interest_from_schedule(schedule, yr)

        atcf = calculate_atcf(noi_yr, ds, annual_depreciation, annual_interest, tax_rate)

        # 세금 — 정확한 값으로 한 번만 계산
        taxable_income = noi_yr - annual_depreciation - annual_interest
        tax = max(taxable_income, 0) * tax_rate

        # 마지막 해 매각 현금흐름
        sale_cf = 0.0
        if yr == hold_years:
            terminal_noi = noi_year1 * (1 + noi_growth) ** yr  # 다음해 NOI
            # 매각가 = 터미널NOI / (Cap Rate + 0.005)
            terminal_value = terminal_noi / (cap_rate + 0.005)
            # 로직 규칙 #2: 매각 시 대출잔액
            remaining_loan = loan_balance_at(
                loan_principal, loan_rate, loan_years, yr
            )
            sale_cf = terminal_value - remaining_loan
            # 매각 차익에 대한 세금 (단순화: 동일 세율)
            capital_gain = terminal_value - purchase_price
            sale_tax = max(capital_gain, 0) * tax_rate
            sale_cf -= sale_tax
            # 로직 규칙 #5: 보증금은 신규 임차인 보증금으로 rollover (순현금유출 없음)

        total_cf = atcf + sale_cf
        cf_list.append(total_cf)

        rows.append({
            "연도": yr,
            "NOI": round(noi_yr),
            "DS": round(ds),
            "이자": round(annual_interest),
            "감가상각": round(annual_depreciation),
            "BTCF": round(noi_yr - ds),
            "세금": round(tax),
            "ATCF": round(atcf),
            "매도수익": round(sale_cf),
            "총CF": round(total_cf),
        })

    cf_df = pd.DataFrame(rows)

    # IRR / NPV / Equity Multiple
    try:
        irr_raw = npf.irr(cf_list)

        # IRR 수렴 실패 또는 전 기간 손실 체크
        if irr_raw is None or np.isnan(irr_raw):
            # 모든 현금흐름이 비양수(≤0)인 경우: 전 기간 손실
            if all(cf <= 0 for cf in cf_list):
                irr = -100.0  # "전 기간 손실" 표시 (명시적)
            else:
                irr = None  # 수렴 실패 (드물지만 가능)
        else:
            irr = irr_raw * 100
    except Exception:
        # 계산 오류 시에도 전 기간 손실 체크
        if all(cf <= 0 for cf in cf_list):
            irr = -100.0
        else:
            irr = None

    npv = npf.npv(cap_rate, cf_list)  # 할인율로 Cap Rate 사용
    total_cash_in = sum(c for c in cf_list[1:])
    equity_multiple = total_cash_in / equity if equity > 0 else 0

    return {
        "irr": irr,
        "npv": npv,
        "equity_multiple": equity_multiple,
        "equity": equity,
        "setup_cost": setup_cost,
        "cashflows": cf_df,
        "cf_list": cf_list,
    }


# ── 5. 2원 민감도 분석 (엑셀 데이터 테이블 재현) ────────────

def run_sensitivity_analysis(
    base_params: dict,
    mortgage: dict,
    mode: str,
) -> pd.DataFrame:
    """2변수 민감도 히트맵용 DataFrame을 반환한다.

    mode="str" : 점유율(행) × ADR(열) → IRR(%)
    mode="ltr" : 대출금리(행) × Cap Rate(열) → NPV(만 원)
    """
    if mode == "str":
        return _sensitivity_occ_adr(base_params, mortgage)
    elif mode == "ltr":
        return _sensitivity_rate_cap(base_params, mortgage)
    else:
        raise ValueError(f"Unknown mode: {mode}")


def _sensitivity_occ_adr(base_params: dict, mortgage: dict) -> pd.DataFrame:
    """점유율(행) × ADR(열) → IRR(%) 2차원 테이블."""
    p = base_params
    occ_range = np.arange(0.30, 1.00, 0.05)
    adr_base = p["adr"]
    adr_range = np.arange(adr_base * 0.6, adr_base * 1.5, adr_base * 0.1)

    results = np.empty((len(occ_range), len(adr_range)))

    for i, occ in enumerate(occ_range):
        for j, adr in enumerate(adr_range):
            noi_result = calculate_str_noi(
                adr, occ, p["cleaning_fee"], p["platform_fee"], p["opex_fixed"],
            )
            dcf = calculate_dcf_irr(noi_result["noi"], p, mortgage)
            results[i, j] = dcf["irr"] if dcf["irr"] is not None else np.nan

    occ_labels = [f"{o*100:.0f}%" for o in occ_range]
    adr_labels = [f"{a/10000:.1f}만" for a in adr_range]
    return pd.DataFrame(results, index=occ_labels, columns=adr_labels)


def _sensitivity_rate_cap(base_params: dict, mortgage: dict) -> pd.DataFrame:
    """대출금리(행) × Cap Rate(열) → NPV(만 원) 2차원 테이블."""
    p = base_params
    rate_range = np.arange(0.02, 0.085, 0.005)
    cap_range = np.arange(0.03, 0.075, 0.005)

    results = np.empty((len(rate_range), len(cap_range)))

    for i, rate in enumerate(rate_range):
        for j, cap in enumerate(cap_range):
            # 금리가 바뀌면 mortgage도 재계산
            new_mortgage = {
                "principal": mortgage["principal"],
                "annual_rate": rate,
                "loan_years": mortgage["loan_years"],
            }
            new_params = {**p, "cap_rate": cap}
            dcf = calculate_dcf_irr(p["noi_for_sensitivity"], new_params, new_mortgage)
            results[i, j] = dcf["npv"] / 10000  # 만원 단위

    rate_labels = [f"{r*100:.1f}%" for r in rate_range]
    cap_labels = [f"{c*100:.1f}%" for c in cap_range]
    return pd.DataFrame(results, index=rate_labels, columns=cap_labels)
