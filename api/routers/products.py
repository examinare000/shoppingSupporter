"""Product search router.

Owns the HTTP boundary for `GET /api/products/search`:
- Parses and validates query string parameters (FastAPI `Query` constraints).
- Performs the cross-field `priceMin <= priceMax` check.
- Translates camelCase HTTP parameter names into the snake_case `SearchParams`
  consumed by the repository.
- Wraps the repository result in the `{items, page, totalPages, totalCount, meta}`
  envelope. `meta.personalization` reflects whether the search result was
  personalized (T-08 integration: UserProfile / Card / PricingEngine).
"""

from __future__ import annotations

import logging
import math
import time
from collections.abc import Sequence
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..common.database import get_db
from ..common.models import Card, EcSiteProduct, Product, User, UserProfile
from ..common.security import get_current_user_optional
from ..lib.pricing import SiteType as PricingSiteType, compute_pricing
from ..repositories.products import (
    PAGE_SIZE,
    SearchParams,
    SortKey,
    search_products,
)
from ..repositories.user_profiles import get_profile_by_user_id
from ..schemas import (
    BreakdownEntry,
    ListingOut,
    PersonalizationMeta,
    ProductSearchEnvelope,
    ProductSummary,
    SearchMeta,
)

logger = logging.getLogger(__name__)

ROUTER_PREFIX = "/api/products"
SEARCH_PATH = "/search"

# `q` length cap and sort allowlist are part of the public contract; tests
# in test_product_search.py assert the boundaries.
Q_MAX_LENGTH = 100

router = APIRouter(prefix=ROUTER_PREFIX, tags=["products"])


def _validate_price_range(price_min: Optional[int], price_max: Optional[int]) -> None:
    if price_min is None or price_max is None:
        return
    if price_min > price_max:
        # 422 keeps semantics aligned with FastAPI's per-parameter validators
        # so callers see the same status for every input-shape failure.
        raise HTTPException(
            status_code=422,
            detail="priceMin must be less than or equal to priceMax",
        )


def _make_listing(
    sp: EcSiteProduct,
    price: Optional[int],
    profile: Optional[UserProfile],
    card: Optional[Card],
) -> ListingOut:
    """EcSiteProduct 1 件を ListingOut に変換する。

    Why profile=None のときに全フィールド null か:
        未認証・プロフィール未設定のユーザーにはポイント計算を行わない
        （T-08 仕様: 未認証は points/effectivePrice/breakdown=null）。

    Why price=None のときも null か:
        current_price が null の商品はポイント計算不可（算出ベースがない）。
    """
    points = None
    effective_price = None
    breakdown = None
    if profile is not None and price is not None:
        site = PricingSiteType(sp.site_type.value)
        result = compute_pricing(
            price=price,
            shipping=0,  # 送料は DB 未記録のため 0 固定（T-08 設計書より）
            site=site,
            profile=profile,
            card=card,
        )
        points = result.total_points
        effective_price = result.effective_price
        breakdown = [
            BreakdownEntry(label=e.label, rate=e.rate, points=e.points, note=e.note)
            for e in result.breakdown
        ]
    return ListingOut(
        site_type=sp.site_type.value,
        site_product_id=sp.site_product_id,
        url=sp.url,
        points=points,
        effective_price=effective_price,
        breakdown=breakdown,
    )


def _make_personalization_meta(profile: Optional[UserProfile]) -> PersonalizationMeta:
    """UserProfile から PersonalizationMeta を構築する。

    Why profile=None のとき applied=False か:
        未認証・プロフィール未設定ユーザーへはパーソナライズを適用しない
        （T-08 テスト戦略）。
    """
    if profile is None:
        return PersonalizationMeta(applied=False, rakuten_rank=None, has_card=False)
    return PersonalizationMeta(
        applied=True,
        rakuten_rank=profile.rakuten_rank.value,
        has_card=profile.default_card_id is not None,
    )


def _build_envelope(
    items: Sequence[Product],
    page: int,
    total_count: int,
    profile: Optional[UserProfile],
    card: Optional[Card],
) -> ProductSearchEnvelope:
    total_pages = math.ceil(total_count / PAGE_SIZE)
    summaries: List[ProductSummary] = []
    for p in items:
        listings = [
            _make_listing(sp, p.current_price, profile, card)
            for sp in p.site_products
        ]
        # Why model_copy: Pydantic v2 の model_validate は update 引数を
        # サポートしないバージョンがあるため model_copy を使う。
        base = ProductSummary.model_validate(p)
        summaries.append(base.model_copy(update={"listings": listings}))
    meta = SearchMeta(personalization=_make_personalization_meta(profile))
    return ProductSearchEnvelope(
        items=summaries,
        page=page,
        total_pages=total_pages,
        total_count=total_count,
        meta=meta,
    )


# ADR-013 の camelCase 出力規約を適用（schema の serialization_alias を有効化）。
@router.get(
    SEARCH_PATH,
    response_model=ProductSearchEnvelope,
    response_model_by_alias=True,
)
def search_products_endpoint(
    q: str = Query(min_length=1, max_length=Q_MAX_LENGTH),
    inStock: Optional[bool] = Query(default=None),
    priceMin: Optional[int] = Query(default=None, ge=0),
    priceMax: Optional[int] = Query(default=None, ge=0),
    sort: SortKey = Query(default="relevance"),
    page: int = Query(default=1, ge=1),
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
) -> ProductSearchEnvelope:
    # FastAPI's per-Query validation handles bounds, type, and required-ness.
    # The cross-field check is the only validation that lives in the handler
    # because pydantic Query parameters cannot express it directly.
    _validate_price_range(priceMin, priceMax)

    params = SearchParams(
        q=q,
        in_stock=inStock,
        price_min=priceMin,
        price_max=priceMax,
        sort=sort,
        page=page,
    )

    started = time.monotonic()
    items, total_count = search_products(db, params)
    elapsed_ms = (time.monotonic() - started) * 1000
    # Log only metadata. Raw `q` is intentionally not logged so user input
    # never lands in operational logs.
    logger.info(
        "product search executed q_len=%d hits=%d elapsed_ms=%.1f",
        len(q),
        total_count,
        elapsed_ms,
    )

    # プロフィールはループ外で 1 回だけ取得してメモリ保持（N+1 回避）。
    # get_profile_by_user_id は joinedload で default_card を取得するため
    # card の追加クエリは発生しない。
    profile: Optional[UserProfile] = None
    card: Optional[Card] = None
    if current_user is not None:
        profile = get_profile_by_user_id(db, current_user.id)
        if profile is not None:
            card = profile.default_card  # joinedload 済み（追加クエリなし）

    return _build_envelope(items, page=page, total_count=total_count, profile=profile, card=card)
