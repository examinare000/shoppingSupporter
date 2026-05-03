"""Pydantic schemas for API responses.

`ProductOut` mirrors the existing `Product` ORM columns so consumers receive the
canonical product shape without re-defining fields per endpoint.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class ProductOut(BaseModel):
    # `from_attributes=True` lets FastAPI serialize SQLAlchemy ORM rows directly,
    # avoiding a manual mapping layer between models and responses.
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    # No `= None` defaults: `from_attributes=True` always reads the value from
    # the ORM instance, so the default is unreachable. `Optional[...]` alone
    # already permits NULL columns.
    description: Optional[str]
    jan_code: Optional[str]
    image_url: Optional[str]
    created_at: datetime
