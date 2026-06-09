"""CPM(Constant Payment Mortgage) 상환표 모듈."""

import numpy as np
import pandas as pd


def cpm_schedule(
    principal: float,
    annual_rate: float,
    years: int,
    round_output: bool = True,
) -> pd.DataFrame:
    """월별 원리금균등(CPM) 상환 스케줄을 반환한다.

    Parameters
    ----------
    principal : float
        대출 원금 (원)
    annual_rate : float
        연이율 (예: 0.05 = 5 %)
    years : int
        대출 기간 (년)
    round_output : bool
        True면 화면 표시용으로 원 단위 반올림, False면 DCF 내부계산용 원값 유지

    Returns
    -------
    pd.DataFrame
        columns: 회차, 월상환액, 이자, 원금, 잔액
    """
    monthly_rate = annual_rate / 12
    n_months = years * 12

    if monthly_rate == 0:
        pmt = principal / n_months
    else:
        pmt = principal * monthly_rate / (1 - (1 + monthly_rate) ** (-n_months))

    rows = []
    balance = principal
    for i in range(1, n_months + 1):
        interest = balance * monthly_rate
        repay_principal = pmt - interest
        balance -= repay_principal
        if balance < 0:
            balance = 0.0

        row = {
            "회차": i,
            "월상환액": pmt,
            "이자": interest,
            "원금": repay_principal,
            "잔액": balance,
        }

        if round_output:
            row = {
                "회차": i,
                "월상환액": round(pmt),
                "이자": round(interest),
                "원금": round(repay_principal),
                "잔액": round(balance),
            }

        rows.append(row)
    return pd.DataFrame(rows)


def annual_debt_service(principal: float, annual_rate: float, years: int) -> float:
    """연간 원리금 상환액(DS)을 반환한다."""
    monthly_rate = annual_rate / 12
    n_months = years * 12

    if monthly_rate == 0:
        pmt = principal / n_months
    else:
        pmt = principal * monthly_rate / (1 - (1 + monthly_rate) ** (-n_months))

    return pmt * 12


def loan_balance_at(principal: float, annual_rate: float, years: int, after_year: int) -> float:
    """대출 실행 후 after_year 년 시점의 잔액을 반환한다."""
    monthly_rate = annual_rate / 12
    n_months = years * 12
    k = after_year * 12  # 경과 개월

    if monthly_rate == 0:
        return principal - principal / n_months * k

    pmt = principal * monthly_rate / (1 - (1 + monthly_rate) ** (-n_months))
    balance = principal * (1 + monthly_rate) ** k - pmt * ((1 + monthly_rate) ** k - 1) / monthly_rate
    return max(balance, 0.0)
