"""UserProfile リポジトリ。

責務:
    `user_profiles` テーブルに対する取得・UPSERT、および `cards` 行の存在
    確認を SQLAlchemy `Session` 経由で提供する。HTTP 層・認証ロジックには
    触れず、ドメインオブジェクト（`UserProfile`）の取得と保存だけを担当する。

Why この層を持つか:
    docs/design/user-profile.md §4.1 と既存 `api/repositories/users.py` の
    責務分離パターンに合わせる。`default_card_id` の存在確認を FK
    IntegrityError 救済（500 → 422）ではなく事前 SELECT で行う方針
    （docs/design/user-profile.md §3.2「DB の外部キー違反を待たずに検証」）
    の主体もこのリポジトリ層が担う。
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session, joinedload

from ..common.models import Card, UserProfile, RakutenRank


def get_profile_by_user_id(
    db: Session, user_id: uuid.UUID
) -> Optional[UserProfile]:
    """`user_id` の UserProfile を取得する。`default_card` を eager load する。

    Why joinedload:
        レスポンスに `defaultCard` を nested 同梱する契約
        （docs/design/user-profile.md §3.3）と、N+1 を避けるため
        （plan.md「joinedload(UserProfile.default_card)」）。lazy load では
        FastAPI のレスポンスシリアライズ中に Session が閉じられて
        `DetachedInstanceError` を起こすケースがある。
    """
    return (
        db.query(UserProfile)
        .options(joinedload(UserProfile.default_card))
        .filter(UserProfile.user_id == user_id)
        .one_or_none()
    )


def card_exists(db: Session, card_id: int) -> bool:
    """指定 `card_id` のカードが存在するか確認する。

    Why 専用関数:
        FK IntegrityError を 500 から 422 に救済するより、状態整合性を
        意味的に正しい 422 として表現する方が API 利用者にとって明確。
        ルーター層から呼ばれ、422 への変換責務はルーターが持つ
        （リポジトリは存在の真偽だけを返す）。
    """
    return db.query(Card.id).filter(Card.id == card_id).first() is not None


def upsert_profile(
    db: Session,
    *,
    user_id: uuid.UUID,
    rakuten_rank: RakutenRank,
    is_amazon_prime: bool,
    yahoo_premium: bool,
    is_rakuten_mobile: bool,
    is_paypay_linked: bool,
    default_card_id: Optional[int],
) -> UserProfile:
    """`user_id` をキーに UserProfile を全置換 UPSERT する。

    Why 全置換:
        PUT のセマンティクス（docs/design/user-profile.md §3.2「全フィールド
        必須の PUT (全置換)」）に対応。PATCH は将来検討。

    Why keyword-only:
        既存 `create_user(db, *, email, hashed_password)` の慣習に揃え、
        ブール値の位置間違い（`is_amazon_prime` と `yahoo_premium` の
        スワップ等）を呼び出し時に検出する。`is_rakuten_mobile` /
        `is_paypay_linked` を追加してもパラメータスワップが起きないよう、
        keyword-only を継続する。
    """
    now = datetime.utcnow()
    stmt = pg_insert(UserProfile).values(
        user_id=user_id,
        rakuten_rank=rakuten_rank,
        is_amazon_prime=is_amazon_prime,
        yahoo_premium=yahoo_premium,
        is_rakuten_mobile=is_rakuten_mobile,
        is_paypay_linked=is_paypay_linked,
        default_card_id=default_card_id,
        updated_at=now,
    ).on_conflict_do_update(
        index_elements=["user_id"],
        set_={
            "rakuten_rank": rakuten_rank,
            "is_amazon_prime": is_amazon_prime,
            "yahoo_premium": yahoo_premium,
            "is_rakuten_mobile": is_rakuten_mobile,
            "is_paypay_linked": is_paypay_linked,
            "default_card_id": default_card_id,
            "updated_at": now,
        },
    )
    db.execute(stmt)
    db.commit()

    # commit 後に joinedload 付きで再取得する。`db.refresh(existing)` だけでは
    # `default_card` リレーションは lazy のままで、レスポンスシリアライズ時に
    # 追加 SELECT が走る（N+1）。リポジトリ責務として「呼び出し元が常に
    # eager load された行を扱える」状態で返す。
    refreshed = get_profile_by_user_id(db, user_id)
    # 直前に commit した行なので必ず存在する。Optional を剥がすために assert
    # を入れる（Fail Fast）。万一 None が返ったらリポジトリ・トランザクション
    # 整合性の根本破壊なので 500 で気付くべき。
    assert refreshed is not None
    return refreshed
