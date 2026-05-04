# タスク計画

## 元の要求

バックエンドの `api/lib/amazon.py` は現在スタブ実装である。Amazon Product Advertising API (PA-API 5.0) を呼び出す本格実装に置き換える。リクエスト署名（AWS Signature V4）を含む通信処理を実装し、モックによる単体テストでカバーする。日本マーケットプレイスのみ対応、テストはモック単体テストのみ、API失敗時は例外送出、後方互換コードは作らない。

## 分析結果

### 目的

`api/lib/amazon.py` のスタブ（`return None`）を、PA-API 5.0 の `GetItems` を実通信で呼び出し、楽天/Yahoo クライアントと共通シェイプの辞書を返す本実装に置き換える。AWS Signature V4 署名は標準ライブラリで実装し、モック単体テストで検証する。

### 分解した要件

| # | 要件 | 種別 | 備考 |
|---|------|------|------|
| 1 | スタブを PA-API 5.0 への実通信に置換 | 明示 | `amazon.py:13-18` が `print` + `return None` |
| 2 | エンドポイント `https://webservices.amazon.co.jp/paapi5/getitems` への POST | 明示 | パスは小文字 |
| 3 | 必須ヘッダ `Content-Type` を設定 | 明示 | `application/json; charset=UTF-8` |
| 4 | 必須ヘッダ `X-Amz-Date` を設定 | 明示 | `YYYYMMDDTHHMMSSZ`（UTC） |
| 5 | 必須ヘッダ `X-Amz-Target` を設定 | 明示 | `com.amazon.paapi5.v1.ProductAdvertisingAPIv1.GetItems` |
| 6 | 必須ヘッダ `Content-Encoding: amz-1.0` を設定 | 明示 | |
| 7 | 必須ヘッダ `Host` を設定 | 明示 | `webservices.amazon.co.jp` |
| 8 | 必須ヘッダ `Authorization` を設定 | 明示 | SigV4 形式 |
| 9 | ペイロードに `PartnerTag`, `PartnerType=Associates`, `Marketplace=www.amazon.co.jp` を含める | 明示 | |
| 10 | ペイロードにオペレーション固有パラメータ `ItemIds`, `ItemIdType=ASIN` を含める | 明示 | |
| 11 | ペイロードに `Resources` を含める | 明示 | `ItemInfo.Title`, `Images.Primary.Large`, `Offers.Listings.Price` |
| 12 | SigV4 の `service=ProductAdvertisingAPI` を使用 | 明示 | |
| 13 | SigV4 の `region=us-west-2` を使用 | 明示 | 既存スタブと一致 |
| 14 | SigV4 で正規リクエスト→StringToSign→SigningKey→Signature の手順で署名 | 明示 | |
| 15 | SigningKey を `AWS4`+SecretKey→date→region→service→`aws4_request` の HMAC-SHA256 連鎖で導出 | 明示 | |
| 16 | レスポンス JSON を呼び出し元が期待する形に整形 | 明示 | 楽天/Yahoo と同じ共通シェイプ |
| 17 | HTTP 429 で指数バックオフによるリトライ | 明示 | |
| 18 | リトライ回数の上限を定数化 | 明示 | `MAX_RETRIES=3` |
| 19 | リトライ上限超過で例外送出 | 明示 | |
| 20 | 4xx/5xx で例外送出 | 明示 | 429 以外 |
| 21 | PA-API エラーレスポンス（`Errors` 配列）で例外送出 | 明示 | |
| 22 | Amazon 用例外型を新規定義 | 明示 | 既存例外なし→新規 `AmazonAPIError` |
| 23 | HTTP クライアントをモック化した正常系テスト（リクエスト検査） | 明示 | |
| 24 | HTTP クライアントをモック化した正常系テスト（レスポンス整形検査） | 明示 | |
| 25 | 4xx/5xx で例外送出される異常系テスト | 明示 | |
| 26 | PA-API `Errors` で例外送出される異常系テスト | 明示 | |
| 27 | 429 後に成功するリトライ動作テスト（指数バックオフ確認） | 明示 | |
| 28 | リトライ上限超過で例外送出されるテスト | 明示 | |
| 29 | SigV4 署名生成ロジックの単独テスト（CanonicalRequest / StringToSign / SigningKey / Signature / Authorization の各段階） | 明示 | 期待値は AWS 公式仕様の手順に沿った事前計算値 |
| 30 | 設定/認証情報の取得経路を確認・実装 | 明示 | 既存パターン `os.getenv` を踏襲（暗黙不要） |
| 31 | スタブ残骸（`pass`/`NotImplementedError`/ダミー戻り値）を残さない | 明示 | |
| 32 | 既存呼び出し元すべてが新実装で動作する | 明示 | `update_prices.py` の整合 |
| 33 | 共通シェイプ `{site, id, title, price, image_url, url}` で返す | 暗黙 | 要件16から導出。楽天 (`api/lib/rakuten.py:29-36`) / Yahoo (`api/lib/yahoo.py:30-37`) と同形 |
| 34 | `update_prices.py:18-20` の Amazon 分岐を `try/except AmazonAPIError` でラップ | 暗黙 | 要件20/21（例外送出）と要件32（呼び出し元整合）の両立。1商品の失敗で cron 全体を落とさない |
| 35 | Python 単体テスト基盤（`pytest`, `pytest-asyncio`, `pytest.ini`, `tests/`）を新設 | 暗黙 | 要件23-29から導出。既存テスト基盤不在（grep で `test_*.py`/`pyproject.toml`/`conftest.py` 全て無し） |

