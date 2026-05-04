# 実装計画: 商品検索エンドポイント `GET /api/products/search`

## 1. 参照資料の確認結果

- **タスク指示書**: `.takt/runs/20260503-152937-get-api-products-se/context/task/order.md` を読了。`order.md` 単独構成（参照資料は他に指定されていない）。
- **既存コード調査結果**: バックエンド `backend/` は雛形のみで、ルーティング・Pydanticスキーマ・テスト基盤・DBマイグレーションすべて未整備。`backend/main.py:1-7` に `GET /` が1本あるのみ。
- **ADR**: `docs/adr/002-multi-container-architecture.md:18` で「DBスキーマの変更時に、BackendとAnalysisの両方で同期が必要」と規定されている。

## 2. 要件と既存コードのギャップ分析

| 要件 | 既存実装 | 判定 |
|---|---|---|
| `Product` の **商品名** 検索 | `backend/models.py:59` `name: String(255)` あり | OK |
| `Product` の **説明文** 検索 | **`description` カラム不在**（`backend/models.py:55-64` に `id`/`name`/`jan_code`/`image_url`/`created_at` のみ） | **要追加** |
| 既存ルーティング規約 | 未整備（`backend/main.py:5-7` にウェルカムのみ） | 新規策定 |
| 既存エラーハンドリング規約 | 未整備 | 新規策定 |
| 既存バリデーション規約 | 未整備 | 新規策定 |
| 既存商品スキーマ（Pydantic） | 未整備 | 新規策定（モデル準拠） |
| 既存あいまい検索基盤 | 未整備（`pg_trgm` 拡張も `rapidfuzz` も導入なし） | 新規選定 |
| テスト基盤 | 未整備（`backend/tests/` なし、`pytest` 未依存化） | 新規導入 |

> **要件分解の根拠**: 「商品名のみマッチ・説明文のみマッチ・両方マッチ各ケース」（`order.md:58`）が必須テストとして指示されているため、`description` カラムの追加は明示要求から直接導かれる暗黙要求である。

## 3. 技術選定（あいまい検索アルゴリズム）

| 候補 | 採否 | 理由 |
|---|---|---|
| `pg_trgm` + `similarity()` | ✗ | DB初期化スクリプト・拡張作成が未整備で導入コストが高い |
| `rapidfuzz` 等のPythonライブラリ | ✗ | 全件ロード前提で性能劣化、新規依存追加 |
| **PostgreSQL `ILIKE` + 重み付き relevance** | **✓** | 既存依存（FastAPI/SQLAlchemy/psycopg2）のみで実現、SQLite互換でテスト容易、十分な「あいまい性」 |
| Postgres全文検索 (`tsvector`) | ✗ | 日本語形態素未整備で実用性低 |

**relevance 計算（SQLAlchemy `case()` で SQL に押し込み）**:

| 順位 | 条件 | スコア |
|---|---|---|
| 1 | `name` が `q` と完全一致（大小無視） | 4 |
| 2 | `name` が `q` で始まる | 3 |
| 3 | `name` に `q` を含む | 2 |
| 4 | `description` に `q` を含む（`name` 一致せず） | 1 |
| 0 | いずれにも一致せず（`WHERE` で除外） | — |

`ORDER BY relevance DESC, name ASC, id ASC`（同点時の安定ソート）

## 4. ファイル構成

```
backend/
├── main.py                 # 既存修正: include_router 追加
├── models.py               # 既存修正: Product.description カラム追加
├── schemas.py              # 新規: Pydantic ProductOut
├── routers/
│   ├── __init__.py         # 新規: パッケージマーカー
│   └── products.py         # 新規: GET /api/products/search ハンドラ
├── requirements.txt        # 既存修正: pytest, httpx を追加
└── tests/
    ├── __init__.py         # 新規
    ├── conftest.py         # 新規: 一時SQLite + TestClient フィクスチャ
    └── test_product_search.py  # 新規: 単体 + ルーティング統合テスト

analysis/
└── models.py               # 既存修正: Product.description（ADR-002同期）
```

> **シンプル性根拠**: 1機能 1エンドポイントなので Vertical Slice まで切らず、ルータ層 + スキーマ層 + モデル層のレイヤード構成に留める。`services/` を増やすほどの分量はない（router 内に小さな private 関数で検索クエリを組み立てる）。

## 5. ハンドラ仕様

### エンドポイント
- パス: `GET /api/products/search`
- ルータ: `APIRouter(prefix="/api/products", tags=["products"])`
- 認証: なし（ミドルウェア未適用）

### クエリパラメータ
- `q: Optional[str] = Query(None)` — トリム後に空・None・100文字超なら `[]` を返す
- `limit: Optional[int] = Query(10)` — `1 ≤ limit ≤ 100` にクランプ。範囲外は `[]`、非数値（FastAPIが先に弾く可能性あり）は `try/except` で捕捉して `[]`

