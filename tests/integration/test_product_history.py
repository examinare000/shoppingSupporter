"""Tests for GET /api/products/{id}/history.

Exercises the repository's downsampling logic and the router's grouping behavior.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta

import pytest

from api.common.models import PriceHistory
from api.repositories.products import get_product_history


def _seed(session, objects):
    for obj in objects:
        session.add(obj)
    session.commit()


class TestRepositoryProductHistory:
    def test_should_return_history_with_downsampling(self, db_session, make_product, make_site_product):
        # Given: a product with multiple history records per day
        product = make_product(name="apple", jan_code="1234567890123")
        _seed(db_session, [product])
        
        sp = make_site_product(product, "amazon", site_product_id="ASIN1")
        db_session.add(sp)
        db_session.commit()
        
        now = datetime.utcnow()
        # Today: 2 records. Latest (h2) should be picked by the DISTINCT ON logic.
        h1 = PriceHistory(ec_site_product_id=sp.id, price=1000, points=10, recorded_at=now - timedelta(hours=2))
        h2 = PriceHistory(ec_site_product_id=sp.id, price=950, points=9, recorded_at=now - timedelta(hours=1))
        
        # Yesterday: 1 record
        h3 = PriceHistory(ec_site_product_id=sp.id, price=1100, points=11, recorded_at=now - timedelta(days=1))
        
        _seed(db_session, [h1, h2, h3])
        
        # When: getting history via repository
        result = get_product_history(db_session, product.jan_code, days=7)
        assert result is not None
        pid, histories = result
        
        # Then: product_id matches, and only 2 records are returned (one per day per site)
        assert pid == product.id
        assert len(histories) == 2
        
        # Prices should be the representative one for each day.
        # h2 (950) is the latest for today, h3 (1100) is the only one for yesterday.
        prices = {h.price for h in histories}
        assert prices == {950, 1100}

    def test_should_match_by_uuid_string(self, db_session, make_product):
        # Given: a product
        product = make_product(name="apple")
        _seed(db_session, [product])
        
        # When: searching by its UUID as a string
        result = get_product_history(db_session, str(product.id))
        
        # Then: it is found
        assert result is not None
        assert result[0] == product.id

    def test_should_return_none_for_nonexistent_product(self, db_session):
        assert get_product_history(db_session, "nonexistent-jan") is None
        assert get_product_history(db_session, str(uuid.uuid4())) is None


class TestEndpointProductHistory:
    def test_should_return_404_for_nonexistent_product(self, client):
        response = client.get(f"/api/products/{uuid.uuid4()}/history")
        assert response.status_code == 404

    def test_should_return_grouped_history_envelope(self, client, db_session, make_product, make_site_product):
        # Given: history across multiple sites on the same day
        product = make_product(name="apple")
        _seed(db_session, [product])
        
        amazon_sp = make_site_product(product, "amazon", site_product_id="ASIN1")
        rakuten_sp = make_site_product(product, "rakuten", site_product_id="RAKU1")
        _seed(db_session, [amazon_sp, rakuten_sp])
        
        # Use a fixed date to avoid timezone/boundary issues in assertions
        base_time = datetime(2026, 5, 1, 12, 0, 0)
        h_amz = PriceHistory(ec_site_product_id=amazon_sp.id, price=1000, recorded_at=base_time)
        h_rak = PriceHistory(ec_site_product_id=rakuten_sp.id, price=1100, recorded_at=base_time)
        
        _seed(db_session, [h_amz, h_rak])
        
        # When: hitting the endpoint
        response = client.get(f"/api/products/{product.id}/history")
        
        # Then: 200 and correctly grouped body with camelCase keys
        assert response.status_code == 200
        body = response.json()
        assert body["productId"] == str(product.id)
        assert len(body["histories"]) == 1
        
        today_history = body["histories"][0]
        assert today_history["date"] == "2026-05-01"
        assert today_history["sites"]["amazon"]["price"] == 1000
        assert today_history["sites"]["rakuten"]["price"] == 1100

    def test_should_respect_days_parameter(self, client, db_session, make_product, make_site_product):
        # Given: history from 10 days ago and today
        product = make_product(name="apple")
        _seed(db_session, [product])
        sp = make_site_product(product, "amazon")
        _seed(db_session, [sp])
        
        now = datetime.utcnow()
        old_h = PriceHistory(ec_site_product_id=sp.id, price=500, recorded_at=now - timedelta(days=10))
        new_h = PriceHistory(ec_site_product_id=sp.id, price=1000, recorded_at=now)
        _seed(db_session, [old_h, new_h])
        
        # When: requesting only the last 5 days
        response = client.get(f"/api/products/{product.id}/history", params={"days": 5})
        
        # Then: only today's record is returned
        body = response.json()
        assert len(body["histories"]) == 1
        assert body["histories"][0]["sites"]["amazon"]["price"] == 1000

    def test_should_return_422_for_invalid_days(self, client):
        # ge=1, le=365 constraints
        assert client.get("/api/products/some-id/history", params={"days": 0}).status_code == 422
        assert client.get("/api/products/some-id/history", params={"days": 400}).status_code == 422


class TestPriceHistoryMigrationIndex:
    """Migration 0005 が price_histories に複合インデックスを作成することを検証する。

    Why: 設計書 F-16「インデックス最適化 (ec_site_product_id, recorded_at)」の
    充足確認。Alembic マイグレーションは conftest の postgres_url fixture が
    upgrade head で適用済みのため、ここでは存在確認のみ行う。
    """

    def test_should_have_composite_index_on_price_histories(self, test_engine):
        # Given: Alembic migrations have been applied (postgres_url fixture runs upgrade head)
        from sqlalchemy import inspect as sa_inspect

        inspector = sa_inspect(test_engine)

        # When: inspecting indexes on price_histories
        indexes = inspector.get_indexes("price_histories")
        index_names = {idx["name"] for idx in indexes}

        # Then: the composite index defined in migration 0005 must exist
        assert "ix_price_histories_ec_site_product_id_recorded_at" in index_names

    def test_composite_index_covers_ec_site_product_id_and_recorded_at(self, test_engine):
        # Given: Alembic migrations have been applied
        from sqlalchemy import inspect as sa_inspect

        inspector = sa_inspect(test_engine)
        indexes = inspector.get_indexes("price_histories")

        # When: finding the target index
        target = next(
            (
                idx
                for idx in indexes
                if idx["name"] == "ix_price_histories_ec_site_product_id_recorded_at"
            ),
            None,
        )

        # Then: the index covers exactly (ec_site_product_id, recorded_at) in that order
        assert target is not None, "Index ix_price_histories_ec_site_product_id_recorded_at not found"
        assert target["column_names"] == ["ec_site_product_id", "recorded_at"]


class TestOpenApiSiteHistorySchema:
    """OpenAPI スキーマが SiteHistory を公開し、PricePoint を含まないことを検証する。

    Why: 設計書 T-10 は `SiteHistory` を正式なスキーマ名として定義している。
    PricePoint はリネーム前の旧名であり、実装後に消えていることを保証する。
    """

    def test_should_expose_site_history_component(self, client):
        # Given: the application is running
        # When: fetching the OpenAPI schema
        response = client.get("/openapi.json")
        assert response.status_code == 200
        components = response.json().get("components", {}).get("schemas", {})

        # Then: SiteHistory is defined in components/schemas (T-10)
        assert "SiteHistory" in components, (
            "SiteHistory must be defined in OpenAPI components/schemas per T-10"
        )

    def test_should_not_expose_price_point_component(self, client):
        # PricePoint is the pre-rename name and must not appear after migration
        response = client.get("/openapi.json")
        components = response.json().get("components", {}).get("schemas", {})

        assert "PricePoint" not in components, (
            "PricePoint must be renamed to SiteHistory (乖離 #2)"
        )

    def test_site_history_should_have_price_and_points_fields(self, client):
        # Given / When
        response = client.get("/openapi.json")
        components = response.json().get("components", {}).get("schemas", {})
        site_history = components.get("SiteHistory", {})

        # Then: the schema has both required fields
        properties = site_history.get("properties", {})
        assert "price" in properties
        assert "points" in properties

    def test_price_history_entry_sites_should_reference_site_history(self, client):
        # PriceHistoryEntry.sites.additionalProperties must point to SiteHistory
        response = client.get("/openapi.json")
        components = response.json().get("components", {}).get("schemas", {})
        price_history_entry = components.get("PriceHistoryEntry", {})
        sites_schema = price_history_entry.get("properties", {}).get("sites", {})

        # additionalProperties holds the per-site value schema
        additional_props = sites_schema.get("additionalProperties", {})
        ref = additional_props.get("$ref", "")
        assert "SiteHistory" in ref, (
            f"PriceHistoryEntry.sites.additionalProperties should reference SiteHistory, got: {ref!r}"
        )
