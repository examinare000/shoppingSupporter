from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum

class SiteType(str, Enum):
    AMAZON = "amazon"
    RAKUTEN = "rakuten"
    YAHOO = "yahoo"

# 各サイト共通の基本ストアポイント還元率
# Why: Amazon/楽天/Yahoo すべて公称 1%。API から取得できないため一律定数として集約する。
BASE_STORE_RATE: float = 0.01

class RakutenRank(str, Enum):
    REGULAR = "regular"
    SILVER = "silver"
    GOLD = "gold"
    PLATINUM = "platinum"
    DIAMOND = "diamond"

@dataclass(frozen=True)
class RewardEntry:
    """内訳項目"""
    label: str    # 表示名 (例: "楽天SPU", "Amazonポイント")
    rate: float   # 倍率 (例: 0.01)
    points: int   # 算出されたポイント数
    note: str = "" # 補足情報

@dataclass(frozen=True)
class PricingResult:
    """算出結果"""
    total_points: int            # 円換算された総ポイント
    effective_price: int         # 実質価格 (price + shipping - total_points)
    breakdown: list[RewardEntry] # 内訳

@dataclass(frozen=True)
class UserContext:
    """ポイント算出に必要なユーザー属性"""
    # Why: build_context でモデル値から変換・格納されるが、現行算出ロジックでは参照しない。
    # 将来の楽天ランク別SPU算出（段階的還元拡張）のために保持する。
    rakuten_rank: RakutenRank = RakutenRank.REGULAR
    is_amazon_prime: bool = False
    is_rakuten_mobile: bool = False
    yahoo_premium: bool = False
    is_paypay_linked: bool = False
    card_base_rate: float = 0.0  # カードなし時は 0%（BASE_STORE_RATE が基本還元を担う）
    card_special_rewards: dict[str, float] | None = None  # SiteType.value -> rate (%)

    def get_special_reward(self, site: SiteType) -> float:
        if self.card_special_rewards is None:
            return 0.0
        return self.card_special_rewards.get(site.value, 0.0)


@dataclass(frozen=True)
class ActiveCampaign:
    """適用中キャンペーンの純粋データ（ORM 非依存）。

    Why ORM 非依存: engine.py は外部依存を持たない純粋関数モジュール（pricing-engine.md §1）。
    ORM モデルとのブリッジは __init__.py の build_active_campaigns アダプターが担う。
    """
    site: SiteType
    name: str
    bonus: dict  # {"type": "additive_rate", "rate": float}
    cap: dict | None = None  # {"type": "points", "value": int} | None


@dataclass(frozen=True)
class UsageContext:
    """月次利用実績のコンテキスト（キャンペーン上限チェック用）。

    Why engine 層に持つか: calculate_effective_price がキャンペーン上限を
    計算するために必要。ORM 非依存の純粋データとして保持する。
    """
    site: SiteType
    amount_spent: int = 0
    points_earned: int = 0
    shop_count: int = 0

def _build_base_card_entry(price: int, context: UserContext) -> RewardEntry:
    """サイト固有特典がない場合のカード基本還元エントリを返す"""
    rate = context.card_base_rate / 100.0
    return RewardEntry("カード基本還元", rate, math.floor(price * rate))

def calculate_points_amazon(price: int, shipping: int, context: UserContext) -> PricingResult:
    """Amazon.co.jp のポイント算出 (2025/2026基準)"""
    breakdown = []

    # 1. 基本ポイント (通常 1%)
    # NOTE: 本来は商品ごとに異なるが、APIから取得できないため一律 1% と仮定
    base_points = math.floor(price * BASE_STORE_RATE)
    breakdown.append(RewardEntry("Amazon基本ポイント", BASE_STORE_RATE, base_points))

    # 2. Amazon Mastercard 特典
    special_rate_pct = context.get_special_reward(SiteType.AMAZON)
    if special_rate_pct > 0:
        # プライム会員なら +2.0%, 一般なら +1.5% (Mastercard公式仕様)
        # seedデータには 1.5% が入っている想定なので、プライムなら 0.5% 加算する
        actual_card_rate_pct = special_rate_pct
        if context.is_amazon_prime and special_rate_pct == 1.5:
            actual_card_rate_pct = 2.0
        card_rate = actual_card_rate_pct / 100.0
        card_points = math.floor(price * card_rate)
        breakdown.append(RewardEntry("Amazon Mastercard特典", card_rate, card_points))
    else:
        breakdown.append(_build_base_card_entry(price, context))

    total_points = sum(e.points for e in breakdown)
    actual_shipping = 0 if context.is_amazon_prime else shipping
    effective_price = max(0, price + actual_shipping - total_points)

    return PricingResult(total_points, effective_price, breakdown)

