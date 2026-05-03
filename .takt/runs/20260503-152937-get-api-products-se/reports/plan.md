# タスク計画

## 元の要求

商品名と説明文を対象としたあいまい検索エンドポイント `GET /api/products/search` を新規実装する（`order.md`）。リクエストは `q`（必須・検索キーワード）と `limit`（任意・デフォルト10）。商品名 + 説明文に対するあいまい検索を関連度順で返却し、`limit` 件まで返す。検索エラー・該当なしを含むエラー時は空配列を返す。認証不要。レスポンスは既存商品スキーマ準拠。

## 分析結果

### 目的

`GET /api/products/search` を新設し、商品名・説明文に対するあいまい検索を、関連度順で `limit` 件まで返す HTTP API を提供する。エラーパスでも常に 200 + `[]` を返す堅牢なハンドラを既存 FastAPI バックエンド（`backend/`）に組み込む。

### 分解した要件

| # | 要件 | 種別 | 備考 |
|---|------|------|------|
| 1 | `GET /api/products/search` のルートを `backend/` の FastAPI アプリに登録する | 明示 | `order.md` 作業項目#3 |
| 2 | `q`（必須・string）クエリパラメータをパースする | 明示 | `order.md` リクエスト |
| 3 | `limit`（任意・number、デフォルト 10）クエリパラメータをパースする | 明示 | `order.md` リクエスト |
| 4 | `Product.name` を対象にあいまい検索を実行する | 明示 | `order.md` 検索ロジック |
| 5 | `Product.description` を対象にあいまい検索を実行する | 明示 | `order.md` 検索ロジック |
| 6 | 結果を関連度順（デフォルトソート）で返す | 明示 | `order.md` 検索ロジック |
| 7 | レスポンスは既存商品スキーマ準拠の配列とする | 明示 | `order.md` レスポンス |
| 8 | `limit` のみのページネーション（オフセット/ページ指定なし）に限定する | 明示 | `order.md` レスポンス |
| 9 | 検索エラー時は空配列を返す | 明示 | `order.md` エラー時挙動 |
| 10 | 該当なしの場合も空配列を返す | 明示 | `order.md` エラー時挙動 |
| 11 | 認証不要（ミドルウェア不要） | 明示 | `order.md` 認証 |
| 12 | `q` クエリパラメータと `limit` の Pydantic 型 / 既存型システムへの整合 | 明示 | `order.md` 中優先度#5 |
| 13 | レスポンス型は既存 `Product` スキーマを再利用する | 明示 | `order.md` 制約 |
| 14 | `Product` モデルに `description` カラムを追加する | 暗黙（要件5・テスト「説明文のみマッチ」由来） | `backend/models.py:55-64` に未存在のため、要件5を満たす前提として必要 |
| 15 | `analysis/models.py` の `Product` にも同じ `description` を同期追加する | 暗黙（要件14由来 + ADR-002） | `docs/adr/002-multi-container-architecture.md:18`「DBスキーマ変更時は Backend と Analysis の両方で同期が必要」 |
| 16 | `q` 正規化（トリム）と長さ上限（100文字）を設けて空・超過は空配列 | 暗黙（要件9・`order.md:77` 確認方法5・`12-security-guidelines.md:32`「想定サイズの上限を設定」由来） | 既存の他エンドポイント規約が無いため最小限の規約を新設 |
| 17 | `limit` の境界値（0 / 負値 / 非数値 / 上限超過）でも空配列または安全クランプで応答する | 暗黙（要件9・`order.md:57` 境界値テスト由来） | 422 を返さず 200+`[]` に統一 |

### 参照資料の調査結果

`order.md` 以外の外部実装は参照指定されていない。既存リポジトリ調査で以下を確認:

- **`backend/main.py:1-7`**: FastAPI `app` に `GET /` のウェルカム1本のみ。ルーティング規約・エラーハンドリング規約・バリデーション規約はいずれも未整備。
- **`backend/models.py:55-64`**: `Product` の現フィールドは `id`/`name(String 255)`/`jan_code`/`image_url`/`created_at` のみで、**`description` カラムは存在しない**。
- **`backend/database.py:10-15`**: `get_db()` ジェネレータが定義済。`Depends(get_db)` で再利用可能。
- **`backend/requirements.txt`**: `fastapi` `uvicorn[standard]` `sqlalchemy` `psycopg2-binary` `pydantic-settings` のみ。`pg_trgm` 連携や `rapidfuzz`、`pytest`、`httpx` は未導入。
- **`analysis/models.py`**: `backend/models.py` と完全同一（ADR-002 同期対象）。
- **`docs/adr/002-multi-container-architecture.md:18`**: スキーマ変更時の Backend/Analysis 同期義務を規定。
- **`db/init/`**: ディレクトリ自体が存在せず、Alembic/初期化スクリプトもなし。本番マイグレーション運用の前例は無い。