### 参照資料の調査結果

**Primary spec**: `.takt/.../context/task/order.md` を実 Read。PA-API 5.0 公式仕様と既存スタブが「正本」。両者に矛盾があれば仕様優先で既存を修正してよいと明記。

**既存スタブ** (`api/lib/amazon.py:1-19`):
- `class AmazonAPI` / `__init__()` で `os.getenv("AMAZON_ACCESS_KEY"/"AMAZON_SECRET_KEY"/"AMAZON_PARTNER_TAG")` を取得
- `self.host = "webservices.amazon.co.jp"`、`self.region = "us-west-2"`（PA-API 5.0 JP 仕様と一致 → 修正不要）
- `async def fetch_product(self, asin: str) -> Optional[Dict]` が `print` + `return None`（要書き換え）

**呼び出し元** (`api/cron/update_prices.py:18-45`、grep で唯一の Python 呼び出し元):
- `result["price"]` (必須・int)、`result.get("points", 0)`、`result.get("url")` を消費
- 戻り値の None 許容を前提とした `if result:` 分岐あり

**設定機構**: `pydantic_settings` / `dotenv` の利用は grep で 0 件。全クライアントが `os.getenv` 直接利用（`api/lib/rakuten.py:7`, `api/lib/yahoo.py:7`, `api/common/database.py:6`）→ **新規 settings ローダは作らない**。

**主要差異**:
- 現在: 通信なし、署名なし、例外なし、None 返却
- 目標: POST + SigV4 + リトライ + 共通シェイプ dict 返却 / 失敗時例外

**参照資料の意図判断**: PA-API 5.0 仕様は「採用すべき設計アプローチ」、既存スタブは「維持すべき公開シグネチャの基準」。スコープを狭めない。

### スコープ

**変更**:
- `api/lib/amazon.py`（全面書き換え）
- `api/cron/update_prices.py`（Amazon 分岐に try/except 追加。楽天/Yahoo 分岐は無修正）
- `requirements.txt` または新規 `requirements-dev.txt`（テスト依存追加）
- `.env.example`（`AMAZON_*` の雛形を追記）

**新規**:
- `api/lib/aws_sigv4.py`（SigV4 純粋関数）
- `tests/__init__.py`, `tests/conftest.py`, `tests/unit/__init__.py`
- `tests/unit/test_amazon.py`, `tests/unit/test_aws_sigv4.py`
- `pytest.ini`

**変更しない**:
- `api/lib/rakuten.py`, `api/lib/yahoo.py`（タスクスコープ外）
- `api/main.py`, `vercel.json`（cron 経路は既存配線で成立）
- `api/common/models.py`, `api/common/database.py`

### 検討したアプローチ

