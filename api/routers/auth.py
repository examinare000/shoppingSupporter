"""認証エンドポイント。

`POST /api/auth/signup`、`POST /api/auth/login`、`GET /api/auth/me` の
HTTP 境界を担当する。実際のパスワード検証・トークン発行は
`api/common/security.py`、永続化は `api/repositories/users.py` に委譲し、
本モジュールは入力バリデーションと HTTP レスポンス整形のみを行う。
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..common.database import get_db
from ..common.models import User
from ..common.security import (
    INVALID_CREDENTIALS_MESSAGE,
    create_access_token,
    get_current_user,
    hash_password,
    verify_password,
)
from ..repositories.users import create_user, get_user_by_email
from ..schemas import LoginRequest, SignupRequest, TokenResponse, UserResponse

ROUTER_PREFIX = "/api/auth"
SIGNUP_PATH = "/signup"
LOGIN_PATH = "/login"
ME_PATH = "/me"

# Why 409: 重複 email は永続化時の状態競合であり、入力フォーマット違反では
# ない（plan.md「重複 email 409」決定）。
EMAIL_ALREADY_REGISTERED_MESSAGE = "Email already registered"

router = APIRouter(prefix=ROUTER_PREFIX, tags=["auth"])


@router.post(
    SIGNUP_PATH,
    response_model=UserResponse,
    response_model_by_alias=True,
    status_code=status.HTTP_201_CREATED,
)
def signup(payload: SignupRequest, db: Session = Depends(get_db)) -> User:
    # 先行 SELECT で重複を検出する。IntegrityError を 500 から 409 に
    # 救済するより、状態競合を意味的に正しい 409 として表現する方が
    # 利用者・運用ともに分かりやすい。
    if get_user_by_email(db, payload.email) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=EMAIL_ALREADY_REGISTERED_MESSAGE,
        )
    hashed = hash_password(payload.password)
    return create_user(db, email=payload.email, hashed_password=hashed)


@router.post(
    LOGIN_PATH,
    response_model=TokenResponse,
    response_model_by_alias=True,
)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    user = get_user_by_email(db, payload.email)
    # Why 401 を共通メッセージで返す:
    #   ユーザー存在有無の漏洩を避けるため、未登録 email とパスワード違いを
    #   区別しない（plan.md「内部詳細を露出しない」）。
    if user is None or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=INVALID_CREDENTIALS_MESSAGE,
        )
    access_token = create_access_token(user.id)
    return TokenResponse(access_token=access_token)


@router.get(
    ME_PATH,
    response_model=UserResponse,
    response_model_by_alias=True,
)
def me(current_user: User = Depends(get_current_user)) -> User:
    return current_user
