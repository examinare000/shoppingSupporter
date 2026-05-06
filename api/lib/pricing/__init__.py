from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from api.common.models import Card as OrmCard
    from api.common.models import UserProfile as OrmUserProfile

from .engine import (
    PricingResult,
    RakutenRank,
    RewardEntry,
    SiteType,
    UserContext,
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
        card_base_rate=card.base_reward_rate if card is not None else 1.0,
        card_special_rewards=dict(card.special_rewards) if card is not None else None,
    )


def compute_pricing(
    price: int,
    shipping: int,
    site: SiteType,
    profile: "OrmUserProfile | None" = None,
    card: "OrmCard | None" = None,
) -> PricingResult:
    """T-08 から呼ばれる公開インターフェース。

    profile=None, card=None のとき UserContext デフォルト（ゲスト状態）で計算。
    """
    # Why ローカルimport: calculate_effective_price をパッケージ名前空間に露出させない。
    # 外部から直接呼び出すと build_context によるORM変換層をバイパスできてしまう。
    from .engine import calculate_effective_price

    context = build_context(profile, card)
    return calculate_effective_price(site, price, shipping, context)


__all__ = [
    "compute_pricing",
    "build_context",
    "SiteType",
    "RakutenRank",
    "UserContext",
    "PricingResult",
    "RewardEntry",
]