| アプローチ | 採否 | 理由 |
|-----------|------|------|
| SigV4 を `amazon.py` 内のプライベート関数に閉じ込める | 不採用 | 1モジュール1責務違反。SigV4 は AWS 汎用ロジックで PA-API 固有ではない。order.md「署名生成ロジックの単独テスト」も別モジュールの方が直接的 |
| SigV4 を別モジュール `api/lib/aws_sigv4.py` に分離 | **採用** | 純粋関数で標準ライブラリのみ依存。テスト可能性・凝集度・将来再利用性で優位 |
| `boto3` / `botocore` 等の外部ライブラリで署名 | 不採用 | order.md 6節「サードパーティライブラリに頼らず標準ライブラリで実装してよい」+ 依存最小化 + テストしやすさ |
| HTTP モックに `respx` を導入 | 不採用 | 追加依存。`httpx.MockTransport` で同等のことが追加依存なしで可能 |
| HTTP モックに `httpx.MockTransport` + コンストラクタ DI | **採用** | 追加依存ゼロ。`AmazonAPI(transport=...)` で本番は省略・テスト時のみ注入 |
| `Optional[Dict]` 戻り値を維持し失敗時 None | 不採用 | order.md「失敗時は例外」「後方互換コードは含めない」明示違反 |
| 戻り値を `Dict`（成功）/例外（失敗）に変更 + 呼び出し元を try/except 化 | **採用** | 仕様準拠。呼び出し元の堅牢性は楽天/Yahoo と同等を維持 |
| `pydantic-settings` で設定ローダ新設 | 不採用 | 既存パターン（`os.getenv` 直接利用）が確立済。order.md「既存システムがあればそれを使う」相当 |
| 5xx もリトライ対象に含める | 不採用 | order.md は「429 および PA-API レート制限相当エラー」を指数バックオフ対象と明示。5xx は「429 以外の API エラー」として例外送出側に分類 |
| `MAX_RETRIES=5` | 不採用 | 課金 API。3 回で十分（指数バックオフで合計約 1+2+4=7秒の待機を許容） |
| `MAX_RETRIES=3` | **採用** | 妥当な上限。jitter 込みでサーバ負荷も配慮 |
| テスト依存を `requirements.txt` に混入 | 不採用 | Vercel ランタイムに不要な依存が乗る |
| テスト依存を `requirements-dev.txt` に分離 | **採用** | 本番ランタイムを汚さない |

### 実装アプローチ

1. **テスト基盤の整備**（write_tests ステップで実施）
   - `pytest.ini`（`asyncio_mode = auto`）
   - `requirements-dev.txt`（`pytest`, `pytest-asyncio`）
   - `tests/`, `tests/unit/`, `conftest.py`

2. **SigV4 純粋関数モジュール `api/lib/aws_sigv4.py`** を先に実装
   - 公開関数: `sign_request(method, host, path, headers, payload, access_key, secret_key, region, service, amz_date) -> str`（Authorization ヘッダ文字列を返す）
   - 内部関数（テスト容易にするため `_` 接頭辞だが import 可能）:
     - `_canonical_request(...)`
     - `_string_to_sign(...)`
     - `_signing_key(secret_key, date_stamp, region, service)`
     - `_signature(signing_key, string_to_sign)`
   - 標準ライブラリ `hmac` / `hashlib` / `urllib.parse` のみ使用

3. **`api/lib/amazon.py` 全面書き換え**
   - `class AmazonAPIError(Exception)` を定義
   - 定数: `PAAPI_HOST`, `PAAPI_PATH = "/paapi5/getitems"`, `PAAPI_TARGET`, `PAAPI_REGION = "us-west-2"`, `PAAPI_SERVICE = "ProductAdvertisingAPI"`, `MARKETPLACE = "www.amazon.co.jp"`, `PARTNER_TYPE = "Associates"`, `MAX_RETRIES = 3`, `RETRY_BASE_DELAY = 1.0`, `HTTP_TIMEOUT = 10.0`
   - `class AmazonAPI`:
     - `__init__(self, transport: Optional[httpx.AsyncBaseTransport] = None)`：env から認証情報を取得し、未設定なら即 `AmazonAPIError` 送出（境界での解決）
     - `async def fetch_product(self, asin: str) -> Dict`：`_build_payload` → `_post_with_retry` → `_format_response` の 3 段
     - `_build_payload(asin)` / `_format_response(asin, paapi_response)`：純粋関数寄りに切り出し
     - `_post_with_retry(payload)`：429 のみ指数バックオフ + jitter、その他は即例外。`async with httpx.AsyncClient(transport=self._transport, timeout=HTTP_TIMEOUT) as client:` でリーク防止
   - 共通シェイプ: `{"site": "amazon", "id": <asin>, "title": str, "price": int, "image_url": str|None, "url": str}`
   - `points` キーは PA-API 5.0 が直接提供しないため返さない（呼び出し元の `result.get("points", 0)` で default 0 が使われる。Why コメントで明記）

