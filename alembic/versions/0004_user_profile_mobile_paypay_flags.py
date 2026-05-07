"""user_profiles.is_rakuten_mobile / is_paypay_linked

`docs/plans/user-profile-enhancement.md` §2.1 で追加した SPU / Yahoo!
ショッピング指定支払特典の判定フラグを `user_profiles` に追加する。

- `is_rakuten_mobile`: 楽天モバイル契約者の SPU +4% を T-06 ポイント算出
  ロジックで判定するための boolean。
- `is_paypay_linked`: Yahoo! ショッピングの LINE 連携 + 指定支払特典 +4% を
  同じく T-06 で判定するための boolean。

3 ステップロールアウト（0003 と同じパターン。`user-profile.md` §2.1 参照）:

    1. add column as nullable
    2. backfill `false` for existing rows
    3. set NOT NULL

Why 3 ステップ:
    本番環境に既存ユーザーがいる場合、いきなり NOT NULL を立てると既存行が
    制約違反になる。NULLABLE で先に列を作って backfill で確実に値を埋め、
    最後に NOT NULL に締めることで、既存ユーザーへ無停止で新フラグを
    rollout できる（agent-rules/50-production-reliability.md「無停止 rollout」）。

Revision ID: 0004
Revises: 0003
Create Date: 2026-05-05

"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Why 2 列まとめて: どちらも同じセマンティクス（user-profile-enhancement
    # §2.1 の追加フラグ）で 3 ステップ rollout も同形なので、1 リビジョンに
    # 同居させてマイグレーション履歴のノイズを抑える。
    # Step 1: nullable で先に列を追加（既存行の制約違反を回避）。
    op.add_column(
        "user_profiles",
        sa.Column("is_rakuten_mobile", sa.Boolean(), nullable=True),
    )
    op.add_column(
        "user_profiles",
        sa.Column("is_paypay_linked", sa.Boolean(), nullable=True),
    )
    # Step 2: 既存行を false で backfill。新フラグは「opt-in（楽天モバイル契約 /
    # PayPay 連携している場合のみ true）」のセマンティクスなので、既存ユーザーを
    # false 扱いにすることが docs/plans/user-profile-enhancement.md §4 の
    # 「破壊的変化を起こさない」を満たす。
    op.execute(
        "UPDATE user_profiles SET is_rakuten_mobile = false "
        "WHERE is_rakuten_mobile IS NULL"
    )
    op.execute(
        "UPDATE user_profiles SET is_paypay_linked = false "
        "WHERE is_paypay_linked IS NULL"
    )
    # Step 3: backfill 完了後に NOT NULL を締める。
    op.alter_column("user_profiles", "is_rakuten_mobile", nullable=False)
    op.alter_column("user_profiles", "is_paypay_linked", nullable=False)


def downgrade() -> None:
    # 列削除のみ。backfill した値は 0003 への巻き戻し時には不要。
    op.drop_column("user_profiles", "is_paypay_linked")
    op.drop_column("user_profiles", "is_rakuten_mobile")
