# タスク完了サマリー

## タスク
`searchClient.ts` を fetch ベースの非同期実装へ切り替え、`HomePage` を SWR 経由で「ローディング／エラー／成功」の 3 状態描画に対応させ、スピナーとリトライボタン付きエラー画面の UI を実装する。

## 結果
完了

## 変更内容
| 種別 | ファイル | 概要 |
|------|---------|------|
| 作成 | `frontend/lib/api/endpoints.ts` | エンドポイント契約文字列（`PRODUCTS_SEARCH_PATH`／`PRODUCTS_SEARCH_QUERY_PARAM`／`buildProductsSearchUrl`）を 1 箇所に集約 |
| 作成 | `frontend/lib/api/searchClient.ts` | fetch ベース `searchProducts(query): Promise<Product[]>`。`Response.ok` チェック後 JSON 解決、HTTP/ネットワーク異常は throw して SWR に伝播 |
| 作成 | `frontend/lib/api/endpoints.test.ts` | URL 組み立ての契約テスト（ASCII／日本語 encodeURIComponent／`%20`／特殊文字／空文字）5 ケース |
| 作成 | `frontend/lib/api/searchClient.test.ts` | `global.fetch` をスタブし HTTP 呼び出し契約を検証（正常系／URL 一致／GET メソッド／エンコーディング／空配列／4xx／5xx／ネットワーク例外）8 ケース |
| 作成 | `frontend/components/feedback/Spinner.tsx` | CSS-only スピナー（`role="status"`／`aria-label`／`aria-live="polite"`）。`prefers-reduced-motion` は `globals.css` で吸収 |
| 作成 | `frontend/components/feedback/SearchErrorState.tsx` | 二重罫線の枠＋見出し＋クエリ文脈＋`<button>リトライ` ＋ `MarginalNote` で詳細メッセージ |
| 作成 | `reports/supervisor-validation.md` | 監督者最終検証レポート（要件 27 項目分解／前段 finding 再評価／検証サマリー／APPROVE 判定） |
| 作成 | `reports/summary.md` | タスク完了サマリー |
| 変更 | `frontend/app/page.tsx` | `useMemo` → `useSWR<Product[]>`。空クエリで `key=null` にして fetch 抑止、`isLoading`／`error`／`data` 分岐で `Spinner`／`SearchErrorState`／`SearchResultsSection` に振り分け、`onRetry={() => void mutate()}` で再検証 |
| 変更 | `frontend/app/page.test.tsx` | `SWRConfig` でテスト間キャッシュ分離、`fetchMock` ベースの非同期テスト 6 ケース（初期表示／ローディング／成功／エラー／リトライ／0 件 EmptyState） |
| 変更 | `frontend/package.json` | `swr@^2.4.1` を依存に追加 |
| 変更 | `frontend/package-lock.json` | 依存追従 |
| 削除 | `frontend/lib/mock/searchClient.ts` | 旧同期実装 |
| 削除 | `frontend/lib/mock/searchClient.test.ts` | 旧同期テスト |
| 削除 | `frontend/lib/mock/products.ts` | 旧同期 `searchClient.ts` の唯一の依存先（参照元消滅でデッドコード化） |
| 削除 | `frontend/lib/mock/` | 空ディレクトリ |

## 検証証跡
- 要件充足確認: タスク指示書（`order.md`）から要件 27 項目を最小単位に分解し、`reports/supervisor-validation.md` で全項目を実コード（ファイル:行）で個別検証。要件 #1〜#25 はすべて充足、#2〜#5 は SoT 不在のため ADR-005 を暫定採用（`plan.md` 確認事項#1／`coder-decisions.md` Decision #5）、#26〜#27（ビルド・テスト合格）は実行証跡なしのため未確認。
- 静的検証:
  - `git status -s` で変更内訳を確認（M 4／D 3／?? 2）
  - `grep useMemo frontend/app/page.tsx` ヒット 0 件（旧同期処理の完全削除を確認）
  - `grep "MOCK_PRODUCTS\|@/lib/mock" frontend/` ヒット 0 件（関連デッドコードの完全削除を確認）
  - 各実装ファイル・テストファイルを直読し、責務分離・型整合・契約文字列の集約・a11y 属性を確認
- 前段レビュー: `reports/ai-review.md`／`reports/architect-review.md`／`reports/frontend-review.md`／`reports/testing-review.md`／`reports/qa-review.md`／`reports/security-review.md` の全 6 レビューが APPROVE。前段 finding（`AI-NEW-frontend-lib-mock-products-L17`／`QA-NEW-phase1-L0`／`QA-NEW-report-L0`／`SEC-NEW-phase1-failure`）はいずれも resolved 判定が妥当と再評価。false_positive・overreach は検出なし。
- ビルド／テスト／動作確認の実行証跡: 本 run 内では未取得（編集禁止フェーズのため supervise で再実行不可）。`reports/test-report.md` は write_tests 時点の Pass 63／想定内 Fail 3 suites を記録するが実装後の値ではない。後続ステップ（fix_supervisor またはマージ前）で `cd frontend && npm install && npm run typecheck && npm test && npm run build` を必ず実行する旨を `reports/supervisor-validation.md` に引き継ぎ事項として明記。
- 留意事項: `docs/design/backend-api-spec.md` 不在のため ADR-005 (`docs/adr/005-mock-to-backend-migration.md`) の `GET /api/products/search?q=...`／レスポンス `Product[]` 直返し／HTTP エラーで throw を暫定採用。SoT 確定後の差分は `endpoints.ts` 1 ファイルと `searchClient.test.ts`／`endpoints.test.ts` の URL アサーションだけで吸収できる構造。`as Product[]` の runtime バリデーション無しは同一オリジン信頼前提で妥当だが、外部入力相当のフィールドが混入し得るスコープ拡大時に zod 等の検討を推奨（`reports/security-review.md` 警告）。