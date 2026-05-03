# 実装計画: GET /api/products/search

## 1. 参照資料の確認

タスク指示書の「参照資料」セクションで指定された3つを確認した。

### 1-1. 既存設計書（`docs/`）
- `docs/system-design.md`: マイクロサービス構成（Frontend/Backend/Analysis/DB）。データモデル詳細は `backend/models.py` を正本としている。
- `docs/adr/001-tech-stack-selection.md`: FastAPI + PostgreSQL + Next.js
- `docs/adr/002-multi-container-architecture.md`: 「DBスキーマの変更時に、BackendとAnalysisの両方で同期が必要」と明記
- `docs/adr/003-playwright-scraping.md`: スクレイピング関連（本タスク対象外）

検索エンドポイントのレスポンス envelope や認証要否の規定はドキュメントに **存在しない**。これらは Planner 判断事項として委ねられている（指示書 67-74 行）。

### 1-2. 既存の商品関連エンドポイント実装
- `backend/main.py`: FastAPI アプリ本体。`RequestValidationError` を `/api/products/search` に限り `200 + []` に変換する handler が登録されている（main.py 12-21 行）。
- `backend/routers/products.py`: 既存の検索ハンドラ。**ILIKE ベースの実装**（products.py 53-92 行）。`q` と `limit` だけを受け、エラーは全て `200 + []` を返す。**現タスク仕様とは別物**（後述）。
- `backend/schemas.py`: `ProductOut` のみ。pydantic v2 の `from_attributes` 使用。
- `backend/database.py`: SQLAlchemy エンジン + `get_db` 依存性。
- `backend/models.py`: ORM 定義。

### 1-3. 既存マイグレーション
**存在しない**。`compose.yml` 11 行目で `./db/init:/docker-entrypoint-initdb.d` をマウントしているが、`./db/init` ディレクトリは未作成。スキーマは `Base.metadata.create_all()` 経由で生成されている前提。Alembic 等の正規マイグレーションフレームワークは未導入。

---

## 2. 現行コードと新仕様の差分

### 2-1. 既存実装は別タスクの成果物
`backend/tests/test_product_search.py` の冒頭コメント（2-6行）:
```
.takt/runs/20260503-152937-get-api-products-se/context/task/order.md
```
別 run（15:29）の order.md に対する成果物が現在のリポジトリにコミットされている。今タスク（15:37 run）の order.md は **異なる契約** を要求している。

| 項目 | 既存実装（旧 order.md） | 新 order.md |
|------|---------------------|------------|
| 検索方式 | ILIKE `%q%` | Postgres FTS（tsvector）+ Trigram（pg_trgm） |
| クエリパラメータ | `q`, `limit` | `q`（必須）, `inStock`, `priceMin`, `priceMax`, `sort`, `page` |
| ページネーション | `limit` のみ | 1ページ10件固定 + 総件数/現在ページ/総ページ数 envelope |
| 検索対象 | name + description | name + description + **tags** |
| エラー応答 | 全エラーで `200 + []` | バリデーションエラーは **エラー応答** |
| レスポンス形式 | bare array | envelope（オブジェクト） |
| 認証 | なし | Planner 判断（既存実装踏襲: なし） |

### 2-2. データモデルの不足
`backend/models.py` の `Product` には以下が **存在しない**:
- `tags`（新仕様で検索対象として明示）
- 在庫信号（`inStock` フィルタの根拠）
- 価格信号（`priceMin/priceMax` フィルタの根拠）

`PriceHistory` に `price` はあるが、Product 単位の集約価格を毎回 JOIN/サブクエリで算出するか、Product に denormalize するかは設計判断。

### 2-3. テスト基盤との非互換
`backend/tests/conftest.py` 4-6 行で `DATABASE_URL` を SQLite in-memory にピン止め。**SQLite は tsvector / pg_trgm を持たない**ため、新仕様のコア機能はテスト不能。新仕様に合わせるには Postgres ベースのテスト基盤に切り替える必要がある。

---

## 3. 要件分解と「変更要/不要」判定

明示要求のみを列挙する。一般論や将来拡張は含めない。

