# Amazon PA-API 5.0 本実装 — Plan レポート

## 1. 参照資料の読み込み（実施結果）

| 参照 | 状態 | 確認内容 |
|---|---|---|
| `.takt/.../context/task/order.md` | ✅ Read済 | 本タスクの Primary spec |
| `.takt/.../context/knowledge/plan.1.20260503T172204Z.md` | ✅ Read済 | アーキテクチャ知識 |
| `agent-rules/00-core-principles.md` / `11-testing-strategy.md` / `12-security-guidelines.md` / `50-production-reliability.md` / `13-readability.md` / `91-claude-subagent-coding.md` | ✅ Read済 | 全エージェント制約 |
| `.takt/.../context/previous_responses/` | 空 | 差し戻しなし（初回 plan） |

タスク指示書の「参照資料の正本」は **PA-API 5.0 公式仕様** と **既存スタブ `amazon.py` のシグネチャ**。前者は外部仕様、後者は `api/lib/amazon.py:1-19` で実コード確認済。

## 2. 既存実装の確認

### 2.1 既存スタブ（`api/lib/amazon.py:1-19`）

```python
class AmazonAPI:
    def __init__(self):
        self.access_key = os.getenv("AMAZON_ACCESS_KEY")
        self.secret_key = os.getenv("AMAZON_SECRET_KEY")
        self.partner_tag = os.getenv("AMAZON_PARTNER_TAG")
        self.host = "webservices.amazon.co.jp"
        self.region = "us-west-2"

    async def fetch_product(self, asin: str) -> Optional[Dict]:
        print(f"Fetching Amazon product: {asin} (Stub)")
        return None
```

- **公開 API**: `AmazonAPI()` コンストラクタ（無引数）と `fetch_product(asin: str) -> Optional[Dict]`
- **環境変数**: `AMAZON_ACCESS_KEY` / `AMAZON_SECRET_KEY` / `AMAZON_PARTNER_TAG`
- **設定値**: `host=webservices.amazon.co.jp` / `region=us-west-2`（PA-API 5.0 JP の公式値と一致）

### 2.2 呼び出し元（`Grep amazon` で全件確認）

唯一の Python 呼び出し元は `api/cron/update_prices.py:18-20, 30-45`：

```python
if site_product.site_type == SiteType.AMAZON:
    api = AmazonAPI()
    result = await api.fetch_product(site_product.site_product_id)
...
if result:
    price_history = PriceHistory(price=result["price"], points=result.get("points", 0), ...)
    if result.get("url"):
        site_product.url = result["url"]
```

呼び出し元が消費するキー：

| キー | 必須 | 型 | 用途 |
|---|---|---|---|
| `result["price"]` | ✅ 必須 | `int` | `PriceHistory.price` |
| `result["points"]` | 任意 (default 0) | `int` | `PriceHistory.points` |
| `result["url"]` | 任意 | `str` | `EcSiteProduct.url` 上書き |

### 2.3 楽天/Yahoo クライアントの返却形（`api/lib/rakuten.py:29-36`, `api/lib/yahoo.py:30-37`）

両者は共通形 `{"site", "id", "title", "price", "image_url", "url"}` を返却。Amazon もこの **共通シェイプ** に合わせる（呼び出し元の現行消費キー `price`/`url`/`points` を含むスーパーセット）。

### 2.4 既存設定機構

- `pydantic_settings` / `BaseSettings` / `dotenv` の利用は **コードベースに無し**（grep 結果: matches none）
- 全クライアントが `os.getenv("...")` を直接利用（`api/lib/rakuten.py:7`, `api/lib/yahoo.py:7`, `api/common/database.py:6`）
- → **既存パターン踏襲**：`os.getenv` をそのまま使う。新規 settings ローダは作らない

### 2.5 既存テスト構成

- `tests/` ディレクトリ・`pytest.ini`・`pyproject.toml`・`conftest.py` のいずれも **存在しない**（Python テストはフロントの Vitest のみ）
- `requirements.txt`: `fastapi`, `uvicorn[standard]`, `sqlalchemy`, `psycopg2-binary`, `pydantic-settings`, `httpx`
- → Python 単体テスト基盤を **新設する必要がある**

### 2.6 既存例外

- Amazon 専用例外は無し
- 楽天/Yahoo は `except Exception as e: print(...); return None` で握り潰し（task 指示「失敗時は例外」の方針と矛盾する設計だが、Amazon のみ修正対象）
- → **新規例外 `AmazonAPIError`** を `api/lib/amazon.py` に定義