### スコープ

| 種別 | 対象 |
|---|---|
| 修正 | `backend/main.py`（ルータ取り込み）、`backend/models.py`（`description` 追加）、`analysis/models.py`（同期）、`backend/requirements.txt`（`pytest`/`httpx` 追加） |
| 新規 | `backend/schemas.py`、`backend/routers/__init__.py`、`backend/routers/products.py`、`backend/tests/__init__.py`、`backend/tests/conftest.py`、`backend/tests/test_product_search.py` |
| 影響範囲 | バックエンドAPIのみ。フロントエンド・スクレイパ・DB初期化スクリプトは変更なし |

### 検討したアプローチ

| アプローチ | 採否 | 理由 |
|-----------|------|------|
| PostgreSQL `pg_trgm` 拡張 + `similarity()` 関数 | 不採用 | DB 初期化スクリプト運用が無く、`CREATE EXTENSION` の管理コストを新規導入する必要がある。既存依存を増やさない方針に反する |
| Python `rapidfuzz` ライブラリで全件ロード後フィルタ | 不採用 | 全件メモリロードは性能劣化、依存追加。SQL に押し込めない |
| **PostgreSQL `ILIKE` + SQLAlchemy `case()` 重み付き relevance** | **採用** | 既存依存（`fastapi`/`sqlalchemy`/`psycopg2-binary`）のみで実現。SQLite 互換でテスト容易。仕様の「あいまい検索」を case-insensitive 部分一致 + 関連度ソートとして十分に表現できる |
| Postgres 全文検索（`tsvector` / `to_tsquery`） | 不採用 | 日本語形態素解析の整備が必要で導入コストが高い。本タスクのスコープを超える |
| `q`/`limit` バリデーション失敗時に 422 を返す（FastAPI 標準） | 不採用 | `order.md:23` でエラー時は空配列指定。422 では仕様違反になる |
| 全エラーパスを 200 + `[]` に統一（`try/except` + `RequestValidationError` ハンドラ） | 採用 | 仕様準拠を最優先 |
| `services/` 層を切る（router/service/schema の3層） | 不採用 | 1エンドポイントで「過度な抽象化や将来への備えは不要」原則に従いレイヤード簡略形（router 内に検索関数を置く）に留める |

### 実装アプローチ

