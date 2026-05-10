from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from api.common.models import Card as OrmCard
    from api.common.models import MonthlyUsage as OrmMonthlyUsage
    from api.common.models import SaleCampaign as OrmSaleCampaign
    from api.common.models import UserProfile as OrmUserProfile

from .engine import (
    ActiveCampaign,
    PricingResult,
    RakutenRank,
    RewardEntry,
    SiteType,
    UserContext,
    UsageContext,
)


def build_context(
    profile: "OrmUserProfile | None",
    card: "OrmCard | None",
) -> UserContext:
    """ORM モデルを純粋関数エンジンの入力型に変換する。

    Why: engine.py は ORM に依存しない純粋関数モジュールとして保つ。
    ORM モデルとのブリッジはこのアダプター層が担う。
    profile=None は認証なし（ゲスト）の場合。デフォルト UserContext を返す。
    """
    if profile is None:
        return UserContext()
    return UserContext(
        rakuten_rank=RakutenRank(profile.rakuten_rank.value),
        is_amazon_prime=profile.is_amazon_prime,
        is_rakuten_mobile=profile.is_rakuten_mobile,
        yahoo_premium=profile.yahoo_premium,
        is_paypay_linked=profile.is_paypay_linked,
        card_base_rate=card.base_reward_rate if card is not None else 0.0,
        card_special_rewards=dict(card.special_rewards) if card is not None and card.special_rewards is not None else None,
    )


def build_active_campaigns(
    orm_campaigns: "list[OrmSaleCampaign]",
) -> list[ActiveCampaign]:
    """ORM SaleCampaign リストを engine 層の ActiveCampaign リストに変換する。

    Why このアダプターが必要か: engine.py は ORM 非依存を維持する。
    ORM モデルの SiteType と engine の SiteType は同じ値体系（小文字 value）を
    持つが、型が異なるため変換が必要（pricing-engine.md §1）。
    """
    result: list[ActiveCampaign] = []
    for c in orm_campaigns:
        # Why SiteType(c.site.value): ORM SiteType.AMAZON.value="amazon" →
        # engine SiteType("amazon") = engine SiteType.AMAZON
        engine_site = SiteType(c.site.value)
        result.append(ActiveCampaign(
            site=engine_site,
            name=c.name,
            bonus=c.bonus,
            cap=c.cap,
        ))
    return result


def build_usage_context(
    orm_records: "list[OrmMonthlyUsage]",
    site: SiteType,
) -> UsageContext | None:
    """ORM MonthlyUsage リストから指定サイトの UsageContext を返す。

    指定サイトのレコードが存在しない場合は None を返す。
    None は「利用実績不明」を意味し、キャンペーン上限チェックをスキップする
    （安全側として全額適用する）。
    """
    for record in orm_records:
        if record.site.value == site.value:
            return UsageContext(
                site=site,
                amount_spent=record.amount_spent,
                points_earned=record.points_earned,
                shop_count=record.shop_count,
            )
    return None


def compute_pricing(
    price: int,
    shipping: int,
    site: SiteType,
    profile: "OrmUserProfile | None" = None,
    card: "OrmCard | None" = None,
    campaigns: "list[OrmSaleCampaign] | None" = None,
    usage_records: "list[OrmMonthlyUsage] | None" = None,
) -> PricingResult:
    """T-08 から呼ばれる公開インターフェース。

    profile=None, card=None のとき UserContext デフォルト（ゲスト状態）で計算。
    campaigns=None / usage_records=None は後方互換（既存呼び出しに影響なし）。
    """
    # Why ローカルimport: calculate_effective_price をパッケージ名前空間に露出させない。
    # 外部から直接呼び出すと build_context によるORM変換層をバイパスできてしまう。
    from .engine import calculate_effective_price

    context = build_context(profile, card)
    active_campaigns = build_active_campaigns(campaigns) if campaigns is not None else []
    usage_context = build_usage_context(usage_records, site) if usage_records is not None else None

    return calculate_effective_price(
        site, price, shipping, context,
        campaigns=active_campaigns,
        usage_context=usage_context,
    )


__all__ = [
    "compute_pricing",
    "build_context",
    "build_active_campaigns",
    "build_usage_context",
    "SiteType",
    "RakutenRank",
    "UserContext",
    "UsageContext",
    "ActiveCampaign",
    "PricingResult",
    "RewardEntry",
]