## 3. 要件 vs 現状の差分判定

| # | 要件（order.md より） | 変更要否 | 根拠 |
|---|---|---|---|
| R1 | スタブを PA-API 5.0 実通信に置換 | **要** | `amazon.py:13-18` が `print` + `return None` |
| R2 | AWS SigV4 署名 | **要** | 既存実装なし（grep でも未検出） |
| R3 | エンドポイント `https://webservices.amazon.co.jp/paapi5/<operation>` | **要** | スタブには URL 構築なし。`host` のみ存在 |
| R4 | 必須ヘッダ生成（`X-Amz-Date` 等） | **要** | 既存実装なし |
| R5 | レスポンスを共通シェイプに整形 | **要** | スタブは `None` を返す |
| R6 | 429 で指数バックオフリトライ | **要** | リトライ機構なし |
| R7 | 4xx/5xx・PA-API `Errors` で例外送出 | **要** | 例外型なし／握り潰し動作 |
| R8 | 単体テスト（モックのみ） | **要** | テスト基盤自体が不在 |
| R9 | 設定/認証情報取得 | **不要** | `amazon.py:7-9` で既に `os.getenv` 経由（既存パターンに整合） |
| R10 | host / region | **不要** | `amazon.py:10-11` が既に `webservices.amazon.co.jp` / `us-west-2` |
| R11 | `.env` ローダ新設 | **不要** | 既存全クライアントが `os.getenv` 直接利用、`README.md:62-67` も `.env` 配置のみ案内（明示要件「既存があればそれを使う」に該当） |
| R12 | `httpx` 追加 | **不要** | `requirements.txt:6` で導入済 |
| R13 | `Optional[Dict]` 返却契約の見直し | **要（破壊的）** | order.md「失敗時は例外」「後方互換コードは含めない」より、戻り値は `Dict`（成功）または例外（失敗）。呼び出し元 `update_prices.py:14-47` を例外捕捉に修正 |

### 3.1 参照資料の意図判断

参照資料は **PA-API 5.0 公式仕様**（外部仕様）と **既存スタブ**（インターフェース基準）。前者は「採用すべき設計アプローチ」、後者は「維持すべき接点」。スコープを狭めない。

### 3.2 暗黙要求の根拠

| 暗黙要求 | 根拠となる明示要求 |
|---|---|
| 共通シェイプ `{site, id, title, price, image_url, url}` で返す | order.md「呼び出し元が期待する構造も plan で確定」+ 楽天/Yahoo クライアントの実装パターン |
| `update_prices.py` の `try/except` 追加 | order.md「呼び出し元すべてが新しい実装で問題なく動作する」+ 「失敗時は例外を投げる」の両立。1商品の失敗で cron 全体が落ちないようにする |
| 単体テスト基盤の新設（`pytest`, `pytest-asyncio`） | order.md「単体テスト作成」+ 既存 Python テスト基盤不在 |

## 4. 設計

### 4.1 ファイル構成（新規・変更）

```
api/lib/
├── amazon.py            # ★全面書き換え：AmazonAPI クラス + AmazonAPIError + リクエスト構築/レスポンス整形
└── aws_sigv4.py         # ★新規：AWS Signature V4 署名（純粋関数群）

api/cron/
└── update_prices.py     # 軽微修正：Amazon 呼び出しを try/except でラップ

tests/                   # ★新規ディレクトリ
├── __init__.py
├── conftest.py          # 共通フィクスチャ（環境変数設定 / 固定タイムスタンプ）
└── unit/
    ├── __init__.py
    ├── test_amazon.py        # AmazonAPI のリクエスト/レスポンス/リトライ/例外テスト
    └── test_aws_sigv4.py     # SigV4 段階別テスト（CanonicalRequest / StringToSign / SigningKey / Signature / Authorization）

pytest.ini               # ★新規：asyncio_mode=auto 等の最小設定
requirements.txt         # 軽微更新：pytest, pytest-asyncio をテスト用に追加
.env.example             # 軽微更新：AMAZON_ACCESS_KEY 系の雛形を追記
```

#### 4.1.1 `aws_sigv4.py` を別モジュ���ルにする理由

- 1モジュール1責務（知識: 構造・設計）。SigV4 は AWS 汎用認証ロジックで、Amazon PA-API 固有の知識ではない
- **テスト容易性**: order.md 5節「AWS Signature V4 署名生成ロジックの単独テスト」を直接サポート。署名関数を import してテスト可能
- 純粋関数のみ（`hmac` / `hashlib` / 標準ライブラリのみ依存）。amazon.py から `from .aws_sigv4 import sign_request` で利用

