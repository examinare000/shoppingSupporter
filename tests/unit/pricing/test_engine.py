import pytest
from api.lib.pricing.engine import (
    calculate_effective_price,
    UserContext,
    SiteType,
    RakutenRank,
)

# テーブル駆動テスト
# 各行: (id, site, price, shipping, context, expected_points, expected_effective_price, expected_breakdown_count)
CASES = [
    (
        "amazon_basic_no_special_card",
        SiteType.AMAZON, 1000, 500,
        UserContext(),
        # 基本1%=10、カードなし=0、送料そのまま
        10, 1490, 2,
    ),
    (
        "amazon_non_prime_mastercard_1_5pct",
        SiteType.AMAZON, 1000, 500,
        UserContext(card_special_rewards={"amazon": 1.5}),
        # 基本1%=10 + Mastercard1.5%=15 = 25
        25, 1475, 2,
    ),
    (
        "amazon_prime_mastercard_1_5pct_upgraded_2_0pct",
        SiteType.AMAZON, 1000, 500,
        UserContext(is_amazon_prime=True, card_special_rewards={"amazon": 1.5}),
        # 基本1%=10 + Mastercard2.0%(プライム昇格)=20 = 30、送料0
        30, 970, 2,
    ),
    (
        "amazon_prime_free_shipping_no_special_card",
        SiteType.AMAZON, 1000, 500,
        UserContext(is_amazon_prime=True),
        # 基本1%=10、カードなし=0、送料0(プライム)
        10, 990, 2,
    ),
    (
        "rakuten_regular_no_card",
        SiteType.RAKUTEN, 1000, 200,
        UserContext(),
        # ストア1%=10、カードなし=0
        10, 1190, 2,
    ),
    (
        "rakuten_gold_card_2pct",
        SiteType.RAKUTEN, 1000, 0,
        UserContext(card_special_rewards={"rakuten": 2.0}),
        # ストア1%=10 + SPU2%=20 = 30
        30, 970, 2,
    ),
    (
        "rakuten_premium_card_4pct_and_mobile",
        SiteType.RAKUTEN, 1000, 0,
        UserContext(
            rakuten_rank=RakutenRank.DIAMOND,
            is_rakuten_mobile=True,
            card_special_rewards={"rakuten": 4.0},
        ),
        # ストア1%=10 + SPU4%=40 + モバイル4%=40 = 90
        90, 910, 3,
    ),
    (
        "yahoo_basic_no_premium_no_paypay",
        SiteType.YAHOO, 1000, 0,
        UserContext(),
        # ストア1%=10、カードなし=0
        10, 990, 2,
    ),
    (
        "yahoo_premium_only",
        SiteType.YAHOO, 1000, 0,
        UserContext(yahoo_premium=True),
        # ストア1%=10 + LYPプレミアム2%=20 + カードなし=0 = 30
        30, 970, 3,
    ),
    (
        "yahoo_paypay_only",
        SiteType.YAHOO, 1000, 0,
        UserContext(is_paypay_linked=True),
        # ストア1%=10 + PayPay4%=40 = 50
        50, 950, 2,
    ),
    (
        "yahoo_premium_and_paypay",
        SiteType.YAHOO, 1000, 0,
        UserContext(yahoo_premium=True, is_paypay_linked=True),
        # ストア1%=10 + LYPプレミアム2%=20 + PayPay4%=40 = 70
        70, 930, 3,
    ),
    (
        "effective_price_clamp_zero",
        SiteType.AMAZON, 100, 0,
        UserContext(card_base_rate=200.0),
        # 基本1%=1 + カード200%=200 = 201 → effective=max(0, 100-201)=0
        201, 0, 2,
    ),
    (
        "floor_truncation_non_integer_intermediate",
        SiteType.AMAZON, 999, 0,
        UserContext(),
        # floor(999*0.01)=floor(9.99)=9 (ceil なら10)、カードなし=0
        # effective = max(0, 999 + 0 - 9) = 990
        # Why: price × rate が非整数になる値を使い、math.floor() の切り捨て挙動を検証する。
        # math.ceil() に置換すると base_points=10 になりテストが失敗する。
        9, 990, 2,
    ),
]


@pytest.mark.parametrize(
    "site,price,shipping,context,expected_points,expected_effective,expected_breakdown_count",
    [row[1:] for row in CASES],
    ids=[row[0] for row in CASES],
)
def test_calculate_effective_price(
    site, price, shipping, context,
    expected_points, expected_effective, expected_breakdown_count,
):
    result = calculate_effective_price(site, price, shipping, context)
    assert result.total_points == expected_points
    assert result.effective_price == expected_effective
    assert len(result.breakdown) == expected_breakdown_count


def test_regression_matches_frontend_effectivePrice():
    """profile=None 相当（UserContext デフォルト）で、バックエンドがフロント effectivePrice.ts と同値になること。

    フロント算式 (frontend/lib/pricing/effectivePrice.ts:8-10):
        max(0, listing.price + listing.shippingFee - listing.points)

    ゲスト状態 (UserContext デフォルト) での期待値:
        price=5000, shipping=500
        Amazon基本1% = floor(5000*0.01) = 50
        カードなし = 0
        total_points = 50
        effective = max(0, 5000 + 500 - 50) = 5450

    Why ハードコード期待値を使う:
        `max(0, price + shipping - result.total_points)` との比較は循環アサーション
        (engine が同じ算式で effective_price を計算するため常にパスする)。
        独立した計算値で検証することでバグを検出できる。
    """
    price = 5000
    shipping = 500
    # UserContext() は profile=None に相当するデフォルト状態
    context = UserContext()

    result = calculate_effective_price(SiteType.AMAZON, price, shipping, context)

    assert result.total_points == 50
    assert result.effective_price == 5450
