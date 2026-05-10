"""PricingEngine のキャンペーン機能 (T-18) の単体テスト。

テスト対象:
    - ActiveCampaign dataclass（キャンペーン bonus / cap の格納）
    - UsageContext dataclass（エンジン層の利用実績コンテキスト）
    - calculate_effective_price の campaigns / usage_context 拡張パラメータ

Why engine.py の純粋関数テストを adapter テストと分離するか:
    engine.py は ORM に依存しない純粋関数モジュール。このファイルでは
    dataclass と算出ロジックだけを検証し、ORM 変換の不具合を混入させない。
"""
from __future__ import annotations

import math

import pytest

from api.lib.pricing.engine import (
    ActiveCampaign,
    UsageContext,
    SiteType,
    UserContext,
    calculate_effective_price,
)


# ── ActiveCampaign dataclass ──────────────────────────────────────────────────


class TestActiveCampaign:
    def test_can_create_with_bonus_only(self):
        """ActiveCampaign は bonus 必須、cap は省略可（デフォルト None）。"""
        # Given/When
        campaign = ActiveCampaign(
            site=SiteType.AMAZON,
            name="Amazonポイントアップ",
            bonus={"type": "additive_rate", "rate": 0.04},
        )
        # Then
        assert campaign.site == SiteType.AMAZON
        assert campaign.name == "Amazonポイントアップ"
        assert campaign.bonus == {"type": "additive_rate", "rate": 0.04}
        assert campaign.cap is None

    def test_can_create_with_cap(self):
        """cap 付きの ActiveCampaign を作成できる。"""
        # Given/When
        campaign = ActiveCampaign(
            site=SiteType.RAKUTEN,
            name="楽天お買いまわりキャンペーン",
            bonus={"type": "additive_rate", "rate": 0.04},
            cap={"type": "points", "value": 7000},
        )
        # Then
        assert campaign.cap == {"type": "points", "value": 7000}

    def test_is_frozen_dataclass(self):
        """ActiveCampaign は frozen dataclass で不変。"""
        campaign = ActiveCampaign(
            site=SiteType.AMAZON,
            name="テスト",
            bonus={"type": "additive_rate", "rate": 0.01},
        )
        with pytest.raises((AttributeError, TypeError)):
            campaign.name = "変更後"  # type: ignore[misc]


# ── UsageContext dataclass ────────────────────────────────────────────────────


class TestUsageContext:
    def test_defaults_to_zero_values(self):
        """UsageContext の数値フィールドはすべて 0 がデフォルト。"""
        # Given/When
        usage = UsageContext(site=SiteType.AMAZON)
        # Then
        assert usage.site == SiteType.AMAZON
        assert usage.amount_spent == 0
        assert usage.points_earned == 0
        assert usage.shop_count == 0

    def test_can_create_with_all_values(self):
        """全フィールドを指定して UsageContext を作成できる。"""
        # Given/When
        usage = UsageContext(
            site=SiteType.RAKUTEN,
            amount_spent=50000,
            points_earned=3000,
            shop_count=5,
        )
        # Then
        assert usage.amount_spent == 50000
        assert usage.points_earned == 3000
        assert usage.shop_count == 5

    def test_is_frozen_dataclass(self):
        """UsageContext は frozen dataclass で不変。"""
        usage = UsageContext(site=SiteType.AMAZON)
        with pytest.raises((AttributeError, TypeError)):
            usage.points_earned = 100  # type: ignore[misc]


# ── calculate_effective_price の campaigns 拡張 ───────────────────────────────


