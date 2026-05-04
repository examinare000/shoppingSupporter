"""Product search repository.

Query strategy: full-text (tsvector @@ websearch_to_tsquery) OR trigram
similarity above a threshold. Both signals are summed into a relevance score
(`ts_rank + similarity`) so an exact word match outranks a fuzzy/typo match
at sort=relevance. Filters and pagination are pushed to SQL so we never
materialize the full table in Python.

`SearchParams` is the contract between the HTTP handler and this layer:
the handler is responsible for translating camelCase query string params
into snake_case fields, validating bounds (Query constraints + cross-field
priceMin <= priceMax check), and constructing the params object. This module
performs no further input interpretation.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal, Optional, Tuple

from sqlalchemy import ColumnElement, and_, bindparam, func, literal, or_, select
from sqlalchemy.orm import Session

from ..common.models import Product

PAGE_SIZE = 10

# Minimum trigram similarity for fuzzy matching. Below this threshold, fully
# unrelated terms (e.g. "xyz" against "apple") would otherwise bleed into
# results. The value is conservative enough to still admit single-character
# typos like "strawbery" -> "strawberry".
TRIGRAM_SIMILARITY_THRESHOLD = 0.3

SortKey = Literal["relevance", "price_asc", "price_desc", "newest"]


@dataclass(frozen=True)
class SearchParams:
    """Resolved, validated search parameters.

    Built by the HTTP handler from query-string inputs. Frozen so the
    repository cannot mutate the caller's view of the request.
    """

    q: str
    in_stock: Optional[bool]
    price_min: Optional[int]
    price_max: Optional[int]
    sort: SortKey
    page: int


def _searchable_text() -> ColumnElement[str]:
    # Must match the trigram GIN index expression in the search-columns
    # migration so Postgres can use the index instead of falling back to a
    # sequential scan. `immutable_array_to_string` is the wrapper introduced
    # in that migration because the built-in `array_to_string` is STABLE
    # (not IMMUTABLE) and therefore cannot be used inside an expression index.
    space = literal(" ")
    return (
        func.coalesce(Product.name, "")
        + space
        + func.coalesce(Product.description, "")
        + space
        + func.coalesce(func.immutable_array_to_string(Product.tags, " "), "")
    )


def _build_filters(params: SearchParams, q_param) -> list[ColumnElement[bool]]:
    searchable = _searchable_text()
    fts_match = Product.search_vector.op("@@")(
        func.websearch_to_tsquery(literal("simple"), q_param)
    )
    trigram_match = func.similarity(searchable, q_param) > TRIGRAM_SIMILARITY_THRESHOLD

    filters: list[ColumnElement[bool]] = [or_(fts_match, trigram_match)]

    if params.in_stock is not None:
        filters.append(Product.in_stock.is_(params.in_stock))
    # NULL current_price is correctly excluded by these comparisons (NULL
    # comparisons yield UNKNOWN, treated as false in WHERE), matching the
    # documented behavior in test_should_exclude_products_with_null_current_price.
    if params.price_min is not None:
        filters.append(Product.current_price >= params.price_min)
    if params.price_max is not None:
        filters.append(Product.current_price <= params.price_max)

    return filters


def _relevance_score(q_param) -> ColumnElement[float]:
    fts_rank = func.ts_rank(
        Product.search_vector,
        func.websearch_to_tsquery(literal("simple"), q_param),
    )
    trigram_score = func.similarity(_searchable_text(), q_param)
    # Both signals are non-negative; summing keeps the strongest of either
    # path while letting matches that hit both rank above ones that hit only
    # one.
    return fts_rank + trigram_score


def _order_by(sort: SortKey, q_param) -> list[ColumnElement]:
    # Tie-breaker on `id` keeps pagination stable across pages when the
    # primary sort key has duplicates (e.g. equal price, equal relevance).
    if sort == "price_asc":
        return [Product.current_price.asc().nulls_last(), Product.id.asc()]
    if sort == "price_desc":
        return [Product.current_price.desc().nulls_last(), Product.id.asc()]
    if sort == "newest":
        return [Product.created_at.desc(), Product.id.asc()]
    # relevance: highest score first, then newest, then id
    return [
        _relevance_score(q_param).desc(),
        Product.created_at.desc(),
        Product.id.asc(),
    ]


def search_products(
    db: Session, params: SearchParams
) -> Tuple[Sequence[Product], int]:
    """Run the search and return `(items, total_count)`.

    `total_count` is the unpaginated total so callers can compute totalPages.
    """
    # Bind `q` once and reuse it across the WHERE, ORDER BY, and COUNT
    # subquery. Reusing a single bindparam guarantees the same parameter
    # value reaches Postgres, and it is the only path q takes into SQL
    # (SQL injection is structurally impossible here).
    q_param = bindparam("q", value=params.q, type_=Product.name.type)

    filters = _build_filters(params, q_param)
    where_clause = and_(*filters)

    count_stmt = select(func.count()).select_from(Product).where(where_clause)
    total_count = db.execute(count_stmt).scalar_one()

    items_stmt = (
        select(Product)
        .where(where_clause)
        .order_by(*_order_by(params.sort, q_param))
        .limit(PAGE_SIZE)
        .offset((params.page - 1) * PAGE_SIZE)
    )
    items = db.execute(items_stmt).scalars().all()
    return items, total_count
