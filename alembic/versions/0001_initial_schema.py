"""initial schema

Baseline migration capturing every table that existed before the search
overhaul. The new search-related columns (`tags`, `in_stock`, `current_price`,
`search_vector`) and supporting indexes are introduced in 0002 to keep this
revision easy to compare with the pre-search-feature schema.

Revision ID: 0001
Revises:
Create Date: 2026-05-03

"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Raw SQL with IF NOT EXISTS sidesteps a quirk where
    # `postgresql.ENUM(...).create(checkfirst=True)` plus per-column
    # `Enum(create_type=False)` still races on `before_create` and tries to
    # re-emit the CREATE TYPE during the first `create_table` that references
    # the enum.
    op.execute(
        "DO $$ BEGIN "
        "CREATE TYPE rakutenrank AS ENUM ("
        "'REGULAR', 'SILVER', 'GOLD', 'PLATINUM', 'DIAMOND'); "
        "EXCEPTION WHEN duplicate_object THEN null; END $$"
    )
    op.execute(
        "DO $$ BEGIN "
        "CREATE TYPE sitetype AS ENUM ('AMAZON', 'RAKUTEN', 'YAHOO'); "
        "EXCEPTION WHEN duplicate_object THEN null; END $$"
    )

    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False, unique=True),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )

    op.create_table(
        "cards",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("base_reward_rate", sa.Float(), nullable=True),
        sa.Column("annual_fee", sa.Integer(), nullable=True),
        sa.Column("special_rewards", sa.JSON(), nullable=True),
    )

    op.create_table(
        "user_profiles",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("default_card_id", sa.Integer(), nullable=True),
        sa.Column(
            "rakuten_rank",
            postgresql.ENUM(
                "REGULAR",
                "SILVER",
                "GOLD",
                "PLATINUM",
                "DIAMOND",
                name="rakutenrank",
                create_type=False,
            ),
            nullable=True,
        ),
        sa.Column("is_amazon_prime", sa.Boolean(), nullable=True),
        sa.Column("yahoo_premium", sa.Boolean(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["default_card_id"], ["cards.id"]),
    )

    op.create_table(
        "products",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("jan_code", sa.String(20), nullable=True, unique=True),
        sa.Column("image_url", sa.String(1024), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_products_jan_code", "products", ["jan_code"])

    op.create_table(
        "ec_site_products",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "site_type",
            postgresql.ENUM("AMAZON", "RAKUTEN", "YAHOO", name="sitetype", create_type=False),
            nullable=False,
        ),
        sa.Column("site_product_id", sa.String(100), nullable=False),
        sa.Column("url", sa.String(1024), nullable=False),
        sa.Column("last_updated", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"]),
    )

    op.create_table(
        "price_histories",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("ec_site_product_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("price", sa.Integer(), nullable=False),
        sa.Column("points", sa.Integer(), nullable=True),
        sa.Column("recorded_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["ec_site_product_id"], ["ec_site_products.id"]),
    )


def downgrade() -> None:
    op.drop_table("price_histories")
    op.drop_table("ec_site_products")
    op.drop_index("ix_products_jan_code", table_name="products")
    op.drop_table("products")
    op.drop_table("user_profiles")
    op.drop_table("cards")
    op.drop_table("users")

    op.execute("DROP TYPE IF EXISTS sitetype")
    op.execute("DROP TYPE IF EXISTS rakutenrank")
