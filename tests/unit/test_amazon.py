"""AmazonAPI (PA-API 5.0 GetItems) の単体テスト。

Why httpx.MockTransport を使う:
    依存追加なし（httpx 既存）で透過的に HTTP をモック化でき、
    実 API を叩かない要件 (order.md 制約) を満たす。
    AmazonAPI(__init__) が transport: Optional[httpx.AsyncBaseTransport] = None
    を受け取る前提（plan 4.1.2）。

Why monkeypatch で asyncio.sleep / datetime をいじる:
    リトライの待機時間（指数バックオフ）と署名タイムスタンプは時刻依存。
    テスト中は決定論的に進めたい。
"""

import json

import httpx
import pytest

# Why: 実装ステップで `api/lib/amazon.py` が全面書き換えされる想定（plan 4.1）。
# 未実装段階の write_tests では import 自体は通るが各テストは Red になる想定。
from api.lib import amazon as amazon_module
from api.lib.amazon import AmazonAPI, AmazonAPIError


# ---------- Helpers --------------------------------------------------


def _success_payload(asin: str = "B0EXAMPLE01") -> dict:
    """PA-API 5.0 GetItems の正常レスポンス（最小スーパーセット）"""
    return {
        "ItemsResult": {
            "Items": [
                {
                    "ASIN": asin,
                    "DetailPageURL": f"https://www.amazon.co.jp/dp/{asin}",
                    "ItemInfo": {
                        "Title": {
                            "DisplayValue": "テスト商品 タイトル",
                            "Label": "Title",
                            "Locale": "ja_JP",
                        }
                    },
                    "Images": {
                        "Primary": {
                            "Large": {
                                "URL": f"https://m.media-amazon.com/images/{asin}.jpg",
                                "Width": 500,
                                "Height": 500,
                            }
                        }
                    },
                    "Offers": {
                        "Listings": [
                            {
                                "Price": {
                                    "Amount": 1980,
                                    "Currency": "JPY",
                                    "DisplayAmount": "￥1,980",
                                }
                            }
                        ]
                    },
                }
            ]
        }
    }


def _error_payload(code: str = "InvalidParameterValue", message: str = "ASIN is invalid") -> dict:
    """PA-API 5.0 のエラー時レスポンス（HTTP 200 で Errors を含むケース）"""
    return {
        "Errors": [
            {"Code": code, "Message": message}
        ]
    }


def _make_transport(handler) -> httpx.MockTransport:
    """httpx.MockTransport を非同期ハンドラから作る

    handler: (httpx.Request) -> httpx.Response
    """
    return httpx.MockTransport(handler)


# ---------- 認証情報の境界検証 -------------------------------------------


class TestInitCredentialValidation:
    """環境変数欠落時に __init__ が AmazonAPIError を送出する（境界での解決）"""

    def test_missing_access_key_raises(self, monkeypatch):
        # Given: SECRET_KEY と PARTNER_TAG はあるが ACCESS_KEY がない
        monkeypatch.setenv("AMAZON_SECRET_KEY", "x")
        monkeypatch.setenv("AMAZON_PARTNER_TAG", "y")
        # When/Then
        with pytest.raises(AmazonAPIError):
            AmazonAPI()

    def test_missing_secret_key_raises(self, monkeypatch):
        # Given
        monkeypatch.setenv("AMAZON_ACCESS_KEY", "x")
        monkeypatch.setenv("AMAZON_PARTNER_TAG", "y")
        # When/Then
        with pytest.raises(AmazonAPIError):
            AmazonAPI()

    def test_missing_partner_tag_raises(self, monkeypatch):
        # Given
        monkeypatch.setenv("AMAZON_ACCESS_KEY", "x")
        monkeypatch.setenv("AMAZON_SECRET_KEY", "y")
        # When/Then
        with pytest.raises(AmazonAPIError):
            AmazonAPI()

    def test_credential_error_message_does_not_leak_secret(self, monkeypatch):
        # Given: SECRET_KEY だけ欠落
        monkeypatch.setenv("AMAZON_ACCESS_KEY", "exposed-access-key-value")
        monkeypatch.setenv("AMAZON_PARTNER_TAG", "tag")
        # When
        with pytest.raises(AmazonAPIError) as ei:
            AmazonAPI()
        # Then: 例外メッセージに値そのものを載せない（security guideline）
        msg = str(ei.value)
        assert "exposed-access-key-value" not in msg

    def test_all_credentials_present_does_not_raise(self, amazon_env):
        # Given: 必須 3 変数すべて設定済み
        # When/Then: 例外なく構築できる
        AmazonAPI()
        # PA-API JP の正規定数はモジュール定数として直接アサート（実 URL/署名は別テストで網羅）
        assert amazon_module.PAAPI_HOST == "webservices.amazon.co.jp"
        assert amazon_module.PAAPI_REGION == "us-west-2"


