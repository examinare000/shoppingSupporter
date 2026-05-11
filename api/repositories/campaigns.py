"""Sale campaign repository.

サジェストエンジンが必要とするキャンペーン取得クエリを集約する。
"""
from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from ..common.models import CampaignKind, SaleCampaign, SiteType

# ONESHOT キャンペーンのデフォルト検索期間
_DEFAULT_FUTURE_DAYS = 60


def get_campaigns_for_suggestion(
    db: Session,
    sites: list[SiteType],
    reference_date: datetime,
    future_days: int = _DEFAULT_FUTURE_DAYS,
) -> list[SaleCampaign]:
    """サジェスト用のキャンペーンを取得する。

    RECURRING: 日付に関係なく常に返す（recurrence_rule が周期性を表す）。
    ONESHOT: start_at が reference_date から future_days 以内のものだけ返す。

    Args:
        db: SQLAlchemy セッション。
        sites: 取得対象サイトのリスト。空リストは常に 0 件を返す。
        reference_date: 基準日時（ONESHOT のフィルタリング起点）。
        future_days: ONESHOT の検索期間（日数）。

    Returns:
        条件を満たす SaleCampaign のリスト。
    """
    if not sites:
        return []

    future_cutoff = reference_date + timedelta(days=future_days)

    stmt = select(SaleCampaign).where(
        and_(
            SaleCampaign.site.in_(sites),
            or_(
                # RECURRING は常に対象
                SaleCampaign.kind == CampaignKind.RECURRING,
                # ONESHOT は future_days 以内に start_at があるもの
                and_(
                    SaleCampaign.kind == CampaignKind.ONESHOT,
                    SaleCampaign.start_at.is_not(None),
                    SaleCampaign.start_at <= future_cutoff,
                    or_(
                        SaleCampaign.end_at.is_(None),
                        SaleCampaign.end_at >= reference_date,
                    ),
                ),
            ),
        )
    )

    return list(db.execute(stmt).scalars().all())