4. **`api/cron/update_prices.py` の軽微修正**
   - Amazon 分岐のみ `try: result = await api.fetch_product(...) except AmazonAPIError as e: logger.warning(...); result = None` でラップ
   - 楽天/Yahoo 分岐は無修正（タスクスコープ外）

5. **`.env.example` 追記**
   - `AMAZON_ACCESS_KEY=`, `AMAZON_SECRET_KEY=`, `AMAZON_PARTNER_TAG=` を追加

### 到達経路・起動条件

| 項目 | 内容 |
|------|------|
| 利用者が到達する入口 | バックエンド内部実装の差し替えのみで、新規利用者向け機能なし。既存導線: `vercel.json` の cron `/api/cron/update-prices`（毎時 0 分） → `api/main.py:22-36` → `api/cron/update_prices.py:14` → `AmazonAPI().fetch_product()` |
| 更新が必要な呼び出し元・配線 | `api/cron/update_prices.py:18-20`（Amazon 分岐を `try/except AmazonAPIError` でラップ）。本番呼び出し側の引数追加は不要（`AmazonAPI(transport=...)` の `transport` は既定 None でテスト専用） |
| 起動条件 | DB に `SiteType.AMAZON` の `EcSiteProduct` が存在し、Vercel Cron が `/api/cron/update-prices` を起動すること。環境変数 `AMAZON_ACCESS_KEY` / `AMAZON_SECRET_KEY` / `AMAZON_PARTNER_TAG` がすべて設定されていること（未設定なら `AmazonAPI()` 構築時点で `AmazonAPIError`） |
| 未対応項目 | なし（既存 cron 配線で成立） |

## 実装ガイドライン

- **参照すべき既存パターン**:
  - クライアントクラスの基本形: `api/lib/rakuten.py:1-39`, `api/lib/yahoo.py:1-40`（`__init__` で env 取得 → `async def fetch_product`）
  - 返却シェイプ: `api/lib/rakuten.py:29-36`（`{site, id, title, price, image_url, url}` を揃える）
  - 環境変数取得: `api/lib/rakuten.py:7`（`os.getenv` 直接利用）
  - 呼び出し元の消費パターン: `api/cron/update_prices.py:30-45`（`result["price"]`, `result.get("points", 0)`, `result.get("url")` を必ず満たす）

- **配線が必要な箇所（変更の影響範囲）**:
  - `AmazonAPI.fetch_product` の戻り値契約変更（`Optional[Dict]` → `Dict` or 例外）→ `api/cron/update_prices.py:18-27` を `try/except AmazonAPIError` でラップ
  - `AmazonAPI.__init__` への `transport` 引数追加 → 本番呼び出し元は省略可（既定 None）。テストのみ利用

- **境界での解決（Tell, Don't Ask）**:
  - 環境変数読み出しは `__init__` 内のみ。`fetch_product` 内で再度 `os.getenv` を呼ばない
  - 認証情報未設定時は `__init__` で即 `AmazonAPIError`。リクエスト時まで遅延させない

- **PA-API 5.0 仕様の固定値**:
  - URL: `https://webservices.amazon.co.jp/paapi5/getitems`（パス小文字）
  - `X-Amz-Target`: `com.amazon.paapi5.v1.ProductAdvertisingAPIv1.GetItems`
  - `Content-Type`: `application/json; charset=UTF-8`
  - `Content-Encoding`: `amz-1.0`
  - `Resources`: `["ItemInfo.Title", "Images.Primary.Large", "Offers.Listings.Price"]`
  - SignedHeaders: `content-encoding;host;x-amz-date;x-amz-target`（小文字 alphabet 順）

- **レスポンス整形マッピング**:
  | 共通キー | PA-API ソース |
  |---|---|
  | `site` | `"amazon"` 固定 |
  | `id` | `ItemsResult.Items[0].ASIN`（リクエスト ASIN と一致確認） |
  | `title` | `ItemsResult.Items[0].ItemInfo.Title.DisplayValue` |
  | `price` | `int(ItemsResult.Items[0].Offers.Listings[0].Price.Amount)` |
  | `image_url` | `ItemsResult.Items[0].Images.Primary.Large.URL`（欠落時 `None`） |
  | `url` | `ItemsResult.Items[0].DetailPageURL` |

