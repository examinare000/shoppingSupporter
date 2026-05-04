"""Pydantic schemas for API responses.

`ProductSummary` and `ProductSearchEnvelope` belong to the search endpoint.
`CardResponse` belongs to the cards endpoint. The wire format is camelCase
to match the public HTTP contract; pydantic aliases let the ORM-side stay
snake_case while the JSON response uses camelCase without a manual mapping
layer.
"""

from __future__ import annotations

import uuid
from typing import Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


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
