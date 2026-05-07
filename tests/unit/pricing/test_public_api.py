"""`api.lib.pricing` の公開インターフェース (build_context, compute_pricing) のテスト。

Why このファイルで __init__.py のテストを test_engine.py と分離する:
    test_engine.py は ORM に依存しない純粋関数エンジンをテストする。
    このファイルは ORM アダプター層 (build_context) と
    公開インターフェース (compute_pricing) を専門にテストする。
    責務の分離により、エンジンバグとアダプターバグを区別できる。
"""

from __future__ import annotations

from types import MappingProxyType, SimpleNamespace

import pytest

from api.common.models import RakutenRank as ModelRakutenRank
from api.lib.pricing import (
    RakutenRank,
    SiteType,
    UserContext,
    build_context,
    compute_pricing,
)
from api.lib.pricing.engine import calculate_effective_price


# ── Helpers ──────────────────────────────────────────────────────────────────


def make_profile(**kwargs) -> SimpleNamespace:
    """ORM UserProfile を SimpleNamespace で模倣する。

    Why SimpleNamespace: ORM モデルを直接インスタンス化するには DB セッションが
    必要。SimpleNamespace は duck typing で同じ属性アクセスを提供し、
    外部依存なしでユニットテストを完結させられる。
    """
    defaults = dict(
        rakuten_rank=ModelRakutenRank.REGULAR,
        is_amazon_prime=False,
        is_rakuten_mobile=False,
        yahoo_premium=False,
        is_paypay_linked=False,
    )
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def make_card(**kwargs) -> SimpleNamespace:
    """ORM Card を SimpleNamespace で模倣する。"""
    defaults = dict(base_reward_rate=1.0, special_rewards={})
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


# ── build_context のテスト ────────────────────────────────────────────────────


class TestBuildContext:
    def test_profile_none_card_none_returns_default_user_context(self):
        """profile=None, card=None のとき UserContext デフォルト値を返す。

        ゲストユーザー（未認証）の場合に相当。compute_pricing でも同様の動作。
        """
        # Given: no profile, no card
        # When
        ctx = build_context(None, None)
        # Then
        assert ctx == UserContext()

    def test_profile_none_card_non_none_ignores_card(self):
        """profile=None のとき card が non-None でも UserContext() デフォルトを返す。

        Why: profile=None は未認証ゲストを意味するため、カード情報があっても無視する。
        カードなしゲストと同じ扱いにすることで、認証状態の境界を明確に保つ。
        """
        # Given: no profile, but card is present
        card = make_card(base_reward_rate=2.0, special_rewards={"amazon": 1.5})
        # When
        ctx = build_context(None, card)
        # Then: card は無視されてデフォルトの UserContext() と等しい
        assert ctx == UserContext()

    def test_profile_set_card_none_uses_default_card_rate(self):
        """profile が設定されているが card=None のとき card_base_rate=0.0 になる。"""
        # Given
        profile = make_profile(rakuten_rank=ModelRakutenRank.REGULAR)
        # When
        ctx = build_context(profile, None)
        # Then
        assert ctx.card_base_rate == 0.0
        assert ctx.card_special_rewards is None

    def test_profile_and_card_populates_context_fully(self):
        """profile と card の両方が設定されているとき、全フィールドが正しく変換される。"""
        # Given
        profile = make_profile(
            rakuten_rank=ModelRakutenRank.DIAMOND,
            is_rakuten_mobile=True,
        )
        card = make_card(
            base_reward_rate=2.0,
            special_rewards={"rakuten": 4.0},
        )
        # When
        ctx = build_context(profile, card)
        # Then
        assert ctx.rakuten_rank == RakutenRank.DIAMOND
        assert ctx.is_rakuten_mobile is True
        assert ctx.card_base_rate == 2.0
        assert ctx.card_special_rewards == {"rakuten": 4.0}

    def test_profile_booleans_are_passed_through(self):
        """profile の boolean フラグが UserContext に正しく反映される。"""
        # Given
        profile = make_profile(
            is_amazon_prime=True,
            is_rakuten_mobile=True,
            yahoo_premium=True,
            is_paypay_linked=True,
        )
        # When
        ctx = build_context(profile, None)
        # Then
        assert ctx.is_amazon_prime is True
        assert ctx.is_rakuten_mobile is True
        assert ctx.yahoo_premium is True
        assert ctx.is_paypay_linked is True

    def test_special_rewards_mapping_proxy_converted_to_dict(self):
        """card.special_rewards が MappingProxyType でも dict に変換される。

        Why: SQLAlchemy の JSON カラムは MappingProxy を返す場合がある。
        engine.py の get() は通常 dict を想定しているため、変換が必要。
        """
        # Given: MappingProxyType で SQLAlchemy JSON カラムの返り値を模倣
        card = make_card(special_rewards=MappingProxyType({"amazon": 1.5}))
        profile = make_profile()
        # When
        ctx = build_context(profile, card)
        # Then: 通常の dict になっている
        assert isinstance(ctx.card_special_rewards, dict)
        assert ctx.card_special_rewards == {"amazon": 1.5}

    @pytest.mark.parametrize(
        "model_rank,engine_rank",
        [
            (ModelRakutenRank.REGULAR, RakutenRank.REGULAR),
            (ModelRakutenRank.SILVER, RakutenRank.SILVER),
            (ModelRakutenRank.GOLD, RakutenRank.GOLD),
            (ModelRakutenRank.PLATINUM, RakutenRank.PLATINUM),
            (ModelRakutenRank.DIAMOND, RakutenRank.DIAMOND),
        ],
        ids=["regular", "silver", "gold", "platinum", "diamond"],
    )
    def test_rakuten_rank_converted_from_model_to_engine(
        self, model_rank: ModelRakutenRank, engine_rank: RakutenRank
    ):
        """models.RakutenRank → engine.RakutenRank の値ベース変換が全ランクで正しい。

        Why .value 経由の変換が必要: models.RakutenRank は enum.Enum、
        engine.RakutenRank は str, Enum。異なるクラスなので直接比較は False になる。
        RakutenRank(model_rank.value) で文字列値を経由して変換する。
        """
        # Given
        profile = make_profile(rakuten_rank=model_rank)
        # When
        ctx = build_context(profile, None)
        # Then
        assert ctx.rakuten_rank == engine_rank
        # 念のため: 型が engine.RakutenRank であることを確認
        assert isinstance(ctx.rakuten_rank, RakutenRank)