| # | 明示要求 | 変更要否 | 根拠 |
|---|----------|---------|------|
| R1 | `GET /api/products/search` を提供 | 変更要 | 既存ハンドラの契約が新仕様と異なる（旧: `q`, `limit` のみ） |
| R2 | `q` 必須、未指定はバリデーションエラー | 変更要 | 既存は `q` 未指定で `200 + []` を返す（products.py 101-102 行） |
| R3 | `inStock`, `priceMin`, `priceMax`, `sort`, `page` 受付 | 変更要 | 既存ハンドラは未対応（products.py 95-99 行） |
| R4 | Postgres FTS + Trigram 併用 | 変更要 | 既存は ILIKE のみ（products.py 53-92 行） |
| R5 | 検索対象に **tags** を含む | 変更要 | `Product` モデルに `tags` カラムなし（models.py 55-65 行） |
| R6 | 1ページ10件固定 + 総件数/現在ページ/総ページ数 | 変更要 | 既存は bare array、ページング/件数情報なし |
| R7 | `inStock` フィルタ | 変更要 | 在庫信号がモデルに存在しない |
| R8 | `priceMin`, `priceMax` フィルタ | 変更要 | 価格信号は `PriceHistory.price` のみで集約未提供 |
| R9 | バリデーションエラー時のエラーレスポンス | 変更要 | 既存は `RequestValidationError` を `200 + []` に変換（main.py 12-21 行） |
| R10 | GIN 等インデックスのマイグレーション | 変更要 | マイグレーションフレームワーク自体が未導入 |
| R11 | 商品サマリのみを返却 | 変更要 | 具体フィールド未確定（既存 `ProductOut` 流用は応答 envelope で再評価） |

明示要求から直接導ける暗黙要求:
- **R12 (R5 から派生)**: `tags` カラム追加に伴う `analysis/models.py` の追従（ADR-002 で明文化された同期義務）
- **R13 (R10 から派生)**: マイグレーションフレームワーク（Alembic）の導入。タスク指示書「マイグレーション」を実行可能にするための前提整備
- **R14 (R4, R7, R8 から派生)**: テスト基盤の Postgres 化。SQLite では tsvector/pg_trgm/ARRAY/`in_stock` 集約のいずれも検証不能

---

## 4. 設計判断（Planner 委任事項への結論）

指示書 67-74 行で Planner に委ねられた判断と、その結論。

### 4-1. ディレクトリ・ファイル配置
既存は `routers/` のみのレイヤード構成。検索クエリは複雑化するため、**Repository 層を新設**:
```
backend/
├── routers/
│   └── products.py        ← ハンドラ（バリデーション + 呼び出し）
├── repositories/
│   ├── __init__.py        ← 新規
│   └── products.py        ← 新規: 検索クエリビルダ
├── schemas.py             ← 拡張: 新エンベロープ + サマリ
├── models.py              ← 拡張: tags / in_stock / current_price / search_vector
├── alembic/               ← 新規
│   ├── env.py
│   ├── script.py.mako
│   └── versions/
│       ├── 0001_initial_schema.py
│       └── 0002_product_search_columns.py
├── alembic.ini            ← 新規
└── tests/                 ← 新規: Postgres ベース conftest に書き直し
```

ナレッジ「操作の一覧性」「Controller→Service→Repository」に基づく構造選択。検索固有のクエリ組み立てを Repository に集約することで、ハンドラがバリデーションと配線のみに専念できる。

### 4-2. ソート選択肢
既存設計書に規定なし。最小限で必要十分な4種:
- `relevance`（既定。FTS rank + trigram similarity の合計スコア降順）
- `price_asc` / `price_desc`（`current_price` ベース。NULL は末尾）
- `newest`（`created_at` 降順）

### 4-3. 返却サマリのフィールド
`ProductOut` をそのまま��用せず、**検索結果用の `ProductSummary` を schemas.py に追加**:
- `id`, `name`, `description`, `imageUrl`, `tags`, `inStock`, `currentPrice`
- `jan_code` と `created_at` は除外（サマリの意図に合わない）

camelCase は FastAPI の `alias_generator=to_camel` か pydantic `Field(alias=...)` で吸収（`ProductOut` の方針との不整合を生まないよう、ProductSummary は別クラスで定義）。

### 4-4. 認証要否
ADR や設計書に規定なし。既存検索エンドポイントも未認証。商品検索はリードオンリーかつ匿名ユースケースが想定される（フロントの SSR ホームページ等）。**未認証で公開**。

