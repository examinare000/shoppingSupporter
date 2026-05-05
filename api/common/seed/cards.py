"""Initial Card seed.

Inserts the four launch cards documented in `docs/plans/phase1-foundation.md`
T-04 and `docs/api/cards.md`. Names are spec strings and must not be
abbreviated, translated, or punctuation-normalized.

CLI usage (run against the configured `DATABASE_URL`):

    python -m api.common.seed.cards

Idempotency: a non-empty `cards` table short-circuits the seed. We do not
have a unique constraint on `cards.name`, so `ON CONFLICT` is not available
without a schema change; the count==0 gate is the simplest safe alternative
that also avoids a destructive re-seed (which would invalidate
`UserProfile.default_card_id` FKs in T-05).
"""

from __future__ import annotations

from typing import Dict, List

from sqlalchemy.orm import Session

from ..models import Card

# Source of truth for the four launch cards. Keys are intentionally
# snake_case to match the SQLAlchemy column names so `Card(**row)` works
# directly. Values for `special_rewards` use `SiteType` value strings;
# semantics (additive bonus rate in %) are spelled out in
# `docs/api/cards.md`.
CARDS_SEED_DATA: List[Dict] = [
    {
        "name": "楽天カード",
        "base_reward_rate": 1.0,
        "annual_fee": 0,
        "special_rewards": {"rakuten": 1.0},
    },
    {
        "name": "Amazon Mastercard",
        "base_reward_rate": 1.0,
        "annual_fee": 0,
        "special_rewards": {"amazon": 0.5},
    },
    {
        "name": "Yahoo! JAPAN カード",
        "base_reward_rate": 1.0,
        "annual_fee": 0,
        "special_rewards": {"yahoo": 1.0},
    },
    {
        "name": "一般 1% 還元カード",
        "base_reward_rate": 1.0,
        "annual_fee": 0,
        "special_rewards": {},
    },
]


def seed_cards(db: Session) -> None:
    """Insert the four spec cards if the table is empty.

    Returns silently when the table already has any row. This is the
    documented contract — it is what makes the function safe to re-run
    in deploy pipelines and test environments.
    """
    if db.query(Card).count() > 0:
        return
    for row in CARDS_SEED_DATA:
        db.add(Card(**row))
    db.commit()


if __name__ == "__main__":
    # Late import keeps the module importable in test environments where
    # `DATABASE_URL` may not be set; the CLI path is the only one that
    # actually needs `SessionLocal`.
    from ..database import SessionLocal

    db = SessionLocal()
    try:
        seed_cards(db)
    finally:
        db.close()
