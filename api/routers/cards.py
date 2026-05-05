"""Cards router.

Owns the HTTP boundary for the public, read-only Card master endpoints:
- `GET /api/cards` returns every card ordered by `id` ASC (bare array).
- `GET /api/cards/{card_id}` returns a single card or 404.

Why no repository layer: each handler is a one-line ORM call (no FTS, no
trigram, no filter / sort matrix to reuse). Extracting a repository now
would be premature; T-08 may revisit if the search endpoint needs to join
cards.
"""

from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..common.database import get_db
from ..common.models import Card
from ..schemas import CardResponse

ROUTER_PREFIX = "/api/cards"

router = APIRouter(prefix=ROUTER_PREFIX, tags=["cards"])


# `response_model_by_alias=True` is what makes the JSON keys camelCase
# (`baseRewardRate`, `annualFee`, `specialRewards`). Without it the snake_case
# attribute names would leak into the wire format.
@router.get(
    "",
    response_model=List[CardResponse],
    response_model_by_alias=True,
)
def list_cards(db: Session = Depends(get_db)) -> List[Card]:
    # `ORDER BY id ASC` pins a stable, test-observable order. Insertion
    # order is not a contract Postgres guarantees, so we fix it explicitly.
    return db.query(Card).order_by(Card.id.asc()).all()


@router.get(
    "/{card_id}",
    response_model=CardResponse,
    response_model_by_alias=True,
)
def get_card(card_id: int, db: Session = Depends(get_db)) -> Card:
    card = db.get(Card, card_id)
    if card is None:
        # 404 (not 200 + null) so callers can distinguish "missing" from
        # "found but empty fields". Path-level type validation handles the
        # 422 case before this handler runs.
        raise HTTPException(status_code=404, detail="Card not found")
    return card
