"""국토부 실거래가 API 호출 모듈.

오피스텔 매매가 및 전월세 실거래 데이터를 가져온다.
"""

import os
import requests
import xml.etree.ElementTree as ET
import pandas as pd
from datetime import datetime
from typing import Optional
from dotenv import load_dotenv


# .env 파일 로드
load_dotenv()

# API 설정
API_KEY = os.getenv("DATA_GO_KR_KEY")
BASE_URL_TRADE = "https://apis.data.go.kr/1613000/RTMSDataSvcOffiTrade/getRTMSDataSvcOffiTrade"
BASE_URL_RENT = "https://apis.data.go.kr/1613000/RTMSDataSvcOffiRent/getRTMSDataSvcOffiRent"


def fetch_officetel_trade(
    lawd_cd: str,
    deal_ymd: str,
    page_no: int = 1,
    num_of_rows: int = 100,
) -> pd.DataFrame:
    """오피스텔 매매 실거래가를 조회한다.

    Parameters
    ----------
    lawd_cd : str
        지역코드 5자리 (예: 11680 = 강남구)
    deal_ymd : str
        계약년월 6자리 (예: 202406)
    page_no : int
        페이지 번호 (기본: 1)
    num_of_rows : int
        한 페이지 결과 수 (기본: 100)

    Returns
    -------
    pd.DataFrame
        columns: sggNm, umdNm, jibun, offiNm, excluUseAr, dealAmount(원), floor, buildYear, dealDate
    """
    params = {
        "serviceKey": API_KEY,
        "LAWD_CD": lawd_cd,
        "DEAL_YMD": deal_ymd,
        "pageNo": page_no,
        "numOfRows": num_of_rows,
    }

    response = requests.get(BASE_URL_TRADE, params=params, timeout=10)
    response.raise_for_status()

    # XML 파싱
    root = ET.fromstring(response.content)

    # 결과 확인 (resultCode "000" = 정상)
    result_code = root.find(".//resultCode")
    if result_code is not None and result_code.text not in ["00", "000"]:
        result_msg = root.find(".//resultMsg").text if root.find(".//resultMsg") is not None else "Unknown error"
        raise ValueError(f"API Error: {result_msg} (code: {result_code.text})")

    # 데이터 추출
    items = root.findall(".//item")
    records = []

    for item in items:
        deal_amount_str = item.findtext("dealAmount", "0").replace(",", "").strip()
        try:
            deal_amount = int(deal_amount_str) * 10000  # 만원 → 원
        except ValueError:
            continue  # 빈 값이나 파싱 불가 시 스킵

        try:
            floor_val = int(item.findtext("floor", "0").strip() or "0")
        except ValueError:
            floor_val = 0

        try:
            build_year_val = int(item.findtext("buildYear", "0").strip() or "0")
        except ValueError:
            build_year_val = 0

        records.append({
            "sggNm": item.findtext("sggNm", ""),
            "umdNm": item.findtext("umdNm", ""),
            "jibun": item.findtext("jibun", ""),
            "offiNm": item.findtext("offiNm", ""),
            "excluUseAr": float(item.findtext("excluUseAr", "0")),
            "dealAmount": deal_amount,
            "floor": floor_val,
            "buildYear": build_year_val,
            "dealDate": f"{item.findtext('dealYear', '')}-{item.findtext('dealMonth', '').zfill(2)}-{item.findtext('dealDay', '').zfill(2)}",
        })

    return pd.DataFrame(records)


