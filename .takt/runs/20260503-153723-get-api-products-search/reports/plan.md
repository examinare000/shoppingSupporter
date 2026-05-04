# タスク計画

## 元の要求
`GET /api/products/search` を実装し、商品名・説明文・タグを対象にした Postgres 全文検索 + Trigram 併用の検索 API を提供する。クエリパラメータは `q`（必須）、`inStock`、`priceMin`、`priceMax`、`sort`、`page`。1ページ10件固定、レスポンスに総件数・現在ページ・総ページ数を含める。Postgres FTS（tsvector/tsquery）と Trigram（pg_trgm）を併用し、検索対象は商品名・説明文・タグ。必要なインデックス（GIN等）のマイグレーションも本タスクのスコープ。

## 分析結果

### 目的
新仕様の `/api/products/search` を提供する。FTS と Trigram の併用により、完全単語一致とタイポ含みのあいまい一致の両方をヒットさせる。フィルタ・ソート・ページネーションを備え、利用者は商品サマリのページ（envelope 形式）を取得できる。

### 分解した要件
| # | 要件 | 種別 | 備考 |
|---|------|------|------|
| R1 | `GET /api/products/search` を提供する | 明示 | 既存ハンドラの契約と異なるため置換が必要 |
| R2 | `q` を必須クエリパラメータとして受け取る | 明示 | 既存は `q` 未指定で `200 + []`（products.py 101-102 行）→ 変更要 |
| R3 | `q` 未指定時はバリデーションエラーを返す | 明示 | 指示書 62 行 |
| R4 | `inStock` を任意クエリパラメータとして受け取り在庫ありフィルタを適用する | 明示 | 既存ハンドラ未対応 |
| R5 | `priceMin` を任意クエリパラメータとして受け取り価格下限フィルタを適用する | 明示 | 既存ハンドラ未対応 |
| R6 | `priceMax` を任意クエリパラメータとして受け取り価格上限フィルタを適用する | 明示 | 既存ハンドラ未対応 |
| R7 | `priceMin > priceMax` はバリデーションエラー | 明示 | 指示書 39 行「数値・大小関係」 |
| R8 | `priceMin/Max` の非数値はバリデーションエラー | 明示 | 指示書 62 行 |
| R9 | `sort` の値域違反はバリデーションエラー | 明示 | 指示書 62 行 |
| R10 | `page` は正整数で受け取り、不正値はバリデーションエラー | 明示 | 指示書 39 行「正整数チェック」 |
| R11 | 1ページ10件固定 | 明示 | 指示書 22 行 |
| R12 | レスポンスに総件数を含める | 明示 | 指示書 23 行 |
| R13 | レスポンスに現在ページを含める | 明示 | 指示書 23 行 |
| R14 | レスポンスに総ページ数を含める | 明示 | 指示書 23 行 |
| R15 | Postgres 全文検索（tsvector / tsquery）を使用する | 明示 | 指示書 26 行。既存は ILIKE のみ |
| R16 | Trigram（pg_trgm）を併用する | 明示 | 指示書 26 行 |
| R17 | 検索対象に商品名を含める | 明示 | 指示書 27 行 |
| R18 | 検索対象に説明文を含める | 明示 | 指示書 27 行 |
| R19 | 検索対象にタグを含める | 明示 | 指示書 27 行。`Product` モデルに `tags` カラムなし（models.py 55-65 行）→ 追加要 |
| R20 | 必要に応じて GIN 等のインデックスを追加するマイグレーションを提供する | 明示 | 指示書 29 行・40 行 |
| R21 | 商品サマリのみを返却する | 明示 | 指示書 32 行。具体項目は Planner 判断 |
| R22 | ソート選択肢を ORDER BY で切り替える | 明示 | 指示書 43 行・60 行 |
| R23 | バリデーションエラー時のレスポンスを既存 API の規約に揃える | 明示 | 既存規約 = FastAPI 既定の 422 |
| R24 | 検索クエリの発行を既存ロガー慣習に合わせて記録する | 明示 | 指示書 49 行 |
| R25 | `q` 等のユーザ入力をそのままログに残さない（既存ポリシー踏襲） | 明示 | 既存実装は `q` をログに出さない（products.py 116-118 行） |
| R26 | 認証要否を既存設計書から判断し、必要なら既存ミドルウェアを適用する | 明示 | 設計書に規定なし → 既存実装踏襲（未認証）と結論 |
| R27 | `analysis/models.py` の `Product` モデルを backend と同期させる | 暗黙 | R19 から派生。ADR-002「DBスキーマ変更時に Backend と Analysis の両方で同期が必要」（002 行 19）に基づく |
| R28 | マイグレーションフレームワーク（Alembic）を導入する | 暗黙 | R20 から派生。リポジトリにマイグレーション基盤がなく、R20 を実行可能にするための前提整備 |
| R29 | テスト基盤を Postgres 化する | 暗黙 | R15・R16・R19 から派生。SQLite では tsvector/pg_trgm/ARRAY を検証不能（conftest.py 4-6 行で SQLite ピン止め） |

