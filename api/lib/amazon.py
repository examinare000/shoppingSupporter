"""Amazon Product Advertising API 5.0 (PA-API) GetItems クライアント。

Why このモジュールが SigV4 と分離されているか:
    SigV4 は AWS 全般の認証ロジックで PA-API 固有の知識を含まない。
    PA-API の通信処理（エンドポイント／ヘッダ／ペイロード／レスポンス整形／リトライ）は
    `aws_sigv4` を呼び出して使う側として分離する（高凝集・低結合）。

Why 戻り値が Optional[Dict] ではなく Dict | raise:
    タスク仕様（order.md）で「失敗時は例外」「後方互換コードは作らない」と明示。
    呼び出し元（`api/cron/update_prices.py`）側が `try/except AmazonAPIError` で
    握って cron loop を継続させる方針（plan 4 / test_update_prices_amazon.py 参照）。
"""

from __future__ import annotations

import asyncio
import json
import os
import random
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import httpx

from . import aws_sigv4


# ----- PA-API 5.0 JP の正規定数 ---------------------------------------------
# Why 定数化: マジックナンバー禁止 (policy)。仕様変更時の追従点を 1 箇所に集約。

PAAPI_HOST = "webservices.amazon.co.jp"
PAAPI_PATH = "/paapi5/getitems"
PAAPI_TARGET = "com.amazon.paapi5.v1.ProductAdvertisingAPIv1.GetItems"
PAAPI_REGION = "us-west-2"
PAAPI_SERVICE = "ProductAdvertisingAPI"
PAAPI_MARKETPLACE = "www.amazon.co.jp"
PAAPI_PARTNER_TYPE = "Associates"
PAAPI_RESOURCES = [
    "ItemInfo.Title",
    "Images.Primary.Large",
    "Offers.Listings.Price",
]

# Why リトライ上限 3: 課金 API のため過剰呼び出しを避ける。
# 指数バックオフで合計約 1+2+4=7 秒の待機を許容。
MAX_RETRIES = 3
RETRY_BASE_DELAY = 1.0
RETRY_JITTER_MAX = 0.1

HTTP_TIMEOUT = 10.0


class AmazonAPIError(Exception):
    """Amazon PA-API 通信に関する全失敗を表す。

    Why 単一例外型: 呼び出し元（cron）は具体的な失敗種別ごとに分岐せず、
    「Amazon の失敗で他商品の処理を止めない」という単一目的で握る。
    """


