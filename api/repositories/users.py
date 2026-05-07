"""User リポジトリ。

責務:
    `users` テーブルに対する CRUD のうち認証フローで必要な最小限の操作を
    SQLAlchemy `Session` 経由で提供する。HTTP 層・認証ロジックには触れず、
    ドメインオブジェクト（`User`）の取得と作成だけを担当する。
"""
from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..common.models import User


def get_user_by_email(db: Session, email: str) -> Optional[User]:
    return db.query(User).filter(User.email == email).one_or_none()


def get_user_by_id(db: Session, user_id: uuid.UUID) -> Optional[User]:
    return db.query(User).filter(User.id == user_id).one_or_none()


def create_user(db: Session, *, email: str, hashed_password: str) -> User:
    """email と既にハッシュ化されたパスワードで新規 User を永続化する。

    パスワードのハッシュ化は呼び出し元（`api/common/security.py` 経由）の
    責務。リポジトリ層には平文パスワードを通さない。
    """
    user = User(email=email, hashed_password=hashed_password)
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise
    db.refresh(user)
    return user
