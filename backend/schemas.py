"""Pydantic schemas for API responses.

`ProductSummary` and `ProductSearchEnvelope` belong to the search endpoint.
The envelope's keys are camelCase to match the public HTTP contract; pydantic
aliases let the ORM-side stay snake_case while the JSON response uses
camelCase without a manual mapping layer.
"""

from __future__ import annotations

import uuid
from typing import List, Optional

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
