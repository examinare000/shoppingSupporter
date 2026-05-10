"""sale_campaigns と monthly_usage テーブルを追加

セールカレンダー・月次利用実績のデータ基盤（T-16）。
これらは「真の還元率」算出に必要な入力データを提供する
（docs/plans/phase3-analytics-suggestion.md §4）。

Revision ID: 0006
Revises: 0005
Create Date: 2026-05-10

"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# テーブル名を定数として 1 箇所で定義し、upgrade/downgrade 間の不一致を防ぐ。
SALE_CAMPAIGNS_TABLE = "sale_campaigns"
MONTHLY_USAGE_TABLE = "monthly_usage"


def upgrade() -> None:
    # campaignkind enum 作成。sitetype と同じ DO $$ BEGIN パターンで
    # 冪等性を保証する（0001_initial_schema.py §27-43 と同じ手法）。
    # Why 大文字値: 既存 sitetype / rakutenrank と同じ規約に揃える。
    op.execute(
        "DO $$ BEGIN "
        "CREATE TYPE campaignkind AS ENUM ('RECURRING', 'ONESHOT'); "
        "EXCEPTION WHEN duplicate_object THEN null; END $$"
    )

    op.create_table(
        SALE_CAMPAIGNS_TABLE,
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "site",
            postgresql.ENUM("AMAZON", "RAKUTEN", "YAHOO", name="sitetype", create_type=False),
            nullable=False,
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column(
            "kind",
            postgresql.ENUM("RECURRING", "ONESHOT", name="campaignkind", create_type=False),
            nullable=False,
        ),
        sa.Column("recurrence_rule", postgresql.JSONB(), nullable=True),
        sa.Column("start_at", sa.DateTime(), nullable=True),
        sa.Column("end_at", sa.DateTime(), nullable=True),
        sa.Column("bonus", postgresql.JSONB(), nullable=False),
        sa.Column("cap", postgresql.JSONB(), nullable=True),
        sa.Column("conditions", postgresql.JSONB(), nullable=True),
    )

    op.create_table(
        MONTHLY_USAGE_TABLE,
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "site",
            postgresql.ENUM("AMAZON", "RAKUTEN", "YAHOO", name="sitetype", create_type=False),
            nullable=False,
        ),
        # Why String(7): YYYY-MM 形式は 7 文字固定。Date 型より wire format と同形で一貫性が高い。
        sa.Column("recorded_month", sa.String(7), nullable=False),
        sa.Column("amount_spent", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("points_earned", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("shop_count", sa.Integer(), nullable=False, server_default="0"),
        sa.PrimaryKeyConstraint("user_id", "site", "recorded_month"),
        # Why ondelete CASCADE: User 削除時に MonthlyUsage も連動削除する。
        # bulk DELETE でも DB レベルで連動させるため FK 側に持たせる（user_profiles と同パターン）。
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )


def downgrade() -> None:
    op.drop_table(MONTHLY_USAGE_TABLE)
    op.drop_table(SALE_CAMPAIGNS_TABLE)
    op.execute("DROP TYPE IF EXISTS campaignkind")
