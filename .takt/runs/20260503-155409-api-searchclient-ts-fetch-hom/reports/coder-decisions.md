# 決定ログ

## 1. SWR の `key` を「URL 文字列 / null」に、fetcher は closure で `query` を受け渡す
- **背景**: SWR `useSWR(key, fetcher)` の key に何を入れるか、また `searchProducts(query)` のシグネチャ（引数 = query 文字列）と SWR の fetcher 契約（fetcher は key を引数として受け取る）をどう繋ぐかの選択が必要だった。
- **検討した選択肢**:
  1. key = query 文字列、fetcher = `searchProducts`（key がそのまま fetcher 引数に渡る）
  2. key = `buildProductsSearchUrl(query)`、fetcher = `() => searchProducts(query)`（closure 経由で query を渡す）
  3. key = `[path, query]` のタプル、fetcher = `([_, q]) => searchProducts(q)`
- **理由**: 計画レポート §実装アプローチ「`key` は `query !== ''` のときのみ URL 文字列、空クエリでは `null` にして fetch をスキップ」に従い (2) を採用。URL 文字列をキーにすることで、エンドポイント・クエリパラメータ名が変わったとき `endpoints.ts` の差し替えが SWR キャッシュキーにも自然に反映される。`query` 文字列だけだと「同じクエリで別エンドポイントに切り替えた時にキャッシュが衝突する」リスクがあるが、URL なら衝突しない。

## 2. リトライ導線は `mutate()` のみ（`revalidate` オプション省略）
- **背景**: `SearchErrorState` の `onRetry` で SWR の再検証をどう起動するか。
- **検討した選択肢**:
  1. `mutate()` をそのまま呼ぶ（既定で revalidate=true）
  2. `mutate(undefined, { revalidate: true })` と明示
  3. `mutate(undefined, true)` の旧 API
- **理由**: SWR v2 の `mutate()` は引数なしで「現在 key の再検証」が既定挙動のため (1) を採用。明示する書き方は冗長で、API の既定値を二度書くことになる（Policy「フォールバック・デフォルト引数の禁止」の趣旨と整合）。

## 3. `lib/mock/products.ts`（MOCK_PRODUCTS）を削除する（AI Review #1 受けて修正）
- **背景**: 旧同期実装 `lib/mock/searchClient.ts` を削除した結果、その唯一の依存先 `MOCK_PRODUCTS`（368 行）が未参照のデッドコードとなった。AI Review #1 で finding `AI-NEW-frontend-lib-mock-products-L17`（dead-code）として指摘され REJECT。
- **検討した選択肢**:
  1. 削除する（クリーンアップ。order.md の「同期前提でのみ使われていたコード」「関連デッドコードが残っていない」要件に合致）
  2. テスト側を `MOCK_PRODUCTS` 利用に書き換えて保持する（ADR-005 §2 のフィクスチャ用途を実体化）
  3. 当初判断のまま放置する
- **理由**: (1) を採用。検証結果として grep 上 `MOCK_PRODUCTS|@/lib/mock/products` の参照は本ファイル自身を除いてゼロ、storybook も存在しない。タスク指示書 (`order.md`) は「旧同期処理（および同期前提でのみ使われていたコード）は削除する」「旧 useMemo 同期実装と関連デッドコードが残っていない」を明示しており、`MOCK_PRODUCTS` は同期 `searchClient` 専用データだったためスコープ内。Policy「未使用コード」「リファクタリング後の旧コード残存 → 削除」にも該当する。当初の決定（保持）は ADR-005 §2 の文言に過剰追従し、order.md と Policy の優先順位を取り違えていた。(2) は 8 件のデータセットのうち 1〜2 件しか使わず、テストの境界粒度（最小フィクスチャ）まで変えるためスコープ拡張になる。空になった `frontend/lib/mock/` ディレクトリも併せて削除した。

## 4. `Spinner` の `label` props を最終的に削除（固定文言）
- **背景**: 初版で `label?: string` の optional prop を持たせたが、唯一の呼び出し元 `HomePage` が省略していた。
- **検討した選択肢**:
  1. デフォルト引数を残す
  2. 必須引数にして HomePage に明示渡し
  3. props を完全に削除し固定文言にする
- **理由**: Policy「全呼び出し元が省略しているか？ → デフォルト引数を削除し、必須にする」に該当する状態だった。さらに `Spinner` は「検索結果のローディング」という単一用途の UI のため、ラベルを呼び出し側が選ぶ意義が薄い。(3) を採用して値の出処を 1 箇所に固定し、「値がどこから来るか分からない」状態を解消した。

## 5. `searchClient.ts` のレスポンスは `Product[]` 直返しを前提に型アサーション
- **背景**: SoT `docs/design/backend-api-spec.md` が不在のため、レスポンスボディの型をどう扱うか。
- **検討した選択肢**:
  1. `unknown` で受けて手書き型ガードで検証
  2. `as Product[]` で前提型をそのまま採用
  3. zod 等の runtime バリデーションを導入
- **理由**: 計画レポート「レスポンスは `Product[]` で受ける。`unknown` → 型ガードまで踏み込まず、サーバー応答信頼の前提（フロント・バック責務分離知識）」に従い (2) を採用。ADR-005 §5 でも OpenAPI 経由の型同期が方針。タスクスコープ外の zod 導入は避け、SoT 確定後に endpoints / レスポンス検証の追加で対応できる構造に留める（変更点を `endpoints.ts` と `searchClient.ts` に局所化）。