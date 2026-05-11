"""Integration tests for GET /api/products/{id}/suggestion.

HTTP 契約の検証:
    - 404: 存在しない商品
    - 200: 正しいレスポンス形式（camelCase、全フィールド存在）
    - productId がリクエストと一致する
    - action は "buy_now" または "wait" のいずれか
    - 認証不要（公開エンドポイント）

振る舞いの検証:
    - 価格履歴なし → buy_now（データ不足）
    - 価格履歴あり・キャンペーンなし → buy_now
    - recurring キャンペーン（10% ボーナス）あり → wait

Why インテグレーションテストを書くか:
    Router → Repository(campaigns) → forecaster → suggestion という
    3 モジュール以上を横断するデータフローが存在する。
    ユニットテストでは各層の正確さを検証できるが、
    パラメータが連鎖を通じて末端まで届くかはインテグレーションテストで保証する。
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest

from api.common.models import CampaignKind, PriceHistory, SaleCampaign
from api.common.models import SiteType as ModelSiteType


def _seed(session, objects):
    for obj in objects:
        session.add(obj)
    session.commit()


SUGGESTION_URL = "/api/products/{product_id}/suggestion"


# ── HTTP 契約テスト ───────────────────────────────────────────────────────────


class TestEndpointSuggestionContract:
    """エンドポイントの HTTP 契約（ステータスコード・レスポンス形式）を検証する。"""

    def test_returns_404_for_nonexistent_product(self, client):
        """存在しない商品 UUID → 404。"""
        response = client.get(SUGGESTION_URL.format(product_id=uuid.uuid4()))

        assert response.status_code == 404

    def test_returns_200_for_existing_product(self, client, db_session, make_product):
        """存在する商品 → 200。"""
        product = make_product(name="テスト商品")
        _seed(db_session, [product])

        response = client.get(SUGGESTION_URL.format(product_id=product.id))

        assert response.status_code == 200

    def test_response_content_type_is_json(self, client, db_session, make_product):
        """レスポンスの Content-Type は application/json。"""
        product = make_product(name="テスト商品")
        _seed(db_session, [product])

        response = client.get(SUGGESTION_URL.format(product_id=product.id))

        assert response.headers["content-type"].startswith("application/json")

    def test_response_fields_are_camel_case(self, client, db_session, make_product):
        """レスポンスフィールドはすべてキャメルケース（スネークケース禁止）。

        Why: フロントエンドは camelCase を期待する。スネークケースの混入は
        サイレントなバグ（undefined アクセス）になる。
        """
        product = make_product(name="テスト商品")
        _seed(db_session, [product])

        response = client.get(SUGGESTION_URL.format(product_id=product.id))
        body = response.json()

        # 必須 camelCase フィールドがすべて存在する
        for field in [
            "productId",
            "action",
            "rationale",
            "currentBestEffectivePrice",
            "expectedSaleEffectivePrice",
            "estimatedSaving",
            "nextSaleDate",
            "nextSaleCampaign",
        ]:
            assert field in body, f"Expected camelCase field '{field}' missing from response"

        # スネークケースは混入しない
        for snake_field in [
            "product_id",
            "current_best_effective_price",
            "expected_sale_effective_price",
            "estimated_saving",
            "next_sale_date",
            "next_sale_campaign",
        ]:
            assert snake_field not in body, (
                f"snake_case field '{snake_field}' must not appear in response"
            )

    def test_response_product_id_matches_request(self, client, db_session, make_product):
        """レスポンスの productId がリクエストの商品 UUID と一致する。

        Why: productId の取り違えはフロントエンドで誤ったサジェストを
        キャッシュする原因になる。
        """
        product = make_product(name="テスト商品")
        _seed(db_session, [product])

        response = client.get(SUGGESTION_URL.format(product_id=product.id))
        body = response.json()

        assert body["productId"] == str(product.id)

    def test_action_is_valid_enum_value(self, client, db_session, make_product):
        """action は 'buy_now' または 'wait' のいずれか。"""
        product = make_product(name="テスト商品")
        _seed(db_session, [product])

        response = client.get(SUGGESTION_URL.format(product_id=product.id))
        body = response.json()

        assert body["action"] in ("buy_now", "wait"), (
            f"action must be 'buy_now' or 'wait', got {body['action']!r}"
        )

    def test_rationale_is_non_empty_string(self, client, db_session, make_product):
        """rationale は常に非空の文字列。"""
        product = make_product(name="テスト商品")
        _seed(db_session, [product])

        response = client.get(SUGGESTION_URL.format(product_id=product.id))
        body = response.json()

        assert isinstance(body["rationale"], str)
        assert len(body["rationale"]) > 0

    def test_does_not_require_authentication(self, client, db_session, make_product):
        """Authorization ヘッダーなしで 200（公開エンドポイント）。

        Why: サジェストは全ユーザーに表示する機能。認証を要求すると
        ゲストユーザーがサジェストを受け取れなくなる（T-20 仕様違反）。
        """
        product = make_product(name="テスト商品")
        _seed(db_session, [product])

        # Authorization ヘッダーを付けない
        response = client.get(SUGGESTION_URL.format(product_id=product.id))

        # 401/403 ではなく 200
        assert response.status_code == 200

    def test_request_body_is_not_accepted_as_path_substitute(self, client, db_session, make_product):
        """productId はパスパラメータで渡すこと（body や query ではない）。

        Why: エンドポイント契約のテスト。リクエスト body を path に流用する
        実装ミスを検出するため、正しいパス経由でのみ商品が見つかることを確認する。
        """
        product = make_product(name="テスト商品")
        _seed(db_session, [product])

        # 正しいパスで成功する
        response_correct = client.get(SUGGESTION_URL.format(product_id=product.id))
        assert response_correct.status_code == 200

        # 誤った UUID のパスでは 404
        response_wrong = client.get(SUGGESTION_URL.format(product_id=uuid.uuid4()))
        assert response_wrong.status_code == 404


# ── 振る舞いテスト ────────────────────────────────────────────────────────────


class TestEndpointSuggestionBehavior:
    """エンドポイントが返すサジェスト内容の振る舞いを検証する。"""

    def test_action_is_buy_now_when_no_price_history(self, client, db_session, make_product):
        """価格履歴なし → データ不足として buy_now。"""
        product = make_product(name="テスト商品")
        _seed(db_session, [product])

        response = client.get(SUGGESTION_URL.format(product_id=product.id))
        body = response.json()

        assert body["action"] == "buy_now"

    def test_optional_fields_are_null_for_buy_now_with_no_history(
        self, client, db_session, make_product
    ):
        """buy_now（履歴なし）のとき optional フィールドは null。"""
        product = make_product(name="テスト商品")
        _seed(db_session, [product])

        response = client.get(SUGGESTION_URL.format(product_id=product.id))
        body = response.json()

        assert body["action"] == "buy_now"
        assert body["expectedSaleEffectivePrice"] is None
        assert body["estimatedSaving"] is None
        assert body["nextSaleDate"] is None
        assert body["nextSaleCampaign"] is None

    def test_action_is_buy_now_when_history_exists_but_no_campaigns(
        self, client, db_session, make_product, make_site_product
    ):
        """価格履歴あり・キャンペーンなし → upcoming_sales が空 → buy_now。"""
        product = make_product(name="テスト商品")
        _seed(db_session, [product])
        sp = make_site_product(product, "amazon", site_product_id="ASIN1")
        _seed(db_session, [sp])

        now = datetime.now(timezone.utc)
        h = PriceHistory(
            ec_site_product_id=sp.id,
            price=10000,
            points=100,
            recorded_at=now - timedelta(days=5),
        )
        _seed(db_session, [h])

        response = client.get(SUGGESTION_URL.format(product_id=product.id))
        body = response.json()

        # キャンペーンなし → upcoming_sales=[] → buy_now
        assert body["action"] == "buy_now"

    def test_action_is_wait_when_recurring_campaign_saves_over_5_percent(
        self, client, db_session, make_product, make_site_product
    ):
        """recurring キャンペーン（10% ボーナス）があるとき wait。

        Why [5,10,15,20,25] キャンペーン日を使うか:
            最大ギャップが 10 日（例: 5/25 → 6/5）となり、
            どの実行日からでも horizon_days=30 以内に必ず次回が存在する。
            実行日依存のフレーキーテストを避けるための設計。
        """
        product = make_product(name="テスト商品")
        _seed(db_session, [product])
        sp = make_site_product(product, "rakuten", site_product_id="RAKU1")
        _seed(db_session, [sp])

        now = datetime.now(timezone.utc)
        h = PriceHistory(
            ec_site_product_id=sp.id,
            price=10000,
            points=0,
            recorded_at=now - timedelta(days=5),
        )
        _seed(db_session, [h])

        # RAKUTEN recurring キャンペーン: 10% bonus (>> 5% 閾値)
        campaign = SaleCampaign(
            site=ModelSiteType.RAKUTEN,
            name="お買い物マラソン",
            kind=CampaignKind.RECURRING,
            recurrence_rule={"type": "day_of_month", "days": [5, 10, 15, 20, 25]},
            bonus={"type": "additive_rate", "rate": 0.10},
        )
        _seed(db_session, [campaign])

        response = client.get(SUGGESTION_URL.format(product_id=product.id))
        body = response.json()

        assert body["action"] == "wait"
        assert body["estimatedSaving"] is not None
        assert body["estimatedSaving"] > 0
        assert body["nextSaleCampaign"] == "お買い物マラソン"
        assert body["nextSaleDate"] is not None

    def test_wait_response_has_expected_sale_effective_price(
        self, client, db_session, make_product, make_site_product
    ):
        """wait 時: expectedSaleEffectivePrice は現在価格 × (1 - ボーナス率)。"""
        product = make_product(name="テスト商品")
        _seed(db_session, [product])
        sp = make_site_product(product, "rakuten", site_product_id="RAKU1")
        _seed(db_session, [sp])

        now = datetime.now(timezone.utc)
        h = PriceHistory(
            ec_site_product_id=sp.id,
            price=10000,
            points=0,
            recorded_at=now - timedelta(days=5),
        )
        _seed(db_session, [h])

        campaign = SaleCampaign(
            site=ModelSiteType.RAKUTEN,
            name="お買い物マラソン",
            kind=CampaignKind.RECURRING,
            recurrence_rule={"type": "day_of_month", "days": [5, 10, 15, 20, 25]},
            bonus={"type": "additive_rate", "rate": 0.10},
        )
        _seed(db_session, [campaign])

        response = client.get(SUGGESTION_URL.format(product_id=product.id))
        body = response.json()

        # expected_sale = 10000 * (1 - 0.10) = 9000
        assert body["expectedSaleEffectivePrice"] == 9000
        # saving = 10000 - 9000 = 1000
        assert body["estimatedSaving"] == 1000


# ── キャンペーンリポジトリのテスト ────────────────────────────────────────────


class TestCampaignsRepository:
    """api.repositories.campaigns.get_campaigns_for_suggestion のテスト。

    Why インテグレーション層でテストするか:
        RECURRING/ONESHOT のフィルタリングは SQL レベルで行われるため、
        実際の DB 操作を通じて正確さを確認する必要がある。
    """

    def test_recurring_campaign_is_always_returned(self, db_session):
        """RECURRING キャンペーンは reference_date に関係なく返される。"""
        from api.repositories.campaigns import get_campaigns_for_suggestion

        campaign = SaleCampaign(
            site=ModelSiteType.RAKUTEN,
            name="定常キャンペーン",
            kind=CampaignKind.RECURRING,
            recurrence_rule={"type": "day_of_month", "days": [15]},
            bonus={"type": "additive_rate", "rate": 0.04},
        )
        _seed(db_session, [campaign])

        now = datetime.now(timezone.utc)
        result = get_campaigns_for_suggestion(
            db_session,
            sites=[ModelSiteType.RAKUTEN],
            reference_date=now,
        )

        assert len(result) == 1
        assert result[0].name == "定常キャンペーン"

    def test_oneshot_campaign_within_future_days_is_returned(self, db_session):
        """ONESHOT キャンペーンで start_at が future_days 以内なら返される。"""
        from api.repositories.campaigns import get_campaigns_for_suggestion

        now = datetime.now(timezone.utc)
        campaign = SaleCampaign(
            site=ModelSiteType.AMAZON,
            name="近日開催セール",
            kind=CampaignKind.ONESHOT,
            start_at=now + timedelta(days=10),  # 10日後: future_days=60 以内
            bonus={"type": "additive_rate", "rate": 0.05},
        )
        _seed(db_session, [campaign])

        result = get_campaigns_for_suggestion(
            db_session,
            sites=[ModelSiteType.AMAZON],
            reference_date=now,
            future_days=60,
        )

        assert len(result) == 1
        assert result[0].name == "近日開催セール"

    def test_oneshot_campaign_beyond_future_days_is_excluded(self, db_session):
        """ONESHOT キャンペーンで start_at が future_days 超 → 除外。"""
        from api.repositories.campaigns import get_campaigns_for_suggestion

        now = datetime.now(timezone.utc)
        campaign = SaleCampaign(
            site=ModelSiteType.AMAZON,
            name="遠い将来のセール",
            kind=CampaignKind.ONESHOT,
            start_at=now + timedelta(days=90),  # 90日後: future_days=60 を超える
            bonus={"type": "additive_rate", "rate": 0.05},
        )
        _seed(db_session, [campaign])

        result = get_campaigns_for_suggestion(
            db_session,
            sites=[ModelSiteType.AMAZON],
            reference_date=now,
            future_days=60,
        )

        assert result == []

    def test_filters_by_site(self, db_session):
        """sites に含まれないサイトのキャンペーンは除外される。"""
        from api.repositories.campaigns import get_campaigns_for_suggestion

        campaign_rakuten = SaleCampaign(
            site=ModelSiteType.RAKUTEN,
            name="楽天キャンペーン",
            kind=CampaignKind.RECURRING,
            bonus={"type": "additive_rate", "rate": 0.04},
        )
        campaign_amazon = SaleCampaign(
            site=ModelSiteType.AMAZON,
            name="Amazonキャンペーン",
            kind=CampaignKind.RECURRING,
            bonus={"type": "additive_rate", "rate": 0.04},
        )
        _seed(db_session, [campaign_rakuten, campaign_amazon])

        now = datetime.now(timezone.utc)
        result = get_campaigns_for_suggestion(
            db_session,
            sites=[ModelSiteType.RAKUTEN],
            reference_date=now,
        )

        names = {c.name for c in result}
        assert "楽天キャンペーン" in names
        assert "Amazonキャンペーン" not in names

    def test_returns_campaigns_for_multiple_sites(self, db_session):
        """複数サイトを指定すると両サイトのキャンペーンが返される。"""
        from api.repositories.campaigns import get_campaigns_for_suggestion

        campaign_rakuten = SaleCampaign(
            site=ModelSiteType.RAKUTEN,
            name="楽天キャンペーン",
            kind=CampaignKind.RECURRING,
            bonus={"type": "additive_rate", "rate": 0.04},
        )
        campaign_amazon = SaleCampaign(
            site=ModelSiteType.AMAZON,
            name="Amazonキャンペーン",
            kind=CampaignKind.RECURRING,
            bonus={"type": "additive_rate", "rate": 0.04},
        )
        _seed(db_session, [campaign_rakuten, campaign_amazon])

        now = datetime.now(timezone.utc)
        result = get_campaigns_for_suggestion(
            db_session,
            sites=[ModelSiteType.RAKUTEN, ModelSiteType.AMAZON],
            reference_date=now,
        )

        names = {c.name for c in result}
        assert "楽天キャンペーン" in names
        assert "Amazonキャンペーン" in names

    def test_empty_result_when_no_campaigns(self, db_session):
        """キャンペーンが存在しない場合は空リストを返す。"""
        from api.repositories.campaigns import get_campaigns_for_suggestion

        now = datetime.now(timezone.utc)
        result = get_campaigns_for_suggestion(
            db_session,
            sites=[ModelSiteType.RAKUTEN],
            reference_date=now,
        )

        assert result == []