# ── compute_pricing のテスト（サイト × ランク × カード × Prime 有無）────────────
#
# テーブル:
#   (id, site, price, shipping, profile, card, expected_points, expected_effective)
#
# Why このテーブルで 13 ケースを網羅する:
#   Amazon × Prime(有/無) × Mastercard(有/無): 4 ケース
#   Rakuten × ランク × カード × モバイル: 4 ケース
#   Yahoo × プレミアム × PayPay: 4 ケース
#   境界値（実質価格を 0 にクランプ）: 1 ケース
#   = 計 13 ケース

_COMPUTE_CASES = [
    # ── Amazon ──────────────────────────────────────────────────────────────
    (
        "amazon_guest_no_card",
        SiteType.AMAZON, 1000, 500,
        None, None,
        # Amazon基本1%=10、カードなし=0, 送料そのまま(非Prime)
        10, 1490,
    ),
    (
        "amazon_prime_no_special_card",
        SiteType.AMAZON, 1000, 500,
        make_profile(is_amazon_prime=True), None,
        # Amazon基本1%=10、カードなし=0, 送料0(Prime)
        10, 990,
    ),
    (
        "amazon_non_prime_mastercard_1_5pct",
        SiteType.AMAZON, 1000, 500,
        make_profile(), make_card(special_rewards={"amazon": 1.5}),
        # Amazon基本1%=10 + Mastercard1.5%=15 = 25
        25, 1475,
    ),
    (
        "amazon_prime_mastercard_upgraded_to_2_0pct",
        SiteType.AMAZON, 1000, 500,
        make_profile(is_amazon_prime=True), make_card(special_rewards={"amazon": 1.5}),
        # Amazon基本1%=10 + Mastercard2.0%(Prime昇格)=20 = 30, 送料0(Prime)
        30, 970,
    ),
    # ── Rakuten ─────────────────────────────────────────────────────────────
    (
        "rakuten_regular_no_special_card",
        SiteType.RAKUTEN, 1000, 200,
        make_profile(rakuten_rank=ModelRakutenRank.REGULAR), None,
        # ストア1%=10、カードなし=0
        10, 1190,
    ),
    (
        "rakuten_regular_card_2pct_spu",
        SiteType.RAKUTEN, 1000, 0,
        make_profile(rakuten_rank=ModelRakutenRank.REGULAR),
        make_card(special_rewards={"rakuten": 2.0}),
        # ストア1%=10 + SPU2%=20 = 30
        30, 970,
    ),
    (
        "rakuten_gold_card_2pct_no_mobile",
        SiteType.RAKUTEN, 1000, 0,
        make_profile(rakuten_rank=ModelRakutenRank.GOLD),
        make_card(special_rewards={"rakuten": 2.0}),
        # ストア1%=10 + SPU2%=20 = 30（ランクはポイント計算に直接影響しない）
        30, 970,
    ),
    (
        "rakuten_diamond_card_4pct_and_mobile",
        SiteType.RAKUTEN, 1000, 0,
        make_profile(rakuten_rank=ModelRakutenRank.DIAMOND, is_rakuten_mobile=True),
        make_card(special_rewards={"rakuten": 4.0}),
        # ストア1%=10 + SPU4%=40 + モバイル4%=40 = 90
        90, 910,
    ),
    # ── Yahoo ───────────────────────────────────────────────────────────────
    (
        "yahoo_guest_no_premium_no_paypay",
        SiteType.YAHOO, 1000, 0,
        None, None,
        # ストア1%=10、カードなし=0
        10, 990,
    ),
    (
        "yahoo_lyp_premium_only",
        SiteType.YAHOO, 1000, 0,
        make_profile(yahoo_premium=True), None,
        # ストア1%=10 + LYPプレミアム2%=20 + カードなし=0 = 30
        30, 970,
    ),
    (
        "yahoo_paypay_only",
        SiteType.YAHOO, 1000, 0,
        make_profile(is_paypay_linked=True), None,
        # ストア1%=10 + PayPay4%=40 = 50
        50, 950,
    ),
    (
        "yahoo_premium_and_paypay",
        SiteType.YAHOO, 1000, 0,
        make_profile(yahoo_premium=True, is_paypay_linked=True), None,
        # ストア1%=10 + LYPプレミアム2%=20 + PayPay4%=40 = 70
        70, 930,
    ),
    # ── 境界値 ───────────────────────────────────────────────────────────────
    (
        "effective_price_clamps_to_zero_when_points_exceed_price",
        SiteType.AMAZON, 100, 0,
        make_profile(),
        make_card(base_reward_rate=200.0),
        # Amazon基本1%=1 + カード200%=200 = 201
        # effective = max(0, 100 + 0 - 201) = 0
        201, 0,
    ),
]