# ---------- 正常系: リクエスト組み立て ------------------------------------


class TestRequestBuilding:
    """送信される PA-API リクエストが仕様準拠であることを検証"""

    async def test_post_method_and_endpoint(self, amazon_env):
        # Given: 200 を返すハンドラ。受信した request を捕捉する
        captured: dict = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["method"] = request.method
            captured["url"] = str(request.url)
            return httpx.Response(200, json=_success_payload())

        api = AmazonAPI(transport=_make_transport(handler))
        # When
        await api.fetch_product("B0EXAMPLE01")
        # Then: PA-API 5.0 仕様の POST + 小文字パス
        assert captured["method"] == "POST"
        assert captured["url"] == "https://webservices.amazon.co.jp/paapi5/getitems"

    async def test_required_headers_are_present(self, amazon_env):
        # Given
        captured_headers: dict = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured_headers.update({k.lower(): v for k, v in request.headers.items()})
            return httpx.Response(200, json=_success_payload())

        api = AmazonAPI(transport=_make_transport(handler))
        # When
        await api.fetch_product("B0EXAMPLE01")
        # Then: PA-API 5.0 必須ヘッダ
        assert captured_headers["host"] == "webservices.amazon.co.jp"
        assert captured_headers["content-encoding"] == "amz-1.0"
        assert captured_headers["x-amz-target"] == (
            "com.amazon.paapi5.v1.ProductAdvertisingAPIv1.GetItems"
        )
        assert "x-amz-date" in captured_headers
        # X-Amz-Date は YYYYMMDDTHHMMSSZ 形式
        amz_date = captured_headers["x-amz-date"]
        assert len(amz_date) == 16
        assert amz_date.endswith("Z")
        assert "T" in amz_date
        # Authorization ヘッダが SigV4 形式
        auth = captured_headers["authorization"]
        assert auth.startswith("AWS4-HMAC-SHA256 ")
        assert "Credential=" in auth
        assert "SignedHeaders=" in auth
        assert "Signature=" in auth
        # Credential scope が PA-API JP 用
        assert "/us-west-2/ProductAdvertisingAPI/aws4_request" in auth
        # AccessKey が含まれている
        assert amazon_env["access_key"] in auth

    async def test_payload_structure(self, amazon_env):
        # Given
        captured_body: dict = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured_body.update(json.loads(request.content))
            return httpx.Response(200, json=_success_payload())

        api = AmazonAPI(transport=_make_transport(handler))
        # When
        await api.fetch_product("B0EXAMPLE01")
        # Then: PA-API 5.0 GetItems 仕様準拠
        assert captured_body["ItemIds"] == ["B0EXAMPLE01"]
        assert captured_body["ItemIdType"] == "ASIN"
        assert captured_body["PartnerTag"] == amazon_env["partner_tag"]
        assert captured_body["PartnerType"] == "Associates"
        assert captured_body["Marketplace"] == "www.amazon.co.jp"
        # 価格・タイトル・画像が取れる Resources
        assert "ItemInfo.Title" in captured_body["Resources"]
        assert "Offers.Listings.Price" in captured_body["Resources"]
        assert "Images.Primary.Large" in captured_body["Resources"]

    async def test_authorization_signed_headers_includes_required(self, amazon_env):
        # Given: SigV4 SignedHeaders に必須ヘッダが入っているか確認
        captured: dict = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["auth"] = request.headers["Authorization"]
            return httpx.Response(200, json=_success_payload())

        api = AmazonAPI(transport=_make_transport(handler))
        # When
        await api.fetch_product("B0EXAMPLE01")
        # Then: 必須 SignedHeaders（content-encoding, host, x-amz-date, x-amz-target）
        auth = captured["auth"]
        # SignedHeaders=...; を抽出
        for required in ("content-encoding", "host", "x-amz-date", "x-amz-target"):
            assert required in auth.lower()


# ---------- 正常系: レスポンス整形 -----------------------------------------


