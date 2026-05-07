"""Initial Card seed.

Inserts the launch cards documented in `docs/plans/phase1-foundation.md`
T-04, `docs/api/cards.md`, and the rate calibration tracked in
`docs/plans/user-profile-enhancement.md` §2.2. Names are spec strings and
must not be abbreviated, translated, or punctuation-normalized.

CLI usage (run against the configured `DATABASE_URL`):

    python -m api.common.seed.cards

Idempotency: matches cards by name. Existing rows are updated in-place
(base_reward_rate / annual_fee / special_rewards); missing rows are inserted.
This avoids duplicates and preserves `UserProfile.default_card_id` FKs
across re-seeds, allowing reward-rate corrections without a destructive
re-seed cycle.
"""

from __future__ import annotations

from typing import Dict, List

from sqlalchemy.orm import Session

from ..models import Card

# Source of truth for the launch cards. Keys are intentionally snake_case to
# match the SQLAlchemy column names so `Card(**row)` works directly. Values
# for `special_rewards` use `SiteType` value strings; semantics (additive
# bonus rate in %) are spelled out in `docs/api/cards.md`.
#
# Rate calibration (docs/plans/user-profile-enhancement.md §2.2, 2025/2026):
#   - 楽天カード: rakuten +2.0%（カード保有 SPU の最新値）
#   - 楽天プレミアムカード: rakuten +4.0%（プレミアム加算分。年会費 11000 円）
#   - Amazon Mastercard: amazon +1.5%（一般会員ベース。プライム加算は
#     T-06 の算出ロジックで `is_amazon_prime` を参照して合算する）
# 楽天プレミアムカードは楽天カードの直後に配置し、ファミリーを隣接させる。
CARDS_SEED_DATA: List[Dict] = [
    {
        "name": "楽天カード",
        "base_reward_rate": 1.0,
        "annual_fee": 0,
        "special_rewards": {"rakuten": 2.0},
    },
    {
        "name": "楽天プレミアムカード",
        "base_reward_rate": 1.0,
        "annual_fee": 11000,
        "special_rewards": {"rakuten": 4.0},
    },
    {
        "name": "Amazon Mastercard",
        "base_reward_rate": 1.0,
        "annual_fee": 0,
        "special_rewards": {"amazon": 1.5},
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
    """Insert or update the spec cards.

    Idempotency: Matches cards by name. This allows updating reward rates in
    the seed data without creating duplicates or breaking existing FKs
    that reference these cards.
    """
    for row in CARDS_SEED_DATA:
        existing = db.query(Card).filter(Card.name == row["name"]).one_or_none()
        if existing:
            # Update existing row fields
            existing.base_reward_rate = row["base_reward_rate"]
            existing.annual_fee = row["annual_fee"]
            existing.special_rewards = row["special_rewards"]
        else:
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
