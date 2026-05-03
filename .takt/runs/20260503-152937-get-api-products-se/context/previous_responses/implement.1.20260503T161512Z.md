## 自己チェック

- 新パラメータ`description`の伝搬: `Product`モデル（backend/analysis両方）→ `ProductOut` → `search_products` の SQL 列参照、すべて確認済み。
- `??` / `||` / デフォルト引数の濫用: なし。`Query(default=None)` / `Query(default=LIMIT_DEFAULT)` は FastAPI の必須宣言の枠組み内で、`q` の `None` ガードは即 `[]` 返却（フォールバックではなく明示的なエラーパス）。
- リファクタリングで残ったコード: `main.py` を上書きしたので残骸なし。
- タスク指示書にない機能追加: なし。description カラム追加は order.md の「説明文を対象に検索」要件から導かれる。
- if/else で同じ関数を引数違いで呼ぶ二重化: なし。
- 既存パターンとの一貫性: `Depends(get_db)` を再利用し、router 命名・スタイルは plan.md 指示通り。

## 作業結果
- `GET /api/products/search` のあいまい検索エンドポイントを実装。
- `Product` モデルに `description` カラムを Backend と Analysis の両方に同期追加（ADR-002 準拠）。
- `RequestValidationError` ハンドラを `/api/products/search` パスに限定して 200+`[]` に変換するよう登録。
- 全エラーパス（`q` 未指定 / 空文字 / 空白 / 101文字超 / `limit<1` / 非数値 `limit` / DB 例外）を 200+`[]` に統一。
- httpx API 変更に伴うテスト1件を `client.request("GET", ..., json=...)` 形式に修正（理由は coder-decisions.md に記録）。

## 変更内容
- **`backend/models.py`**: `Product.description: Optional[str]` を `Text` カラムで追加。`Text` を import 追加。
- **`analysis/models.py`**: 同上（ADR-002 同期）。
- **`backend/schemas.py`** (新規): `ProductOut` Pydantic schema を定義。`from_attributes=True` で ORM 直変換。
- **`backend/routers/__init__.py`** (新規): 空のパッケージマーカー。
- **`backend/routers/products.py`** (新規): `APIRouter(prefix="/api/products")` と `search_products(db, q, limit)` ヘルパ + `GET /search` ハンドラ。`ILIKE` + `case` 4段 relevance + name/id タイブレーク + `\` エスケープを SQL 側に push。
- **`backend/main.py`**: `include_router(products_router)` と `RequestValidationError` ハンドラ（`SEARCH_FULL_PATH` 限定で 200+`[]`、他パスはデフォルトハンドラへ委譲）を追加。
- **`backend/requirements.txt`**: `pytest`, `httpx` 追加。
- **`backend/tests/test_product_search.py`**: 1テストを `client.request("GET", ..., json=...)` 形式に修正（httpx API 整合）。

## ビルド結果
- `python -m py_compile` 全変更ファイル → OK（構文エラーなし）。
- import 整合確認（`main`, `routers.products`, `schemas`, `models`）→ OK。
- `ProductOut.model_fields` と `Product` の DB カラム集合が完全一致を実機確認: `{id, name, description, jan_code, image_url, created_at}`。

## テスト結果
- 実行コマンド: `python -m pytest backend/tests/ -v`
- 結果: **31 passed, 0 failed, 0 errors** (210 warnings は SQLAlchemy 内部の `datetime.utcnow()` deprecation で本タスクスコープ外)
- 内訳: 単体11 + 統合20 = 31、すべて期待通りの振る舞いを確認。