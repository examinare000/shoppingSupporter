"""product search columns and indexes

Adds the columns needed by `GET /api/products/search`:
- `tags` (text[]): tag-based filtering / search
- `in_stock` (bool): in-stock filter
- `current_price` (int, nullable): price range filter and price sort
- `search_vector` (tsvector): FTS source, populated by trigger

Plus the supporting indexes:
- GIN on `search_vector` for FTS
- GIN with `gin_trgm_ops` on the searchable text expression for trigram fuzzy match
- B-tree on `current_price` for range scans and sort

A BEFORE INSERT/UPDATE trigger maintains `search_vector`. A `GENERATED ... STORED`
column would be cleaner, but Postgres requires the generation expression to be
IMMUTABLE; `to_tsvector(regconfig, text)` is only STABLE, so generated columns
are not an option here.

Revision ID: 0002
Revises: 0001
Create Date: 2026-05-03

"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# tsvector content. Wrapped in `to_tsvector('simple', ...)`. Used inside the
# trigger function below; kept here as a constant so the trigger and the
# trigram index expression can not drift relative to each other.
_TSVECTOR_BODY = (
    "to_tsvector('simple', "
    "coalesce(NEW.name, '') || ' ' || "
    "coalesce(NEW.description, '') || ' ' || "
    "coalesce(immutable_array_to_string(NEW.tags, ' '), ''))"
)

# Trigram index uses the raw concatenated text, not the tsvector. tsvector
# normalizes/lemmatizes which would defeat the per-character similarity
# pg_trgm relies on for typo tolerance. `immutable_array_to_string` (created
# in upgrade()) replaces the STABLE built-in so the expression qualifies for
# an index.
_TRIGRAM_EXPRESSION = (
    "(coalesce(name, '') || ' ' || "
    "coalesce(description, '') || ' ' || "
    "coalesce(immutable_array_to_string(tags, ' '), ''))"
)


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    # `array_to_string(text[], text)` is STABLE in Postgres, not IMMUTABLE,
    # which disqualifies it from expression indexes. The wrapper coerces the
    # call into an IMMUTABLE function so the trigram GIN index over the
    # concatenated searchable text can be created.
    op.execute(
        """
        CREATE OR REPLACE FUNCTION immutable_array_to_string(text[], text)
        RETURNS text LANGUAGE sql IMMUTABLE AS $$
        SELECT array_to_string($1, $2)
        $$
        """
    )

    op.add_column(
        "products",
        sa.Column(
            "tags",
            postgresql.ARRAY(sa.String()),
            nullable=False,
            server_default="{}",
        ),
    )
    op.add_column(
        "products",
        sa.Column(
            "in_stock",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
    )
    op.add_column(
        "products",
        sa.Column("current_price", sa.Integer(), nullable=True),
    )
    op.add_column(
        "products",
        sa.Column("search_vector", postgresql.TSVECTOR(), nullable=True),
    )

    op.execute(
        f"""
        CREATE OR REPLACE FUNCTION products_search_vector_update()
        RETURNS trigger AS $$
        BEGIN
            NEW.search_vector := {_TSVECTOR_BODY};
            RETURN NEW;
        END
        $$ LANGUAGE plpgsql
        """
    )
    op.execute(
        """
        CREATE TRIGGER products_search_vector_trigger
        BEFORE INSERT OR UPDATE OF name, description, tags ON products
        FOR EACH ROW EXECUTE FUNCTION products_search_vector_update()
        """
    )

    op.execute(
        "CREATE INDEX ix_products_search_vector "
        "ON products USING GIN (search_vector)"
    )
    op.execute(
        "CREATE INDEX ix_products_searchable_trgm "
        f"ON products USING GIN ({_TRIGRAM_EXPRESSION} gin_trgm_ops)"
    )
    op.create_index("ix_products_current_price", "products", ["current_price"])


def downgrade() -> None:
    op.drop_index("ix_products_current_price", table_name="products")
    op.execute("DROP INDEX IF EXISTS ix_products_searchable_trgm")
    op.execute("DROP INDEX IF EXISTS ix_products_search_vector")
    op.execute("DROP TRIGGER IF EXISTS products_search_vector_trigger ON products")
    op.execute("DROP FUNCTION IF EXISTS products_search_vector_update()")
    op.execute("DROP FUNCTION IF EXISTS immutable_array_to_string(text[], text)")
    op.drop_column("products", "search_vector")
    op.drop_column("products", "current_price")
    op.drop_column("products", "in_stock")
    op.drop_column("products", "tags")
    # pg_trgm extension is left installed: other features may rely on it,
    # and removing extensions is rarely the right thing to do on downgrade.
