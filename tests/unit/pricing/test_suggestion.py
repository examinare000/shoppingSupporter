"""Unit tests for api.lib.pricing.suggestion (T-19).

対象: compute_suggestion の決定ロジック

決定アルゴリズム（優先順）:
    1. price_stats is None → buy_now（データ不足）
    2. upcoming_sales が存在し estimated_saving >= 5% → wait
    3. current_best_price <= price_stats.median * 0.98 → buy_now（お得な価格）
    4. デフォルト → buy_now

Why ユニットテストで網羅するか:
    ステップ間の優先順位が微妙で、インテグレーションテストではシナリオを
    精密に制御しにくい。純粋関数なので DB なしで全分岐を検証できる。
"""
from __future__ import annotations

import math
from datetime import date

import pytest

from api.lib.pricing.forecaster import PriceStats, UpcomingSale
from api.lib.pricing.suggestion import SuggestionInput, SuggestionResult, compute_suggestion


# ── ヘルパー ──────────────────────────────────────────────────────────────────


def _make_price_stats(
    sample_count: int = 10,
    median: float = 10000.0,
    mean: float = 10000.0,
    min_price: int = 8000,
    max_price: int = 12000,
    avg_30d: float | None = 10000.0,
    avg_90d: float | None = 10000.0,
) -> PriceStats:
    return PriceStats(
        sample_count=sample_count,
        median=median,
        mean=mean,
        min_price=min_price,
        max_price=max_price,
        avg_30d=avg_30d,
        avg_90d=avg_90d,
    )


def _make_upcoming_sale(
    campaign_name: str = "お買い物マラソン",
    estimated_date: date = date(2026, 5, 15),
    bonus_rate: float = 0.10,
) -> UpcomingSale:
    return UpcomingSale(
        campaign_name=campaign_name,
        estimated_date=estimated_date,
        bonus_rate=bonus_rate,
    )


# ── SuggestionInput の型確認 ──────────────────────────────────────────────────


class TestSuggestionInputDataclass:
    def test_is_frozen(self):
        """SuggestionInput は frozen dataclass。"""
        inp = SuggestionInput(
            current_best_price=10000,
            price_stats=None,
            upcoming_sales=[],
        )
        with pytest.raises(Exception):  # FrozenInstanceError
            inp.current_best_price = 9000  # type: ignore


# ── ステップ 1: データ不足 ────────────────────────────────────────────────────


class TestComputeSuggestionDataInsufficiency:
    """price_stats/current_best_price が None のときのフォールバック動作。"""

    def test_returns_buy_now_when_price_stats_is_none(self):
        """価格履歴なし（price_stats=None）→ buy_now。"""
        inp = SuggestionInput(
            current_best_price=10000,
            price_stats=None,
            upcoming_sales=[],
        )

        result = compute_suggestion(inp)

        assert isinstance(result, SuggestionResult)
        assert result.action == "buy_now"

    def test_rationale_is_non_empty_when_price_stats_is_none(self):
        """データ不足時でも rationale は非空の文字列。"""
        inp = SuggestionInput(
            current_best_price=10000,
            price_stats=None,
            upcoming_sales=[],
        )

        result = compute_suggestion(inp)

        assert isinstance(result.rationale, str)
        assert len(result.rationale) > 0

    def test_returns_buy_now_when_no_current_price(self):
        """current_best_price=None → 比較不能として buy_now。

        Why: 現在価格が不明では節約額を計算できない。
        wait を推奨してもユーザーが節約額を確認できない。
        """
        inp = SuggestionInput(
            current_best_price=None,
            price_stats=_make_price_stats(),
            upcoming_sales=[_make_upcoming_sale(bonus_rate=0.20)],
        )

        result = compute_suggestion(inp)

        assert result.action == "buy_now"


# ── ステップ 2: wait 判定（5% 節約閾値）────────────────────────────────────


