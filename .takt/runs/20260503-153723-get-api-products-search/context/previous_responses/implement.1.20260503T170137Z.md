All expected files modified/created. Final summary:

## 作業結果
- 商品検索エンドポイント `GET /api/products/search` を Postgres FTS + pg_trgm 併用で新実装。
- 既存 `/api/products/search`（ILIKE + 全エラー 200+[]）を完全置換し、422 検証エラー応答と `{items, page, totalPages, totalCount}` envelope を導入。
- Postgres スキーマ変更を Alembic で管理する基盤を整備し、`analysis/models.py` を ADR-002 に従って同期。
- 既存テスト（write_tests ステップで作成済みの 52 ケース）を全てパス。

## 変更内容
**作成**
- `backend/repositories/__init__.py`、`backend/repositories/products.py`（`SearchParams` frozen dataclass + `search_products(db, params) -> (items, total)`、relevance スコア = `ts_rank + similarity`、トリガラム閾値 0.3、ページ 10件固定）
- `backend/alembic.ini`、`backend/alembic/env.py`、`backend/alembic/script.py.mako`
- `backend/alembic/versions/0001_initial_schema.py`（既存スキーマのベースライン化、enum は `DO ... duplicate_object` で冪等作成）
- `backend/alembic/versions/0002_product_search_columns.py`（`tags`/`in_stock`/`current_price`/`search_vector` 追加、`pg_trgm` 拡張、トリガで `search_vector` 維持、`immutable_array_to_string` ラッパー、tsvector GIN・trigram GIN・current_price B-tree インデックス）

**変更**
- `backend/models.py`：`Product` に `tags`/`in_stock`/`current_price`/`search_vector` 追加
- `analysis/models.py`：同一スキーマで同期
- `backend/schemas.py`：`ProductSummary`（camelCase エイリアス付き）、`ProductSearchEnvelope`（`totalPages`/`totalCount` エイリアス）追加
- `backend/routers/products.py`：旧仕様を完全置換。Query 引数の制約 + 横断的 `priceMin <= priceMax` チェック + `SearchParams` 構築 + envelope 組立。`q` の生値はログ非出力。
- `backend/main.py`：旧 `_request_validation_exception_handler` と `SEARCH_FULL_PATH` import を削除
- `backend/Dockerfile`：起動時 `alembic upgrade head` を実行
- `backend/requirements.txt`：`alembic`、`testcontainers[postgresql]` 追加

## ビルド結果
- Python の型チェックはプロジェクトに専用ツール（mypy 等）が定義されていないため、import 通過と FastAPI ルート登録（`/api/products/search` を含む 6 ルート）で代替確認。全 import 成功。
- `from main import app`、`from repositories.products import SearchParams, search_products`、`from schemas import ProductSummary, ProductSearchEnvelope`、analysis 側 `from models import Product` すべて正常ロード。

## テスト結果
- 実行コマンド: `pytest backend/tests/test_product_search.py`（Python 3.10、testcontainers 経由の Postgres 15-alpine、Alembic マイグレーション適用済み）
- 結果: **52 passed in 3.74s**（リポジトリ単体 18、エンドポイント結合 13、バリデーション 422 が 12、クエリ文字列契約 3、その他 6）
- レポート出力: `coder-scope.md`（変更スコープ宣言）、`coder-decisions.md`（生成カラム→トリガ転換、`immutable_array_to_string` 導入、enum 重複対処、camelCase エイリアス方針、`total_pages` 0件時の明示）