#### 4.1.2 `amazon.py` 内構成

```
amazon.py:
  - class AmazonAPIError(Exception)              # 新規例外
  - 定数: PAAPI_HOST, PAAPI_REGION, PAAPI_SERVICE,
          MARKETPLACE, PARTNER_TYPE,
          MAX_RETRIES (= 3), RETRY_BASE_DELAY (= 1.0)
  - class AmazonAPI:
      __init__(self, transport: Optional[httpx.AsyncBaseTransport] = None)
        # transport は DI for テスト。本番は None で素のクライアント
      async fetch_product(self, asin: str) -> Dict
        # GetItems を1ASIN分呼び出し、共通シェイプを返す。失敗時は AmazonAPIError
      async _post_with_retry(self, operation, payload) -> dict
        # 指数バックオフを内包
      _build_payload(self, asin: str) -> dict
      _format_response(self, asin: str, paapi_response: dict) -> Dict
```

責務:
- **`AmazonAPI` クラス**: PA-API ドメイン（GetItems 呼び出し、レスポンス整形、リトライ制御）
- **`aws_sigv4.py`**: AWS 認証ドメイン（純粋）
- **`AmazonAPIError`**: ドメイン例外

行数見積: amazon.py 約 150 行、aws_sigv4.py 約 80 行 → 知識「200行超で分割検討」の閾値内。

### 4.2 PA-API 5.0 仕様準拠

- **オペレーション**: `GetItems`（ASIN 単一指定）
- **URL**: `https://webservices.amazon.co.jp/paapi5/getitems`（パスは小文字）
- **必須ヘッダ**:
  - `Host: webservices.amazon.co.jp`
  - `Content-Type: application/json; charset=UTF-8`
  - `Content-Encoding: amz-1.0`
  - `X-Amz-Date: <YYYYMMDDTHHMMSSZ>`（UTC）
  - `X-Amz-Target: com.amazon.paapi5.v1.ProductAdvertisingAPIv1.GetItems`
  - `Authorization: AWS4-HMAC-SHA256 Credential=..., SignedHeaders=..., Signature=...`
- **ペイロード**:
  ```json
  {
    "ItemIds": ["<ASIN>"],
    "ItemIdType": "ASIN",
    "PartnerTag": "<PARTNER_TAG>",
    "PartnerType": "Associates",
    "Marketplace": "www.amazon.co.jp",
    "Resources": [
      "ItemInfo.Title",
      "Images.Primary.Large",
      "Offers.Listings.Price"
    ]
  }
  ```
- **SigV4**:
  - `service = "ProductAdvertisingAPI"`
  - `region = "us-west-2"`
  - 標準手順: CanonicalRequest → StringToSign → SigningKey（`AWS4`+SecretKey → date → region → service → `aws4_request` の順に HMAC-SHA256） → Signature（StringToSign を SigningKey で HMAC-SHA256）
  - SignedHeaders: `content-encoding;host;x-amz-date;x-amz-target`（小文字 alphabet 順）

### 4.3 レスポンス整形（共通シェイプ）

PA-API 5.0 の正常レスポンス → 楽天/Yahoo と揃った辞書：

| 共通キー | PA-API 5.0 のソース | 備考 |
|---|---|---|
| `site` | `"amazon"` 固定 | |
| `id` | `Items[0].ASIN` | リクエスト ASIN と一致確認 |
| `title` | `Items[0].ItemInfo.Title.DisplayValue` | |
| `price` | `Items[0].Offers.Listings[0].Price.Amount`（整数化） | JPY は整数。`Amount` は number で来るので `int(...)` |
| `image_url` | `Items[0].Images.Primary.Large.URL` | 欠落時 `None` |
| `url` | `Items[0].DetailPageURL` | |

`points` キーは PA-API 5.0 仕様に該当データ無し。Amazon Prime/カードは別文脈で計算するため **本タスクのスコープ外**。呼び出し元 `update_prices.py:34` の `result.get("points", 0)` は default 0 で動作するので互換維持。

### 4.4 エラー判定とリトライ

