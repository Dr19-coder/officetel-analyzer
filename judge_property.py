"""내 매물 판정 함수."""


def judge_property(
    str_irr: float,
    breakeven_occupancy: float,
    expected_occupancy: float,
    str_noi: float,
    ltr_noi: float,
) -> dict:
    """사용자 매물에 대한 판정을 반환한다.

    Parameters
    ----------
    str_irr : 단기임대 IRR (%)
    breakeven_occupancy : 손익분기 점유율 (0~1)
    expected_occupancy : 예상 점유율 (0~1)
    str_noi : 단기임대 NOI (원)
    ltr_noi : 장기임대 NOI (원)

    Returns
    -------
    dict with keys: verdict, color, emoji, reason
        verdict: "추천" / "신중" / "비추천"
        color: "success" / "warning" / "error"
        emoji: "✅" / "⚠️" / "❌"
        reason: 판정 이유 (str)
    """
    # IRR이 None이거나 -100인 경우 처리
    if str_irr is None or str_irr == -100.0:
        return {
            "verdict": "비추천",
            "color": "error",
            "emoji": "❌",
            "reason": "단기임대로 수익을 낼 수 없습니다 (전 기간 손실).",
        }

    # 손익분기 점검
    if expected_occupancy < breakeven_occupancy:
        return {
            "verdict": "비추천",
            "color": "error",
            "emoji": "❌",
            "reason": f"예상 점유율({expected_occupancy*100:.0f}%)이 손익분기({breakeven_occupancy*100:.0f}%)에 못 미칩니다. "
                     f"장기임대보다 수익이 낮을 가능성이 높습니다.",
        }

    # IRR 기준 판정
    if str_irr >= 15.0:
        noi_ratio = str_noi / ltr_noi if ltr_noi > 0 else 0
        return {
            "verdict": "추천",
            "color": "success",
            "emoji": "✅",
            "reason": f"목표 수익률(15%) 달성! IRR {str_irr:.1f}%로 에어비앤비 투자 적합합니다. "
                     f"단기임대 NOI가 장기임대 대비 {noi_ratio:.1f}배 높습니다.",
        }
    elif str_irr >= 5.0:
        return {
            "verdict": "신중",
            "color": "warning",
            "emoji": "⚠️",
            "reason": f"IRR {str_irr:.1f}%로 본전은 넘지만 목표 수익률(15%)에는 미달합니다. "
                     f"점유율 유지에 자신 있다면 고려 가능하나, 리스크를 신중히 평가하세요.",
        }
    else:
        return {
            "verdict": "비추천",
            "color": "error",
            "emoji": "❌",
            "reason": f"IRR {str_irr:.1f}%로 목표 수익률에 크게 못 미칩니다. "
                     f"일반 임대(4~7%) 수준에도 미달하여 투자 매력이 낮습니다.",
        }
