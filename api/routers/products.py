"""Product search router.

Owns the HTTP boundary for `GET /api/products/search`:
- Parses and validates query string parameters (FastAPI `Query` constraints).
- Performs the cross-field `priceMin <= priceMax` check.
- Translates camelCase HTTP parameter names into the snake_case `SearchParams`
  consumed by the repository.
- Wraps the repository result in the `{items, page, totalPages, totalCount}`
  envelope.
"""

from __future__ import annotations

import logging
import math
import time
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..common.database import get_db
from ..repositories.products import (
    PAGE_SIZE,
    SearchParams,
    SortKey,
    search_products,
)
from ..schemas import ProductSearchEnvelope, ProductSummary

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


def _build_envelope(
    items, page: int, total_count: int
) -> ProductSearchEnvelope:
    total_pages = math.ceil(total_count / PAGE_SIZE) if total_count else 0
    summaries = [ProductSummary.model_validate(p) for p in items]
    return ProductSearchEnvelope(
        items=summaries,
        page=page,
        total_pages=total_pages,
        total_count=total_count,
    )


# `response_model_by_alias=True` is what makes the JSON keys camelCase
# (`imageUrl`, `inStock`, `currentPrice`, `totalPages`, `totalCount`).
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

    return _build_envelope(items, page=page, total_count=total_count)