1. **モデル拡張**: `backend/models.py` の `Product` に `description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)` を追加し、`from sqlalchemy import ... Text` を追記。`analysis/models.py` に同一変更を適用（ADR-002）。
2. **Pydantic スキーマ新設**: `backend/schemas.py` に `ProductOut(BaseModel)` を作成し、`Product` モデルの全フィールド（`id`/`name`/`description`/`jan_code`/`image_url`/`created_at`）を持たせる。`model_config = ConfigDict(from_attributes=True)` で ORM 直変換可能にする。
3. **ルータ作成**: `backend/routers/products.py` に `APIRouter(prefix="/api/products", tags=["products"])` を定義し、`@router.get("/search", response_model=list[ProductOut])` のハンドラを実装する。
   - 入力: `q: str | None = Query(None)`、`limit: int | None = Query(10)`、`db: Session = Depends(get_db)`
   - `q` を `strip()` し、空文字 / `None` / 100 文字超なら `[]` を返す
   - `limit` を `1..100` にクランプ。`<1` または `None` で `[]`（必須は `q` のみ）
   - SQLAlchemy で `ILIKE` パターン `f"%{q_escaped}%"`（`%` `_` `\` をエスケープ + `escape="\\"` 指定）を組み立て、`Product.name.ilike(...) | Product.description.ilike(...)` を `WHERE` 句に、`case()` で相対 relevance を計算して `ORDER BY` する
   - relevance: `name` 完全一致 = 4 / `name` 前方一致 = 3 / `name` 部分一致 = 2 / `description` 部分一致 = 1。`name`、`id` を tie-break に追加
   - 全体を `try/except Exception` で囲み、例外時は `logger.warning(..., exc_info=True)` の上 `[]` を返す
4. **アプリ配線**: `backend/main.py` で `from routers.products import router as products_router` し、`app.include_router(products_router)` を追加。
5. **バリデーションエラー吸収**: `backend/main.py` に `app.exception_handler(RequestValidationError)` を登録し、リクエストパスが `/api/products/search` の場合のみ `JSONResponse(status_code=200, content=[])` を返す（他のパスへの影響を避けるためパスでガード）。
6. **依存追加**: `backend/requirements.txt` に `pytest`、`httpx` を追加。
7. **テスト基盤**: `backend/tests/conftest.py` で SQLite in-memory エンジン + `Base.metadata.create_all` + `app.dependency_overrides[get_db]` の `TestClient` フィクスチャを用意。
8. **テスト記述**: `order.md:51-62` の必須テストケースに沿って単体（`search_products` 関数）と統合（`TestClient` 経由）の両層を網羅。

### 到達経路・起動条件

| 項目 | 内容 |
|------|------|
| 利用者が到達する入口 | HTTP クライアントから `GET http://<host>:${BACKEND_PORT:-8000}/api/products/search?q=<keyword>&limit=<n>` を直接呼び出す（`compose.yml:23` のポートマッピング経由）。フロントエンドからの呼び出し配線は本タスクスコープ外 |
| 更新が必要な呼び出し元・配線 | `backend/main.py` で `app.include_router(products_router)` を追加。これがないと 404。`backend/routers/__init__.py` のパッケージ化必須。`backend/main.py` の `RequestValidationError` ハンドラ登録 |
| 起動条件 | 認証ヘッダ不要・権限不要・フラグ不要。`BACKEND_PORT`（既定 8000）でリッスン中の FastAPI に対する直接 GET |
| 未対応項目 | フロントエンドからの呼び出し（`order.md` スコープ外）、本番Postgresへのスキーマ反映運用（既存にマイグレーション基盤がなく、本タスクで新設しない方針） |

## 実装ガイドライン

### 参照すべき既存実装パターン
- **モデル定義**: `backend/models.py:55-64` `Product` クラス。`description` 追加は `Mapped[Optional[str]] = mapped_column(Text, nullable=True)` の1行。`Text` 型は `from sqlalchemy import ... Text` に追加すること。
- **DBセッション取得**: `backend/database.py:10-15` の `get_db` をそのまま `Depends(get_db)` で利用。新規 DI を作らない。
- **enum/モデル命名**: `backend/models.py:13-23` のスタイルに合わせる（PascalCase クラス、snake_case カラム）。
- **ハンドラスタイル**: `backend/main.py:5-7`。I/O 待機がないため `async def` ではなく `def` で十分。

### 配線が必要な全箇所（漏れ禁止）
1. `backend/models.py` に `description` カラム追加 + `Text` import。
2. **`analysis/models.py` に同じ変更を同期適用**（ADR-002 違反防止）。漏らすと Analysis 側の Insert で列ズレが発生する。
3. `backend/schemas.py`（新規）で `ProductOut` 定義。
4. `backend/routers/products.py`（新規）で `APIRouter` と検索ハンドラ実装。
5. `backend/routers/__init__.py`（新規）。空でよいがパッケージ化に必須。
6. `backend/main.py` で `include_router(products_router)` と `RequestValidationError` ハンドラ登録。
7. `backend/requirements.txt` に `pytest` と `httpx` 追加（`TestClient` および `pytest` 起動に必須）。
8. `backend/tests/__init__.py` `backend/tests/conftest.py` `backend/tests/test_product_search.py`（新規）。