### バリデーション設計の根拠
- 仕様 `order.md:23` 「検索エラーや該当なしを含むエラー時は **空配列** を返却する」に従い、**全エラーパスで 200 + `[]`** を返す（422を返さない）。
- そのため `q`/`limit` を `Optional[str]` で受けず `Optional[int]` 等で受けても、`try/except Exception` で全体を覆って `[]` を返す方針。最大上限値はセキュリティガイド `12-security-guidelines.md:32` に基づき設定。

### レスポンス
- ステータス: 常に 200
- ボディ: `List[ProductOut]`
- `ProductOut` フィールド（既存 `Product` モデル準拠、`from_attributes=True`）:
  - `id: UUID`
  - `name: str`
  - `description: Optional[str]`
  - `jan_code: Optional[str]`
  - `image_url: Optional[str]`
  - `created_at: datetime`

### 検索ロジック（疑似コード）

```python
def search_products(db: Session, q: str, limit: int) -> list[Product]:
    pattern = f"%{q}%"
    name_lower = func.lower(Product.name)
    q_lower = q.lower()
    relevance = case(
        (name_lower == q_lower, 4),
        (name_lower.like(f"{q_lower}%"), 3),
        (Product.name.ilike(pattern), 2),
        (Product.description.ilike(pattern), 1),
        else_=0,
    )
    stmt = (
        select(Product)
        .where(or_(Product.name.ilike(pattern), Product.description.ilike(pattern)))
        .order_by(relevance.desc(), Product.name.asc(), Product.id.asc())
        .limit(limit)
    )
    return list(db.execute(stmt).scalars())
```

## 6. モデル変更詳細

`backend/models.py` および `analysis/models.py` の `Product`（行 55-64）に1行追加:

```python
description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
```

- 型は `String(N)` ではなく `Text`（説明文長は不定）
- `Text` を `from sqlalchemy import ...` に追加
- `Optional` は既存 import 済（`backend/models.py:4`）

> **DBマイグレーション**: 本リポジトリには Alembic 等のマイグレーション基盤が存在しない（`db/init/` も空）。`Product.description` の追加は新規スキーマ要件として `models.py` への追記のみ行う。テストは SQLAlchemy `Base.metadata.create_all` で SQLite に都度作成するため問題なし。本番Postgresへの反映手順は今回スコープ外（既存にマイグレーション運用が無いため、逸脱しない）。

## 7. 影響範囲

| ファイル | 変更種別 | 内容 |
|---|---|---|
| `backend/models.py` | 修正 | `Product` に `description` カラム + `Text` import |
| `analysis/models.py` | 修正 | 同上（ADR-002同期） |
| `backend/main.py` | 修正 | `from routers import products as products_router` + `app.include_router(products_router.router)` |
| `backend/schemas.py` | 新規 | `ProductOut` Pydantic モデル |
| `backend/routers/__init__.py` | 新規 | 空ファイル |
| `backend/routers/products.py` | 新規 | `APIRouter` + 検索ハンドラ + 検索クエリ関数 |
| `backend/requirements.txt` | 修正 | `pytest`, `httpx` 追加 |
| `backend/tests/__init__.py` | 新規 | 空ファイル |
| `backend/tests/conftest.py` | 新規 | テスト用エンジン/セッション/`TestClient` のフィクスチャ |
| `backend/tests/test_product_search.py` | 新規 | テスト本体 |

## 8. テスト方針（write_tests へ申し送り）

### 単体（DB直叩きの検索関数 `search_products`）
- 正常系: `q` ヒット、複数件返却、関連度順（name完全一致 > name前方一致 > name部分一致 > description部分一致）
- 正常系: `limit=N` で件数制限が効く
- 正常系: `limit` 未指定で10件まで
- 異常系: ヒット0件で `[]`
- 境界値: 大文字/小文字違いで一致（ILIKEの確認）
- マッチパターン: 商品名のみ／説明文のみ／両方一致のソート順

### ルーティング/統合（`TestClient` 経由）
- `GET /api/products/search?q=foo` → 200 + JSON配列
- `GET /api/products/search?q=foo&limit=3` → 最大3件
- 認証ヘッダなしで200（認証不要の確認）
- レスポンス各要素のキー集合が `ProductOut` と一致
- `q` 省略 → 200 + `[]`
- `q=""` → 200 + `[]`
- `q="   "`（空白のみ）→ 200 + `[]`
- `q` が101文字 → 200 + `[]`
- `limit=0` / `limit=-1` → 200 + `[]`
- `limit=abc` → 200 + `[]`（FastAPIの422を握り潰す）
- `limit=9999` → 100にクランプ（または100件以下で返却）
- DBエラー注入時（モンキーパッチで `db.execute` を例外化）→ 200 + `[]`、ログに記録

### 共通フィクスチャ
- `conftest.py` で SQLite in-memory + `Base.metadata.create_all` でテーブル作成
- 各テスト関数で seed データを Insert
- `app.dependency_overrides[get_db]` で DI 差し替え

