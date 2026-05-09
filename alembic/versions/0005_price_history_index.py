"""price_histories 複合インデックス追加

docs/plans/phase2-price-history.md F-16「インデックス最適化」要件。
`GET /api/products/{id}/history` の DISTINCT ON クエリが
(ec_site_product_id, recorded_at) の順でフィルタ・ソートするため、
同順の複合インデックスを作成してインデックススキャンを有効にする。

Revision ID: 0005
Revises: 0004
Create Date: 2026-05-08

"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# インデックス名を定数として1箇所で定義し、upgrade/downgrade 間の不一致を防ぐ。
INDEX_NAME = "ix_price_histories_ec_site_product_id_recorded_at"
TABLE_NAME = "price_histories"
COLUMNS = ["ec_site_product_id", "recorded_at"]


def upgrade() -> None:
    op.create_index(INDEX_NAME, TABLE_NAME, COLUMNS)


def downgrade() -> None:
    op.drop_index(INDEX_NAME, table_name=TABLE_NAME)