- **エラー判定マトリクス**:
  - HTTP 429 → 指数バックオフでリトライ（最大 `MAX_RETRIES=3` 回）。上限超過で `AmazonAPIError`
  - HTTP 4xx (429除く) / 5xx → 即 `AmazonAPIError`
  - HTTP 200 with `Errors` 配列 → `AmazonAPIError`（`Errors[].Code`/`Message` をメッセージに含める）
  - HTTP 200 with 空 `Items` または該当 ASIN なし → `AmazonAPIError`

- **指数バックオフ**: `delay = RETRY_BASE_DELAY * 2 ** attempt + uniform(0, 0.1)`（`attempt` は 0,1,2）。`asyncio.sleep` を使用（テストでは `monkeypatch` で待機計測）

- **タイムアウト**: `httpx.AsyncClient(timeout=HTTP_TIMEOUT=10.0)` 必��（`agent-rules/12-security-guidelines.md`）

- **シークレット保護**:
  - `AccessKey` / `SecretKey` / 署名バイト列 / `Authorization` ヘッダ値を `print` / `logger` / 例外メッセージに **絶対に含めない**
  - 例外メッセージは ASIN / HTTP ステータス / PA-API `Errors[].Code`・`Message` までに留める

- **アンチパターン回避**:
  - 説明コメント（What/How）禁止。Why のみ（例: SigV4 の HMAC 連鎖順序が AWS 仕様である理由）
  - エラー握りつぶし禁止（楽天/Yahoo の `except Exception: print` パターンは Amazon では踏襲しない）
  - マジックナンバー禁止（リトライ回数・遅延・タイムアウトはすべて定数化）
  - TODO コメント禁止（`points` 未対応は「PA-API 5.0 がポイント値を直接提供しないため呼び出し元の default=0 に委ねる」を Why コメントで記録）
  - グローバル `httpx.AsyncClient` 共有禁止（`async with` でスコープ管理）

- **テスト実装方針（write_tests ステップへの先行ガイド）**:
  - `tests/unit/test_aws_sigv4.py` から書く（純粋関数で Red を明確化）
    - 段階別テスト: `_canonical_request` / `_string_to_sign` / `_signing_key` / `_signature` / `sign_request`（Authorization ヘッダ最終形）
    - 期待値は AWS 公式仕様の手順で事前計算した固定値。テストコメントで導出根拠を Why として残す
  - 続いて `tests/unit/test_amazon.py`（`httpx.MockTransport` で `AmazonAPI(transport=mock)` に DI）
    - 正常系: 送信リクエスト URL/ヘッダ/ボディが PA-API 5.0 仕様通り
    - 正常系: レスポンス JSON が共通シェイプに整形される
    - 異常系: 4xx/5xx で `AmazonAPIError`
    - 異常系: 200 with `Errors` で `AmazonAPIError`
    - 異常系: 200 with 空 `Items` で `AmazonAPIError`
    - リトライ: 429 → 200 で成功、`asyncio.sleep` 呼び出し回数・引数を検証
    - リトライ上限: 429 を `MAX_RETRIES` 回返した後 `AmazonAPIError`
    - 設定検証: 環境変数欠落時 `AmazonAPI()` 構築自体で `AmazonAPIError`（`monkeypatch.delenv`）
  - 実 API は呼ばない

- **ファイル行数目安**: `amazon.py` ≈ 150 行、`aws_sigv4.py` ≈ 80 行（知識「200行超で分割検討」の閾値内）

## スコープ外

| 項目 | 除外理由 |
|------|---------|
| 複数マーケットプレイス対応 | order.md「対象マーケットプレイスは日本のみ」明示 |
| 実 API を叩く統合テスト | order.md「テストはモックによる単体テストのみ」明示 |
| 後方互換コード（旧スタブ形を残す分岐等） | order.md「後方互換コードは含めない」明示 |
| 楽天/Yahoo クライアントの例外化リファクタ | タスクスコープ外。order.md は Amazon のみを対象 |
| `pydantic-settings` ベースの設定ローダ新設 | 既存パターン（`os.getenv` 直接利用）が確立済 |
| `points` フィールドの算出 | PA-API 5.0 が直接提供しない。Amazon Prime/カード還元は別文脈で扱う |
| `api/main.py` / `vercel.json` の cron 経路変更 | 既存配線で本実装が動作する |
| ASIN 複数指定の `GetItems` バッチ呼び出し | 既存呼び出し元 (`update_prices.py:14`) が 1 商品単位の逐次呼び出し前提 |

## 確認事項

なし（コードと仕様で全て解決済み）。