class AmazonAPI:
    def __init__(self, transport: Optional[httpx.AsyncBaseTransport] = None) -> None:
        # 境界での解決: 認証情報は構築時に必ず揃っていることを保証する。
        # 未設定で fetch_product まで遅延させると、cron loop の途中で
        # 初めて失敗が発覚し原因切り分けが難しくなる。
        access_key = os.getenv("AMAZON_ACCESS_KEY")
        secret_key = os.getenv("AMAZON_SECRET_KEY")
        partner_tag = os.getenv("AMAZON_PARTNER_TAG")

        missing = [
            name
            for name, value in (
                ("AMAZON_ACCESS_KEY", access_key),
                ("AMAZON_SECRET_KEY", secret_key),
                ("AMAZON_PARTNER_TAG", partner_tag),
            )
            if not value
        ]
        if missing:
            # Why: 例外メッセージにシークレットの値そのものを載せない（security guideline）。
            # 不足しているキー名のみ。
            raise AmazonAPIError(
                f"Missing required Amazon credentials: {', '.join(missing)}"
            )

        # 認証情報は AmazonAPI のインスタンス内のみで保持し、ログ／例外には出さない。
        # 上の missing チェックで None の可能性は排除済み。
        self._access_key = access_key
        self._secret_key = secret_key
        self._partner_tag = partner_tag

        # Why transport をフィールドに保持: テスト時は MockTransport を注入する。
        # 本番は None のまま（httpx.AsyncClient のデフォルトを使う）。
        self._transport = transport

    async def fetch_product(self, asin: str) -> Dict[str, Any]:
        """ASIN を受け取り共通シェイプの dict を返す。失敗時は AmazonAPIError。"""
        payload = self._build_payload(asin)
        body = self._serialize_payload(payload)
        response_json = await self._post_with_retry(asin=asin, body=body)
        return self._format_response(asin=asin, response_json=response_json)

    # ----- 内部: リクエスト組み立て --------------------------------------

    def _build_payload(self, asin: str) -> Dict[str, Any]:
        return {
            "ItemIds": [asin],
            "ItemIdType": "ASIN",
            "PartnerTag": self._partner_tag,
            "PartnerType": PAAPI_PARTNER_TYPE,
            "Marketplace": PAAPI_MARKETPLACE,
            "Resources": list(PAAPI_RESOURCES),
        }

    @staticmethod
    def _serialize_payload(payload: Dict[str, Any]) -> bytes:
        # Why separators=(",", ":") 固定: SigV4 の署名対象は HTTP ボディとバイト一致が必須。
        # json.dumps のデフォルトは空白入り `(", ", ": ")` なので空白なしを明示する。
        return json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")

    def _build_signed_headers(self, body: bytes) -> Dict[str, str]:
        amz_datetime = datetime.now(tz=timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        # Why content-encoding/host/x-amz-date/x-amz-target を SignedHeaders に含める:
        # PA-API 5.0 仕様で必須。これら以外（Content-Type など）は SignedHeaders から除外する。
        signing_headers = {
            "Host": PAAPI_HOST,
            "Content-Encoding": "amz-1.0",
            "X-Amz-Date": amz_datetime,
            "X-Amz-Target": PAAPI_TARGET,
        }
        authorization = aws_sigv4.sign_request(
            method="POST",
            path=PAAPI_PATH,
            headers=signing_headers,
            payload=body,
            access_key=self._access_key,
            secret_key=self._secret_key,
            region=PAAPI_REGION,
            service=PAAPI_SERVICE,
            amz_datetime=amz_datetime,
        )
        return {
            **signing_headers,
            "Authorization": authorization,
            # Content-Type は署名対象外だが PA-API が要求する。
            "Content-Type": "application/json; charset=UTF-8",
        }

    # ----- 内部: HTTP 送信 + リトライ ------------------------------------

    async def _post_with_retry(self, *, asin: str, body: bytes) -> Dict[str, Any]:
        url = f"https://{PAAPI_HOST}{PAAPI_PATH}"
        async with httpx.AsyncClient(
            transport=self._transport, timeout=HTTP_TIMEOUT
        ) as client:
            for attempt in range(MAX_RETRIES + 1):
                # Why ヘッダ生成をループ内に置く: SigV4 の X-Amz-Date は秒単位で進む。
                # リトライで時間が経過した場合に再署名する必要がある。
                headers = self._build_signed_headers(body)
                response = await client.post(url, content=body, headers=headers)

                if response.status_code == 200:
                    return self._parse_success_or_raise(asin=asin, response=response)

                if response.status_code == 429 and attempt < MAX_RETRIES:
                    delay = (
                        RETRY_BASE_DELAY * (2 ** attempt)
                        + random.uniform(0, RETRY_JITTER_MAX)
                    )
                    await asyncio.sleep(delay)
                    continue

                # 429 上限超過 / その他の 4xx・5xx は即例外
                raise AmazonAPIError(
                    f"PA-API request failed for ASIN={asin} "
                    f"status={response.status_code}"
                )

    @staticmethod
    def _parse_success_or_raise(
        *, asin: str, response: httpx.Response
    ) -> Dict[str, Any]:
        try:
            data = response.json()
        except ValueError as exc:
            raise AmazonAPIError(
                f"PA-API returned non-JSON 200 response for ASIN={asin}"
            ) from exc

        # PA-API はドメインエラーを HTTP 200 + Errors 配列で返すことがある。
        if "Errors" in data and data["Errors"]:
            errors = data["Errors"]
            first = errors[0] if isinstance(errors, list) and errors else {}
            code = first.get("Code", "Unknown")
            message = first.get("Message", "")
            raise AmazonAPIError(
                f"PA-API error for ASIN={asin}: {code}: {message}"
            )
        return data

    # ----- 内部: レスポンス整形 ------------------------------------------

    @staticmethod
    def _format_response(*, asin: str, response_json: Dict[str, Any]) -> Dict[str, Any]:
        items_result = response_json.get("ItemsResult") or {}
        items = items_result.get("Items") or []
        if not items:
            raise AmazonAPIError(f"PA-API returned no items for ASIN={asin}")
        item = items[0]

        title = (
            item.get("ItemInfo", {})
            .get("Title", {})
            .get("DisplayValue")
        )
        listings = item.get("Offers", {}).get("Listings") or []
        price_amount = (
            listings[0].get("Price", {}).get("Amount")
            if listings
            else None
        )
        if title is None or price_amount is None:
            raise AmazonAPIError(
                f"PA-API response missing required fields for ASIN={asin}"
            )

        image_url = (
            item.get("Images", {})
            .get("Primary", {})
            .get("Large", {})
            .get("URL")
        )
        detail_url = item.get("DetailPageURL")
        if detail_url is None:
            raise AmazonAPIError(
                f"PA-API response missing DetailPageURL for ASIN={asin}"
            )

        # Why points を返さない:
        # PA-API 5.0 はポイント値を直接提供しない。呼び出し元 update_prices.py が
        # `result.get("points", 0)` で default=0 を採用している前提に委ねる。
        return {
            "site": "amazon",
            "id": item.get("ASIN", asin),
            "title": title,
            "price": int(price_amount),
            "image_url": image_url,
            "url": detail_url,
        }
