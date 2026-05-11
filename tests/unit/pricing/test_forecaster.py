"""Unit tests for api.lib.pricing.forecaster (T-19).

対象モジュール:
    - api.lib.pricing.forecaster: CampaignInfo, PriceStats, UpcomingSale,
      compute_price_stats, estimate_next_sales
    - api.lib.pricing (adapter): build_campaign_infos

build_campaign_infos をここでテストする理由:
    ORM → CampaignInfo 変換アダプターは forecaster モジュールへの橋渡し。
    test_public_api_campaigns.py が engine アダプターを担当するのと対称的に、
    このファイルが forecaster アダプターを担当することで責務を分離する。
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from api.common.models import CampaignKind as ModelCampaignKind
from api.common.models import SiteType as ModelSiteType
from api.lib.pricing import SiteType
from api.lib.pricing import build_campaign_infos
from api.lib.pricing.forecaster import (
    CampaignInfo,
    PriceStats,
    UpcomingSale,
    compute_price_stats,
    estimate_next_sales,
)


# ── ヘルパー ──────────────────────────────────────────────────────────────────


def _make_campaign_info(
    site: SiteType = SiteType.RAKUTEN,
    name: str = "テストキャンペーン",
    kind: str = "recurring",
    recurrence_rule: dict | None = None,
    bonus_rate: float = 0.04,
) -> CampaignInfo:
    return CampaignInfo(
        site=site,
        name=name,
        kind=kind,
        recurrence_rule=recurrence_rule,
        bonus_rate=bonus_rate,
    )


def _make_orm_campaign(
    site: ModelSiteType = ModelSiteType.RAKUTEN,
    name: str = "テストキャンペーン",
    kind: ModelCampaignKind | None = None,
    recurrence_rule: dict | None = None,
    bonus: dict | None = None,
) -> SimpleNamespace:
    """ORM SaleCampaign を SimpleNamespace で模倣する。

    Why SimpleNamespace: build_active_campaigns テストと同理由。
    ORM インスタンス化に DB セッションが不要になり、ユニットテストが完結する。
    """
    return SimpleNamespace(
        site=site,
        name=name,
        kind=kind if kind is not None else ModelCampaignKind.RECURRING,
        recurrence_rule=recurrence_rule,
        bonus=bonus if bonus is not None else {"type": "additive_rate", "rate": 0.04},
    )


# ── Dataclass: frozen 検証 ────────────────────────────────────────────────────


class TestDataclasses:
    """各 dataclass が frozen=True であることを確認する。

    Why frozen: 純粋関数エンジン層のデータは不変であるべき。
    同じオブジェクトを複数の関数に渡しても意図せず書き換えられないことを保証する。
    """

    def test_campaign_info_is_frozen(self):
        info = _make_campaign_info(
            recurrence_rule={"type": "day_of_month", "days": [5]},
        )
        with pytest.raises(Exception):  # dataclasses.FrozenInstanceError (subclass of AttributeError)
            info.name = "変更"  # type: ignore

    def test_price_stats_is_frozen(self):
        stats = PriceStats(
            sample_count=1,
            median=10000.0,
            mean=10000.0,
            min_price=10000,
            max_price=10000,
            avg_30d=10000.0,
            avg_90d=10000.0,
        )
        with pytest.raises(Exception):
            stats.median = 2000.0  # type: ignore

    def test_upcoming_sale_is_frozen(self):
        sale = UpcomingSale(
            campaign_name="テスト",
            estimated_date=date(2026, 5, 15),
            bonus_rate=0.10,
        )
        with pytest.raises(Exception):
            sale.bonus_rate = 0.20  # type: ignore


# ── compute_price_stats ───────────────────────────────────────────────────────


class TestComputePriceStats:
    """価格統計算出関数のテスト。

    30/90 日窓の境界と None 条件を重点的に検証する。
    """

    # テスト全体で固定した基準日を使用することで、タイムゾーン依存の揺れを防ぐ
    REF = datetime(2026, 5, 10, 12, 0, 0, tzinfo=timezone.utc)

    def test_empty_records_returns_none(self):
        """レコードリストが空のとき None を返す（データ不足）。"""
        assert compute_price_stats([], self.REF) is None

    def test_single_record_returns_stats(self):
        """1 件のレコードから正しい統計を算出する。"""
        # Given: 5日前の価格10000円
        record = (self.REF - timedelta(days=5), 10000)

        # When
        result = compute_price_stats([record], self.REF)

        # Then
        assert result is not None
        assert isinstance(result, PriceStats)
        assert result.sample_count == 1
        assert result.median == 10000.0
        assert result.mean == 10000.0
        assert result.min_price == 10000
        assert result.max_price == 10000

    def test_multiple_records_correct_median_odd(self):
        """奇数件のレコードで中央値を正しく算出する。"""
        records = [
            (self.REF - timedelta(days=5), 8000),   # 最安
            (self.REF - timedelta(days=10), 10000),  # 中央
            (self.REF - timedelta(days=15), 12000),  # 最高
        ]

        result = compute_price_stats(records, self.REF)

        assert result is not None
        assert result.sample_count == 3
        assert result.median == 10000.0
        assert result.min_price == 8000
        assert result.max_price == 12000

    def test_multiple_records_correct_median_even(self):
        """偶数件のレコードで中央値を正しく算出する（2 要素の平均）。"""
        records = [
            (self.REF - timedelta(days=5), 8000),
            (self.REF - timedelta(days=10), 12000),
        ]

        result = compute_price_stats(records, self.REF)

        assert result is not None
        assert result.median == 10000.0  # (8000 + 12000) / 2

    def test_mean_uses_all_records(self):
        """mean は 30/90 日窓に限定せず全レコードの平均。"""
        records = [
            (self.REF - timedelta(days=5), 9000),    # 30d 以内
            (self.REF - timedelta(days=100), 11000), # 90d 外
        ]

        result = compute_price_stats(records, self.REF)

        assert result is not None
        assert result.mean == pytest.approx(10000.0)  # (9000 + 11000) / 2

    def test_avg_30d_includes_records_within_30_days(self):
        """直近 30 日以内のレコードのみ avg_30d に含まれる。"""
        records = [
            (self.REF - timedelta(days=10), 9000),   # 30d 以内
            (self.REF - timedelta(days=20), 11000),  # 30d 以内
            (self.REF - timedelta(days=60), 5000),   # 30d 外（avg_30d に含まれない）
        ]

        result = compute_price_stats(records, self.REF)

        assert result is not None
        assert result.avg_30d == pytest.approx(10000.0)  # (9000 + 11000) / 2

    def test_avg_30d_is_none_when_no_records_in_window(self):
        """直近 30 日以内のレコードが 0 件なら avg_30d は None。"""
        records = [
            (self.REF - timedelta(days=45), 10000),
            (self.REF - timedelta(days=60), 12000),
        ]

        result = compute_price_stats(records, self.REF)

        assert result is not None
        assert result.avg_30d is None

    def test_avg_90d_includes_records_within_90_days(self):
        """直近 90 日以内のレコードのみ avg_90d に含まれる。"""
        records = [
            (self.REF - timedelta(days=10), 9000),    # 30d 以内 → avg_30d にも含まれる
            (self.REF - timedelta(days=60), 11000),   # 90d 以内（30d 外）
            (self.REF - timedelta(days=100), 5000),   # 90d 外
        ]

        result = compute_price_stats(records, self.REF)

        assert result is not None
        assert result.avg_90d == pytest.approx(10000.0)  # (9000 + 11000) / 2

    def test_avg_90d_is_none_when_no_records_in_window(self):
        """直近 90 日以内のレコードが 0 件なら avg_90d は None。"""
        records = [
            (self.REF - timedelta(days=100), 10000),
        ]

        result = compute_price_stats(records, self.REF)

        assert result is not None
        assert result.avg_90d is None

    def test_avg_30d_and_avg_90d_both_set_when_data_within_30d(self):
        """30 日以内にデータがあるとき avg_30d・avg_90d の両方が設定される。

        Why: 30d 以内のデータは 90d 以内にも含まれるため、
        avg_30d が設定される場合は avg_90d も必ず設定されるべき。
        """
        records = [(self.REF - timedelta(days=5), 10000)]

        result = compute_price_stats(records, self.REF)

        assert result is not None
        assert result.avg_30d is not None
        assert result.avg_90d is not None


# ── estimate_next_sales ───────────────────────────────────────────────────────


class TestEstimateNextSales:
    """次回セール日推定関数のテスト。

    ADR-014 §1 が定義する day_of_month ルールの解釈を重点的に検証する。
    固定日付 (2026-05-10) を基準日とすることでテストを deterministic にする。
    """

    # 曜日・月末の影響を受けにくい月中旬を基準日に選択
    REF = date(2026, 5, 10)

    def test_empty_campaigns_returns_empty_list(self):
        """キャンペーンリストが空のとき空リストを返す。"""
        assert estimate_next_sales([], self.REF) == []

    def test_single_day_of_month_returns_upcoming_sale(self):
        """day_of_month ルールで次回セール日を推定する。"""
        # Given: 毎月15日のキャンペーン、基準日は10日 → 次は15日
        campaign = _make_campaign_info(
            name="15日セール",
            recurrence_rule={"type": "day_of_month", "days": [15]},
            bonus_rate=0.10,
        )

        result = estimate_next_sales([campaign], self.REF)

        assert len(result) == 1
        assert isinstance(result[0], UpcomingSale)
        assert result[0].campaign_name == "15日セール"
        assert result[0].estimated_date == date(2026, 5, 15)
        assert result[0].bonus_rate == pytest.approx(0.10)

    def test_picks_nearest_day_among_multiple_days(self):
        """複数の日付がある場合、最も近い日を次回として返す。"""
        # Given: [10, 20, 25]、基準日は10日 → 今日は10日なので次は20日
        campaign = _make_campaign_info(
            recurrence_rule={"type": "day_of_month", "days": [10, 20, 25]},
        )

        result = estimate_next_sales([campaign], self.REF)

        assert len(result) == 1
        assert result[0].estimated_date == date(2026, 5, 20)

    def test_month_boundary_wraps_to_next_month(self):
        """月末近くの基準日では翌月の発生日を推定する。"""
        # Given: 毎月5日のキャンペーン、基準日は26日 → 次は6/5
        campaign = _make_campaign_info(
            recurrence_rule={"type": "day_of_month", "days": [5]},
        )
        ref = date(2026, 5, 26)

        result = estimate_next_sales([campaign], ref, horizon_days=30)

        assert len(result) == 1
        assert result[0].estimated_date == date(2026, 6, 5)

    def test_horizon_days_filters_far_future_sales(self):
        """horizon_days を超えるセールは除外される。"""
        # Given: 毎月1日のキャンペーン、基準日は10日 → 次は6/1 = 22日後
        # horizon_days=20 なら 6/1 は圏外
        campaign = _make_campaign_info(
            recurrence_rule={"type": "day_of_month", "days": [1]},
        )

        result = estimate_next_sales([campaign], self.REF, horizon_days=20)

        # 6/1 = 22 days from 5/10 → outside 20d horizon
        assert result == []

    def test_horizon_days_includes_sale_within_window(self):
        """horizon_days 以内のセールは含まれる。"""
        # Given: 毎月15日のキャンペーン、基準日は10日 → 次は5/15 = 5日後
        campaign = _make_campaign_info(
            recurrence_rule={"type": "day_of_month", "days": [15]},
        )

        result = estimate_next_sales([campaign], self.REF, horizon_days=10)

        assert len(result) == 1
        assert result[0].estimated_date == date(2026, 5, 15)

    def test_oneshot_campaign_is_excluded(self):
        """ONESHOT キャンペーンは day_of_month ルールがあっても除外される。

        Why: estimate_next_sales は recurring の周期性に基づく推定。
        oneshot は start_at/end_at で管理され、get_campaigns_for_suggestion 側でフィルタリング済みのため
        ここでは kind による除外を実装する。
        """
        campaign = _make_campaign_info(
            kind="oneshot",
            recurrence_rule={"type": "day_of_month", "days": [15]},
        )

        result = estimate_next_sales([campaign], self.REF)

        assert result == []

    def test_recurring_campaign_without_recurrence_rule_is_excluded(self):
        """recurrence_rule=None の recurring キャンペーンは除外される。"""
        campaign = _make_campaign_info(
            kind="recurring",
            recurrence_rule=None,
        )

        result = estimate_next_sales([campaign], self.REF)

        assert result == []

    def test_unknown_recurrence_rule_type_is_excluded(self):
        """未知の recurrence_rule タイプは除外される。

        Why: ADR-014 §1 が定義するのは day_of_month のみ。
        将来の拡張型（weekly 等）は未実装として安全にスキップする。
        """
        campaign = _make_campaign_info(
            recurrence_rule={"type": "weekly", "weekday": 2},
        )

        result = estimate_next_sales([campaign], self.REF)

        assert result == []

    def test_multiple_campaigns_all_returned(self):
        """複数キャンペーンがすべて返される（各キャンペーン 1 エントリ）。"""
        campaigns = [
            _make_campaign_info(
                name="キャンペーンA",
                recurrence_rule={"type": "day_of_month", "days": [15]},
            ),
            _make_campaign_info(
                name="キャンペーンB",
                recurrence_rule={"type": "day_of_month", "days": [20]},
            ),
        ]

        result = estimate_next_sales(campaigns, self.REF)

        assert len(result) == 2
        names = {s.campaign_name for s in result}
        assert names == {"キャンペーンA", "キャンペーンB"}

    def test_each_campaign_returns_its_nearest_day(self):
        """各キャンペーンが独立して最も近い日を返す。"""
        # キャンペーンA: 5/15、キャンペーンB: 5/20
        campaigns = [
            _make_campaign_info(
                name="A",
                recurrence_rule={"type": "day_of_month", "days": [15, 25]},
            ),
            _make_campaign_info(
                name="B",
                recurrence_rule={"type": "day_of_month", "days": [20, 28]},
            ),
        ]

        result = estimate_next_sales(campaigns, self.REF)

        dates_by_name = {s.campaign_name: s.estimated_date for s in result}
        assert dates_by_name["A"] == date(2026, 5, 15)
        assert dates_by_name["B"] == date(2026, 5, 20)


# ── build_campaign_infos (ORM アダプター) ────────────────────────────────────


class TestBuildCampaignInfos:
    """ORM SaleCampaign → CampaignInfo 変換アダプターのテスト。

    build_active_campaigns が engine.ActiveCampaign を生成するのと対称的に、
    build_campaign_infos は forecaster.CampaignInfo を生成する。
    """

    def test_empty_list_returns_empty_list(self):
        """空リストを渡すと空リストが返る。"""
        assert build_campaign_infos([]) == []

    def test_converts_single_campaign(self):
        """1 件の ORM キャンペーンを CampaignInfo に変換する。"""
        orm = _make_orm_campaign(
            site=ModelSiteType.RAKUTEN,
            name="お買い物マラソン",
            recurrence_rule={"type": "day_of_month", "days": [5, 10, 15]},
            bonus={"type": "additive_rate", "rate": 0.10},
        )

        result = build_campaign_infos([orm])

        assert len(result) == 1
        assert isinstance(result[0], CampaignInfo)
        assert result[0].name == "お買い物マラソン"

    def test_converts_site_type_from_model_to_engine(self):
        """ModelSiteType → engine SiteType へ変換される。"""
        orm = _make_orm_campaign(site=ModelSiteType.RAKUTEN)

        result = build_campaign_infos([orm])

        assert result[0].site == SiteType.RAKUTEN
        assert isinstance(result[0].site, SiteType)

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
        """全サイトタイプが正しく変換される。"""
        orm = _make_orm_campaign(site=model_site)
        result = build_campaign_infos([orm])
        assert result[0].site == engine_site

    def test_extracts_bonus_rate_from_bonus_dict(self):
        """bonus["rate"] が CampaignInfo.bonus_rate に設定される。"""
        orm = _make_orm_campaign(bonus={"type": "additive_rate", "rate": 0.10})

        result = build_campaign_infos([orm])

        assert result[0].bonus_rate == pytest.approx(0.10)

    def test_kind_is_converted_to_string(self):
        """Enum の kind が文字列に変換される。"""
        orm_recurring = _make_orm_campaign(kind=ModelCampaignKind.RECURRING)
        orm_oneshot = _make_orm_campaign(kind=ModelCampaignKind.ONESHOT)

        result_recurring = build_campaign_infos([orm_recurring])
        result_oneshot = build_campaign_infos([orm_oneshot])

        assert result_recurring[0].kind == "recurring"
        assert result_oneshot[0].kind == "oneshot"

    def test_preserves_recurrence_rule(self):
        """recurrence_rule がそのまま保持される。"""
        rule = {"type": "day_of_month", "days": [5, 10, 15, 20, 25]}
        orm = _make_orm_campaign(recurrence_rule=rule)

        result = build_campaign_infos([orm])

        assert result[0].recurrence_rule == rule

    def test_recurrence_rule_none_is_preserved(self):
        """recurrence_rule=None が None のまま保持される。"""
        orm = _make_orm_campaign(recurrence_rule=None)

        result = build_campaign_infos([orm])

        assert result[0].recurrence_rule is None

    def test_converts_multiple_campaigns(self):
        """複数の ORM キャンペーンがすべて変換される。"""
        orms = [
            _make_orm_campaign(name="キャンペーンA", site=ModelSiteType.AMAZON),
            _make_orm_campaign(name="キャンペーンB", site=ModelSiteType.RAKUTEN),
            _make_orm_campaign(name="キャンペーンC", site=ModelSiteType.YAHOO),
        ]

        result = build_campaign_infos(orms)

        assert len(result) == 3
        names = {c.name for c in result}
        assert names == {"キャンペーンA", "キャンペーンB", "キャンペーンC"}
