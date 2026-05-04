"""update_prices と AmazonAPI の結合テスト。

Why インテグレーションテストを書くか:
    - AmazonAPI の戻り値契約が破壊的に変わる: Optional[Dict] → Dict（成功） or AmazonAPIError（失敗）
    - update_site_product 側を try/except でラップする方針 (plan 5.2)
    - 「AmazonAPI raise → cron が落ちずに次の商品へ進む」という新しい振る舞いが
      3 モジュール (AmazonAPI / update_prices / DB Session) を横断する
    - したがって、Amazon の例外が cron 実行を止めない安全網が機能することを
      結合レベルで検証する必要がある

Why DB を Mock にする:
    実 DB を立てる統合テストはユーザー明示制約で禁止。Session/PriceHistory
    の振る舞いだけを検証する。
"""

import uuid
from unittest.mock import MagicMock

import pytest

from api.common.models import EcSiteProduct, SiteType
from api.cron import update_prices
from api.lib.amazon import AmazonAPIError


def _make_site_product(asin: str = "B0EXAMPLE01") -> EcSiteProduct:
    """AMAZON タイプの EcSiteProduct を直接生成（DB セッション不使用）"""
    sp = EcSiteProduct(
        id=uuid.uuid4(),
        product_id=uuid.uuid4(),
        site_type=SiteType.AMAZON,
        site_product_id=asin,
        url=f"https://www.amazon.co.jp/dp/{asin}",
    )
    return sp


class TestUpdateSiteProductAmazonSuccess:
    """成功時: PriceHistory が追加され URL が更新される"""

    async def test_success_flow_persists_price_history(self, amazon_env, monkeypatch):
        # Given: AmazonAPI.fetch_product が共通シェイプを返す
        site_product = _make_site_product("B0EXAMPLE01")
        db = MagicMock()

        async def fake_fetch(self, asin):
            return {
                "site": "amazon",
                "id": asin,
                "title": "Title",
                "price": 1980,
                "image_url": "https://img/x.jpg",
                "url": f"https://www.amazon.co.jp/dp/{asin}",
            }

        monkeypatch.setattr(
            "api.lib.amazon.AmazonAPI.fetch_product",
            fake_fetch,
        )
        # When
        await update_prices.update_site_product(db, site_product)
        # Then: PriceHistory が db.add に渡され、commit が呼ばれる
        assert db.add.called
        added = db.add.call_args[0][0]
        assert added.price == 1980
        assert added.points == 0  # PA-API は points を返さない（呼び出し元 default=0）
        assert added.ec_site_product_id == site_product.id
        db.commit.assert_called_once()

    async def test_success_updates_site_product_url(self, amazon_env, monkeypatch):
        # Given
        site_product = _make_site_product("B0EXAMPLE01")
        old_url = site_product.url
        db = MagicMock()

        async def fake_fetch(self, asin):
            return {
                "site": "amazon",
                "id": asin,
                "title": "T",
                "price": 100,
                "image_url": None,
                "url": "https://www.amazon.co.jp/dp/UPDATED",
            }

        monkeypatch.setattr(
            "api.lib.amazon.AmazonAPI.fetch_product",
            fake_fetch,
        )
        # When
        await update_prices.update_site_product(db, site_product)
        # Then
        assert site_product.url == "https://www.amazon.co.jp/dp/UPDATED"
        assert site_product.url != old_url


class TestUpdateSiteProductAmazonErrorContainment:
    """異常時: AmazonAPIError は cron 内で握り、上位に伝播させない"""

    async def test_amazon_api_error_does_not_propagate(self, amazon_env, monkeypatch):
        # Given: fetch_product が AmazonAPIError を送出
        site_product = _make_site_product("B0NOTFOUND0")
        db = MagicMock()

        async def fake_fetch(self, asin):
            raise AmazonAPIError("ASIN not found")

        monkeypatch.setattr(
            "api.lib.amazon.AmazonAPI.fetch_product",
            fake_fetch,
        )
        # When/Then: 例外が呼び出し元 (cron loop) まで伝播しない
        # AmazonAPIError 単体商品の失敗で cron 全体が止まらないことが本テストの趣旨
        await update_prices.update_site_product(db, site_product)
        # Then: PriceHistory 追加されない
        assert not db.add.called
        # commit も呼ばれない（無意味な空 commit を避ける）
        assert not db.commit.called

    async def test_init_credential_error_is_contained(self, monkeypatch):
        # Given: 認証情報が欠落しており AmazonAPI() 構築段階で例外
        monkeypatch.delenv("AMAZON_ACCESS_KEY", raising=False)
        monkeypatch.delenv("AMAZON_SECRET_KEY", raising=False)
        monkeypatch.delenv("AMAZON_PARTNER_TAG", raising=False)
        site_product = _make_site_product("B0EXAMPLE01")
        db = MagicMock()
        # When/Then: 環境変数欠落でも cron 全体は止めない
        await update_prices.update_site_product(db, site_product)
        # Then: DB 書き込みなし
        assert not db.add.called

    async def test_main_loop_continues_when_one_amazon_fails(self, amazon_env, monkeypatch):
        # Given: 2 件の Amazon 商品。1 件目は失敗、2 件目は成功
        sp_fail = _make_site_product("B0FAIL00000")
        sp_ok = _make_site_product("B0OK0000001")

        call_log = []

        async def fake_fetch(self, asin):
            call_log.append(asin)
            if asin == "B0FAIL00000":
                raise AmazonAPIError("transient")
            return {
                "site": "amazon",
                "id": asin,
                "title": "T",
                "price": 500,
                "image_url": None,
                "url": f"https://www.amazon.co.jp/dp/{asin}",
            }

        monkeypatch.setattr(
            "api.lib.amazon.AmazonAPI.fetch_product",
            fake_fetch,
        )

        db = MagicMock()
        # When: 2 件続けて処理
        await update_prices.update_site_product(db, sp_fail)
        await update_prices.update_site_product(db, sp_ok)
        # Then: 両方 fetch が呼ばれ、成功側のみ PriceHistory が追加される
        assert call_log == ["B0FAIL00000", "B0OK0000001"]
        # add は 1 回（成功側のみ）
        assert db.add.call_count == 1
        added = db.add.call_args[0][0]
        assert added.price == 500