### 検索クエリ設計の固定要件
- `WHERE`: `Product.name.ilike(pattern) | Product.description.ilike(pattern)`。`pattern = f"%{escape_like(q)}%"`、`escape_like` は `\`/`%`/`_` を `\` でエスケープし、`.ilike(pattern, escape="\\")` で渡す。
- `ORDER BY`: `case((func.lower(Product.name) == q.lower(), 4), (func.lower(Product.name).like(f"{escape_like(q.lower())}%"), 3), (Product.name.ilike(pattern), 2), (Product.description.ilike(pattern), 1), else_=0).desc(), Product.name.asc(), Product.id.asc()`。
- `LIMIT`: クランプ後の `limit`。
- フィルタ・ソート・LIMIT は **すべて SQL 側に押し込む**。Python 側で `.all()` 後フィルタ禁止。

### `q` / `limit` の取り扱い規約
- `q`: トリム、空文字 / `None` / 100 文字超 → `[]`。長さ上限は `12-security-guidelines.md:32` 準拠。
- `limit`: 既定 10。`<1` → `[]`、`>100` → 100 にクランプ、非数値 → `RequestValidationError` 経由で `[]`。
- 全エラーは 200 + `[]` で返却（`order.md:23`）。

### 特に注意すべきアンチパターン
1. **SQLインジェクション対策の落とし穴**: SQLAlchemy `ilike` 自体はバインド変数化されるが、ユーザー入力に含まれる `%` `_` `\` はワイルドカード意味を変えるためエスケープ必須（上記 `escape_like` を実装）。
2. **全件ロード**: `db.query(Product).all()` してから Python で絞るのは禁止。
3. **422 を返す**: 仕様違反。`RequestValidationError` ハンドラでパスをガードして 200 + `[]` に変換すること。他パスは標準動作を維持。
4. **`analysis/models.py` の同期忘れ**: ADR-002 違反。
5. **`description IS NULL` の扱い**: `NULL ILIKE x` は条件から脱落するのが SQL 仕様。これは期待動作（説明なし商品は description 一致で返らない、name 一致なら返る）なので意図的。テストでカバーする。
6. **過剰ログ**: 例外時の `logger.warning("product search failed", exc_info=True)` 程度に留める。`q` の生値を INFO レベルで記録しない。
7. **`async def` の濫用**: SQLAlchemy 同期セッションを使うので `def` で書く。`async def` 内で同期I/Oを呼ぶとイベントループブロックの原因。

### テスト指針（write_tests への申し送り）
- 単体（`search_products` 関数直叩き）: 関連度順検証（name完全一致 > name前方一致 > name部分一致 > description部分一致）、`limit` 制限、ヒット0件、大文字/小文字、商品名のみ／説明文のみ／両方一致パターン。
- 統合（`TestClient` 経由）: 200応答、認証なし、レスポンスキー一致、`q` 省略 / 空 / 空白のみ / 101文字 / `limit=0` / `limit=-1` / `limit=abc` / `limit=9999` / DB 例外注入で常に 200 + `[]`。
- フィクスチャ: SQLite in-memory + `app.dependency_overrides[get_db]`。

### 制約照合
- `12-security-guidelines.md:32-44`: ORM + バインド変数で SQLi 対策、長さ上限設定 → 充足。
- `50-production-reliability.md:14-23`: 例外時の汎用フォールバック（`[]`）→ 充足。
- ナレッジ「1モジュール1責務」「200-400 行目安」→ 新規ファイルはすべて 100 行未満で収まる見込み。

## スコープ外

| 項目 | 除外理由 |
|------|---------|
| Alembic 等 DB マイグレーション基盤の整備 | 既存リポジトリに前例なく、`order.md` でも要求されていない。`Product.description` のスキーマ反映運用は別タスクに委ねる |
| 本番 Postgres への `description` カラム追加スクリプト（`db/init/*.sql` 等） | 同上。既存に `db/init/` 自体が存在せず、新規導入はスコープ拡大 |
| フロントエンド（`frontend/`）からの検索 UI/API 呼び出し配線 | `order.md` に記述なし |
| 認��・レート制限ミドルウェアの導入 | `order.md` で「認証不要」「レート制限指定なし」 |
| `analysis/` スクレイパが `description` を埋める処理 | スクレイパ仕様変更は `order.md` スコープ外。`description` は `Optional` のままで API は動作する |
| `pg_trgm` 等 PostgreSQL 拡張の導入 | 採用アプローチで不要。導入はスコープ拡大 |
| 他の商品関連エンドポイント（一覧・詳細・作成） | `order.md` で `/search` のみ要求 |

## 確認事項

なし。`order.md` 末尾の Open Questions（あいまい検索手段・`q` の最大長/正規化）は本計画で確定済み。`description` カラム不在問題は明示要求「説明文を対象に検索」「説明文のみマッチケースのテスト」から直接導かれる暗黙要求として ADR-002 同期込みで対処する。