### 4-5. FTS と Trigram の併用方式
**OR 結合 + スコア合算順**:
```sql
WHERE search_vector @@ websearch_to_tsquery('simple', :q)
   OR similarity(searchable_text, :q) > 0.1
ORDER BY (
   ts_rank(search_vector, websearch_to_tsquery('simple', :q))
   + similarity(searchable_text, :q)
) DESC, products.id ASC
```
UNION より単純で 1パスで済み、ts_rank と similarity を線形結合した relevance スコアが自然。`websearch_to_tsquery` を採用するのは、ユーザー入力をそのままパースできて記号で例外を投げないため。

### 4-6. レスポンス envelope
既存 API に envelope の前例なし（`/api/products/search` は bare list、ルート `/` は `{"message": ...}`）。新仕様で必須なため新設:
```json
{
  "items": [ProductSummary, ...],
  "page": 1,
  "totalPages": 5,
  "totalCount": 47
}
```

### 4-7. インデックス設計
- `search_vector tsvector` を **生成カラム**（`GENERATED ALWAYS AS ... STORED`）として `Product` に追加。GIN インデックスを張る。
- Trigram 用に `pg_trgm` 拡張を有効化（マイグレーションで `CREATE EXTENSION IF NOT EXISTS pg_trgm`）し、`searchable_text` 式 GIN インデックス（`gin_trgm_ops`）を作成。
- `current_price` に通常の B-tree インデックス（`price_asc/desc` ソートと priceMin/Max フィルタ用）。

`search_vector` 生成式: `to_tsvector('simple', coalesce(name,'') || ' ' || coalesce(description,'') || ' ' || coalesce(array_to_string(tags,' '),''))`。

### 4-8. データモデル拡張
`Product` に4カラムを追加（denormalize を採用）:
- `tags: list[str]` — `ARRAY(String)`、デフォルト空配列
- `in_stock: bool` — デフォルト `True`
- `current_price: Optional[int]` — 円単位、デフォルト NULL
- `search_vector` — generated tsvector（SQLAlchemy の `Computed` で表現）

`current_price` と `in_stock` の同期責務は **本タスク対象外**（analysis サービスが PriceHistory/EcSiteProduct から更新する想定）。テスト/シードでは直接設定する。

`analysis/models.py` も同じカラムを追加（ADR-002 同期義務）。

### 4-9. マイグレーション戦略
Alembic を新規導入する。
- `0001_initial_schema.py`: 現行スキーマ全体をベースラインとして起こす。
- `0002_product_search_columns.py`: `pg_trgm` 拡張、`tags`/`in_stock`/`current_price` 追加、`search_vector` 生成カラム追加、tsvector GIN、trigram GIN、`current_price` B-tree。

`compose.yml` の `./db/init` マウントは Alembic 経由運用に切り替えるか、`db/init/00_extensions.sql` で `pg_trgm` だけ先打ちにする選択肢があるが、**全工程を Alembic に寄せる**（再現性が高い）。`backend/Dockerfile` で起動時に `alembic upgrade head` を実行するエントリポイントスクリプトを追加。

### 4-10. テスト基盤
SQLite を完全に廃止し、**testcontainers-python** で Postgres コンテナを spin up:
- 旧 `conftest.py`（SQLite）を置き換え
- session スコープで Postgres コンテナを1つ立ち上げ、関数スコープでスキーマを recreate
- testcontainers と psycopg2 を test 依存に追加

`docker compose` ベースの統合テスト（compose 環境内で pytest 実行）も併用可能だが、本タスクでは testcontainers のみで完結させる。

### 4-11. バリデーション仕様（FastAPI Query 制約）
- `q`: `min_length=1`, `max_length=100`（前後空白は trim 後に長さ判定）
- `priceMin`, `priceMax`: `ge=0` の `int`。両方指定時は `priceMin <= priceMax`（モデルで検証して 422）
- `inStock`: `bool`（FastAPI が `"true"/"false"` を自動変換）
- `sort`: `Literal["relevance", "price_asc", "price_desc", "newest"]`、未指定は `relevance`
- `page`: `int, ge=1`、未指定は `1`

違反は FastAPI 既定の 422（`{"detail": [...]}`）でエラー応答する。**`main.py` の `RequestValidationError` 変換ハンドラは削除**（旧仕様の遺物）。

### 4-12. ロギング
- `q` をそのままログに残さない（既存実装の方針 products.py 116-118 行を踏襲）
- `len(q)`, ヒット件数, 経過 ms を info ログに出す
- DB 例外は `logger.exception` で記録し、500 として伝播