### 参照資料の調査結果
- `docs/system-design.md` / `docs/adr/001`〜`003`: アーキテクチャは FastAPI + PostgreSQL + Next.js のマルチコンテナ構成。検索エンドポイントの envelope・認証要否・ソート選択肢の規定は **存在しない**。ADR-002 が DB スキーマ変更時の Backend/Analysis 同期を明文化。
- `backend/main.py` / `backend/routers/products.py`: 既存の `/api/products/search` 実装が存在するが、**別 run（`20260503-152937-get-api-products-se`）の order.md 向け成果物**で、本タスクの新仕様とは契約が異なる。具体差異:
  - 検索方式: 既存は ILIKE `%q%`、新仕様は FTS + Trigram
  - クエリパラメータ: 既存は `q`/`limit`、新仕様は `q`/`inStock`/`priceMin`/`priceMax`/`sort`/`page`
  - 検索対象: 既存は name+description、新仕様は name+description+**tags**
  - エラー応答: 既存は全エラー `200 + []`（main.py 12-21 行で `RequestValidationError` を路径限定で 200 化）、新仕様はバリデーションエラーをエラー応答
  - ページネーション: 既存は `limit` のみ、新仕様は 10件/page 固定 + envelope
- `backend/models.py`: `Product` に `tags`/在庫信号/価格信号いずれも **存在しない**。
- 既存マイグレーション: **存在しない**。`compose.yml` 11 行で `./db/init` をマウントしているがディレクトリ未作成。`Base.metadata.create_all()` 前提運用。

### スコープ
- 新規追加: `backend/repositories/`（products リポジトリ）、`backend/alembic/` 一式（`alembic.ini`・`env.py`・`script.py.mako`・初期スキーマ＋検索カラム追加の 2 マイグレーション）
- 変更: `backend/models.py`（`Product` に `tags`・`in_stock`・`current_price`・`search_vector` 追加）、`analysis/models.py`（同期）、`backend/schemas.py`（`ProductSummary` と `ProductSearchEnvelope` 追加、`ProductOut` は現状維持）、`backend/routers/products.py`（新仕様で書き換え）、`backend/main.py`（旧 `RequestValidationError` ハンドラ削除）、`backend/Dockerfile`（起動時 `alembic upgrade head`）、`backend/requirements.txt`（`alembic`・`testcontainers[postgresql]` 等追加）、`backend/tests/conftest.py`（Postgres ベースに置換）、`backend/tests/test_product_search.py`（新仕様用に置換、write_tests ステップで実施）
- 変更規模: Medium（200-500 行）
- 後方互換: 不要。旧 `q`/`limit` 契約と「全エラー 200+[]」挙動は新仕様で完全置換

### 検討したアプローチ
| アプローチ | 採否 | 理由 |
|-----------|------|------|
| FTS と Trigram の OR 結合 + スコア合算順 | 採用 | 1パスで済み、`ts_rank + similarity` の線形和が relevance として自然 |
| FTS と Trigram の UNION ALL + 後段 dedupe | 不採用 | クエリが二重化し ORDER BY の整合性が複雑になる |
| `current_price` を Product に denormalize | 採用 | 検索クエリが単純化、`price_asc/desc` ソートが B-tree インデックスで O(log n)。同期責務は本タスク外（analysis 側�� |
| 価格を毎回 PriceHistory + EcSiteProduct で集約 | 不採用 | 検索 1 リクエストごとに相関サブクエリ 2 段が走り、スケーラビリティに難 |
| `in_stock` を Product に追加 | 採用 | 単一信号で十分、フィルタ実装が単純 |
| `in_stock` を EcSiteProduct ごとに保持しサブクエリ集約 | 不採用 | 「Product に対し 1 件でも在庫サイトがある」を毎回サブクエリで判定する必要があり、本タスクの検索性能を阻害 |
| `search_vector` を生成カラム（`GENERATED ALWAYS AS ... STORED`） | 採用 | クエリで `WHERE search_vector @@ ...` がそのまま使え GIN が効く。書き込み時に Postgres が自動更新 |
| 式 GIN インデックス（`to_tsvector(...)` を毎回式で書く） | 不採用 | 全クエリで同じ式を再掲する必要があり DRY 違反 |
| `pytest-postgresql`（ホストの Postgres バイナリ要） | 不採用 | Docker 前提の本プロジェクトでは余分な依存 |
| `testcontainers-python`（コンテナ起動） | 採用 | 既存の Docker 前提と整合、CI 環境差を吸収 |
| Alembic 導入 | 採用 | SQLAlchemy 標準、再現性のあるマイグレーション運用が可能 |
| `db/init/*.sql` のみで運用 | 不採用 | 初期化時のみ実行され、以降のスキーマ進化に追従不可 |
| 認証必須化 | 不採用 | 既存設計書に規定なし、既存検索エンドポイント未認証、商品検索は匿名ユースケースが想定される |
| Envelope: `{items, page, totalPages, totalCount}` | 採用 | 既存 API に envelope の前例なく新設、必要十分な4キー |

