"""Pydantic schemas for API responses.

`ProductSummary` and `ProductSearchEnvelope` belong to the search endpoint.
The envelope's keys are camelCase to match the public HTTP contract; pydantic
aliases let the ORM-side stay snake_case while the JSON response uses
camelCase without a manual mapping layer.

Auth schemas (`SignupRequest` / `LoginRequest` / `TokenResponse` /
`UserResponse`) follow the same camelCase serialization convention so the
public HTTP contract stays consistent across endpoints.

`CardResponse` belongs to the cards endpoint and applies the same camelCase
alias convention.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Dict, List, Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from .common.models import RakutenRank


class ProductSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    description: Optional[str]
    image_url: Optional[str] = Field(serialization_alias="imageUrl")
    tags: List[str]
    in_stock: bool = Field(serialization_alias="inStock")
    current_price: Optional[int] = Field(serialization_alias="currentPrice")


class ProductSearchEnvelope(BaseModel):
    # Items are typed as `ProductSummary`; FastAPI converts each ORM row via
    # `from_attributes=True` when the handler returns SQLAlchemy instances.
    items: List[ProductSummary]
    page: int
    total_pages: int = Field(serialization_alias="totalPages")
    total_count: int = Field(serialization_alias="totalCount")


# パスワードの最小長は agent-rules/12-security-guidelines.md「最小 8 文字以上」
# に従う。スキーマ側で 422 を返すことで router にバリデーションロジックが
# 漏れないようにする。
PASSWORD_MIN_LENGTH = 8


class SignupRequest(BaseModel):
    # Why extra="forbid": response envelope の形（accessToken/tokenType 等）を
    # body に流用された場合に 422 で弾く。tests/integration/test_auth.py の
    # `TestRequestBodyContract` で要求される契約。
    model_config = ConfigDict(extra="forbid")

    email: EmailStr
    password: str = Field(min_length=PASSWORD_MIN_LENGTH)


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr
    password: str = Field(min_length=PASSWORD_MIN_LENGTH)


class TokenResponse(BaseModel):
    access_token: str = Field(serialization_alias="accessToken")
    # OAuth2 慣習に合わせ "bearer" を返す。Authorization ヘッダの
    # "Bearer " スキームと一致させる責務はクライアント側にある。
    token_type: str = Field(default="bearer", serialization_alias="tokenType")


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: EmailStr
    created_at: datetime = Field(serialization_alias="createdAt")


class CardResponse(BaseModel):
    # `from_attributes=True` lets the cards router return SQLAlchemy `Card`
    # rows directly; FastAPI serializes them through this schema with the
    # camelCase aliases below.
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    base_reward_rate: float = Field(serialization_alias="baseRewardRate")
    annual_fee: int = Field(serialization_alias="annualFee")
    # Keys are `SiteType` values (e.g. "rakuten", "amazon", "yahoo"); see
    # `docs/api/cards.md` for the structural contract that downstream
    # pricing logic depends on.
    special_rewards: Dict[str, float] = Field(serialization_alias="specialRewards")


class UserProfileUpdate(BaseModel):
    # Why extra="forbid": response envelope（`accessToken` 等）や GET レスポンスの
    # 形（`updatedAt` / `defaultCard` を含む）を body にそのまま流用された場合に
    # 422 で弾く。ADR-013 §2 / docs/design/user-profile.md §3.3 の必須要件。
    model_config = ConfigDict(extra="forbid")

    # Why validation_alias: 入力 JSON は camelCase（HTTP 契約）、Python 属性は
    # snake_case（リポジトリと統一）。ADR-013 §4「個別指定」に従い、フィールド
    # 単位で入力エイリアスを宣言する（`alias_generator` の一括変換は禁止）。
    rakuten_rank: RakutenRank = Field(validation_alias="rakutenRank")
    # Why strict=True for bool: Pydantic v2 既定のゆるい bool 強制（"yes" /
    # "true" / 1 等を bool に変換）を無効化する。ADR-013 §2 の `extra="forbid"`
    # と同じ趣旨で、HTTP 契約上 boolean のみを受理することを Pydantic レベル
    # で固定する（user-profile.md §3.3 / 422 で弾く）。
    is_amazon_prime: bool = Field(validation_alias="isAmazonPrime", strict=True)
    yahoo_premium: bool = Field(validation_alias="yahooPremium", strict=True)
    # Optional[int] にデフォルトは付けない（PUT 全置換セマンティクス: 省略は
    # 422、明示 null は 200 受理）。docs/design/user-profile.md §3.2。
    default_card_id: Optional[int] = Field(validation_alias="defaultCardId")


class UserProfileResponse(BaseModel):
    # ORM の UserProfile 行（`default_card` を joinedload 済み）をそのまま
    # 返却できるようにする。GET 未保存時はハンドラ側で UserProfileResponse の
    # インスタンスを直接構築するため、from_attributes と通常コンストラクトの
    # 両方を経路として使う。
    model_config = ConfigDict(from_attributes=True)

    rakuten_rank: RakutenRank = Field(serialization_alias="rakutenRank")
    is_amazon_prime: bool = Field(serialization_alias="isAmazonPrime")
    yahoo_premium: bool = Field(serialization_alias="yahooPremium")
    default_card_id: Optional[int] = Field(serialization_alias="defaultCardId")
    # nested CardResponse: 検索パーソナライズ統合 (T-08) と方針を揃え、
    # joinedload で取得した Card を nested 返却する（フロント設定画面が ID
    # から名前を引くための追加リクエストを不要にする）。
    default_card: Optional[CardResponse] = Field(serialization_alias="defaultCard")
    # 未保存ユーザー（DB にレコードがない）の場合は `None` を返す。
    # docs/design/user-profile.md §3.1「保存済み / 未保存の区別」。
    updated_at: Optional[datetime] = Field(serialization_alias="updatedAt")
