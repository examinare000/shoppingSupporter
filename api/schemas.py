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


class BreakdownEntry(BaseModel):
    """PricingEngine の内訳 1 件。camelCase 変換不要（すべて lowercase）。

    Why RewardEntry をそのまま使わないか:
        engine.py の RewardEntry は dataclass であり ORM に非依存の純粋関数層。
        HTTP レスポンス向けシリアライズの責務はスキーマ層に持たせるため、
        Pydantic BaseModel として別定義する。
    """
    label: str
    rate: float
    points: int
    note: str


class ListingOut(BaseModel):
    """検索結果 1 件に含まれる EC サイトリスト情報。

    Why from_attributes=False（デフォルト）:
        router 側で EcSiteProduct ORM から明示的に構築するため、
        ORM 属性マッピングは不要。
    """
    site_type: str = Field(serialization_alias="siteType")
    site_product_id: str = Field(serialization_alias="siteProductId")
    url: str
    # 未認証・プロフィール未設定の場合は null を返す（T-08 仕様）
    points: Optional[int]
    effective_price: Optional[int] = Field(serialization_alias="effectivePrice")
    breakdown: Optional[List[BreakdownEntry]]


class PersonalizationMeta(BaseModel):
    """パーソナライズ適用状態のメタ情報。"""
    applied: bool
    # 未認証時は null
    rakuten_rank: Optional[str] = Field(serialization_alias="rakutenRank")
    has_card: bool = Field(serialization_alias="hasCard")


class SearchMeta(BaseModel):
    """検索レスポンスのメタフィールド。認証有無に関わらず常に返す。"""
    personalization: PersonalizationMeta


class ProductSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    description: Optional[str]
    image_url: Optional[str] = Field(serialization_alias="imageUrl")
    tags: List[str]
    in_stock: bool = Field(serialization_alias="inStock")
    current_price: Optional[int] = Field(serialization_alias="currentPrice")
    listings: List[ListingOut] = Field(default_factory=list)


class ProductSearchEnvelope(BaseModel):
    items: List[ProductSummary]
    page: int
    total_pages: int = Field(serialization_alias="totalPages")
    total_count: int = Field(serialization_alias="totalCount")
    # meta は認証有無に関わらず常にレスポンスに含まれる（T-08 テスト契約）
    meta: SearchMeta


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
    # `from_attributes=True` lets the cards router return SQLAlchemy `Card` rows directly.
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    base_reward_rate: float = Field(serialization_alias="baseRewardRate")
    annual_fee: int = Field(serialization_alias="annualFee")
    # Keys are `SiteType` values (e.g. "rakuten", "amazon", "yahoo"); see
    # `docs/api/cards.md` for the structural contract that downstream
    # pricing logic depends on.
    special_rewards: Dict[str, float] = Field(serialization_alias="specialRewards")


class UserProfileBase(BaseModel):
    """UserProfile の共通フィールド定義。

    Why Base クラス:
        Update (PUT) と Response (GET) で同じフィールド名・エイリアス定義を
        共有し、エイリアスの付け忘れや型の不一致を構造的に防ぐ。
        ADR-013 §4 の「個別指定」を維持しつつ、冗長性を排除する。

    Why populate_by_name:
        validation_alias を指定すると Pydantic 既定ではフィールド名での
        コンストラクトが不可になる。`api/routers/profile.py` の
        `_default_response()` 等で snake_case 属性名を用いて Pydantic
        インスタンスを生成可能にするため、このフラグを有効にする。
    """
    model_config = ConfigDict(populate_by_name=True)

    rakuten_rank: RakutenRank = Field(
        validation_alias="rakutenRank", serialization_alias="rakutenRank"
    )
    is_amazon_prime: bool = Field(
        validation_alias="isAmazonPrime",
        serialization_alias="isAmazonPrime",
        strict=True,
    )
    yahoo_premium: bool = Field(
        validation_alias="yahooPremium", serialization_alias="yahooPremium", strict=True
    )
    # Why is_rakuten_mobile / is_paypay_linked: docs/plans/user-profile-enhancement.md
    # §2.1 の追加フラグ。`is_amazon_prime` と同じ strict=True パターンで
    # ゆるい bool 強制（"yes"/"true"/1）を 422 で弾く。
    is_rakuten_mobile: bool = Field(
        validation_alias="isRakutenMobile",
        serialization_alias="isRakutenMobile",
        strict=True,
    )
    is_paypay_linked: bool = Field(
        validation_alias="isPayPayLinked",
        serialization_alias="isPayPayLinked",
        strict=True,
    )
    # Optional[int] にデフォルトは付けない（PUT 全置換セマンティクス: 省略は
    # 422、明示 null は 200 受理）。docs/design/user-profile.md §3.2。
    default_card_id: Optional[int] = Field(
        validation_alias="defaultCardId", serialization_alias="defaultCardId"
    )


class UserProfileUpdate(UserProfileBase):
    # Why extra="forbid": response envelope（`accessToken` 等）や GET レスポンスの
    # 形（`updatedAt` / `defaultCard` を含む）を body にそのまま流用された場合に
    # 422 で弾く。ADR-013 §2 / docs/design/user-profile.md §3.3 の必須要件。
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class UserProfileResponse(UserProfileBase):
    # ORM の UserProfile 行（`default_card` を joinedload 済み）をそのまま
    # 返却できるようにする。GET 未保存時はハンドラ側で UserProfileResponse の
    # インスタンスを直接構築するため、from_attributes と通常コンストラクトの
    # 両方を経路として使う。
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    # nested CardResponse: 検索パーソナライズ統合 (T-08) と方針を揃え、
    # joinedload で取得した Card を nested 返却する（フロント設定画面が ID
    # から名前を引くための追加リクエストを不要にする）。
    default_card: Optional[CardResponse] = Field(serialization_alias="defaultCard")
    # 未保存ユーザー（DB にレコードがない）の場合は `None` を返す。
    # docs/design/user-profile.md §3.1「保存済み / 未保存の区別」。
    updated_at: Optional[datetime] = Field(serialization_alias="updatedAt")
