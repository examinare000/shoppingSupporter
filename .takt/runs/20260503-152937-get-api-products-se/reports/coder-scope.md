# 変更スコープ宣言

## タスク
`GET /api/products/search` エンドポイントの実装（あいまい検索 + 関連度順 + 全エラー 200+`[]` フォールバック）。

## 変更予定
| 種別 | ファイル |
|------|---------|
| 変更 | `backend/main.py` |
| 変更 | `backend/models.py` |
| 変更 | `backend/requirements.txt` |
| 変更 | `analysis/models.py` |
| 変更 | `backend/tests/test_product_search.py` |
| 作成 | `backend/schemas.py` |
| 作成 | `backend/routers/__init__.py` |
| 作成 | `backend/routers/products.py` |

## 推定規模
Medium

## 影響範囲
- バックエンド API: `/api/products/search` を新設。`APIRouter(prefix="/api/products")` を `main.py` に登録。
- 商品スキーマ: `Product` モデルに `description: Optional[str]` (Text, nullable) を追加。ADR-002 に従い `backend/models.py` と `analysis/models.py` の両方を同期更新。
- 例外処理: `RequestValidationError` ハンドラを `main.py` に登録。`/api/products/search` パスのみ 200+`[]` に変換、他パスは FastAPI 既定の 422 動作を維持。
- レスポンス契約: 新規 `ProductOut` Pydantic schema が `Product` ORM 列を 1:1 公開（`id`, `name`, `description`, `jan_code`, `image_url`, `created_at`）。
- 依存関係: `backend/requirements.txt` に `pytest`, `httpx` を追加（`TestClient` 起動に必須）。
- テスト: 既存 `tests/test_product_search.py` の 1 テストを httpx 0.20+ API 整合のため `client.request("GET", ..., json=...)` に書き換え（修正理由は `coder-decisions.md` に記録）。
- フロントエンド・スクレイパ・DB 初期化スクリプト・認証ミドルウェアは変更なし（`order.md` スコープ外）。