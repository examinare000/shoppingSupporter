"""UserProfile エンドポイント。

`GET /api/me/profile` と `PUT /api/me/profile` の HTTP 境界を担当する。
データ取得・永続化は `api/repositories/user_profiles.py`、認証は
`api/common/security.get_current_user` に委譲し、本モジュールは入力
バリデーションと HTTP レスポンス整形のみを行う。

バリデーション順序（docs/design/user-profile.md §3.2）:
    (1) Pydantic（型・Enum・extra=forbid）→ (2) 認証 401 →
    (3) リポジトリ層でカード存在確認 422
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from ..common.database import get_db
from ..common.models import RakutenRank, User, UserProfile
from ..common.security import get_current_user
from ..repositories.user_profiles import (
    card_exists,
    get_profile_by_user_id,
    upsert_profile,
)
from ..schemas import UserProfileResponse, UserProfileUpdate

ROUTER_PREFIX = "/api/me/profile"

# Why 422 メッセージを定数化:
#   docs/design/user-profile.md §3.2「FastAPI 既定 `{"detail": [...]}` 形式」と
#   plan.md「アンチパターン: FK IntegrityError 経由で 500」を満たすため、
#   存在確認 422 のメッセージを 1 箇所に集約する。
DEFAULT_CARD_NOT_FOUND_MESSAGE = "default_card_id does not reference an existing card"

router = APIRouter(prefix=ROUTER_PREFIX, tags=["profile"])


def _default_response() -> UserProfileResponse:
    """未保存ユーザー向けに返すデフォルト UserProfileResponse を構築する。

    Why ここに集約:
        docs/design/user-profile.md §3.1「未保存時は 200 + デフォルト値」を
        意味する Pydantic インスタンスは GET ハンドラの 1 箇所でしか使わない
        が、テスト対象のキー（`updatedAt: null` を含む）が文書化された
        「契約デフォルト」なので、ヘルパに切り出して値を可視化する。
    """
    return UserProfileResponse(
        rakuten_rank=RakutenRank.REGULAR,
        is_amazon_prime=False,
        yahoo_premium=False,
        # docs/plans/user-profile-enhancement.md §2.1 の追加フラグも未保存時は
        # false（DB のカラム default と一致させ、初回 PUT 前後で破壊的変化が
        # 起きないことを保証する）。
        is_rakuten_mobile=False,
        is_paypay_linked=False,
        default_card_id=None,
        default_card=None,
        # `updatedAt: null` で「保存済み（datetime 値）」と区別する。
        updated_at=None,
    )


@router.get(
    "",
    response_model=UserProfileResponse,
    response_model_by_alias=True,
    responses={status.HTTP_401_UNAUTHORIZED: {"description": "Missing or invalid JWT"}},
)
def get_profile(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UserProfileResponse | UserProfile:
    """認証ユーザー自身のプロファイルを返す。

    未保存時は 200 + デフォルト値 + `updatedAt: null` を返し、DB へのレコード
    作成は行わない（docs/design/user-profile.md §3.1）。
    """
    profile = get_profile_by_user_id(db, current_user.id)
    if profile is None:
        return _default_response()
    return profile


@router.put(
    "",
    response_model=UserProfileResponse,
    response_model_by_alias=True,
    responses={
        status.HTTP_401_UNAUTHORIZED: {"description": "Missing or invalid JWT"},
        status.HTTP_422_UNPROCESSABLE_ENTITY: {"description": DEFAULT_CARD_NOT_FOUND_MESSAGE},
    },
)
def update_profile(
    # Why `payload` を受けるが `Depends(get_current_user)` を使わない:
    #   FastAPI は `Depends(...)` を request-body 検証より先に解決する。
    #   そのため `Depends(get_current_user)` を置くと、不正な body + 未認証
    #   の組み合わせが 401（先に raise）になり、user-profile.md §3.2 の
    #   バリデーション順序（(1) Pydantic → (2) 401 → (3) 422）が崩れる。
    #   `Header` は通常パラメータ扱いで body と並列に解決されるため、
    #   ここで `authorization` を生で受け、body 検証通過後に
    #   `get_current_user` を直接呼ぶことで順序を固定する。
    payload: UserProfileUpdate,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> UserProfile:
    """全フィールド必須の PUT で UserProfile を全置換する（初回 INSERT を含む）。

    `default_card_id` が指定されカードが存在しない場合は 422（FK
    IntegrityError 経由ではなく事前 SELECT でドメインエラーに翻訳）。
    """
    # body 検証通過後に認証を評価する（401）。`get_current_user` は通常の
    # Python 関数として呼べる（FastAPI の Depends 経由でなくても同じロジック
    # が走る）。auth 解決責務は `api/common/security.py` の 1 箇所に集約する
    # 方針を維持する。
    current_user: User = get_current_user(authorization=authorization, db=db)

    if payload.default_card_id is not None and not card_exists(
        db, payload.default_card_id
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=DEFAULT_CARD_NOT_FOUND_MESSAGE,
        )
    return upsert_profile(
        db,
        user_id=current_user.id,
        rakuten_rank=payload.rakuten_rank,
        is_amazon_prime=payload.is_amazon_prime,
        yahoo_premium=payload.yahoo_premium,
        is_rakuten_mobile=payload.is_rakuten_mobile,
        is_paypay_linked=payload.is_paypay_linked,
        default_card_id=payload.default_card_id,
    )