class TestCalculateEffectivePriceWithCampaigns:
    def test_no_campaigns_preserves_existing_behavior(self):
        """campaigns を省略すると既存の挙動と同一になる（後方互換）。"""
        # Given: campaigns なし（省略）
        result = calculate_effective_price(SiteType.AMAZON, 1000, 0, UserContext())
        # Then: Amazon基本1%=10
        assert result.total_points == 10
        assert result.effective_price == 990

    def test_empty_campaigns_list_preserves_existing_behavior(self):
        """campaigns=[] でも既存の挙動と同一。"""
        # Given: 空リスト
        result = calculate_effective_price(
            SiteType.AMAZON, 1000, 0, UserContext(), campaigns=[]
        )
        # Then
        assert result.total_points == 10
        assert result.effective_price == 990

    def test_additive_rate_campaign_adds_bonus_points(self):
        """additive_rate キャンペーンが基本ポイントに加算される。

        Why: docs/plans/phase3-analytics-suggestion.md §3.1
        bonus type "additive_rate": rate をそのまま price に掛けて加算。
        """
        # Given: AMAZON, price=1000, rate=4%
        campaign = ActiveCampaign(
            site=SiteType.AMAZON,
            name="Amazonポイントアップキャンペーン",
            bonus={"type": "additive_rate", "rate": 0.04},
        )
        # When
        result = calculate_effective_price(
            SiteType.AMAZON, 1000, 0, UserContext(), campaigns=[campaign]
        )
        # Then: base floor(1000*0.01)=10 + campaign floor(1000*0.04)=40 = 50
        assert result.total_points == 50
        assert result.effective_price == 950

    def test_campaign_for_different_site_is_not_applied(self):
        """異なるサイトのキャンペーンは算出に含まれない。"""
        # Given: AMAZON を計算するが、キャンペーンは RAKUTEN 向け
        campaign = ActiveCampaign(
            site=SiteType.RAKUTEN,
            name="楽天スーパーSALE",
            bonus={"type": "additive_rate", "rate": 0.05},
        )
        # When: AMAZON で算出
        result = calculate_effective_price(
            SiteType.AMAZON, 1000, 0, UserContext(), campaigns=[campaign]
        )
        # Then: キャンペーンは適用されず基本ポイントのみ
        assert result.total_points == 10
        assert result.effective_price == 990

    def test_campaign_with_cap_not_reached_applies_full_bonus(self):
        """上限未到達のキャンペーンはボーナス全額が適用される。

        cap=7000、既獲得 5000 → 残余 2000 > bonus(40) なのでフル適用。
        """
        # Given
        campaign = ActiveCampaign(
            site=SiteType.AMAZON,
            name="ポイントアップキャンペーン",
            bonus={"type": "additive_rate", "rate": 0.04},
            cap={"type": "points", "value": 7000},
        )
        usage = UsageContext(site=SiteType.AMAZON, points_earned=5000)
        # When
        result = calculate_effective_price(
            SiteType.AMAZON, 1000, 0, UserContext(),
            campaigns=[campaign],
            usage_context=usage,
        )
        # Then: base 10 + campaign 40 = 50（全額適用）
        assert result.total_points == 50
        assert result.effective_price == 950

    def test_campaign_cap_partially_reached_applies_partial_bonus(self):
        """上限に近いキャンペーンは残余分だけボーナスが適用される。

        cap=7000、既獲得 6980 → 残余 20 < bonus(40) → partial bonus=20。
        """
        # Given
        campaign = ActiveCampaign(
            site=SiteType.AMAZON,
            name="ポイントアップキャンペーン",
            bonus={"type": "additive_rate", "rate": 0.04},
            cap={"type": "points", "value": 7000},
        )
        usage = UsageContext(site=SiteType.AMAZON, points_earned=6980)
        # When
        result = calculate_effective_price(
            SiteType.AMAZON, 1000, 0, UserContext(),
            campaigns=[campaign],
            usage_context=usage,
        )
        # Then: base 10 + partial min(40, 7000-6980=20) = 30
        assert result.total_points == 30
        assert result.effective_price == 970

    def test_campaign_cap_exactly_reached_applies_no_bonus(self):
        """ポイント上限に到達済みのキャンペーンはボーナスなし。

        cap=7000、points_earned=7000 → 残余 0 → bonus=0。
        """
        # Given
        campaign = ActiveCampaign(
            site=SiteType.AMAZON,
            name="ポイントアップキャンペーン",
            bonus={"type": "additive_rate", "rate": 0.04},
            cap={"type": "points", "value": 7000},
        )
        usage = UsageContext(site=SiteType.AMAZON, points_earned=7000)
        # When
        result = calculate_effective_price(
            SiteType.AMAZON, 1000, 0, UserContext(),
            campaigns=[campaign],
            usage_context=usage,
        )
        # Then: base のみ
        assert result.total_points == 10
        assert result.effective_price == 990

    def test_campaign_cap_exceeded_applies_no_bonus(self):
        """上限超過（異常値）でもボーナス 0（負にはならない）。"""
        # Given: points_earned=8000 が cap=7000 を超えている
        campaign = ActiveCampaign(
            site=SiteType.AMAZON,
            name="キャンペーン",
            bonus={"type": "additive_rate", "rate": 0.04},
            cap={"type": "points", "value": 7000},
        )
        usage = UsageContext(site=SiteType.AMAZON, points_earned=8000)
        # When
        result = calculate_effective_price(
            SiteType.AMAZON, 1000, 0, UserContext(),
            campaigns=[campaign],
            usage_context=usage,
        )
        # Then
        assert result.total_points == 10

    def test_multiple_campaigns_stack(self):
        """複数のキャンペーンは加算される。"""
        # Given: 2つのキャンペーン（4% と 2%）
        campaign_a = ActiveCampaign(
            site=SiteType.AMAZON,
            name="キャンペーンA",
            bonus={"type": "additive_rate", "rate": 0.04},
        )
        campaign_b = ActiveCampaign(
            site=SiteType.AMAZON,
            name="キャンペーンB",
            bonus={"type": "additive_rate", "rate": 0.02},
        )
        # When
        result = calculate_effective_price(
            SiteType.AMAZON, 1000, 0, UserContext(), campaigns=[campaign_a, campaign_b]
        )
        # Then: base 10 + A 40 + B 20 = 70
        assert result.total_points == 70
        assert result.effective_price == 930

    def test_campaign_bonus_appears_in_breakdown(self):
        """キャンペーンのボーナスが breakdown に含まれる。"""
        # Given
        campaign = ActiveCampaign(
            site=SiteType.AMAZON,
            name="Amazonポイントアップ",
            bonus={"type": "additive_rate", "rate": 0.04},
        )
        # When
        result = calculate_effective_price(
            SiteType.AMAZON, 1000, 0, UserContext(), campaigns=[campaign]
        )
        # Then: キャンペーン名が breakdown のラベルに現れる
        labels = [e.label for e in result.breakdown]
        assert "Amazonポイントアップ" in labels

    def test_campaign_floor_truncation(self):
        """キャンペーンボーナスも math.floor で切り捨てられる。

        Why: price=999, rate=0.04 → 999*0.04=39.96 → floor=39（ceil なら 40）。
        math.ceil に置換するとこのテストが失敗する。
        """
        # Given
        campaign = ActiveCampaign(
            site=SiteType.RAKUTEN,
            name="楽天キャンペーン",
            bonus={"type": "additive_rate", "rate": 0.04},
        )
        # When
        result = calculate_effective_price(
            SiteType.RAKUTEN, 999, 0, UserContext(), campaigns=[campaign]
        )
        # Then: base floor(999*0.01)=9 + campaign floor(999*0.04)=39 = 48
        assert result.total_points == 48

    def test_usage_context_without_campaigns_has_no_effect(self):
        """usage_context があっても campaigns なければ基本ポイントのみ。"""
        # Given: usage_context あり、campaigns なし
        usage = UsageContext(site=SiteType.AMAZON, points_earned=5000)
        # When
        result = calculate_effective_price(
            SiteType.AMAZON, 1000, 0, UserContext(), usage_context=usage
        )
        # Then: 既存動作と同一
        assert result.total_points == 10
        assert result.effective_price == 990

    def test_cap_without_usage_context_applies_full_bonus(self):
        """usage_context=None のとき cap があっても上限確認なしで全額適用。

        Why: 利用実績が不明な場合、安全側として全額適用する（0 にしない）。
        """
        # Given: campaign with cap、usage_context なし
        campaign = ActiveCampaign(
            site=SiteType.AMAZON,
            name="キャンペーン",
            bonus={"type": "additive_rate", "rate": 0.04},
            cap={"type": "points", "value": 7000},
        )
        # When: usage_context を渡さない
        result = calculate_effective_price(
            SiteType.AMAZON, 1000, 0, UserContext(), campaigns=[campaign]
        )
        # Then: 全額適用
        assert result.total_points == 50  # base 10 + campaign 40

    def test_multiple_campaigns_with_cap_accumulate_points_earned_so_far(self):
        """複数キャンペーンが cap を共有するとき、先着順に points_earned_so_far を消費する。

        Why: plan.md §5「各 cap は先着順に points_earned_so_far を消費して独立計算」。
        キャンペーンAが残余20を全消費すると points_earned_so_far=5000 となり、
        キャンペーンBの残余=0 でボーナスが0になることを検証する。

        Scenario:
            usage.points_earned = 4980
            campaignA: cap=5000, rate=0.04, price=1000
                raw_bonus = floor(1000*0.04) = 40
                remaining = max(0, 5000 - 4980) = 20
                bonus = min(40, 20) = 20
                points_earned_so_far = 4980 + 20 = 5000
            campaignB: cap=5000, rate=0.04, price=1000
                raw_bonus = floor(1000*0.04) = 40
                remaining = max(0, 5000 - 5000) = 0
                bonus = min(40, 0) = 0
                points_earned_so_far = 5000 + 0 = 5000
            total = base(10) + A(20) + B(0) = 30
        """
        # Given
        campaign_a = ActiveCampaign(
            site=SiteType.AMAZON,
            name="キャンペーンA",
            bonus={"type": "additive_rate", "rate": 0.04},
            cap={"type": "points", "value": 5000},
        )
        campaign_b = ActiveCampaign(
            site=SiteType.AMAZON,
            name="キャンペーンB",
            bonus={"type": "additive_rate", "rate": 0.04},
            cap={"type": "points", "value": 5000},
        )
        usage = UsageContext(site=SiteType.AMAZON, points_earned=4980)
        # When
        result = calculate_effective_price(
            SiteType.AMAZON, 1000, 0, UserContext(),
            campaigns=[campaign_a, campaign_b],
            usage_context=usage,
        )
        # Then: base 10 + A 20 (残余消費) + B 0 (残余ゼロ) = 30
        assert result.total_points == 30
        assert result.effective_price == 970
        # B のボーナスが 0 であることを breakdown で確認
        b_entry = next(e for e in result.breakdown if e.label == "キャンペーンB")
        assert b_entry.points == 0

    @pytest.mark.parametrize(
        "site,campaign_site,expected_bonus",
        [
            (SiteType.AMAZON, SiteType.AMAZON, 40),
            (SiteType.RAKUTEN, SiteType.RAKUTEN, 40),
            (SiteType.YAHOO, SiteType.YAHOO, 40),
            (SiteType.AMAZON, SiteType.RAKUTEN, 0),   # 異サイト → 適用なし
            (SiteType.AMAZON, SiteType.YAHOO, 0),     # 異サイト → 適用なし
        ],
        ids=[
            "amazon_self",
            "rakuten_self",
            "yahoo_self",
            "amazon_rakuten_cross",
            "amazon_yahoo_cross",
        ],
    )
    def test_campaign_applies_only_to_matching_site(
        self, site, campaign_site, expected_bonus
    ):
        """キャンペーンは一致するサイトにのみ適用される。"""
        campaign = ActiveCampaign(
            site=campaign_site,
            name="テストキャンペーン",
            bonus={"type": "additive_rate", "rate": 0.04},
        )
        result = calculate_effective_price(site, 1000, 0, UserContext(), campaigns=[campaign])
        base = math.floor(1000 * 0.01)  # 基本 1%
        assert result.total_points == base + expected_bonus
