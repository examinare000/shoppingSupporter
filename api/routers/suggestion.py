"""Suggestion router (T-20).

GET /api/products/{id}/suggestion を提供する。
認証不要の公開エンドポイント。

データフロー:
    1. 商品 ID で Product を特定（404 チェック）
    2. PriceHistory を全件取得し compute_price_stats で統計化
    3. 商品が紐づくサイトの SaleCampaign を取得
    4. build_campaign_infos で CampaignInfo に変換
    5. estimate_next_sales で次回セール日を推定
    6. compute_suggestion でサジェストを決定
    7. SuggestionResponse として返却（camelCase）
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Path
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..common.database import get_db
from ..common.models import EcSiteProduct, Product
from ..lib.pricing import build_campaign_infos
from ..lib.pricing.forecaster import compute_price_stats, estimate_next_sales
from ..lib.pricing.suggestion import SuggestionInput, compute_suggestion
from ..repositories.campaigns import get_campaigns_for_suggestion
from ..schemas import SuggestionResponse

ROUTER_PREFIX = "/api/products"
SUGGESTION_PATH = "/{id}/suggestion"

# estimate_next_sales のデフォルト検索期間
_HORIZON_DAYS = 30

router = APIRouter(prefix=ROUTER_PREFIX, tags=["suggestion"])


@router.get(
    SUGGESTION_PATH,
    response_model=SuggestionResponse,
    response_model_by_alias=True,
)
def get_suggestion(
    product_id: str = Path(..., alias="id"),
    db: Session = Depends(get_db),
) -> SuggestionResponse:
    """商品の購入タイミングサジェストを返す。

    認証不要。ゲストユーザーにもサジェストを提供するための公開エンドポイント（T-20 仕様）。
    """
    # 1. 商品特定
    try:
        parsed_id = uuid.UUID(product_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Product not found")

    product = db.get(Product, parsed_id)
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")

    # 2. 商品に紐づく EC サイト商品を取得
    sp_stmt = (
        select(EcSiteProduct)
        .where(EcSiteProduct.product_id == parsed_id)
        .options(selectinload(EcSiteProduct.price_histories))
    )
    site_products = list(db.execute(sp_stmt).scalars().all())

    # 3. 価格履歴を収集（全サイト・全期間）
    history_records: list[tuple[datetime, int]] = [
        (h.recorded_at, h.price)
        for sp in site_products
        for h in sp.price_histories
    ]

    now = datetime.now(timezone.utc)
    price_stats = compute_price_stats(history_records, now)

    # 4. 現在最安価格（各サイト最新の price の最小値）
    current_best_price: Optional[int] = _get_current_best_price(site_products)

    # 5. キャンペーン取得
    sites = [sp.site_type for sp in site_products]
    model_sites = list(set(sites))  # 重複排除

    campaigns_orm = get_campaigns_for_suggestion(
        db,
        sites=model_sites,
        reference_date=now,
    )

    # 6. ORM → CampaignInfo 変換
    campaign_infos = build_campaign_infos(campaigns_orm)

    # 7. 次回セール推定
    upcoming_sales = estimate_next_sales(
        campaign_infos,
        reference_date=now.date(),
        horizon_days=_HORIZON_DAYS,
    )
    # 日付昇順ソート（最近のセールを先頭に）
    upcoming_sales = sorted(upcoming_sales, key=lambda s: s.estimated_date)

    # 8. サジェスト決定
    inp = SuggestionInput(
        current_best_price=current_best_price,
        price_stats=price_stats,
        upcoming_sales=upcoming_sales,
    )
    result = compute_suggestion(inp)

    return SuggestionResponse(
        product_id=parsed_id,
        action=result.action,
        rationale=result.rationale,
        current_best_effective_price=result.current_best_effective_price,
        expected_sale_effective_price=result.expected_sale_effective_price,
        estimated_saving=result.estimated_saving,
        next_sale_date=result.next_sale_date,
        next_sale_campaign=result.next_sale_campaign,
    )


def _get_current_best_price(site_products: list[EcSiteProduct]) -> Optional[int]:
    """各 EC サイト商品の直近価格の中で最安値を返す。

    price_histories が空の場合は None を返す（現在価格不明）。
    """
    latest_prices: list[int] = []
    for sp in site_products:
        if not sp.price_histories:
            continue
        # recorded_at 降順で最新を取得
        latest = max(sp.price_histories, key=lambda h: h.recorded_at)
        latest_prices.append(latest.price)

    return min(latest_prices) if latest_prices else None
