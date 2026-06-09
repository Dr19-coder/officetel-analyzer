"""한국은행 ECOS Open API - 주요 금융 지표 조회.

엔드포인트: https://ecos.bok.or.kr/api/KeyStatisticList/{key}/json/kr/1/101
"""

import os
import requests


def _load_bok_api_key() -> str:
    try:
        import streamlit as st
        return st.secrets["BOK_API_KEY"]
    except Exception:
        from dotenv import load_dotenv
        load_dotenv()
        return os.getenv("BOK_API_KEY", "")


# 앱에 표시할 지표 (ECOS 명칭 → 표시 라벨)
_STAT_MAP = [
    ("한국은행 기준금리",    "기준금리"),
    ("예금은행 대출금리",    "은행 대출금리"),
    ("국고채수익률(3년)",    "국고채(3년)"),
    ("CD수익률(91일)",       "CD금리(91일)"),
    ("원/달러 환율(종가)",   "원/달러"),
    ("소비자물가지수",       "소비자물가지수"),
    ("주택매매가격지수",     "주택매매가격지수"),
]


def get_investment_indicators() -> dict:
    """투자 판정에 쓰이는 주요 BOK 지표를 반환한다.

    Returns
    -------
    dict : label → {"value": float, "unit": str, "date": str}
           오류 발생 시 {"_error": 오류메시지} 반환.
    """
    key = _load_bok_api_key()
    if not key:
        return {"_error": "BOK_API_KEY가 설정되지 않았습니다. Streamlit Cloud Secrets 또는 .env를 확인하세요."}

    url = f"https://ecos.bok.or.kr/api/KeyStatisticList/{key}/json/kr/1/101"
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        rows = resp.json().get("KeyStatisticList", {}).get("row", [])
    except Exception as e:
        return {"_error": f"API 호출 실패: {e}"}

    lookup = {r["KEYSTAT_NAME"]: r for r in rows}
    result = {}
    for stat_name, label in _STAT_MAP:
        if stat_name not in lookup:
            continue
        row = lookup[stat_name]
        try:
            val = float(row["DATA_VALUE"])
        except (ValueError, TypeError):
            continue
        result[label] = {
            "value": val,
            "unit": row.get("UNIT_NAME") or "",
            "date": row.get("CYCLE", ""),
        }
    return result