```
HTTP 429
  → 指数バックオフでリトライ。MAX_RETRIES (=3) 回まで
  → 上限超過で AmazonAPIError 送出

HTTP 5xx
  → AmazonAPIError 送出（リトライしない／設計判断: 課金 API なので副作用最小に）

HTTP 4xx (429除く)
  → AmazonAPIError 送出（リトライしない）

HTTP 200 with body 内 "Errors" 配列
  → AmazonAPIError 送出（PA-API のドメイン例外）

HTTP 200 with "ItemsResult.Items"=[] または該当 ASIN なし
  → AmazonAPIError 送出（明示的に「ASIN not found」を含む）
```

- **バックオフ式**: `delay = RETRY_BASE_DELAY * 2 ** attempt + uniform(0, 0.1)`（attempt は 0,1,2）
- **タイムアウト**: `httpx.AsyncClient(timeout=10.0)`（`agent-rules/12-security-guidelines.md` の「全外部呼び出しにタイムアウト」遵守）
- **例外メッセージ**: シークレット（AccessKey/SecretKey/SignatureBytes）を絶対に含めない（`agent-rules/12-security-guidelines.md`）

### 4.5 認証情報の境界解決（知識: 境界での解決）

`AmazonAPI.__init__` 内で **必須環境変数の存在検証**を行い、未設定時は `AmazonAPIError("認証情報が未設定です: <KEY>")` を即座に送出する（リクエスト時まで遅延させない）。これにより `fetch_product` 内ロジックは「解決済み認証情報」のみを前提とする。

## 5. 実装ガイドライン（Coder 向け）

### 5.1 参照すべき既存実装パターン

| 観点 | 参照先 | 注意点 |
|---|---|---|
| クライアントクラスの基本構造 | `api/lib/rakuten.py:1-39` / `api/lib/yahoo.py:1-40` | `AmazonAPI` も同じ形（`__init__` で env 取得 → `async def fetch_product`）を維持 |
| 返却シェイプ | `api/lib/rakuten.py:29-36` の dict | `site/id/title/price/image_url/url` を揃える |
| `httpx.AsyncClient` 利用 | `api/lib/rakuten.py:21-25` | ただし Amazon は **POST + JSON body + 署名済ヘッダ** であり GET ではない |
| 環境変数取得 | `api/lib/rakuten.py:7` / `api/common/database.py:6` | `os.getenv` 直接利用。settings ローダは新設しない |
| 呼び出し元の消費パターン | `api/cron/update_prices.py:30-45` | `result["price"]`, `result.get("points", 0)`, `result.get("url")` を必ず満たすこと |

### 5.2 変更の影響範囲（配線必要箇所）

| 変更内容 | 配線が必要な箇所 |
|---|---|
| `AmazonAPI.fetch_product` の戻り値契約変更（`Optional[Dict]` → 例外 or `Dict`） | `api/cron/update_prices.py:18-27` を `try/except AmazonAPIError` でラップし、失敗時は `result = None` 相当に落として既存の `if result:` 分岐に流す（楽天/Yahoo と同じ堅牢性を Amazon でも担保） |
| `AmazonAPI.__init__` への `transport` 引数追加 | 本番呼び出し元 `update_prices.py:19` は引数省略（既定 None）なので無修正。テストのみが利用 |
| `requirements.txt` 更新（pytest 系） | CI / Vercel ビルド設定への影響を確認。`requirements.txt` は本番ランタイム向けなので、テスト専用依存は別ファイル `requirements-dev.txt` に分離するのが望ましい（`pytest`, `pytest-asyncio` のみ） |
| `.env.example` 更新 | README は既に `AMAZON_ACCESS_KEY` 系を案内済み（`README.md:67`）。例ファイル側に追記して整合 |
| 新規 `api/lib/aws_sigv4.py` | `amazon.py` のみが import。他クライアントは利用しない |

### 5.3 テスト方針（write_tests ステップ向けの先行ガイド）

**HTTP モック手法**: `httpx.MockTransport` を使い、`AmazonAPI(transport=mock_transport)` で DI。追加依存なし。

**`test_aws_sigv4.py` の段階別検証**（order.md 5節準拠）:

1. CanonicalRequest 生成: 固定入力（method=POST, path=/paapi5/getitems, headers, body）に対し期待文字列をアサート
2. StringToSign 生成: 固定 timestamp + 固定 CanonicalRequest hash で期待文字列をアサート
3. SigningKey 生成: `AWS4`+SecretKey → date → region → service → `aws4_request` の HMAC 連鎖で期待バイト列
4. Signature 生成: SigningKey ��� StringToSign で HMAC-SHA256 → 期待 hex 文字列
5. Authorization ヘッダ組立: `AWS4-HMAC-SHA256 Credential=..., SignedHeaders=..., Signature=...` の最終形

