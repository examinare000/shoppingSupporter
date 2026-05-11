"""サジェスト決定ロジック (T-20).

決定アルゴリズム（優先順）:
    1. current_best_price or price_stats が None → buy_now（データ不足）
    2. upcoming_sales が存在し estimated_saving >= 5% → wait
    3. current_best_price <= price_stats.median * 0.98 → buy_now（お得な価格帯）
    4. デフォルト → buy_now

設計判断:
    - 純粋関数。DB・HTTP 依存なし。
    - SuggestionInput/SuggestionResult は frozen dataclass（エンジン層の不変原則）。
    - wait 時の節約額は floor(current_best_price * bonus_rate) で整数計算する。
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date
from typing import Literal, Optional

from .forecaster import PriceStats, UpcomingSale

# 待機推奨の最小節約率（5%）
_WAIT_SAVING_THRESHOLD_RATE: float = 0.05

# buy_now 判定の中央値比率（現在価格が中央値の 98% 以下なら「お得」）
_BUY_NOW_MEDIAN_RATE: float = 0.98


@dataclass(frozen=True)
class SuggestionInput:
    """compute_suggestion への入力値。

    current_best_price=None は「現在の最安価格が取得できない」状態。
    price_stats=None は「価格履歴が 0 件」状態。
    """
    current_best_price: Optional[int]
    price_stats: Optional[PriceStats]
    upcoming_sales: list[UpcomingSale]


@dataclass(frozen=True)
class SuggestionResult:
    """compute_suggestion の出力値。

    wait 時: expected_sale_effective_price, estimated_saving, next_sale_date,
             next_sale_campaign が設定される。
    buy_now 時: 上記 4 フィールドは None。
    """
    action: Literal["buy_now", "wait"]
    rationale: str
    current_best_effective_price: Optional[int]
    expected_sale_effective_price: Optional[int]
    estimated_saving: Optional[int]
    next_sale_date: Optional[date]
    next_sale_campaign: Optional[str]


def compute_suggestion(inp: SuggestionInput) -> SuggestionResult:
    """購入タイミングサジェストを決定する純粋関数。

    ステップ 1: データ不足チェック
    ステップ 2: wait 判定（upcoming_sales かつ節約率 >= 5%）
    ステップ 3/4: buy_now（median 比較 or デフォルト）
    """
    # ── ステップ 1: データ不足 ────────────────────────────────────────────────
    if inp.current_best_price is None or inp.price_stats is None:
        return _buy_now_result(
            current_best_effective_price=inp.current_best_price,
            rationale="価格データが不足しているため、買い時の判断ができません。現在の価格でご検討ください。",
        )

    current_price = inp.current_best_price

    # ── ステップ 2: wait 判定 ────────────────────────────────────────────────
    if inp.upcoming_sales:
        sale = inp.upcoming_sales[0]  # 最も近い次回セール
        expected_price = math.floor(current_price * (1 - sale.bonus_rate))
        saving = current_price - expected_price
        threshold = math.floor(current_price * _WAIT_SAVING_THRESHOLD_RATE)

        if saving >= threshold:
            return SuggestionResult(
                action="wait",
                rationale=(
                    f"近日中に{sale.campaign_name}が予定されています。"
                    f"約{sale.bonus_rate * 100:.0f}%のポイント還元で"
                    f"実質¥{saving:,}の節約が見込めます。"
                ),
                current_best_effective_price=current_price,
                expected_sale_effective_price=expected_price,
                estimated_saving=saving,
                next_sale_date=sale.estimated_date,
                next_sale_campaign=sale.campaign_name,
            )

    # ── ステップ 3: 価格が中央値の 98% 以下 → buy_now ────────────────────────
    median_threshold = inp.price_stats.median * _BUY_NOW_MEDIAN_RATE
    if current_price <= median_threshold:
        return _buy_now_result(
            current_best_effective_price=current_price,
            rationale=(
                "現在の価格は過去の中央値を下回っています。今が買い時です。"
            ),
        )

    # ── ステップ 4: デフォルト buy_now ───────────────────────────────────────
    return _buy_now_result(
        current_best_effective_price=current_price,
        rationale="現時点では特に有利なセールや価格の目安はありません。必要であれば今すぐ購入することをおすすめします。",
    )


def _buy_now_result(
    current_best_effective_price: Optional[int],
    rationale: str,
) -> SuggestionResult:
    """buy_now の SuggestionResult を構築するヘルパー。"""
    return SuggestionResult(
        action="buy_now",
        rationale=rationale,
        current_best_effective_price=current_best_effective_price,
        expected_sale_effective_price=None,
        estimated_saving=None,
        next_sale_date=None,
        next_sale_campaign=None,
    )
