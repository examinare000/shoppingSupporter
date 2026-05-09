"""Unit tests for price history schema classes (T-10).

検証対象:
- SiteHistory: PricePoint からリネームされた特定サイト・時点の価格情報スキーマ
- PriceHistoryEntry: 特定日の全サイト価格推移スキーマ
- ProductHistoryResponse: 価格履歴 API のトップレベルレスポンス

Why unit tests here (DB 不要):
    スキーマクラスは Pydantic モデルであり、バリデーション・シリアライズは
    インメモリで完結する。DB なしで仕様を高速に検証できるため、単体テストに切り出す。
    API 契約（OpenAPI スキーマ名）の確認は tests/integration/test_product_history.py
    の TestOpenApiSiteHistorySchema が担う。

Why この段階では ImportError が想定内か:
    write_tests ステップは実装前の Red フェーズ。SiteHistory は implement ステップで
    PricePoint → SiteHistory リネームが適用されるまで import 失敗する。
    テストとして正しい契約を先行定義することが目的。
"""
from __future__ import annotations

import uuid

# Why: implement ステップで api/schemas.py の PricePoint が SiteHistory に
# リネームされるまで、この import は ImportError になる（想定内の Red）。
from api.schemas import PriceHistoryEntry, ProductHistoryResponse, SiteHistory


class TestSiteHistorySchema:
    """SiteHistory が price / points フィールドを正しく保持することを検証する。"""

    def test_should_store_price_and_points(self):
        # Given / When
        entry = SiteHistory(price=1000, points=10)

        # Then
        assert entry.price == 1000
        assert entry.points == 10

    def test_should_accept_zero_points(self):
        # ポイント還元がないサイトは points=0 が正常値
        entry = SiteHistory(price=500, points=0)

        assert entry.price == 500
        assert entry.points == 0

    def test_price_must_be_integer(self):
        # Pydantic は str を int に強制変換するが、非数値は ValidationError
        import pytest
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            SiteHistory(price="not-a-number", points=0)


class TestPriceHistoryEntrySchema:
    """PriceHistoryEntry が日付と複数サイトの SiteHistory を保持することを検証する。"""

    def test_should_hold_date_and_sites(self):
        # Given / When
        entry = PriceHistoryEntry(
            date="2026-05-01",
            sites={"amazon": SiteHistory(price=1000, points=10)},
        )

        # Then
        assert entry.date == "2026-05-01"
        assert entry.sites["amazon"].price == 1000
        assert entry.sites["amazon"].points == 10

    def test_should_hold_multiple_sites(self):
        # Given / When
        entry = PriceHistoryEntry(
            date="2026-05-01",
            sites={
                "amazon": SiteHistory(price=1000, points=10),
                "rakuten": SiteHistory(price=1100, points=0),
                "yahoo": SiteHistory(price=990, points=5),
            },
        )

        # Then: すべてのサイトが保持されている
        assert len(entry.sites) == 3
        assert entry.sites["rakuten"].price == 1100
        assert entry.sites["yahoo"].price == 990

    def test_should_accept_empty_sites(self):
        # 履歴はあるが該当日のレコードがない場合は空辞書が渡り得る
        entry = PriceHistoryEntry(date="2026-05-01", sites={})

        assert entry.date == "2026-05-01"
        assert entry.sites == {}


class TestProductHistoryResponseSchema:
    """ProductHistoryResponse がトップレベルレスポンスとして正しく機能することを検証する。"""

    def test_should_hold_product_id_and_histories(self):
        # Given
        product_id = uuid.uuid4()
        histories = [
            PriceHistoryEntry(
                date="2026-05-01",
                sites={"amazon": SiteHistory(price=1000, points=10)},
            )
        ]

        # When
        response = ProductHistoryResponse(product_id=product_id, histories=histories)

        # Then
        assert response.product_id == product_id
        assert len(response.histories) == 1

    def test_should_serialize_product_id_as_camel_case(self):
        # Why: フロントエンドは camelCase の productId を期待する (T-10)
        product_id = uuid.uuid4()
        response = ProductHistoryResponse(product_id=product_id, histories=[])

        serialized = response.model_dump(by_alias=True)

        assert "productId" in serialized, "product_id must serialize to productId via alias"
        assert serialized["productId"] == product_id
        # snake_case キーが漏れていないことも確認
        assert "product_id" not in serialized

    def test_should_accept_empty_histories(self):
        # 新商品など履歴ゼロ件は正常ケース
        response = ProductHistoryResponse(product_id=uuid.uuid4(), histories=[])

        assert response.histories == []
