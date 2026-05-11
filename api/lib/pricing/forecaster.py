"""価格予測ロジック (T-19).

提供する機能:
    - PriceStats: 価格統計データクラス（中央値・移動平均等）
    - CampaignInfo: forecaster 層のキャンペーン純粋データ（ORM 非依存）
    - UpcomingSale: 次回セール推定結果
    - compute_price_stats: 価格履歴から統計を算出する純粋関数
    - estimate_next_sales: キャンペーン定義から次回セール日を推定する純粋関数

設計判断:
    - 全データクラスは frozen=True。エンジン層のデータは不変であるべきで、
      同じオブジェクトを複数の関数に渡しても意図せず書き換えられないことを保証する。
    - 外部依存（ORM・HTTP）を持たない純粋関数モジュールとして保つ。
      ORM との橋渡しは api/lib/pricing/__init__.py のアダプターが担う。
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Optional


@dataclass(frozen=True)
class CampaignInfo:
    """forecaster 層のキャンペーン純粋データ（ORM 非依存）。

    Why engine.ActiveCampaign と別型か:
        ActiveCampaign は cap/bonus を丸ごと持ち、pricing エンジンの実質価格計算に使う。
        CampaignInfo は forecaster が必要とする recurrence_rule と bonus_rate に絞り、
        責務と型の依存を最小にする。
    """
    site: object  # SiteType（循環 import を避けるため type hint は object）
    name: str
    kind: str  # "recurring" | "oneshot"
    recurrence_rule: Optional[dict]
    bonus_rate: float


@dataclass(frozen=True)
class PriceStats:
    """価格履歴から算出された統計値。

    avg_30d/avg_90d が None のケース:
        対応窓内にレコードが存在しない場合は None。
        呼び出し側で「データ不足」として処理する。
    """
    sample_count: int
    median: float
    mean: float
    min_price: int
    max_price: int
    avg_30d: Optional[float]
    avg_90d: Optional[float]


@dataclass(frozen=True)
class UpcomingSale:
    """次回セール推定結果。estimate_next_sales の出力単位。"""
    campaign_name: str
    estimated_date: date
    bonus_rate: float


def compute_price_stats(
    records: list[tuple[datetime, int]],
    reference_dt: datetime,
) -> Optional[PriceStats]:
    """価格履歴から統計値を算出する。

    Args:
        records: (recorded_at, price) のタプルリスト。順不同で受け入れる。
        reference_dt: 基準日時（30/90 日窓計算の起点）。timezone-aware 推奨。

    Returns:
        レコードが 1 件以上あれば PriceStats。0 件なら None（データ不足）。

    Why mean は全期間対象か:
        avg_30d/avg_90d は移動平均（直近トレンドの把握）に使う。
        mean は全期間の価格水準を把握するための統計で、窓を絞らない。
    """
    if not records:
        return None

    prices = [price for _, price in records]
    sorted_prices = sorted(prices)

    median = _calc_median(sorted_prices)
    mean = sum(prices) / len(prices)
    min_price = sorted_prices[0]
    max_price = sorted_prices[-1]

    # reference_dt を UTC タイムゾーンに揃えて窓計算する
    ref = _ensure_utc(reference_dt)
    cutoff_30 = ref - timedelta(days=30)
    cutoff_90 = ref - timedelta(days=90)

    prices_30 = [p for dt, p in records if _ensure_utc(dt) >= cutoff_30]
    prices_90 = [p for dt, p in records if _ensure_utc(dt) >= cutoff_90]

    avg_30d = sum(prices_30) / len(prices_30) if prices_30 else None
    avg_90d = sum(prices_90) / len(prices_90) if prices_90 else None

    return PriceStats(
        sample_count=len(prices),
        median=median,
        mean=mean,
        min_price=min_price,
        max_price=max_price,
        avg_30d=avg_30d,
        avg_90d=avg_90d,
    )


def estimate_next_sales(
    campaigns: list[CampaignInfo],
    reference_date: date,
    horizon_days: int = 30,
) -> list[UpcomingSale]:
    """キャンペーン定義から次回セール日を推定する。

    対応する recurrence_rule タイプ: day_of_month のみ。
    未知のタイプは安全にスキップする（将来の拡張型は未実装として扱う）。

    Args:
        campaigns: CampaignInfo のリスト。
        reference_date: 基準日（この日の翌日以降を「未来」とする）。
        horizon_days: この日数を超えるセールは除外する。

    Returns:
        UpcomingSale のリスト（horizon_days 内のものだけ）。
        各キャンペーンから最近の次回日を 1 件ずつ返す。
    """
    results: list[UpcomingSale] = []

    for campaign in campaigns:
        # ONESHOT は start_at/end_at 管理であり、day_of_month 推定の対象外
        if campaign.kind != "recurring":
            continue

        if campaign.recurrence_rule is None:
            continue

        rule_type = campaign.recurrence_rule.get("type")
        if rule_type != "day_of_month":
            # 将来の拡張型（weekly 等）は未実装としてスキップ
            continue

        days_of_month: list[int] = campaign.recurrence_rule.get("days", [])
        if not days_of_month:
            continue

        next_date = _find_next_day_of_month(reference_date, days_of_month)
        if next_date is None:
            continue

        delta = (next_date - reference_date).days
        if delta > horizon_days:
            continue

        results.append(UpcomingSale(
            campaign_name=campaign.name,
            estimated_date=next_date,
            bonus_rate=campaign.bonus_rate,
        ))

    return results


# ── 内部ヘルパー ──────────────────────────────────────────────────────────────


def _calc_median(sorted_prices: list[int]) -> float:
    """ソート済みリストの中央値を返す。

    Why statistics.median を使わないか:
        statistics.median は偶数件で Decimal を返す場合があり、
        float 型の一貫性を保つために手動計算する。
    """
    n = len(sorted_prices)
    mid = n // 2
    if n % 2 == 1:
        return float(sorted_prices[mid])
    return (sorted_prices[mid - 1] + sorted_prices[mid]) / 2.0


def _ensure_utc(dt: datetime) -> datetime:
    """timezone-naive datetime を UTC として扱う。timezone-aware はそのまま返す。"""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def _find_next_day_of_month(ref: date, days: list[int]) -> Optional[date]:
    """基準日の翌日以降で最も近い day_of_month の日付を返す。

    基準日自身は「今日」なので翌日（ref + 1）からを「未来」とする。
    今月に該当する日がなければ翌月を試みる。

    Returns:
        次回日付。見つからなければ None（days が空等の異常ケース）。
    """
    start = ref + timedelta(days=1)

    # 今月の候補（start 以降の日）
    candidates_this_month = [
        d for d in days
        if _try_date(start.year, start.month, d) is not None
        and _try_date(start.year, start.month, d) >= start
    ]
    if candidates_this_month:
        min_day = min(candidates_this_month)
        return date(start.year, start.month, min_day)

    # 翌月の候補（最小の day を選択）
    if start.month == 12:
        next_year, next_month = start.year + 1, 1
    else:
        next_year, next_month = start.year, start.month + 1

    valid_next = [
        d for d in days
        if _try_date(next_year, next_month, d) is not None
    ]
    if not valid_next:
        return None
    return date(next_year, next_month, min(valid_next))


def _try_date(year: int, month: int, day: int) -> Optional[date]:
    """存在しない日付（2月30日等）は None を返す。"""
    try:
        return date(year, month, day)
    except ValueError:
        return None
