# 変更スコープ宣言

## タスク
`GET /api/products/search` を FTS + Trigram + envelope ページネーション仕様に置換する実装一式

## 変更予定
| 種別 | ファイル |
|------|---------|
| 変更 | `backend/models.py`（`Product` に `tags`/`in_stock`/`current_price`/`search_vector` 追加） |
| 変更 | `analysis/models.py`（ADR-002 同期） |
| 変更 | `backend/schemas.py`（`ProductSummary`/`ProductSearchEnvelope` 追加） |
| 作成 | `backend/repositories/__init__.py` |
| 作成 | `backend/repositories/products.py`（`SearchParams`/`search_products`） |
| 変更 | `backend/routers/products.py`（旧仕様を完全置換） |
| 変更 | `backend/main.py`（旧 422→200 ハンドラ削除） |
| 作成 | `backend/alembic.ini` |
| 作成 | `backend/alembic/env.py` |
| 作成 | `backend/alembic/script.py.mako` |
| 作成 | `backend/alembic/versions/0001_initial_schema.py` |
| 作成 | `backend/alembic/versions/0002_product_search_columns.py` |
| 変更 | `backend/Dockerfile`（起動時 `alembic upgrade head`） |
| 変更 | `backend/requirements.txt`（`alembic`/`testcontainers[postgresql]`） |

## 推定規模
Medium（200-500 行）

## 影響範囲
- backend の検索 API（フロント側型同期はスコープ外）
- analysis サービスのモデル定義（DB スキーマ整合のため）
- テスト基盤（既に conftest.py が testcontainers + Alembic 前提に置換済み）