class TestResponseFormatting:
    """PA-API レスポンスを共通シェイプに整形できる"""

    async def test_returns_common_shape(self, amazon_env):
        # Given: 仕様通りの成功レスポンス
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=_success_payload("B0EXAMPLE01"))

        api = AmazonAPI(transport=_make_transport(handler))
        # When
        result = await api.fetch_product("B0EXAMPLE01")
        # Then: 楽天/Yahoo と揃った共通シェイプ
        assert result == {
            "site": "amazon",
            "id": "B0EXAMPLE01",
            "title": "テスト商品 タイトル",
            "price": 1980,
            "image_url": "https://m.media-amazon.com/images/B0EXAMPLE01.jpg",
            "url": "https://www.amazon.co.jp/dp/B0EXAMPLE01",
        }

    async def test_price_is_int(self, amazon_env):
        # Given: PA-API は Amount を number で返すが、JPY なので int 化したい
        payload = _success_payload()
        payload["ItemsResult"]["Items"][0]["Offers"]["Listings"][0]["Price"]["Amount"] = 2500.0

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=payload)

        api = AmazonAPI(transport=_make_transport(handler))
        # When
        result = await api.fetch_product("B0EXAMPLE01")
        # Then: 呼び出し元 update_prices.py:33 が int を期待するので int 化
        assert isinstance(result["price"], int)
        assert result["price"] == 2500

    async def test_image_url_missing_returns_none(self, amazon_env):
        # Given: 画像情報が欠落
        payload = _success_payload()
        del payload["ItemsResult"]["Items"][0]["Images"]

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=payload)

        api = AmazonAPI(transport=_make_transport(handler))
        # When
        result = await api.fetch_product("B0EXAMPLE01")
        # Then: image_url は None（楽天実装と整合: rakuten.py:34）
        assert result["image_url"] is None
        # それ以外は埋まっている
        assert result["price"] == 1980


# ---------- 異常系: HTTP / API エラー --------------------------------------


class TestHttpErrors:
    """4xx / 5xx / PA-API Errors / 空 Items で AmazonAPIError"""

    async def test_404_raises_amazon_api_error(self, amazon_env):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(404, json={"__type": "NotFound"})

        api = AmazonAPI(transport=_make_transport(handler))
        with pytest.raises(AmazonAPIError):
            await api.fetch_product("B0NOTFOUND0")

    async def test_500_raises_amazon_api_error(self, amazon_env):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(500, json={"__type": "InternalFailure"})

        api = AmazonAPI(transport=_make_transport(handler))
        with pytest.raises(AmazonAPIError):
            await api.fetch_product("B0EXAMPLE01")

    async def test_400_raises_amazon_api_error(self, amazon_env):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(400, json={"__type": "InvalidSignatureException"})

        api = AmazonAPI(transport=_make_transport(handler))
        with pytest.raises(AmazonAPIError):
            await api.fetch_product("B0EXAMPLE01")

    async def test_200_with_errors_array_raises(self, amazon_env):
        # Given: HTTP 200 だが PA-API ドメインエラー
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=_error_payload("InvalidParameterValue", "Bad ASIN"))

        api = AmazonAPI(transport=_make_transport(handler))
        with pytest.raises(AmazonAPIError) as ei:
            await api.fetch_product("BBADASIN")
        # Then: エラーメッセージに PA-API のエラーコード等が含まれる（ASIN 識別のため）
        msg = str(ei.value)
        assert "InvalidParameterValue" in msg or "Bad ASIN" in msg

    async def test_200_with_empty_items_raises(self, amazon_env):
        # Given: ItemsResult.Items が空（ASIN not found 相当）
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"ItemsResult": {"Items": []}})

        api = AmazonAPI(transport=_make_transport(handler))
        with pytest.raises(AmazonAPIError):
            await api.fetch_product("B0NOTFOUND0")

    async def test_error_message_does_not_leak_authorization_or_secret(self, amazon_env):
        # Given: 5xx
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(500, json={"__type": "InternalFailure"})

        api = AmazonAPI(transport=_make_transport(handler))
        # When
        with pytest.raises(AmazonAPIError) as ei:
            await api.fetch_product("B0EXAMPLE01")
        # Then: SecretKey と Authorization 値が例外メッセージに混入していない
        msg = str(ei.value)
        assert amazon_env["secret_key"] not in msg
        assert "AWS4-HMAC-SHA256" not in msg


# ---------- リトライ -------------------------------------------------------


