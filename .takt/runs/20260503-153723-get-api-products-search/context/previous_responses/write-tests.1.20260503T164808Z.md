Test collection produces exactly one error — the unimplemented `repositories.products` module — which the implementation step (Step 3) will create. All other expected dependencies (testcontainers, alembic, sqlalchemy, fastapi) load cleanly through the new conftest.

## 完了内容

### `backend/tests/conftest.py`（置換）
- testcontainers ベースの Postgres セッションスコープフィクスチャに刷新（FTS / pg_trgm / ARRAY が必要なため SQLite では不可）
- スキーマ適用は Alembic 経由（`alembic upgrade head`）
- `_clean_db` で `Base.metadata.sorted_tables` 単位の TRUNCATE（`alembic_version` は保護）
- `make_product` ファクトリを新フィールド（`tags`/`in_stock`/`current_price`）対応に拡張

### `backend/tests/test_product_search.py`（置換）
2 層構造で 40 件超のテスト：

**リポジトリ単体テスト** — `search_products(db, params) -> (items, total_count)`
- FTS 全文一致（name / description / tags）
- Trigram によるタイポ許容
- フィルタ（`in_stock`, `price_min`, `price_max` 個別 / 範囲, NULL 価格扱い）
- ソート（`relevance`, `price_asc`, `price_desc`, `newest`）
- ページネーション（10件固定、剰余、範囲外）

**エンドポイント結合テスト** — `GET /api/products/search`
- envelope 形状（`{items, page, totalPages, totalCount}`）
- レスポンス item の camelCase キー（`imageUrl`/`inStock`/`currentPrice`）
- 10件/page 固定 + `totalPages` 計算（剰余あり/ぴったり/ゼロ件）
- フィルタ（`inStock`, `priceMin`+`priceMax` 同時指定）
- ソート切替 + デフォルト = `relevance` の同値性
- タグ検索の E2E
- 認証不要

**バリデーション 422（旧仕様の 200+[] からの完全置換）**
- `q` 欠落 / 空文字 / 上限超
- `priceMin > priceMax`
- `priceMin/Max` の非数値 / 負数
- `sort` 値域違反
- `page` 0 / 負数 / 非数値（計 13 ケース）

**クエリストリング契約**（policy で求められた検証）
- `q` を request body に入れても 422（body は読まれない）
- レスポンス envelope 形状の body を入力として解釈しない
- body 経由のフィルタ値は無視される