# テスト作成レポート

## 作成テスト

| ファイル | 種別 | テスト数 | 概要 |
|---------|------|---------|------|
| `backend/pytest.ini` | 設定 | — | `testpaths=tests`, `pythonpath=.` を設定し `from main import ...` を可能にする pytest 設定 |
| `backend/tests/__init__.py` | 設定 | — | テストパッケージマーカー（空ファイル） |
| `backend/tests/conftest.py` | 設定 | — | SQLite in-memory + StaticPool エンジン、`test_engine` / `session_factory` / `db_session` / `client` / `make_product` フィクスチャ。`app.dependency_overrides[get_db]` で DB を差し替え |
| `backend/tests/test_product_search.py` | 単体＋統合 | 27 | 計画で指示された全観点をカバー（下記内訳） |

### 内訳（`test_product_search.py`）

| クラス | 種別 | テスト数 | 観点 |
|--------|------|---------|------|
| `TestSearchProductsName` | 単体 | 3 | 商品名一致、ASCII 大小無視、不一致で空 |
| `TestSearchProductsDescription` | 単体 | 2 | 説明文のみ一致、`description IS NULL` の挙動 |
| `TestSearchProductsRelevanceOrder` | 単体 | 2 | 4段階 relevance（exact > prefix > contains > description）、name ASC タイブレーク |
| `TestSearchProductsLimit` | 単体 | 1 | `limit` 引数で件数制限 |
| `TestSearchProductsMatchKinds` | 単体 | 3 | 商品名のみ／説明文のみ／両方マッチ各ケース（`order.md:58` 必須） |
| `TestEndpointHappyPath` | 統合 | 4 | 200応答、認証不要、`ProductOut.model_fields` キー一致、bare array（envelope でない）|
| `TestEndpointQueryParameterContract` | 統合 | 3 | `q` を query string から読む（body 流用の負テスト含む）、`limit` クエリ反映、デフォルト 10 |
| `TestEndpointRelevanceOrdering` | 統合 | 1 | HTTP 経由で relevance 順序検証 |
| `TestEndpointEmptyResultCases` | 統合 | 5 | q 欠落 / 空文字列 / 空白のみ / 101文字超 / 該当なし |
| `TestEndpointLimitBoundaries` | 統合 | 4 | 0 / 負値 / 非数値（422→200+`[]` 変換）/ 9999 で 100 にクランプ |
| `TestEndpointDatabaseError` | 統合 | 1 | `db.execute` を例外化した `BrokenSession` 注入で 200+`[]` |
| `TestEndpointSpecialCharacterEscaping` | 統合 | 2 | `%` / `_` がワイルドカードとして解釈されないこと（`escape_like` の要件固定）|

## 実行結果（参考）

実装前のためテスト失敗・import エラーは想定内。

| 状態 | 件数 | 備考 |
|------|------|------|
| Pass | 0 | 実装前のため未実行 |
| Fail / Import Error（想定内） | 27 | `from routers.products import search_products` と `from schemas import ProductOut` が未実装で collection 段階で停止。implement ステップで該当モジュールが作成されれば収集される |
| Error（要対応） | 0 | 既存モジュール（`main` / `database` / `models`）の import は確認済み。タイポ・パスミスなし |

実行コマンドと出力（要約）:
```
tests/test_product_search.py:20: in <module>
    from routers.products import search_products
E   ModuleNotFoundError: No module named 'routers'
```

別途、conftest 単体の import 確認では `main` / `database` / `models` / 全フィクスチャが正常にロードされることを検証済み。

## 備考

- **インテグレーションテスト要否判断**: policy のチェックリストに照らして必須と判定（router → schema → model → DB の 3モジュール以上を横断、`q`/`limit`/`description` の新オプションが末端まで伝搬）。`TestClient` 経由の統合テストを作成。
- **テスト DB 戦略**: `sqlite:///:memory:` + `StaticPool` で seeding セッションと request handler セッションが同一接続を共有する構成。Postgres 専用 `UUID(as_uuid=True)` カラムは SQLAlchemy 2.0 のフォールバック（CHAR 32）で SQLite 上でも動作することを事前検証済み。
- **契約テストの観点**: policy「query / path parameter を body に流用する実装を見逃さない」「response 標準 envelope を request 解釈へ流用する実装を見逃さない」に対応するため、`client.get(ENDPOINT, json={"q": "apple"})` で q が body から拾われないことを検証する負テストと、レスポンスが bare array であることのアサーションを含めた。
- **DB エラーテストの実装**: `monkeypatch` ではなく `app.dependency_overrides[get_db]` を使った `BrokenSession` 注入方式を採用。`yield BrokenSession()` 形でジェネレータ依存に整合させ、`finally` 側の `close()` 呼び出しにも対応。
- **`description` カラム未追加状態の扱い**: `make_product(description=...)` を渡すテストは ORM レベルで失敗するが、これは implement ステップで `models.py` への `description` 追加が反映されれば解消する想定（`order.md:58` の「説明文のみマッチ」必須テストが暗黙要求として導く）。
- **未追加事項**: `pytest.ini` は計画書の生成ファイル一覧に明記されていないが、`from main import app` を成立させるため testing infrastructure として最小限追加した。production code の変更ではない。