### 実装アプローチ
1. **モデル拡張**: `backend/models.py` の `Product` に `tags: ARRAY(String)`、`in_stock: bool`（default True）、`current_price: Optional[int]`、`search_vector`（`Computed` で生成）を追加。`analysis/models.py` を ADR-002 に従って同期。
2. **Alembic 導入**: `backend/alembic/` を新設し、`0001_initial_schema.py` で現行スキーマをベースライン化、`0002_product_search_columns.py` で `pg_trgm` 拡張、追加カラム、tsvector GIN、trigram GIN（`gin_trgm_ops`）、`current_price` B-tree を作成。
3. **スキーマ拡張**: `backend/schemas.py` に `ProductSummary`（`id`/`name`/`description`/`imageUrl`/`tags`/`inStock`/`currentPrice`）と `ProductSearchEnvelope`（`items`/`page`/`totalPages`/`totalCount`）を追加。`ProductOut` には触らない。camelCase は `Field(alias=...)` または `alias_generator` で対応。
4. **リポジトリ層追加**: `backend/repositories/products.py` に `search_products(db, params: SearchParams) -> tuple[Sequence[Product], int]` を実装。`SearchParams` は frozen dataclass か pydantic frozen モデル。SQL 構築順は「フィルタ → relevance スコア → ORDER BY → COUNT → LIMIT/OFFSET」。`websearch_to_tsquery('simple', :q)` と `similarity(searchable_text, :q) > 0.1` を OR で結合し、`ts_rank + similarity` を relevance スコアとする。`q` はバインドパラメータでのみ DB に渡す。
5. **ハンドラ書き換え**: `backend/routers/products.py` の既存 search 関連を削除し、新ハンドラを実装。Query 引数で `q: str = Query(min_length=1, max_length=100)`、`inStock: Optional[bool]`、`priceMin: Optional[int] = Query(ge=0)`、`priceMax: Optional[int] = Query(ge=0)`、`sort: Literal["relevance","price_asc","price_desc","newest"] = "relevance"`、`page: int = Query(1, ge=1)` を受け取る。`priceMin > priceMax` はハンドラ内で 422 を発生させる。`SearchParams` に正規化してリポジトリに渡す。レスポンスは `ProductSearchEnvelope` を組み立てて返す。
6. **旧仕様の遺物削除**: `backend/main.py` 12-21 行の `_request_validation_exception_handler` と 6 行の `SEARCH_FULL_PATH` import を削除。
7. **ロギング**: `len(q)`・ヒット件数・経過 ms を info で記録。`q` の生値はログに出さない。DB 例外は `logger.exception` で記録し例外を伝播（500）。
8. **テスト基盤刷新**: `conftest.py` を testcontainers ベースの Postgres セッションスコープフィクスチャに置換。スキーマは Alembic で適用。
9. **Dockerfile 更新**: 起動エントリポイントで `alembic upgrade head` を実行してから uvicorn 起動。

### 到達経路・起動条件
| 項目 | 内容 |
|------|------|
| 利用者が到達する入口 | `GET /api/products/search?q=...` への HTTP リクエスト（フロントエンド Next.js または外部クライアントから直接）。OpenAPI スキーマは FastAPI 自動生成。 |
| 更新が必要な呼び出し元・配線 | `backend/main.py` の `app.include_router(products_router)` は既存のままで新ハンドラを公開（追加配線不要）。`backend/main.py` 内の旧 `RequestValidationError` ハンドラは削除。フロントエンド型同期はスコープ外。 |
| 起動条件 | 認証不要（公開エンドポイント）。URL 条件・フラグなし。DB に対し Alembic マイグレーション適用済みであることが前提（Dockerfile エントリポイントで保証）。 |
| 未対応項目 | なし。`current_price`/`in_stock` の同期責務は本タスク対象外（analysis サービス／seed が更新する想定）。 |

