"""月次利用実績エンドポイント。

`GET /api/me/usage` と `PUT /api/me/usage` の HTTP 境界を担当する。
データ取得・永続化は `api/repositories/monthly_usage.py`、認証は
`api/common/security.get_current_user` に委譲し、本モジュールは入力
バリデーションと HTTP レスポンス整形のみを行う。

バリデーション順序（profile.py と同パターン）:
    (1) Pydantic（型・Literal・extra=forbid）→ (2) 認証 401
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Header, status
from sqlalchemy.orm import Session

from ..common.database import get_db
from ..common.time import current_business_month
from ..common.models import SiteType, User
from ..common.security import get_current_user
from ..repositories.monthly_usage import get_usage_by_user_and_month, upsert_usage
from ..schemas import (
    MonthlyUsageItemResponse,
    MonthlyUsageResponse,
    MonthlyUsageSiteEntry,
    MonthlyUsageUpdate,
)

ROUTER_PREFIX = "/api/me/usage"

# 全サイト一覧。GET レスポンスでデフォルト 0 を補完するために使う。
# Why 定数として 1 箇所で定義: サイト追加時の変更漏れを防ぐ。
ALL_SITES: list[SiteType] = [SiteType.AMAZON, SiteType.RAKUTEN, SiteType.YAHOO]

router = APIRouter(prefix=ROUTER_PREFIX, tags=["usage"])


@router.get(
    "",
    response_model=MonthlyUsageResponse,
    response_model_by_alias=True,
    responses={status.HTTP_401_UNAUTHORIZED: {"description": "Missing or invalid JWT"}},
)
def get_usage(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MonthlyUsageResponse:
    """認証ユーザー自身の当月利用実績を全サイト分返す。

    未保存のサイトは 200 + 0 デフォルトを返す（404 ではない）。
    profile GET と同パターン（docs/plans/phase3-analytics-suggestion.md §3.2）。
    """
    current_month = current_business_month()
    records = get_usage_by_user_and_month(db, current_user.id, current_month)
    record_map = {r.site: r for r in records}

    items: list[MonthlyUsageSiteEntry] = []
    for site in ALL_SITES:
        record = record_map.get(site)
        items.append(MonthlyUsageSiteEntry(
            site=site.value,
            amount_spent=record.amount_spent if record else 0,
            points_earned=record.points_earned if record else 0,
            shop_count=record.shop_count if record else 0,
        ))

    return MonthlyUsageResponse(month=current_month, items=items)


@router.put(
    "",
    response_model=MonthlyUsageItemResponse,
    response_model_by_alias=True,
    responses={
        status.HTTP_401_UNAUTHORIZED: {"description": "Missing or invalid JWT"},
    },
)
def update_usage(
    # Why `Header(default=None)` パターン:
    #   profile.py:104 と同じ理由。Pydantic 検証を認証より先に評価させることで
    #   「不正な body + 未認証 → 422（401 ではない）」を保証する。
    payload: MonthlyUsageUpdate,
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
) -> MonthlyUsageItemResponse:
    """指定サイト×月の利用実績を全置換 UPSERT する。

    同一 (site, month) への再 PUT は値を上書きする（INSERT されない）。
    """
    current_user: User = get_current_user(authorization=authorization, db=db)

    site = SiteType(payload.site)
    record = upsert_usage(
        db,
        user_id=current_user.id,
        site=site,
        recorded_month=payload.month,
        amount_spent=payload.amount_spent,
        points_earned=payload.points_earned,
        shop_count=payload.shop_count,
    )

    return MonthlyUsageItemResponse(
        site=record.site.value,
        month=record.recorded_month,
        amount_spent=record.amount_spent,
        points_earned=record.points_earned,
        shop_count=record.shop_count,
    )