### 4-13. エラーハンドリング
DB 例外を握りつぶさない（旧仕様の `try/except → []` を撤去）。FastAPI 既定の 500 で応答。アンチパターン「エラー握りつぶし」（ナレッジ）に該当するため。

---

## 5. 実装ガイドライン（Coder 向け）

### 5-1. 参照すべき既存実装パターン
- **ルーティング規約**: `backend/routers/products.py` 27-40 行（`APIRouter(prefix=...)`, `tags=`, パス定数化）
- **依存注入**: `backend/routers/products.py` 99 行（`db: Session = Depends(get_db)`）
- **応答スキーマ**: `backend/schemas.py` 16-29 行（`ConfigDict(from_attributes=True)`, Optional の扱い）
- **モデル定義**: `backend/models.py` 55-65 行（`Mapped[uuid.UUID]`, `mapped_column(UUID(as_uuid=True), primary_key=True)`）
- **ロガー**: `backend/routers/products.py` 23 行（`logging.getLogger(__name__)`）

### 5-2. 削除対象（旧仕様の残骸）
- `backend/main.py` 12-21 行: `_request_validation_exception_handler`（旧仕様の `200 + []` 変換）→ 削除
- `backend/main.py` 6 行: `SEARCH_FULL_PATH` の import → 削除（旧 handler 専用）
- `backend/routers/products.py` 既存 `search_products` / `search_products_endpoint` / `_escape_like` / `Q_MAX_LENGTH` 等の定数 → **新実装で置換**（後方互換不要）
- `backend/tests/test_product_search.py` 全体 → 新仕様のテストに置換（write_tests ステップで実施）
- `backend/tests/conftest.py` SQLite 構成 → testcontainers Postgres に置換（write_tests ステップで実施）

### 5-3. 新規・変更ファイル一覧

| ファイル | 区分 | 概要 |
|---------|------|------|
| `backend/models.py` | 変更 | `Product` に `tags`, `in_stock`, `current_price`, `search_vector` を追加 |
| `analysis/models.py` | 変更 | 上記と同期（ADR-002） |
| `backend/schemas.py` | 変更 | `ProductSummary`, `ProductSearchEnvelope` を追加。`ProductOut` は現状維持 |
| `backend/repositories/__init__.py` | 新規 | 空 |
| `backend/repositories/products.py` | 新規 | `search_products(db, params) -> tuple[Sequence[Product], int]` を実装 |
| `backend/routers/products.py` | 変更 | エンドポイントを新仕様に書き換え。バリデーションは Query パラメータ制約 + pydantic validator |
| `backend/main.py` | 変更 | 旧 `RequestValidationError` ハンドラを削除 |
| `backend/alembic.ini` | 新規 | Alembic 設定 |
| `backend/alembic/env.py` | 新規 | DB URL を `os.environ["DATABASE_URL"]` から取得 |
| `backend/alembic/script.py.mako` | 新規 | テンプレート |
| `backend/alembic/versions/0001_initial_schema.py` | 新規 | 既存テーブルのベースラインマイグレーション |
| `backend/alembic/versions/0002_product_search_columns.py` | 新規 | `pg_trgm` 拡張、tags/in_stock/current_price/search_vector 追加、各種 GIN インデックス |
| `backend/Dockerfile` | 変更 | 起���前に `alembic upgrade head` |
| `backend/requirements.txt` | 変更 | `alembic`, `testcontainers[postgresql]`, `pytest-asyncio` 等を追加 |

### 5-4. 配線が必要な全箇所（呼び出しチェーン検証）

新パラメータ（`inStock`, `priceMin`, `priceMax`, `sort`, `page`）について、以下の経路を貫通させる:

1. `backend/routers/products.py` `search_products_endpoint`: Query で受け取り、`SearchParams` dataclass/pydantic に正規化
2. `backend/repositories/products.py` `search_products(db, params)`: `SearchParams` を引数で受け取る（**`options.xxx ?? fallback` のような後段補完を作らない**）
3. SQL 構築: フィルタ → relevance スコア → ORDER BY → COUNT → LIMIT/OFFSET の順で組み立て、フィルタ未指定時は WHERE 句に追加しない（None チェック）
4. レスポンス: `ProductSearchEnvelope(items, page, totalPages, totalCount)` を組み立てて返す