期待値は **AWS SigV4 公式テストベクター**または **手計算で固定**（テストコメントで導出根拠を Why コメントとして残す）。

**`test_amazon.py` のケース**:

- 正常系: モック 200 + 仕様通り JSON を返し、共通シェイプが組み立てられる
- 正常系: 送信されたリクエスト URL/ヘッダ/ボディが PA-API 5.0 仕様通り（`MockTransport` で受信側を検査）
- 異常系: 404, 500 で `AmazonAPIError` 送出
- 異常系: 200 with `Errors` 配列で `AmazonAPIError` 送出
- 異常系: 200 with 空 `Items` で `AmazonAPIError` 送出
- リトライ: 429 → 200 で成功し、`asyncio.sleep` が呼ばれた回数・引数を検証（`monkeypatch` で sleep を計測）
- リトライ上限: 429 を MAX_RETRIES 回返した後 `AmazonAPIError`
- 設定検証: 環境変数欠落時 `AmazonAPI()` 構築自体で `AmazonAPIError`

**実 API は呼ばない**（order.md 制約）。

### 5.4 アンチパターンの回避

知識ファイル `plan.1.20260503T172204Z.md` から本タスクで特に該当するもの：

| アンチパターン | 本タスクでの注意 |
|---|---|
| 説明コメント（What/How） | SigV4 各段階に「なぜこの順序で HMAC を連鎖するか（AWS 仕様）」のような Why コメントのみ。`# Compute the canonical request` のような言い換えコメントは禁止 |
| エラー握りつぶし | 楽天/Yahoo の `except Exception: print` パターンは **Amazon では踏襲しない**。例外型を明示し、ログは `logging` モジュールで構造化（task 制約「失敗時は例外」） |
| マジックナンバー | `MAX_RETRIES=3`, `RETRY_BASE_DELAY=1.0` は定数化し由来コメント。ヘッダ名・サービス名・リージョンも定数化 |
| TODO コメント | 禁止。`points` フィールドが未対応な点は「PA-API 5.0 はポイント値を直接提供しないため呼び出し元の default=0 に委ねる」を Why コメントで記述（コード削除ではなく仕様記録） |
| DRY 違反 | SigV4 ロジックを `amazon.py` に書かず `aws_sigv4.py` へ分離（仮に楽天/Yahoo がいずれ AWS を使ってもこの層を共有可能） |
| 隠れた依存 | `os.getenv` を `__init__` でだけ呼ぶ。`fetch_product` 内で再度 env を読まない（境界での解決） |
| シークレットのログ出力 | `AccessKey/SecretKey/Authorization` ヘッダ・署名バイト列を `print`/`logger` に絶対渡さない。例外メッセージは ASIN・HTTP ステータス・PA-API `Errors[].Code/Message` までに留める |
| グローバル `httpx.AsyncClient` の共有 | スコープ内で `async with httpx.AsyncClient(...) as client:` を使い、リーク防止 |

### 5.5 利用者向け到達経路

本タスクは **バックエンド内部実装の差し替え** で、フロントエンドの新機能ではない。利用者導線への影響：

| 経路 | 状態 |
|---|---|
| `vercel.json` の cron 設定 `/api/cron/update-prices`（毎時 0 分） | 変更不要。既存設定で `AmazonAPI` が呼ばれる |
| `api/main.py` の `trigger_update_prices` エンドポイント | 変更不要。`update_site_product` を経由 |
| `api/cron/update_prices.py:18-20` の Amazon 分岐 | **変更**：`try/except AmazonAPIError` でラップ |

→ 利用者が新機能に到達する条件は「DB に `SiteType.AMAZON` の `EcSiteProduct` が存在し、cron が実行される」こと。これは既存配線で成立しており、新たな入口を追加する必要はない。

## 6. 確認事項

なし。コードと仕様で全て解決済み。

## 7. 次ステップ（write_tests）への申し送り

1. テスト基盤（`pytest.ini`, `tests/__init__.py`, `tests/unit/__init__.py`, `conftest.py`）を最初に配置
2. `requirements-dev.txt` を新設（`pytest`, `pytest-asyncio`）
3. `tests/unit/test_aws_sigv4.py` から書く（純粋関数、最小依存、SigV4 仕様の Red を明確化）
4. 続いて `tests/unit/test_amazon.py`（`MockTransport` でリクエスト検査・レスポンス整形・リトライ・例外）
5. 環境変数欠落ケースは `monkeypatch.delenv` を使用
6. すべて Red を確認してから implement ステップへ