@pytest.mark.parametrize(
    "site,price,shipping,profile,card,expected_points,expected_effective",
    [row[1:] for row in _COMPUTE_CASES],
    ids=[row[0] for row in _COMPUTE_CASES],
)
def test_compute_pricing(
    site: SiteType,
    price: int,
    shipping: int,
    profile: SimpleNamespace | None,
    card: SimpleNamespace | None,
    expected_points: int,
    expected_effective: int,
) -> None:
    """compute_pricing がサイト・ユーザー属性・カード特典に応じた正しい計算結果を返す。"""
    # When
    result = compute_pricing(price, shipping, site, profile, card)
    # Then
    assert result.total_points == expected_points
    assert result.effective_price == expected_effective


# ── 回帰テスト: フロントエンド effectivePrice.ts との一致 ────────────────────


@pytest.mark.parametrize(
    "site",
    [SiteType.AMAZON, SiteType.RAKUTEN, SiteType.YAHOO],
    ids=["amazon", "rakuten", "yahoo"],
)
def test_compute_pricing_regression_matches_frontend_formula(site: SiteType) -> None:
    """profile=None, card=None のとき、フロントエンド effectivePrice.ts と同値になる。

    フロント算式 (frontend/lib/pricing/effectivePrice.ts:8-10):
        max(0, listing.price + listing.shippingFee - listing.points)

    ゲスト状態 (全サイト共通) での期待値:
        price=5000, shipping=500
        ストア基本1% = floor(5000*0.01) = 50
        カードなし = 0
        total_points = 50
        effective = max(0, 5000 + 500 - 50) = 5450

    Why この回帰テストが必要:
        フロントとバックが別々に effective_price を計算するため、
        ゲスト状態（最も単純なケース）で算式の一致を保証する必要がある。

    Why ハードコード期待値を使う:
        `max(0, price + shipping - result.total_points)` との比較は循環アサーション
        (engine が同じ算式で effective_price を計算するため常にパスする)。
        独立した計算値で検証することでバグを検出できる。
    """
    # Given
    price = 5000
    shipping = 500
    # When: profile=None は guest 状態に相当（UserContext デフォルト）
    result = compute_pricing(price, shipping, site, profile=None, card=None)
    # Then: ハードコードした期待値で検証
    assert result.total_points == 50
    assert result.effective_price == 5450


# ── compute_pricing が engine に正しくデリゲートすることの確認 ────────────────


def test_compute_pricing_delegates_to_engine_for_guest_user() -> None:
    """compute_pricing(profile=None, card=None) が calculate_effective_price(UserContext()) と同値になる。

    Why: compute_pricing は build_context → calculate_effective_price の合成。
    profile=None 時に UserContext() をデフォルトとして渡すことを直接検証する。
    """
    # Given
    price = 2000
    shipping = 300
    site = SiteType.AMAZON
    # When
    public_result = compute_pricing(price, shipping, site, profile=None, card=None)
    engine_result = calculate_effective_price(site, price, shipping, UserContext())
    # Then: 公開 API とエンジン直接呼び出しが完全に一致する
    assert public_result.total_points == engine_result.total_points
    assert public_result.effective_price == engine_result.effective_price
    assert public_result.breakdown == engine_result.breakdown
