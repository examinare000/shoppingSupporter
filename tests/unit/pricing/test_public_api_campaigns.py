"""`api.lib.pricing` のキャンペーン対応アダプター (T-18) の単体テスト。

テスト対象:
    - build_active_campaigns: ORM SaleCampaign → ActiveCampaign 変換
    - build_usage_context: ORM MonthlyUsage → UsageContext 変換
    - compute_pricing のキャンペーン対応オプションパラメータ

Why このファイルで __init__.py のキャンペーン機能を test_public_api.py と分離するか:
    test_public_api.py は既存の build_context / compute_pricing を ORM なしでテスト。
    このファイルはキャンペーン・利用実績の ORM アダプター層を専門にテストする。
    責務の分離により、engine バグとアダプターバグを区別できる。
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from api.common.models import CampaignKind as ModelCampaignKind
from api.common.models import SiteType as ModelSiteType
from api.lib.pricing import (
    SiteType,
    build_active_campaigns,
    build_usage_context,
    compute_pricing,
)
from api.lib.pricing.engine import ActiveCampaign, UsageContext


# ── Helpers ───────────────────────────────────────────────────────────────────


def make_orm_campaign(
    site=ModelSiteType.AMAZON,
    name="テストキャンペーン",
    kind=None,
    bonus=None,
    cap=None,
) -> SimpleNamespace:
    """ORM SaleCampaign を SimpleNamespace で模倣する。

    Why SimpleNamespace: ORM モデルを直接インスタンス化するには DB セッションが
    必要。SimpleNamespace は duck typing で同じ属性アクセスを提供し、
    外部依存なしでユニットテストを完結させられる。
    """
    return SimpleNamespace(
        site=site,
        name=name,
        kind=kind if kind is not None else ModelCampaignKind.RECURRING,
        bonus=bonus if bonus is not None else {"type": "additive_rate", "rate": 0.04},
        cap=cap,
    )


def make_orm_usage(
    site=ModelSiteType.AMAZON,
    recorded_month="2026-05",
    amount_spent=0,
    points_earned=0,
    shop_count=0,
) -> SimpleNamespace:
    """ORM MonthlyUsage を SimpleNamespace で模倣する。"""
    return SimpleNamespace(
        site=site,
        recorded_month=recorded_month,
        amount_spent=amount_spent,
        points_earned=points_earned,
        shop_count=shop_count,
    )


# ── build_active_campaigns のテスト ────────────────────────────────────────────


class TestBuildActiveCampaigns:
    def test_empty_list_returns_empty_list(self):
        """ORM キャンペーンリストが空のとき空リストを返す。"""
        assert build_active_campaigns([]) == []

    def test_converts_orm_campaign_to_active_campaign(self):
        """ORM SaleCampaign を ActiveCampaign に変換する。"""
        # Given
        orm_campaign = make_orm_campaign(
            site=ModelSiteType.AMAZON,
            name="Amazonポイントアップ",
            bonus={"type": "additive_rate", "rate": 0.04},
        )
        # When
        result = build_active_campaigns([orm_campaign])
        # Then
        assert len(result) == 1
        assert isinstance(result[0], ActiveCampaign)
        assert result[0].name == "Amazonポイントアップ"
        assert result[0].bonus == {"type": "additive_rate", "rate": 0.04}
        assert result[0].cap is None

    def test_converts_site_type_from_model_to_engine(self):
        """SiteType が models.SiteType から engine.SiteType へ変換される。"""
        # Given
        orm_campaign = make_orm_campaign(site=ModelSiteType.RAKUTEN)
        # When
        result = build_active_campaigns([orm_campaign])
        # Then: engine SiteType（str, Enum）として返る
        assert result[0].site == SiteType.RAKUTEN
        assert isinstance(result[0].site, SiteType)

    def test_converts_cap_field(self):
        """cap フィールドが正しく変換される。"""
        # Given
        orm_campaign = make_orm_campaign(
            cap={"type": "points", "value": 7000},
        )
        # When
        result = build_active_campaigns([orm_campaign])
        # Then
        assert result[0].cap == {"type": "points", "value": 7000}

    def test_cap_none_preserved(self):
        """cap=None の ORM キャンペーンが ActiveCampaign.cap=None になる。"""
        orm_campaign = make_orm_campaign(cap=None)
        result = build_active_campaigns([orm_campaign])
        assert result[0].cap is None

    def test_converts_multiple_campaigns(self):
        """複数のキャンペーンがすべて変換される。"""
        # Given: 3サイット分
        campaigns = [
            make_orm_campaign(site=ModelSiteType.AMAZON, name="キャンペーンA"),
            make_orm_campaign(site=ModelSiteType.RAKUTEN, name="キャンペーンB"),
            make_orm_campaign(site=ModelSiteType.YAHOO, name="キャンペーンC"),
        ]
        # When
        result = build_active_campaigns(campaigns)
        # Then
        assert len(result) == 3
        names = {c.name for c in result}
        assert names == {"キャンペーンA", "キャンペーンB", "キャンペーンC"}

    @pytest.mark.parametrize(
        "model_site,engine_site",
        [
            (ModelSiteType.AMAZON, SiteType.AMAZON),
            (ModelSiteType.RAKUTEN, SiteType.RAKUTEN),
            (ModelSiteType.YAHOO, SiteType.YAHOO),
        ],
        ids=["amazon", "rakuten", "yahoo"],
    )
    def test_all_site_types_convert_correctly(self, model_site, engine_site):
        """全サイトタイプが models.SiteType → engine.SiteType に変換される。"""
        orm_campaign = make_orm_campaign(site=model_site)
        result = build_active_campaigns([orm_campaign])
        assert result[0].site == engine_site


# ── build_usage_context のテスト ───────────────────────────────────────────────


class TestBuildUsageContext:
    def test_empty_list_returns_none(self):
        """ORM 利用実績リストが空のとき None を返す。"""
        result = build_usage_context([], SiteType.AMAZON)
        assert result is None

    def test_finds_matching_site_record(self):
        """指定サイトの利用実績を見つけて UsageContext を返す。"""
        # Given
        orm_usage = make_orm_usage(
            site=ModelSiteType.AMAZON,
            amount_spent=5000,
            points_earned=50,
            shop_count=2,
        )
        # When
        result = build_usage_context([orm_usage], SiteType.AMAZON)
        # Then
        assert result is not None
        assert isinstance(result, UsageContext)
        assert result.site == SiteType.AMAZON
        assert result.amount_spent == 5000
        assert result.points_earned == 50
        assert result.shop_count == 2

    def test_returns_none_when_no_record_for_requested_site(self):
        """指定サイトの利用実績がないとき None を返す。"""
        # Given: RAKUTEN のみ
        orm_usage = make_orm_usage(site=ModelSiteType.RAKUTEN, points_earned=100)
        # When: AMAZON を要求
        result = build_usage_context([orm_usage], SiteType.AMAZON)
        # Then
        assert result is None

    def test_filters_to_correct_site_from_multiple_records(self):
        """複数サイトの記録から指定サイトのみを取得する。"""
        # Given: 全3サイトの記録
        records = [
            make_orm_usage(site=ModelSiteType.AMAZON, points_earned=100),
            make_orm_usage(site=ModelSiteType.RAKUTEN, points_earned=200),
            make_orm_usage(site=ModelSiteType.YAHOO, points_earned=300),
        ]
        # When: RAKUTEN を要求
        result = build_usage_context(records, SiteType.RAKUTEN)
        # Then: RAKUTEN の値
        assert result is not None
        assert result.site == SiteType.RAKUTEN
        assert result.points_earned == 200

    @pytest.mark.parametrize(
        "model_site,engine_site",
        [
            (ModelSiteType.AMAZON, SiteType.AMAZON),
            (ModelSiteType.RAKUTEN, SiteType.RAKUTEN),
            (ModelSiteType.YAHOO, SiteType.YAHOO),
        ],
        ids=["amazon", "rakuten", "yahoo"],
    )
    def test_all_site_types_convert_correctly(self, model_site, engine_site):
        """全サイトタイプで正しく UsageContext を取得できる。"""
        orm_usage = make_orm_usage(site=model_site)
        result = build_usage_context([orm_usage], engine_site)
        assert result is not None
        assert result.site == engine_site


# ── compute_pricing のキャンペーン対応 ────────────────────────────────────────


class TestComputePricingWithCampaigns:
    def test_without_campaigns_is_backward_compatible(self):
        """campaigns=None, usage_records=None は既存動作と同一（後方互換）。"""
        # When: 既存の呼び出しパターン（新引数を渡さない）
        result = compute_pricing(1000, 0, SiteType.AMAZON)
        # Then
        assert result.total_points == 10  # Amazon基本1%
        assert result.effective_price == 990

    def test_with_campaigns_applies_bonus(self):
        """campaigns を渡すとキャンペーンボーナスが適用される。"""
        # Given
        orm_campaign = make_orm_campaign(
            site=ModelSiteType.AMAZON,
            name="Amazonポイントアップ",
            bonus={"type": "additive_rate", "rate": 0.04},
        )
        # When
        result = compute_pricing(1000, 0, SiteType.AMAZON, campaigns=[orm_campaign])
        # Then: base 10 + campaign 40 = 50
        assert result.total_points == 50
        assert result.effective_price == 950

    def test_with_usage_records_applies_cap(self):
        """usage_records を渡すとキャンペーン上限が考慮される。"""
        # Given: cap 付きキャンペーン、利用実績が上限に達している
        orm_campaign = make_orm_campaign(
            site=ModelSiteType.AMAZON,
            name="ポイントアップキャンペーン",
            bonus={"type": "additive_rate", "rate": 0.04},
            cap={"type": "points", "value": 7000},
        )
        orm_usage = make_orm_usage(
            site=ModelSiteType.AMAZON,
            points_earned=7000,  # 上限到達
        )
        # When
        result = compute_pricing(
            1000, 0, SiteType.AMAZON,
            campaigns=[orm_campaign],
            usage_records=[orm_usage],
        )
        # Then: キャンペーンボーナスなし（上限到達）
        assert result.total_points == 10  # base のみ

    def test_campaigns_empty_list_is_backward_compatible(self):
        """campaigns=[] は None と同様に既存動作と同一。"""
        result = compute_pricing(1000, 0, SiteType.AMAZON, campaigns=[])
        assert result.total_points == 10

    def test_profile_and_campaigns_combined(self):
        """profile（UserContext）と campaigns が独立して動作する。

        Why: build_context と build_active_campaigns が独立して機能し、
        両方の結果が calculate_effective_price に渡されることを確認する。
        """
        # Given: Amazon Prime ユーザー + キャンペーン
        from api.common.models import RakutenRank as ModelRakutenRank

        profile = SimpleNamespace(
            rakuten_rank=ModelRakutenRank.REGULAR,
            is_amazon_prime=True,
            is_rakuten_mobile=False,
            yahoo_premium=False,
            is_paypay_linked=False,
        )
        orm_campaign = make_orm_campaign(
            site=ModelSiteType.AMAZON,
            name="Amazonキャンペーン",
            bonus={"type": "additive_rate", "rate": 0.04},
        )
        # When: price=1000, shipping=500, Prime（送料無料）
        result = compute_pricing(
            1000, 500, SiteType.AMAZON,
            profile=profile,
            campaigns=[orm_campaign],
        )
        # Then: base 10 + campaign 40 = 50、送料 0（Prime）
        assert result.total_points == 50
        assert result.effective_price == 950  # 1000 + 0(Prime) - 50 = 950

    def test_usage_records_none_applies_full_campaign_bonus(self):
        """usage_records=None のとき上限チェックなしで全額適用。

        Why: 利用実績が未提供の場合は安全側として全額適用する。
        """
        # Given: cap 付きキャンペーン、usage_records なし
        orm_campaign = make_orm_campaign(
            site=ModelSiteType.AMAZON,
            bonus={"type": "additive_rate", "rate": 0.04},
            cap={"type": "points", "value": 7000},
        )
        # When: usage_records を渡さない
        result = compute_pricing(1000, 0, SiteType.AMAZON, campaigns=[orm_campaign])
        # Then: 全額適用
        assert result.total_points == 50  # base 10 + campaign 40

    def test_cross_site_campaign_not_applied(self):
        """異サイトのキャンペーンは compute_pricing でも適用されない。"""
        # Given: RAKUTEN キャンペーン、AMAZON で計算
        orm_campaign = make_orm_campaign(
            site=ModelSiteType.RAKUTEN,
            bonus={"type": "additive_rate", "rate": 0.05},
        )
        result = compute_pricing(1000, 0, SiteType.AMAZON, campaigns=[orm_campaign])
        # Then: RAKUTEN キャンペーンは AMAZON 計算に含まれない
        assert result.total_points == 10
