"""MonthlyUsage リポジトリ。

責務:
    `monthly_usage` テーブルに対する取得・UPSERT を SQLAlchemy `Session` 経由で提供する。
    HTTP 層・認証ロジックには触れず、MonthlyUsage の取得と保存だけを担当する。

Why この層を持つか:
    user_profiles.py の責務分離パターンに合わせる。
    UPSERT は PostgreSQL INSERT ... ON CONFLICT DO UPDATE を使い、
    同一 PK (user_id, site, recorded_month) へのデータ競合を安全に扱う。
"""
from __future__ import annotations

import uuid

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from ..common.models import MonthlyUsage, SiteType


def get_usage_by_user_and_month(
    db: Session,
    user_id: uuid.UUID,
    recorded_month: str,
) -> list[MonthlyUsage]:
    """指定ユーザー・月の MonthlyUsage を全サイト分取得する。

    Why list[MonthlyUsage]: 当月は最大 3 件（サイトごと）。
    未保存のサイトはリストに含まれない（ルーター側でデフォルト 0 を補完する）。
    """
    return (
        db.query(MonthlyUsage)
        .filter_by(user_id=user_id, recorded_month=recorded_month)
        .all()
    )


def upsert_usage(
    db: Session,
    *,
    user_id: uuid.UUID,
    site: SiteType,
    recorded_month: str,
    amount_spent: int,
    points_earned: int,
    shop_count: int,
) -> MonthlyUsage:
    """(user_id, site, recorded_month) をキーに MonthlyUsage を全置換 UPSERT する。

    Why 全置換:
        PUT のセマンティクス（全フィールド必須）に対応。
        同一キーへの再保存は値を上書きする（INSERT されない）。

    Why keyword-only:
        user_profiles.py の upsert_profile と同じ慣習。ブール値や整数値の
        位置間違いをコンパイル時に検出する。

    Why commit 後に再取得:
        db.refresh() だけではリレーション等が完全に同期されないケースがある。
        user_profiles.py:112-117 と同パターンで、commit 後に SELECT で再取得する。
    """
    stmt = pg_insert(MonthlyUsage).values(
        user_id=user_id,
        site=site,
        recorded_month=recorded_month,
        amount_spent=amount_spent,
        points_earned=points_earned,
        shop_count=shop_count,
    ).on_conflict_do_update(
        index_elements=["user_id", "site", "recorded_month"],
        set_={
            "amount_spent": amount_spent,
            "points_earned": points_earned,
            "shop_count": shop_count,
        },
    )
    db.execute(stmt)
    db.commit()

    # commit 後に再取得してフレッシュな ORM オブジェクトを返す。
    # 直前に commit した行なので必ず存在する。
    refreshed_records = get_usage_by_user_and_month(db, user_id, recorded_month)
    matching = [r for r in refreshed_records if r.site == site]
    if not matching:
        raise RuntimeError(
            f"upsert_usage: record not found after commit "
            f"(user_id={user_id}, site={site}, recorded_month={recorded_month})"
        )
    return matching[0]