class TestRetry:
    """429 で指数バックオフリトライ"""

    async def test_retries_on_429_then_succeeds(self, amazon_env, monkeypatch):
        # Given: 1 回目 429, 2 回目 200
        call_count = {"n": 0}

        def handler(request: httpx.Request) -> httpx.Response:
            call_count["n"] += 1
            if call_count["n"] == 1:
                return httpx.Response(429, json={"__type": "TooManyRequests"})
            return httpx.Response(200, json=_success_payload())

        # asyncio.sleep が呼ばれた delay を記録（実待機しない）
        sleeps: list = []

        async def fake_sleep(delay: float) -> None:
            sleeps.append(delay)

        monkeypatch.setattr(amazon_module.asyncio, "sleep", fake_sleep)

        api = AmazonAPI(transport=_make_transport(handler))
        # When
        result = await api.fetch_product("B0EXAMPLE01")
        # Then: 最終的に成功し、リトライが 1 回挟まる
        assert result["id"] == "B0EXAMPLE01"
        assert call_count["n"] == 2
        assert len(sleeps) == 1
        # 指数バックオフの最初の待機（attempt=0 → BASE * 2**0 = BASE）
        # plan 4.4: delay = RETRY_BASE_DELAY * 2 ** attempt + jitter(0..0.1)
        assert sleeps[0] >= amazon_module.RETRY_BASE_DELAY
        assert sleeps[0] <= amazon_module.RETRY_BASE_DELAY + 0.1 + 1e-9

    async def test_retries_use_exponential_backoff(self, amazon_env, monkeypatch):
        # Given: 全て 429 を返し続ける（上限まで使い切る）
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(429, json={"__type": "TooManyRequests"})

        sleeps: list = []

        async def fake_sleep(delay: float) -> None:
            sleeps.append(delay)

        monkeypatch.setattr(amazon_module.asyncio, "sleep", fake_sleep)

        api = AmazonAPI(transport=_make_transport(handler))
        # When
        with pytest.raises(AmazonAPIError):
            await api.fetch_product("B0EXAMPLE01")
        # Then: MAX_RETRIES 回スリープし、各回が指数で増える
        assert len(sleeps) == amazon_module.MAX_RETRIES
        base = amazon_module.RETRY_BASE_DELAY
        for attempt, delay in enumerate(sleeps):
            expected_min = base * (2 ** attempt)
            expected_max = expected_min + 0.1 + 1e-9  # jitter 上限
            assert expected_min <= delay <= expected_max, (
                f"attempt={attempt}: delay={delay} not in [{expected_min}, {expected_max}]"
            )

    async def test_retry_limit_exhausted_raises(self, amazon_env, monkeypatch):
        # Given: 常に 429
        call_count = {"n": 0}

        def handler(request: httpx.Request) -> httpx.Response:
            call_count["n"] += 1
            return httpx.Response(429, json={"__type": "TooManyRequests"})

        async def fake_sleep(delay: float) -> None:
            return None

        monkeypatch.setattr(amazon_module.asyncio, "sleep", fake_sleep)

        api = AmazonAPI(transport=_make_transport(handler))
        # When/Then
        with pytest.raises(AmazonAPIError):
            await api.fetch_product("B0EXAMPLE01")
        # MAX_RETRIES + 1 回 (= 初回 + リトライ回数) リクエストされる
        assert call_count["n"] == amazon_module.MAX_RETRIES + 1

    async def test_no_retry_on_5xx(self, amazon_env, monkeypatch):
        # Given: 500 はリトライしない設計判断 (plan 4.4: 課金 API なので副作用最小)
        call_count = {"n": 0}

        def handler(request: httpx.Request) -> httpx.Response:
            call_count["n"] += 1
            return httpx.Response(500, json={"__type": "InternalFailure"})

        sleeps: list = []

        async def fake_sleep(delay: float) -> None:
            sleeps.append(delay)

        monkeypatch.setattr(amazon_module.asyncio, "sleep", fake_sleep)

        api = AmazonAPI(transport=_make_transport(handler))
        # When/Then
        with pytest.raises(AmazonAPIError):
            await api.fetch_product("B0EXAMPLE01")
        # Then: 1 回のみ呼ばれ、sleep は使われない
        assert call_count["n"] == 1
        assert sleeps == []

    async def test_no_retry_on_4xx_other_than_429(self, amazon_env, monkeypatch):
        # Given: 400 はリトライしない
        call_count = {"n": 0}

        def handler(request: httpx.Request) -> httpx.Response:
            call_count["n"] += 1
            return httpx.Response(400, json={"__type": "Bad"})

        async def fake_sleep(delay: float) -> None:
            return None

        monkeypatch.setattr(amazon_module.asyncio, "sleep", fake_sleep)

        api = AmazonAPI(transport=_make_transport(handler))
        # When/Then
        with pytest.raises(AmazonAPIError):
            await api.fetch_product("B0EXAMPLE01")
        # Then: 1 回のみ
        assert call_count["n"] == 1


# ---------- 定数の整合性 ---------------------------------------------------


class TestConstants:
    """plan で定数化を求めた値の存在確認"""

    def test_max_retries_defined(self):
        assert hasattr(amazon_module, "MAX_RETRIES")
        assert isinstance(amazon_module.MAX_RETRIES, int)
        assert amazon_module.MAX_RETRIES >= 1

    def test_retry_base_delay_defined(self):
        assert hasattr(amazon_module, "RETRY_BASE_DELAY")
        assert amazon_module.RETRY_BASE_DELAY > 0

    def test_paapi_jp_endpoint_constants(self):
        # PA-API JP の正規値（モジュール定数を直接検証）
        assert amazon_module.PAAPI_HOST == "webservices.amazon.co.jp"
        assert amazon_module.PAAPI_REGION == "us-west-2"
