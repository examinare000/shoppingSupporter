# タスク完了サマリー

## タスク
`GET /api/products/search` を Postgres FTS（tsvector）+ Trigram（pg_trgm）併用で実装し、商品名・説明文・タグを対象にしたページネーション付き検索 API を提供する。

## 結果
完了

## 変更内容

| 種別 | ファイル | 概要 |
|------|---------|------|
| 作成 | `backend/repositories/__init__.py` | リポジトリ層の名前空間 |
| 作成 | `backend/repositories/products.py` | `SearchParams`（frozen dataclass）と `search_products(db, params) -> (items, total_count)`。FTS と Trigram を OR 結合し relevance スコア = `ts_rank + similarity` で合算。トリガラム閾値 0.3、ページサイズ 10 |
| 作成 | `backend/alembic.ini` | Alembic 設定 |
| 作成 | `backend/alembic/env.py` | Alembic 実行環境 |
| 作成 | `backend/alembic/script.py.mako` | マイグレーションテンプレート |
| 作成 | `backend/alembic/versions/0001_initial_schema.py` | 既存スキーマのベースライン化、enum を `DO ... duplicate_object` で冪等作成 |
| 作成 | `backend/alembic/versions/0002_product_search_columns.py` | `tags`/`in_stock`/`current_price`/`search_vector` 追加、`pg_trgm` 拡張、`immutable_array_to_string` ラッパー、トリガで `search_vector` 維持、tsvector GIN / trigram GIN / current_price B-tree |
| 変更 | `backend/models.py` | `Product` に `tags` (ARRAY[String])/`in_stock` (Boolean)/`current_price` (Integer, Optional)/`search_vector` (TSVECTOR) 追加 |
| 変更 | `analysis/models.py` | ADR-002 に従い `Product` モデルを backend と同期 |
| 変更 | `backend/schemas.py` | `ProductSummary`（`imageUrl`/`inStock`/`currentPrice` を `Field(serialization_alias=...)` で camelCase 化）と `ProductSearchEnvelope`（`totalPages`/`totalCount` 同上）を追加。旧 `ProductOut` を削除 |
| 変更 | `backend/routers/products.py` | 旧仕様を完全置換。`Query` 制約 + 横断的 `priceMin <= priceMax` チェック + `SearchParams` 構築 + envelope 組立。`q` 生値はログ非出力 |
| 変更 | `backend/main.py` | 旧 `_request_validation_exception_handler` と `SEARCH_FULL_PATH` import を削除 |
| 変更 | `backend/Dockerfile` | 起動時に `alembic upgrade head` を実行 |
| 変更 | `backend/requirements.txt` | `alembic`、`testcontainers[postgresql]` 追加 |
| 変更 | `backend/tests/conftest.py` | testcontainers Postgres + Alembic 適用ベースに置換、`make_product` ファクトリを `tags`/`in_stock`/`current_price` 対応 |
| 変更 | `backend/tests/test_product_search.py` | 新仕様向けに 52 ケースで全置換（リポジトリ 18 + エンドポイント 25 + バリデーション 12 + クエリ文字列契約 3 など） |

## 検証証跡

- **要件充足**: タスク指示書（`order.md`）から抽出した 36 要件すべてを実コードで個別照合し充足を確認（`reports/supervisor-validation.md` の要件充足チェック表）
- **テスト**: `pytest backend/tests/test_product_search.py` → **52 passed in 3.74s**（`implement.1.20260503T170137Z.md:30-31`）。Python 3.10 + testcontainers Postgres 15-alpine + Alembic 適用済み環境で実行。ai-fix 後の再実行は環境制約により未実施（`ai-fix.1.20260503T171136Z.md:38`）だが、ai-fix の修正範囲（未参照 `ProductOut` 削除、到達不能 `if sort not in ALLOWED_SORTS` 削除、到達不能 `if params.page < 1` 削除、無効効 `populate_by_name=True` 削除）はテストが観測する振る舞いに影響しないため回帰なしと判断
- **ビルド/import**: `from main import app`、`from repositories.products import SearchParams, search_products`、`from schemas import ProductSummary, ProductSearchEnvelope`、`from models import Product`（analysis 側）すべて正常ロード。`/api/products/search` を含む 6 ルート登録確認（`implement.1.20260503T170137Z.md:26-27`）。ai-fix 後に 3 ファイル `python3 -m ast.parse` syntax OK（`ai-fix.1.20260503T171136Z.md:38`）
- **動作確認**: テスト経由 `client.get(ENDPOINT, params={"q": "..."})` で 25 ケースの統合テストを実行（`backend/tests/test_product_search.py:372-729`）。envelope 形状・camelCase キー（`imageUrl`/`inStock`/`currentPrice`/`totalPages`/`totalCount`）・ページネーション境界（25 件で page=3 → 5 件、20 件で totalPages=2、0 件で totalPages=0、page=999 echo）・FTS（name/description/tags 各経路）・Trigram タイポ・フィルタ複合・ソート 4 種・デフォルト=relevance 同値性・認証不要・422 検証 13 ケース・クエリ文字列契約 3 ケースを実行確認
- **AI レビュー**: 2 周目で APPROVE（`reports/ai-review.md`）。1 周目の 4 件指摘（dead-code/dead-defense/misleading-comment）はすべて resolved
- **スコープクリープ**: なし。削除コードはすべて `plan.md:106-110` の「削除対象（後方互換不要）」に明記済み