## 9. Coder への実装ガイドライン

### 参照すべき既存パターン（ファイル:行）
- **モデル定義**: `backend/models.py:55-64` の `Product` クラスに `description` を追記する形で挿入。`Text` 型は `from sqlalchemy import ... Text` に足す。
- **DBセッション取得**: `backend/database.py:10-15` の `get_db` を `Depends(get_db)` で利用。新規作成不要。
- **SiteType 等のEnum宣言**: `backend/models.py:13-23` のスタイルに合わせる（今回は不要だが命名規約として参照）。
- **既存ハンドラの最小例**: `backend/main.py:5-7`。FastAPI 標準の関数定義スタイル（同期関数）に従う（`async def` は I/O 待機がないため不要）。

### 配線が必要な全箇所
1. `backend/models.py` に `description` 追加 → これにより SQLAlchemy 経由で読み取り可能になる。
2. `analysis/models.py` に同じ `description` を追加 → ADR-002 準拠。**忘れると Analysis 側のスクレイパが Insert する商品にカラム差分が発生する**。
3. `backend/schemas.py` に `ProductOut` を定義 → ハンドラ戻り値の型として使用。
4. `backend/routers/products.py` に `router = APIRouter(prefix="/api/products", tags=["products"])` を定義し、`@router.get("/search", response_model=list[ProductOut])` を実装。
5. `backend/main.py` で `app.include_router(products.router)` → これを忘れると 404。
6. `backend/requirements.txt` に `pytest` `httpx` を追加 → これを忘れると `TestClient` が落ちる、`pytest` が起動できない。

### 利用者の到達経路
- 利用者（API クライアント）は `GET http://localhost:8000/api/products/search?q=...` で到達。
- 入口は `backend/main.py` の FastAPI `app` → `include_router` 経由でのみ公開される。
- `compose.yml:23` でホスト `${BACKEND_PORT:-8000}` にマッピング済。Docker 設定変更は不要。

### 特に注意すべきアンチパターン
1. **SQLインジェクション**: `q` を生SQLに文字列結合しない。SQLAlchemy ORM の `ilike(pattern)` は内部でバインド変数化されるので安全。ただし `pattern = f"%{q}%"` の `%` 自体は LIKE のワイルドカードなので、`q` 内の `%` `_` は実装上エスケープしないと意味が変わる。**`q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")` でエスケープし、`.ilike(pattern, escape="\\")` を使うこと**。
2. **全件ロードしての Python フィルタ**: `db.query(Product).all()` してから Python 側で絞るのは禁止。必ず `WHERE` と `ORDER BY` を SQL に押し込む。
3. **422 を返す**: 仕様で全エラーパスが `[]` 200 OK と決まっている。Pydantic バリデーション失敗を握りつぶすために、`q`/`limit` をそのまま `Query()` で型強制せず、可能なら `int` バリデーション失敗を 422 でなく `[]` に変換する exception handler を追加するか、`limit` を `Optional[int]` に保ち FastAPI が 422 を返すケースは `app.exception_handler(RequestValidationError)` で当該パスのみ `[]` 化する。
4. **`analysis/models.py` 同期忘れ**: ADR-002 違反になる。
5. **`Optional` 取り扱い**: `Product.description.ilike(pattern)` は `description IS NULL` の行を「一致しない」と扱う（`NULL ILIKE x` は `NULL` で `WHERE` 条件から脱落）。これは期待動作（説明なし商品は description 一致では返らない、name 一致なら返る）。テストでカバーする。
6. **ログ出力でクエリ全文を出さない**: 仕様上は問題ないが、機密でなくても過剰ログにならないよう `logger.warning("product search failed", exc_info=True)` 程度に留める（`q` 値そのものを INFO 出力しない）。

### 設計上の制約照合
- セキュリティガイド `12-security-guidelines.md:34-44`: ORM 利用 + バインド変数化で SQLi 対策済 ✓
- セキュリティガイド `12-security-guidelines.md:32`: `q` の長さ上限（100文字）を設定 ✓
- 信頼性ガイド `50-production-reliability.md:14-23`: 例外時の汎用フォールバック（空配列）✓
- ナレッジ「1モジュール1責務」: ルータ層／スキーマ層／モデル層を分離 ✓
- ナレッジ「200-400行」: いずれの新規ファイルも100行未満で収まる見込み ✓

## 10. 確認事項

なし。仕様書末尾の Open Questions は本計画で確定:
- **あいまい検索手段** → SQLAlchemy `ilike` + 重み付き `case()` relevance
- **`q` 正規化** → 前後トリムのみ、最大100文字、超過時は `[]`、小文字化は `ilike` で吸収
- **`description` 不在問題** → 明示要求「説明文を対象に検索」「説明文のみマッチケースのテスト」から直接導かれるため `Product.description` を追加（ADR-002 に従い両 `models.py` を同期）