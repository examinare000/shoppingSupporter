"""認証に関する共通基盤。

ここに集約するもの:
    - パスワードのハッシュ化と検証（bcrypt 直接利用）
    - アクセストークン（JWT）の発行とデコード
    - `Depends(get_current_user)` で利用する FastAPI 依存性

Why この集約か:
    plan.md「操作の一覧性」「パブリック API の公開範囲」に基づき、
    `bcrypt` と `jwt` の import はこのモジュール 1 箇所に閉じる。
    ルーター・リポジトリは公開関数経由でのみ認証操作を行う。
"""
from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt as pyjwt
from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from ..repositories.users import get_user_by_id
from .database import get_db
from .models import User

# ADR-007 / plan.md「実装ガイドライン」の決定:
# - HS256: ADR-007 が「秘密鍵 (`JWT_SECRET`) で署名を検証」を示し対称鍵方式を採用。
# - 60 分: ADR-007 で未指定。FastAPI 標準チュートリアルの既定値で最小実装方針に合致。
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRES_MINUTES = 60

# Bearer スキームを契約として定数化。401 メッセージも一意の文字列で集約する。
BEARER_SCHEME = "Bearer"
INVALID_CREDENTIALS_MESSAGE = "Invalid credentials"


def _unauthorized() -> HTTPException:
    """`get_current_user` 経路の 401 を 1 箇所に集約するヘルパ。

    Why:
        plan.md「内部詳細を露出しない」に従い、認証経路の失敗はすべて
        同一の `(401, INVALID_CREDENTIALS_MESSAGE)` 応答に正規化する。
        将来 `WWW-Authenticate: Bearer` ヘッダを付与する／detail を構造化する
        といった変更を、このヘルパ 1 点の修正で済ませるため。
    """
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=INVALID_CREDENTIALS_MESSAGE,
    )


def _get_jwt_secret() -> str:
    """`JWT_SECRET` を環境変数から遅延参照する。

    Why 遅延:
        モジュール import 時に raise すると、conftest.py の
        `os.environ.setdefault("JWT_SECRET", ...)` がアプリ import より
        後に評価されるケースで誤って失敗する。テスト用 placeholder の
        注入順序とプロダクションの fail-fast を両立するため、初回利用
        時に解決する。空文字も「設定済み」とは扱わず RuntimeError にする。
    """
    secret = os.environ.get("JWT_SECRET")
    if not secret:
        raise RuntimeError("JWT_SECRET is not configured")
    return secret


def hash_password(plain: str) -> str:
    """平文パスワードを bcrypt でハッシュ化する。"""
    hashed = bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt())
    return hashed.decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    """平文パスワードと bcrypt ハッシュを照合する。"""
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


def create_access_token(user_id: uuid.UUID) -> str:
    """user id を `sub` に乗せた HS256 アクセストークンを発行する。"""
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "iat": now,
        "exp": now + timedelta(minutes=ACCESS_TOKEN_EXPIRES_MINUTES),
    }
    return pyjwt.encode(payload, _get_jwt_secret(), algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> dict:
    """アクセストークンを検証してクレームを返す。

    無効・期限切れ・改ざんは例外として上位に伝播させる
    （plan.md「エラーハンドリング: 上位層で一元処理」）。
    """
    return pyjwt.decode(token, _get_jwt_secret(), algorithms=[JWT_ALGORITHM])


def _extract_bearer_token(authorization: str | None) -> str:
    """`Authorization: Bearer <token>` ヘッダから token 部分を取り出す。

    Bearer スキーム以外、ヘッダ欠落、空のトークンはすべて 401 にする。
    """
    if not authorization:
        raise _unauthorized()
    scheme, _, token = authorization.partition(" ")
    if scheme.strip().lower() != BEARER_SCHEME.lower() or not token:
        raise _unauthorized()
    return token


def get_current_user(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> User:
    """JWT 認証済みユーザーを返す FastAPI 依存性。

    検証に通らない（ヘッダ欠落・スキーム違い・改ざん・期限切れ・
    sub に対応する User 不在）はすべて 401 に正規化する。
    """
    token = _extract_bearer_token(authorization)
    try:
        payload = decode_access_token(token)
    except pyjwt.PyJWTError as exc:
        raise _unauthorized() from exc

    sub = payload.get("sub")
    if not isinstance(sub, str):
        raise _unauthorized()
    try:
        user_id = uuid.UUID(sub)
    except ValueError as exc:
        raise _unauthorized() from exc

    user = get_user_by_id(db, user_id)
    if user is None:
        raise _unauthorized()
    return user


def get_current_user_optional(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> User | None:
    """JWT 認証済みユーザーを返す。未認証・無効トークンは None を返す FastAPI 依存性。

    Why None を返すか:
        検索エンドポイントは公開エンドポイントだが、認証済みの場合は
        パーソナライズを適用する（T-08 設計）。無効なトークンも
        401 を返さず None として扱い、未認証ユーザーと同様に扱う。
        （T-08 テスト戦略: 「無効トークンは 401 を返さず未認証として扱う」）
    """
    try:
        return get_current_user(authorization=authorization, db=db)
    except HTTPException:
        return None
