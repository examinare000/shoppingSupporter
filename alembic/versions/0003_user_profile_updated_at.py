"""user_profiles.updated_at and user_id ON DELETE CASCADE

Adds the `updated_at` column required by `GET/PUT /api/me/profile`
(`docs/design/user-profile.md` §2.1) and reattaches the `user_id` foreign key
with `ON DELETE CASCADE` so deleting a `users` row removes the dependent
`user_profiles` row in the same statement.

The `updated_at` rollout follows the 3-step pattern documented in
`user-profile.md` §2.1 to keep production-equivalent rollouts safe even if
existing rows are present:

    1. add column as nullable
    2. backfill `now()` for the existing rows
    3. set NOT NULL

Revision ID: 0003
Revises: 0002
Create Date: 2026-05-05

"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Postgres' default naming convention assigns `<table>_<column>_fkey` to a
# constraint declared without an explicit name. The 0001 baseline declared
# the FKs without a name, so this is the live identifier we drop and
# recreate. Centralised here so any future rename happens in one place.
USER_FK_NAME = "user_profiles_user_id_fkey"


def upgrade() -> None:
    # Step 1: add nullable so existing rows are not blocked by NOT NULL.
    op.add_column(
        "user_profiles",
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    # Step 2: backfill so every existing row has a value before the
    # NOT NULL constraint applies. `now()` is the only sensible value at
    # migration time (the original write time is unrecoverable).
    op.execute(
        "UPDATE user_profiles SET updated_at = now() WHERE updated_at IS NULL"
    )
    # Step 3: tighten to NOT NULL once backfill is complete.
    op.alter_column("user_profiles", "updated_at", nullable=False)

    # Reattach `user_id` FK with ON DELETE CASCADE. The 0001 baseline created
    # the FK without `ondelete`, so the constraint must be dropped and
    # recreated; PostgreSQL has no in-place ALTER for the cascade clause.
    op.drop_constraint(USER_FK_NAME, "user_profiles", type_="foreignkey")
    op.create_foreign_key(
        USER_FK_NAME,
        "user_profiles",
        "users",
        ["user_id"],
        ["id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    op.drop_constraint(USER_FK_NAME, "user_profiles", type_="foreignkey")
    op.create_foreign_key(
        USER_FK_NAME,
        "user_profiles",
        "users",
        ["user_id"],
        ["id"],
    )
    op.drop_column("user_profiles", "updated_at")
