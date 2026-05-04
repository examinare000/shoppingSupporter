# 決定ログ

## 1. `TestEndpointQueryParameterContract::test_should_read_q_from_query_string_not_body` の呼び出し方を `client.get(json=...)` から `client.request("GET", ..., json=...)` に変更
- **背景**: 既存テストは `client.get(ENDPOINT, json={"q": "apple"})` で「GET ボディに `q` を入れても拾われない」契約を検証しようとしていたが、`httpx>=0.20`（実行環境は 0.28.1）の `Client.get` は `json` 引数を受け付けず `TypeError: TestClient.get() got an unexpected keyword argument 'json'` で失敗する。テスト自身の API 整合不備であり、実装側の責務ではない。
- **検討した選択肢**:
  1. テストを削除して契約検証を放棄する
  2. 実装側に「ボディがあると `[]` を返す」分岐を追加する
  3. `client.request("GET", ENDPOINT, json=...)` に書き換えて意図（負契約: ボディは無視される）を保つ
- **理由**: 選択肢1は policy「query / path parameter は body に流用しない」の負契約検証を失う。選択肢2は `order.md` にない振る舞いを実装に追加することになり、Coder 行動規範「タスク指示書にない既存機能の構造変更を行わない」に反する。選択肢3は httpx の API 変更に追随するだけのテスト側修正で、`write_tests` レポートに記録された検証意図と完全に一致する。

## 2. `RequestValidationError` ハンドラのパスガードに使う `/api/products/search` を定数化（`SEARCH_FULL_PATH`）
- **背景**: `main.py` の `RequestValidationError` ハンドラ（`limit=abc` 等の 422→200+`[]` 変換）と `routers/products.py` のルーティング定義の双方が同じパス文字列を参照する必要がある。policy「契約文字列を新規導入する場合は定数として 1 箇所で定義」に従う必要がある。
- **検討した選択肢**:
  1. `main.py` 側に文字列リテラル `"/api/products/search"` を直接書く
  2. `routers/products.py` に `ROUTER_PREFIX` / `SEARCH_PATH` / `SEARCH_FULL_PATH` を宣言し、`APIRouter(prefix=...)` / `@router.get(...)` / `main.py` の例外ハンドラの 3 者すべてが同じ定数を参照する
- **理由**: 選択肢2 では「ルータ登録パス」「ハンドラパス」「例外ハンドラのガード対象パス」が単一の定数源から派生するため、リテラル分散による typo 起因のバグ（例えば `/api/products/search` を `/api/product/search` と書いてしまう類）を構造的に防げる。`main.py` 側の値が router 側の prefix とずれた瞬間に `limit=abc` の 200+`[]` 変換が動かなくなる脆さを排除できる。

## 3. `q` のバリデーション（trim・空判定・100 文字上限）を handler 層に置き、`search_products(db, q, limit)` は前提済みの値を受ける純粋な SQL 実行関数とする
- **背景**: `q` の前処理を「handler に置く」「`search_products` に置く」「両方」の 3 通りが考えられる。テストは `search_products` を直接呼ぶ単体テストでは常に正規化済みの `q` を渡しており、空文字 / 空白 / 101 文字 / `None` のケースは全て統合テスト（endpoint 経由）でしか検証していない。
- **検討した選択肢**:
  1. `search_products` 内で trim・長さ判定・`limit` クランプ・例外捕捉まで全部行う
  2. handler が前処理と例外捕捉を担当し、`search_products` は SQL 実行のみ
  3. 両方の層で重複して防御する
- **理由**: 選択肢2 では責務が「入力検証 = HTTP 境界」「SQL 実行 = データアクセス層」に明確に分離され、policy「解決責務の一元化」に従う。選択肢1 は SQL 関数が HTTP ポリシー（100 文字、デフォルト 10 等）を抱え込み、将来別経路から呼ぶ際に重複検証が必要になる。選択肢3 は典型的な「念のため」二重防御で policy「不確実なときにフォールバックで隠す → 禁止」に該当する。例外捕捉も同じ理屈で handler に集約し、`search_products` は失敗時に例外を素直に伝播させる。

## 4. relevance スコアを `case()` で SQL 側に押し込み、Python での後段ソートを行わない
- **背景**: 関連度順ソートの実装は「SQL の `ORDER BY case() DESC, name ASC, id ASC`」と「Python で `.all()` 後にソート」の 2 通り考えられる。
- **検討した選択肢**:
  1. SQL の `CASE` 式で 4 段スコア（name 完全一致=4 / name 前方一致=3 / name 部分一致=2 / description 部分一致=1）を計算し、`ORDER BY` と `LIMIT` も SQL 側で行う
  2. `Product.name.ilike(...) | Product.description.ilike(...)` でフィルタした全件を取得し、Python 側で relevance を再計算してソート・スライス
- **理由**: 選択肢1 は plan.md の固定要件を満たすうえ、policy「フィルタ・ソート・LIMIT は SQL 側に押し込む。Python 側で `.all()` 後フィルタ禁止」に従う。100 万件規模のテーブルで全件ロードを避ける運用上の利点もある。`case()` の最初にマッチした分岐が採用される SQL セマンティクスにより、name が完全一致した行は description でも一致していてもスコア 4 が確定し、relevance 計算と SQL 評価順序が一致する。

## 5. `escape_like` でユーザー入力中の `\` `%` `_` をエスケープし、`ilike(pattern, escape="\\")` で渡す
- **背景**: SQLAlchemy の `ilike` 自体はバインド変数化されるため SQL インジェクションは防げるが、`%` `_` は LIKE のワイルドカード意味を持ったまま渡る。テスト `test_should_treat_percent_in_q_as_literal_not_wildcard` / `test_should_treat_underscore_in_q_as_literal_not_wildcard` は `q="50%"` や `q="under_score"` でこれらが「リテラル」として扱われることを要求している。
- **検討した選択肢**:
  1. エスケープせず素通し（テストで FAIL）
  2. `replace("%", "")` 等でユーザー入力からワイルドカード文字を除去する
  3. `escape_like` で `\` `%` `_` の順にバックスラッシュ前置し、`ilike(pattern, escape="\\")` で SQL 側に escape 文字を伝える
- **理由**: 選択肢2 は `q="50%"` で検索したいユーザーの意図を破壊する（`q="50"` として扱われる）。選択肢3 は LIKE の標準的なエスケープ機構そのもので、入力の意味を保ちつつワイルドカード解釈を抑制できる。replace の順序は「`\` 先 → `%` `_` 後」で固定し、後段で導入したバックスラッシュを再エスケープしないようにした。