class TestComputeSuggestionWaitDecision:
    """upcoming_sales が存在し節約額 >= 5% のとき wait を返す。"""

    def test_returns_wait_when_saving_over_5_percent(self):
        """10% ボーナス → 節約額 10% >= 5% → wait。"""
        # 10% bonus on 10000 = 1000 saving, threshold = 500 (5%)
        sale = _make_upcoming_sale(bonus_rate=0.10)
        inp = SuggestionInput(
            current_best_price=10000,
            price_stats=_make_price_stats(),
            upcoming_sales=[sale],
        )

        result = compute_suggestion(inp)

        assert result.action == "wait"

    def test_returns_wait_when_saving_exactly_5_percent(self):
        """5% ちょうどの節約でも wait（境界値: >= 5%）。"""
        # 5% bonus on 10000 → expected = 9500, saving = 500, threshold = 500
        sale = _make_upcoming_sale(bonus_rate=0.05)
        inp = SuggestionInput(
            current_best_price=10000,
            price_stats=_make_price_stats(),
            upcoming_sales=[sale],
        )

        result = compute_suggestion(inp)

        assert result.action == "wait"

    def test_does_not_return_wait_when_saving_under_5_percent(self):
        """4% の節約は閾値未満 → wait にならない。"""
        # 4% bonus on 10000 → saving = 400, threshold = 500 → 400 < 500
        sale = _make_upcoming_sale(bonus_rate=0.04)
        inp = SuggestionInput(
            current_best_price=10000,
            price_stats=_make_price_stats(),
            upcoming_sales=[sale],
        )

        result = compute_suggestion(inp)

        assert result.action == "buy_now"

    def test_wait_result_contains_correct_sale_details(self):
        """wait 時: 節約額・セール日・キャンペーン名・各価格が result に含まれる。"""
        sale = _make_upcoming_sale(
            campaign_name="お買い物マラソン",
            estimated_date=date(2026, 5, 15),
            bonus_rate=0.10,
        )
        inp = SuggestionInput(
            current_best_price=10000,
            price_stats=_make_price_stats(),
            upcoming_sales=[sale],
        )

        result = compute_suggestion(inp)

        assert result.action == "wait"
        assert result.current_best_effective_price == 10000
        # expected_sale = floor(10000 * (1 - 0.10)) = 9000
        assert result.expected_sale_effective_price == math.floor(10000 * 0.90)
        # saving = 10000 - 9000 = 1000
        assert result.estimated_saving == 1000
        assert result.next_sale_date == date(2026, 5, 15)
        assert result.next_sale_campaign == "お買い物マラソン"

    def test_wait_uses_first_upcoming_sale(self):
        """複数の upcoming_sales がある場合、リストの先頭（最近の日）が使われる。

        Why 先頭: estimate_next_sales が日付昇順で返す前提。
        最も近いセールで節約できるかを判断するのが自然。
        """
        sale1 = _make_upcoming_sale(
            campaign_name="セールA",
            estimated_date=date(2026, 5, 15),
            bonus_rate=0.10,
        )
        sale2 = _make_upcoming_sale(
            campaign_name="セールB",
            estimated_date=date(2026, 5, 20),
            bonus_rate=0.10,
        )
        inp = SuggestionInput(
            current_best_price=10000,
            price_stats=_make_price_stats(),
            upcoming_sales=[sale1, sale2],
        )

        result = compute_suggestion(inp)

        assert result.next_sale_campaign == "セールA"
        assert result.next_sale_date == date(2026, 5, 15)

    def test_wait_overrides_low_price_check(self):
        """wait 条件（5% 節約）は median チェック（ステップ3）より優先される。

        Why: アルゴリズムのステップ順を検証するために必要。
        current_best_price が median * 0.98 以下であっても、
        十分な節約が見込めるなら wait を推奨する方がユーザー利益に適う。
        """
        # current=9000, median=10000, 98%=9800 → ステップ3では buy_now になるはず
        # しかしセールで 900 節約 (>450 閾値) → ステップ2 で wait
        sale = _make_upcoming_sale(bonus_rate=0.10)
        inp = SuggestionInput(
            current_best_price=9000,
            price_stats=_make_price_stats(median=10000.0),
            upcoming_sales=[sale],
        )

        result = compute_suggestion(inp)

        assert result.action == "wait"


# ── ステップ 3 / デフォルト: buy_now 判定 ─────────────────────────────────