def calculate_points_rakuten(price: int, shipping: int, context: UserContext) -> PricingResult:
    """楽天市場 (SPU) のポイント算出 (2025/2026基準)"""
    breakdown = []

    # 1. ストアポイント (基本 1%)
    base_points = math.floor(price * BASE_STORE_RATE)
    breakdown.append(RewardEntry("ストアポイント", BASE_STORE_RATE, base_points))

    # 2. 楽天カード特典 (SPU)
    # card_special_rewards["rakuten"] に SPU 加算分が入っている想定
    spu_card_rate_pct = context.get_special_reward(SiteType.RAKUTEN)
    if spu_card_rate_pct > 0:
        spu_card_rate = spu_card_rate_pct / 100.0
        spu_card_points = math.floor(price * spu_card_rate)
        breakdown.append(RewardEntry("楽天カード利用特典(SPU)", spu_card_rate, spu_card_points))
    else:
        breakdown.append(_build_base_card_entry(price, context))

    # 3. 楽天モバイル特典 (SPU)
    if context.is_rakuten_mobile:
        mobile_rate = 0.04  # +4%
        mobile_points = math.floor(price * mobile_rate)
        breakdown.append(RewardEntry("楽天モバイル特典(SPU)", mobile_rate, mobile_points))

    total_points = sum(e.points for e in breakdown)
    effective_price = max(0, price + shipping - total_points)

    return PricingResult(total_points, effective_price, breakdown)

def calculate_points_yahoo(price: int, shipping: int, context: UserContext) -> PricingResult:
    """Yahoo! ショッピングのポイント算出 (2025/2026基準)"""
    breakdown = []

    # 1. ストアポイント (基本 1%)
    base_points = math.floor(price * BASE_STORE_RATE)
    breakdown.append(RewardEntry("ストアポイント", BASE_STORE_RATE, base_points))

    # 2. LYPプレミアム会員特典 (+2%)
    if context.yahoo_premium:
        premium_rate = 0.02
        premium_points = math.floor(price * premium_rate)
        breakdown.append(RewardEntry("LYPプレミアム特典", premium_rate, premium_points))

    # 3. LINE連携 + 指定支払 (PayPay) 特典 (+4%)
    if context.is_paypay_linked:
        paypay_rate = 0.04
        paypay_points = math.floor(price * paypay_rate)
        breakdown.append(RewardEntry("PayPay支払特典", paypay_rate, paypay_points))
    else:
        breakdown.append(_build_base_card_entry(price, context))

    total_points = sum(e.points for e in breakdown)
    effective_price = max(0, price + shipping - total_points)

    return PricingResult(total_points, effective_price, breakdown)

def _apply_campaign_bonuses(
    price: int,
    site: SiteType,
    base_result: PricingResult,
    campaigns: list[ActiveCampaign],
    usage_context: UsageContext | None,
) -> PricingResult:
    """サイト固有計算の後段でキャンペーンボーナスを積み上げる。

    Why 後段適用: キャンペーンはサイト非依存の構造（加算率 + 上限）のため、
    サイト固有計算と責務を分離して後段で適用する（plan.md 設計判断）。

    複数キャンペーンの上限計算: points_earned_so_far で既取得ポイントを
    累積追跡し、先着順に各キャンペーンのキャップ計算に反映する（plan.md §5）。
    """
    # Why usage_context.points_earned を初期値にする: 当月すでに獲得済みのポイントを
    # 累積の起点とし、この取引分のボーナスが追加される前の状態から計算を始める。
    points_earned_so_far = usage_context.points_earned if usage_context is not None else 0

    extra_entries: list[RewardEntry] = []
    for campaign in campaigns:
        if campaign.site != site:
            continue
        if campaign.bonus.get("type") != "additive_rate":
            # 未知の bonus type はスキップ（将来の拡張に備えた安全措置）
            continue

        raw_bonus = math.floor(price * campaign.bonus["rate"])

        if campaign.cap is not None and usage_context is not None:
            # usage_context が提供されているときのみ上限チェックを行う。
            # Why: 利用実績不明時は安全側として全額適用する（test-report.md）。
            cap_value = campaign.cap["value"]
            remaining = max(0, cap_value - points_earned_so_far)
            bonus_points = min(raw_bonus, remaining)
        else:
            bonus_points = raw_bonus

        points_earned_so_far += bonus_points
        extra_entries.append(RewardEntry(
            label=campaign.name,
            rate=campaign.bonus["rate"],
            points=bonus_points,
        ))

    if not extra_entries:
        return base_result

    total_extra = sum(e.points for e in extra_entries)
    new_total = base_result.total_points + total_extra
    new_effective_price = max(0, base_result.effective_price - total_extra)
    new_breakdown = list(base_result.breakdown) + extra_entries
    return PricingResult(new_total, new_effective_price, new_breakdown)


def calculate_effective_price(
    site: SiteType,
    price: int,
    shipping: int,
    context: UserContext,
    campaigns: list[ActiveCampaign] | None = None,
    usage_context: UsageContext | None = None,
) -> PricingResult:
    """サイトごとのポイント算出エンジン。

    campaigns / usage_context は省略可能（後方互換）。
    campaigns が空または None のとき、既存の挙動と同一になる。
    """
    if site == SiteType.AMAZON:
        base_result = calculate_points_amazon(price, shipping, context)
    elif site == SiteType.RAKUTEN:
        base_result = calculate_points_rakuten(price, shipping, context)
    elif site == SiteType.YAHOO:
        base_result = calculate_points_yahoo(price, shipping, context)
    else:
        # SiteType は閉じた Enum(3値)なので、ここに到達するケースは存在しない
        raise AssertionError(f"Unreachable: unknown SiteType {site!r}")

    if not campaigns:
        return base_result

    return _apply_campaign_bonuses(price, site, base_result, campaigns, usage_context)