## 実装ガイドライン
- **参照すべき既存実装パターン**:
  - ルーティング規約: `backend/routers/products.py` 27-40 行（`APIRouter(prefix=...)`、`tags=`、パス定数化）
  - 依存注入: `backend/routers/products.py` 99 行（`db: Session = Depends(get_db)`）
  - 応答スキーマ: `backend/schemas.py` 16-29 行（`ConfigDict(from_attributes=True)`、`Optional` の扱い）
  - モデル定義: `backend/models.py` 55-65 行（`Mapped[uuid.UUID]`、`mapped_column(UUID(as_uuid=True), primary_key=True)`）
  - ロガー: `backend/routers/products.py` 23 行（`logging.getLogger(__name__)`）
- **配線が必要な全箇所**: 5 つの新クエリパラメータ（`inStock`/`priceMin`/`priceMax`/`sort`/`page`）はハンドラ → `SearchParams` → リポジトリ `search_products(db, params)` まで明示的に貫通させる。リポジトリ内で `params.priceMin or 0` のような後段補完を書かない（ナレッジ「フェーズ分離」「Tell, Don't Ask」）。フィルタ未指定時は WHERE 句に追加しないこと（None チェック）。
- **削除対象（後方互換不要）**:
  - `backend/main.py` 12-21 行の `_request_validation_exception_handler`、6 行の `SEARCH_FULL_PATH` import
  - `backend/routers/products.py` の既存 `search_products` / `search_products_endpoint` / `_escape_like` / `Q_MAX_LENGTH` / `LIMIT_DEFAULT` / `LIMIT_MAX` / `LIKE_ESCAPE` / `SEARCH_FULL_PATH`（新実装で置換）
  - `backend/tests/test_product_search.py` 全体（write_tests ステップで新仕様向けに置換）
  - `backend/tests/conftest.py` の SQLite 構成（write_tests ステップで testcontainers Postgres に置換）
- **特に注意すべきアンチパターン**:
  - エラー握りつぶし禁止: 旧コード `try/except: return []`（products.py 113-119 行）を踏襲しない。DB 例外は伝播し 500、`logger.exception` で記録
  - TODO コメント禁止: `current_price`/`in_stock` の同期について「将来 analysis 側で更新する」と TODO を残さない。読み取りのみ実装で完結させる
  - 状態の直接変更禁止: `SearchParams` は frozen で immutable に保つ
  - SQL インジェクション対策: `q` はパラメータバインド経由でのみ DB に渡す（`websearch_to_tsquery(:q)`、`similarity(searchable_text, :q)`）。文字列結合での SQL 構築禁止
  - フラグ引数で挙動を変えない: `sort` の分岐は dict マップ（`SORT_CLAUSES: dict[Literal[...], list[ColumnElement]]`）で表現する
- **設計指針**:
  - レイヤー: ハンドラ（バリデーション + 配線）→ リポジトリ（SQL 構築・実行）。30 行を超える関数は分割を検討
  - 1 ファイル 200-400 行を目安。`routers/products.py` は新実装で 150-200 行に収まる見込み
  - `search_vector` の生成式は `to_tsvector('simple', coalesce(name,'') || ' ' || coalesce(description,'') || ' ' || coalesce(array_to_string(tags,' '),''))`。Trigram 用の `searchable_text` も同じ式を使用
  - relevance しきい値（similarity > 0.1）はリポジトリ定数として定義
  - `priceMin > priceMax` の検証は pydantic `model_validator` か Query 解釈後の if 分岐で実装し 422 を発生させる
- **ロギングポリシー**: 検索 1 件ごとに `len(q)`、ヒット件数、経過 ms を info で出力。`q` の生値・raw 入力は出力しない。DB 例外は `logger.exception` で stack trace を記録

## スコープ外
| 項目 | 除外理由 |
|------|---------|
| `current_price` / `in_stock` の同期ロジック（analysis サービスからの更新） | 本タスクは検索エンドポイントの実装であり、データ更新側は analysis サービスの責務。指示書に明示要求なし |
| フロントエンド（Next.js）側の型同期・UI 実装 | 指示書の対象は backend のエンドポイント。明示要求なし |
| 既存テスト全体の Postgres 化（`/api/products/search` 以外） | 指示書スコープは検索エンドポイントのみ。他テストへの波及は明示要求なし |
| `q` のログ集計・検索分析機能 | 指示書「検索クエリの発行を記録」はログ出力までで、分析機能は明示要求なし |
| レート制限・スロットリング | 指示書に明示要求なし。一般論ベストプラクティスの範囲 |

## 確認事項
なし。指示書 81-82 行で「未解決事項なし」と明示されており、Planner に委任された判断事項（指示書 67-74 行）は本計画の「検討したアプローチ」「実装アプローチ」セクションで全て結論済み。