class TestComputeSuggestionBuyNowDecision:
    """upcoming_sales がない or 節約不足のとき、価格と median の比較で判断する。"""

    def test_returns_buy_now_when_price_at_exactly_98_percent_of_median(self):
        """current_best_price == median * 0.98 → buy_now（境界値）。"""
        # 10000 * 0.98 = 9800
        inp = SuggestionInput(
            current_best_price=9800,
            price_stats=_make_price_stats(median=10000.0),
            upcoming_sales=[],
        )

        result = compute_suggestion(inp)

        assert result.action == "buy_now"

    def test_returns_buy_now_when_price_below_98_percent_of_median(self):
        """current_best_price < median * 0.98 でも buy_now（お得な価格帯）。"""
        inp = SuggestionInput(
            current_best_price=9000,
            price_stats=_make_price_stats(median=10000.0),
            upcoming_sales=[],
        )

        result = compute_suggestion(inp)

        assert result.action == "buy_now"

    def test_returns_buy_now_by_default_when_no_upcoming_sales(self):
        """upcoming_sales なし・価格が高め → デフォルト buy_now。"""
        # 10500 > 9800 (98% of 10000) → not triggered by step 3
        inp = SuggestionInput(
            current_best_price=10500,
            price_stats=_make_price_stats(median=10000.0),
            upcoming_sales=[],
        )

        result = compute_suggestion(inp)

        assert result.action == "buy_now"

    def test_returns_buy_now_when_upcoming_sale_saving_under_threshold_and_price_is_low(self):
        """節約不足 + 価格が低い → buy_now（ステップ2が失敗してステップ3が適用）。"""
        # 4% bonus: saving=400 < 500 threshold → step 2 fails
        # price=9000 <= 9800 (98% of 10000) → step 3 → buy_now
        sale = _make_upcoming_sale(bonus_rate=0.04)
        inp = SuggestionInput(
            current_best_price=9000,
            price_stats=_make_price_stats(median=10000.0),
            upcoming_sales=[sale],
        )

        result = compute_suggestion(inp)

        assert result.action == "buy_now"


# ── SuggestionResult の構造検証 ─────────────────────────────────────────────


class TestComputeSuggestionResultStructure:
    """result オブジェクトのフィールド型・値を検証する。"""

    def test_buy_now_optional_fields_are_none(self):
        """buy_now 時: expected_sale_effective_price 等は None。"""
        inp = SuggestionInput(
            current_best_price=10000,
            price_stats=None,
            upcoming_sales=[],
        )

        result = compute_suggestion(inp)

        assert result.action == "buy_now"
        assert result.expected_sale_effective_price is None
        assert result.estimated_saving is None
        assert result.next_sale_date is None
        assert result.next_sale_campaign is None

    def test_result_is_frozen(self):
        """SuggestionResult は frozen dataclass（不変）。"""
        inp = SuggestionInput(
            current_best_price=None,
            price_stats=None,
            upcoming_sales=[],
        )
        result = compute_suggestion(inp)

        with pytest.raises(Exception):  # FrozenInstanceError
            result.action = "wait"  # type: ignore

    def test_rationale_is_always_non_empty_string(self):
        """全分岐で rationale は非空の文字列。"""
        cases = [
            SuggestionInput(current_best_price=10000, price_stats=None, upcoming_sales=[]),
            SuggestionInput(
                current_best_price=10000,
                price_stats=_make_price_stats(),
                upcoming_sales=[_make_upcoming_sale(bonus_rate=0.10)],
            ),
            SuggestionInput(
                current_best_price=9000,
                price_stats=_make_price_stats(median=10000.0),
                upcoming_sales=[],
            ),
        ]
        for inp in cases:
            result = compute_suggestion(inp)
            assert isinstance(result.rationale, str), f"rationale must be str for {inp}"
            assert len(result.rationale) > 0, f"rationale must not be empty for {inp}"

    def test_wait_result_is_frozen(self):
        """wait の SuggestionResult も frozen。"""
        sale = _make_upcoming_sale(bonus_rate=0.10)
        inp = SuggestionInput(
            current_best_price=10000,
            price_stats=_make_price_stats(),
            upcoming_sales=[sale],
        )
        result = compute_suggestion(inp)

        assert result.action == "wait"
        with pytest.raises(Exception):
            result.estimated_saving = 0  # type: ignore