def fetch_officetel_rent(
    lawd_cd: str,
    deal_ymd: str,
    page_no: int = 1,
    num_of_rows: int = 100,
    monthly_only: bool = True,
) -> pd.DataFrame:
    """오피스텔 전월세 실거래가를 조회한다.

    Parameters
    ----------
    lawd_cd : str
        지역코드 5자리
    deal_ymd : str
        계약년월 6자리
    page_no : int
        페이지 번호 (기본: 1)
    num_of_rows : int
        한 페이지 결과 수 (기본: 100)
    monthly_only : bool
        True일 경우 월세(monthlyRent > 0)만 반환 (기본: True, 전세 제외)

    Returns
    -------
    pd.DataFrame
        columns: sggNm, umdNm, jibun, offiNm, excluUseAr, deposit(원), monthlyRent(원), floor, buildYear, dealDate, contractType
    """
    params = {
        "serviceKey": API_KEY,
        "LAWD_CD": lawd_cd,
        "DEAL_YMD": deal_ymd,
        "pageNo": page_no,
        "numOfRows": num_of_rows,
    }

    response = requests.get(BASE_URL_RENT, params=params, timeout=10)
    response.raise_for_status()

    # XML 파싱
    root = ET.fromstring(response.content)

    # 결과 확인 (resultCode "000" = 정상)
    result_code = root.find(".//resultCode")
    if result_code is not None and result_code.text not in ["00", "000"]:
        result_msg = root.find(".//resultMsg").text if root.find(".//resultMsg") is not None else "Unknown error"
        raise ValueError(f"API Error: {result_msg} (code: {result_code.text})")

    # 데이터 추출
    items = root.findall(".//item")
    records = []

    for item in items:
        # 보증금, 월세 (만원 → 원)
        deposit_str = item.findtext("deposit", "0").replace(",", "").strip()
        monthly_rent_str = item.findtext("monthlyRent", "0").replace(",", "").strip()

        try:
            deposit = int(deposit_str) * 10000
        except ValueError:
            deposit = 0

        try:
            monthly_rent = int(monthly_rent_str) * 10000
        except ValueError:
            monthly_rent = 0

        # 월세만 필터링 (monthly_only=True일 때)
        if monthly_only and monthly_rent == 0:
            continue

        try:
            floor_val = int(item.findtext("floor", "0").strip() or "0")
        except ValueError:
            floor_val = 0

        try:
            build_year_val = int(item.findtext("buildYear", "0").strip() or "0")
        except ValueError:
            build_year_val = 0

        records.append({
            "sggNm": item.findtext("sggNm", ""),
            "umdNm": item.findtext("umdNm", ""),
            "jibun": item.findtext("jibun", ""),
            "offiNm": item.findtext("offiNm", ""),
            "excluUseAr": float(item.findtext("excluUseAr", "0")),
            "deposit": deposit,
            "monthlyRent": monthly_rent,
            "floor": floor_val,
            "buildYear": build_year_val,
            "dealDate": f"{item.findtext('dealYear', '')}-{item.findtext('dealMonth', '').zfill(2)}-{item.findtext('dealDay', '').zfill(2)}",
            "contractType": item.findtext("contractType", ""),
        })

    return pd.DataFrame(records)


def get_recent_month_ymd() -> str:
    """최근 1개월 전 YYYYMM 반환 (예: 202405)."""
    from dateutil.relativedelta import relativedelta
    one_month_ago = datetime.now() - relativedelta(months=1)
    return one_month_ago.strftime("%Y%m")


if __name__ == "__main__":
    # 테스트: 강남(11680) 최근 1개월 전월세 조회
    import sys
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

    print("=" * 70)
    print("국토부 API 테스트 - 강남 전월세 (월세만)")
    print("=" * 70)

    if not API_KEY or API_KEY == "여기에_실제_인증키를_입력하세요":
        print("\n[!] .env 파일에 DATA_GO_KR_KEY를 설정해주세요.")
        print("공공데이터포털(data.go.kr)에서 발급받은 인증키를 입력하세요.\n")
    else:
        try:
            recent_ymd = get_recent_month_ymd()
            print(f"\n조회 대상: 강남구(11680), {recent_ymd}")
            print("-" * 70)

            df_rent = fetch_officetel_rent("11680", recent_ymd, num_of_rows=10)

            if len(df_rent) > 0:
                print(f"\n[OK] 총 {len(df_rent)}건 조회 성공\n")
                print(df_rent[["sggNm", "umdNm", "offiNm", "excluUseAr", "deposit", "monthlyRent", "dealDate"]].to_string(index=False))

                print("\n통계:")
                print(f"  평균 보증금: {df_rent['deposit'].mean()/10000:,.0f}만원")
                print(f"  평균 월세: {df_rent['monthlyRent'].mean()/10000:,.0f}만원")
                print(f"  평균 전용면적: {df_rent['excluUseAr'].mean():.2f}㎡")
            else:
                print("\n[!] 해당 기간 월세 거래 없음 (전세만 있거나 데이터 없음)")

        except Exception as e:
            print(f"\n[ERROR] API 호출 실패: {e}")
