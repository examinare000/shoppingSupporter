from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, List, Optional
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
    breakdown: List[RewardEntry] # 内訳

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
    card_special_rewards: Optional[Dict[str, float]] = None  # SiteType.value -> rate (%)

    def get_special_reward(self, site: SiteType) -> float:
        if self.card_special_rewards is None:
            return 0.0
        return self.card_special_rewards.get(site.value, 0.0)

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

def calculate_effective_price(
    site: SiteType,
    price: int,
    shipping: int,
    context: UserContext
) -> PricingResult:
    """サイトごとのポイント算出エンジン"""
    if site == SiteType.AMAZON:
        return calculate_points_amazon(price, shipping, context)
    elif site == SiteType.RAKUTEN:
        return calculate_points_rakuten(price, shipping, context)
    elif site == SiteType.YAHOO:
        return calculate_points_yahoo(price, shipping, context)
    # SiteType は閉じた Enum(3値)なので、ここに到達するケースは存在しない
    raise AssertionError(f"Unreachable: unknown SiteType {site!r}")
