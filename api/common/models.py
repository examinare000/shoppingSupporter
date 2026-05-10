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
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, TSVECTOR, UUID
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


class CampaignKind(enum.Enum):
    RECURRING = "recurring"
    ONESHOT = "oneshot"


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

    # Why ondelete="CASCADE": user-profile.md §2.1「カスケード」。`User` 削除時
    # に `user_profiles` を残すと参照孤児になる。bulk delete (ORM の cascade を
    # 経由しない) でも DB レベルで連動させるため FK 側に持たせる。
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    default_card_id: Mapped[Optional[int]] = mapped_column(ForeignKey("cards.id"))
    rakuten_rank: Mapped[RakutenRank] = mapped_column(Enum(RakutenRank), default=RakutenRank.REGULAR)
    
    # Why is_rakuten_mobile / is_paypay_linked: docs/plans/user-profile-enhancement.md
    # §2.1 で追加した SPU / Yahoo! ショッピング指定支払特典の判定フラグ。T-06
    # ポイント算出ロジックが直接参照するため、ドメイン上の必須項目として
    # NOT NULL で持つ（既存ユーザーは 0004 マイグレーションで false に backfill）。
    is_amazon_prime: Mapped[bool] = mapped_column(Boolean, default=False)
    is_rakuten_mobile: Mapped[bool] = mapped_column(Boolean, default=False)
    yahoo_premium: Mapped[bool] = mapped_column(Boolean, default=False)
    is_paypay_linked: Mapped[bool] = mapped_column(Boolean, default=False)

    # Why onupdate: user-profile.md §2.1「`onupdate=datetime.utcnow` で自動更新」。
    # Phase 2 で `If-Unmodified-Since` 楽観ロックの種にする伏線（同 §3.2）。
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    user: Mapped["User"] = relationship(back_populates="profile")
    # Why eager load 戦略はリポジトリで指定: relationship 既定は lazy。
    # N+1 回避は `get_profile_by_user_id` の `joinedload` 1 箇所に閉じる
    # （リレーション宣言で `lazy="joined"` を使うと、別の参照経路でも常に
    # JOIN されてしまい意図しないコストが出る）。
    default_card: Mapped[Optional["Card"]] = relationship()


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
    # Maintained by a Postgres BEFORE INSERT/UPDATE trigger; see
    # alembic/versions/0002_product_search_columns.py.
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


class SaleCampaign(Base):
    """セールキャンペーン定義。bonus/cap/conditions は JSONB として格納する。

    Why JSONB: キャンペーン条件はスキーマが多様で拡張頻度が高い。JSONB にすることで
    スキーマ変更なしに新しい条件タイプを追加できる（phase3-analytics-suggestion.md §3.1）。
    """
    __tablename__ = "sale_campaigns"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    site: Mapped[SiteType] = mapped_column(Enum(SiteType, create_constraint=False, name="sitetype"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    kind: Mapped[CampaignKind] = mapped_column(Enum(CampaignKind, create_constraint=False, name="campaignkind"), nullable=False)
    recurrence_rule: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    start_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    end_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    bonus: Mapped[dict] = mapped_column(JSONB, nullable=False)
    cap: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    conditions: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)


class MonthlyUsage(Base):
    """月次利用実績。複合 PK (user_id, site, recorded_month) で 1 ユーザー × 1 サイト × 1 月を表す。

    Why 複合 PK: 月はリセット単位であり、同月内は UPSERT で上書きする。
    新月は自然に新レコードとして挿入される（phase3-analytics-suggestion.md §3.2）。
    """
    __tablename__ = "monthly_usage"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    site: Mapped[SiteType] = mapped_column(
        Enum(SiteType, create_constraint=False, name="sitetype"),
        primary_key=True,
    )
    # Why String: YYYY-MM 形式の固定フォーマット文字列。Date 型より比較が単純で
    # フロントエンドへの wire format (文字列) と同形のため一貫性が高い。
    recorded_month: Mapped[str] = mapped_column(String(7), primary_key=True)
    amount_spent: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    points_earned: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    shop_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