ナレッジ「呼び出しチェーン検証」「フェーズ分離」に従い、**ハンドラで `SearchParams` に解決し、Repository は解決済みの値だけを扱う** こと。Repository 内で `params.priceMin or 0` のような後段補完を書かない。

### 5-5. このタスクで特に注意すべきアンチパターン

- **エラー握りつぶし禁止**: 旧コードの `try/except: return []` パターン（products.py 113-119 行）を踏襲しない。DB 例外は伝播させ、ログに記録する。
- **denormalize されたカラムの直接更新を search 側で行わない**: `current_price`, `in_stock` の更新責務は本タスク外（analysis サービス／seed が担う）。検索コードからは読み取りのみ。
- **TODO コメント禁止**: 「将来 analysis サービスから更新する」と書きたくなるが、実装するか削除するかの二択。今回は読み取りのみ実装で完結させる。
- **配線漏れ**: 5つのクエリパラメータ全てがハンドラ → Repository まで届いているか、テストで明示的に検証する（write_tests で network of params をカバーすること）。
- **状態の直接変更**: `SearchParams` は frozen dataclass ないし pydantic の `model_config = ConfigDict(frozen=True)` で immutable に保つ。
- **生 SQL の文字列結合禁止**: `q` の値はパラメータバインド経由でのみ DB に渡す（agent-rules 12 のSQLインジェクション対策）。`websearch_to_tsquery(:q)` のように bind パラメータで渡す。

### 5-6. 利用者向け機能の到達経路
本エンドポイントはフロントエンド（Next.js）から `GET /api/products/search` で呼び出される。**入口は単一のクエリパラメータ付き GET リクエスト**で、認証ヘッダ不要。ルーティング規約上の到達経路は `main.py:app.include_router(products_router)` のみ。**起動条件・呼び出し元の追加変更は不要**（既存 `include_router` がそのまま新ハンドラを公開する）。

OpenAPI スキーマは FastAPI が自動生成する。Frontend 側の型同期（ADR-001 影響）は本タスクスコープ外（指示書「やらないこと」記載なしだが、明示要求にも含まれない）。

### 5-7. テスト観点（write_tests ステップへの引き渡し）
- バリデーション境界値: `q` の長さ 0/1/100/101、`page` の 0/1、`priceMin > priceMax`、`sort` 不正値、`priceMin/Max` の負数・非数値
- FTS 一致: 完全一致・部分単語一致 → ヒット
- Trigram 一致: タイポを含むクエリでヒット（指示書 56 行）
- フィルタ: `inStock=true` で在庫ありのみ、`priceMin/Max` で範囲、複合
- ソート: `relevance`/`price_asc`/`price_desc`/`newest` の順序
- ページネーション: `page=1, 2, 3` の境界、`totalPages` の計算（10件/page）
- 認証: 未認証で 200
- DB エラー: 例外は 500 で伝播（旧仕様の握りつぶしは廃止された）
- セキュリティ: `q="' OR 1=1 --"` のような入力で SQL インジェクションが起きない
- レスポンス契約: envelope の `items`/`page`/`totalPages`/`totalCount` の型

---

## 6. 確認事項

ユーザーにしか答えられない質問のみ列挙する。コードで答えが出る事項は本計画内で結論済み。

特になし。指示書 81-82 行で「未解決事項なし」と明示されており、Planner 判断事項（67-74 行）は全て本計画 §4 で結論を出した。

---

## 7. スコープサマリ

| カテゴリ | 内容 |
|---------|------|
| 新規ファイル | `backend/repositories/products.py`, `backend/repositories/__init__.py`, Alembic 一式（`alembic.ini` + `env.py` + `script.py.mako` + 2 マイグレーション） |
| 変更ファイル | `backend/models.py`, `analysis/models.py`, `backend/schemas.py`, `backend/routers/products.py`, `backend/main.py`, `backend/Dockerfile`, `backend/requirements.txt`, `backend/tests/conftest.py`, `backend/tests/test_product_search.py` |
| 変更規模見積 | Medium（200-500 行） |
| 後方互換 | 不要（旧仕様の `q`/`limit` 契約は完全に置換） |
| 削除対象 | `main.py` の旧 RequestValidationError ハンドラ、`routers/products.py` の旧 search ロジック、旧テストファイル全体、SQLite ベースの conftest |