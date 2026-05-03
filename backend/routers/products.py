"""GET /api/products/search router and search helper.

Per order.md, every error path (q missing/empty/oversized, limit out-of-range,
DB failures, validation errors) is converted to 200 + []. Validation-error
fallback for non-numeric `limit` is registered globally in `main.py`; this
module owns the handler-level guards plus the SQL execution.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from database import get_db
from models import Product
from schemas import ProductOut

logger = logging.getLogger(__name__)

# Contract constants. Defined once so the handler, validation-error fallback,
# and any future caller all reference the same values.
ROUTER_PREFIX = "/api/products"
SEARCH_PATH = "/search"
SEARCH_FULL_PATH = ROUTER_PREFIX + SEARCH_PATH

Q_MAX_LENGTH = 100
LIMIT_DEFAULT = 10
LIMIT_MAX = 100

# Backslash is the LIKE escape character; user-supplied % / _ / \ are escaped
# with it so that they are matched as literals rather than wildcards.
LIKE_ESCAPE = "\\"


router = APIRouter(prefix=ROUTER_PREFIX, tags=["products"])


def _escape_like(value: str) -> str:
    # Order matters: escape backslashes first so we do not double-escape the
    # backslashes we then introduce for % and _.
    return (
        value.replace(LIKE_ESCAPE, LIKE_ESCAPE + LIKE_ESCAPE)
        .replace("%", LIKE_ESCAPE + "%")
        .replace("_", LIKE_ESCAPE + "_")
    )


def search_products(db: Session, q: str, limit: int) -> Sequence[Product]:
    """Run the relevance-ordered ILIKE search for `q`.

    Caller is responsible for trimming `q`, enforcing length limits, and
    clamping `limit`. Filter, sort, and limit are all pushed to the SQL layer
    so we never load the full table into Python.

    SQLAlchemy 2.0 `.scalars().all()` already materializes a list, so we
    expose the underlying Sequence rather than copying it again.
    """
    q_lower = q.lower()
    q_lower_escaped = _escape_like(q_lower)
    contains_pattern = f"%{q_lower_escaped}%"
    prefix_pattern = f"{q_lower_escaped}%"

    name_lower = func.lower(Product.name)
    description_lower = func.lower(Product.description)

    # Relevance tiers per plan.md: name exact > name prefix > name contains >
    # description contains. The first matching branch wins, so a product whose
    # name fully equals q is scored 4 even if its description also contains q.
    relevance = case(
        (name_lower == q_lower, 4),
        (name_lower.like(prefix_pattern, escape=LIKE_ESCAPE), 3),
        (name_lower.like(contains_pattern, escape=LIKE_ESCAPE), 2),
        (description_lower.like(contains_pattern, escape=LIKE_ESCAPE), 1),
        else_=0,
    )

    stmt = (
        select(Product)
        .where(
            Product.name.ilike(contains_pattern, escape=LIKE_ESCAPE)
            | Product.description.ilike(contains_pattern, escape=LIKE_ESCAPE)
        )
        .order_by(relevance.desc(), Product.name.asc(), Product.id.asc())
        .limit(limit)
    )

    return db.execute(stmt).scalars().all()


@router.get(SEARCH_PATH, response_model=list[ProductOut])
def search_products_endpoint(
    q: Optional[str] = Query(default=None),
    limit: int = Query(default=LIMIT_DEFAULT),
    db: Session = Depends(get_db),
) -> Sequence[Product]:
    if q is None:
        return []

    normalized_q = q.strip()
    if not normalized_q or len(normalized_q) > Q_MAX_LENGTH:
        return []

    if limit < 1:
        return []

    effective_limit = min(limit, LIMIT_MAX)

    try:
        return search_products(db, normalized_q, effective_limit)
    except Exception:
        # order.md: any error returns []. We log without exposing q so
        # raw user input never lands in operational logs.
        logger.warning("product search failed", exc_info=True)
        return []
