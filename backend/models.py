import enum
import uuid
from datetime import datetime
from typing import List, Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import ARRAY, TSVECTOR, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class RakutenRank(enum.Enum):
    REGULAR = "regular"
    SILVER = "silver"
    GOLD = "gold"
    PLATINUM = "platinum"
    DIAMOND = "diamond"


class SiteType(enum.Enum):
    AMAZON = "amazon"
    RAKUTEN = "rakuten"
    YAHOO = "yahoo"


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    profile: Mapped["UserProfile"] = relationship(back_populates="user", uselist=False)


class Card(Base):
    __tablename__ = "cards"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    base_reward_rate: Mapped[float] = mapped_column(Float, default=1.0)
    annual_fee: Mapped[int] = mapped_column(Integer, default=0)
    special_rewards: Mapped[dict] = mapped_column(JSON, default=dict)


class UserProfile(Base):
    __tablename__ = "user_profiles"

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), primary_key=True)
    default_card_id: Mapped[Optional[int]] = mapped_column(ForeignKey("cards.id"))
    rakuten_rank: Mapped[RakutenRank] = mapped_column(Enum(RakutenRank), default=RakutenRank.REGULAR)
    is_amazon_prime: Mapped[bool] = mapped_column(Boolean, default=False)
    yahoo_premium: Mapped[bool] = mapped_column(Boolean, default=False)

    user: Mapped["User"] = relationship(back_populates="profile")


class Product(Base):
    __tablename__ = "products"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    jan_code: Mapped[Optional[str]] = mapped_column(String(20), unique=True, index=True)
    image_url: Mapped[Optional[str]] = mapped_column(String(1024))
    tags: Mapped[List[str]] = mapped_column(ARRAY(String), nullable=False, default=list)
    in_stock: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    current_price: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    # Maintained by a Postgres BEFORE INSERT/UPDATE trigger (see migration
    # 0002). A GENERATED column would be cleaner, but `to_tsvector(regconfig,
    # text)` is STABLE not IMMUTABLE so it cannot be used in a generated
    # column expression.
    search_vector: Mapped[Optional[str]] = mapped_column(TSVECTOR, nullable=True)

    site_products: Mapped[List["EcSiteProduct"]] = relationship(back_populates="product")


class EcSiteProduct(Base):
    __tablename__ = "ec_site_products"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    product_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("products.id"), nullable=False)
    site_type: Mapped[SiteType] = mapped_column(Enum(SiteType), nullable=False)
    site_product_id: Mapped[str] = mapped_column(String(100), nullable=False)  # ASIN, ItemCode etc.
    url: Mapped[str] = mapped_column(String(1024), nullable=False)
    last_updated: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    product: Mapped["Product"] = relationship(back_populates="site_products")
    price_histories: Mapped[List["PriceHistory"]] = relationship(back_populates="ec_site_product")


class PriceHistory(Base):
    __tablename__ = "price_histories"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    ec_site_product_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("ec_site_products.id"), nullable=False)
    price: Mapped[int] = mapped_column(Integer, nullable=False)
    points: Mapped[int] = mapped_column(Integer, default=0)
    recorded_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    ec_site_product: Mapped["EcSiteProduct"] = relationship(back_populates="price_histories")
