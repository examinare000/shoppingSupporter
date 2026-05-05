"""Pydantic schemas for API responses.

`ProductSummary` and `ProductSearchEnvelope` belong to the search endpoint.
The envelope's keys are camelCase to match the public HTTP contract; pydantic
aliases let the ORM-side stay snake_case while the JSON response uses
camelCase without a manual mapping layer.

Auth schemas (`SignupRequest` / `LoginRequest` / `TokenResponse` /
`UserResponse`) follow the same camelCase serialization convention so the
public HTTP contract stays consistent across endpoints.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field


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
