## 作業結果
- `searchClient.ts` を fetch ベースの非同期実装に切り替え、`HomePage` を SWR で 3 状態描画（ローディング／エラー／成功）に対応させた。
- SWR の key は空クエリで `null`（fetch スキップ）、検索時は `buildProductsSearchUrl(query)` で算出した URL 文字列を使用。リトライは `mutate()` で同 key の再検証を起動する。
- 旧同期実装 `lib/mock/searchClient.ts` を削除。`lib/mock/products.ts`（テスト用フィクスチャ）は計画通り保持。
- スコープ／決定ログを Report Directory に出力。

## 変更内容
- 新規 `frontend/lib/api/endpoints.ts` — `PRODUCTS_SEARCH_PATH` / `PRODUCTS_SEARCH_QUERY_PARAM` 定数と `buildProductsSearchUrl` 純関数。エンドポイント契約文字列を 1 箇所に集約。
- 新規 `frontend/lib/api/searchClient.ts` — fetch ベース `searchProducts(query): Promise<Product[]>`。`response.ok` でなければ `Error` throw、ネットワーク例外はそのまま伝播。
- 新規 `frontend/components/feedback/Spinner.tsx` — `role="status"` / `aria-label`「検索結果を読み込み中」付き CSS-only スピナー。
- 新規 `frontend/components/feedback/SearchErrorState.tsx` — 二重罫線囲みの「読み込みに失敗しました。」見出し＋「リトライ」ボタン＋詳細欄外ノート。
- 変更 `frontend/app/page.tsx` — `useMemo` 同期ロジックを削除し、`useSWR<Product[]>(swrKey, () => searchProducts(query))` に置換。`isLoading` → `Spinner`、`error` → `SearchErrorState`、`data` → `SearchResultsSection` の状態分岐。
- 変更 `frontend/package.json` / `package-lock.json` — `swr@^2.4.1` を追加。
- 削除 `frontend/lib/mock/searchClient.ts` — 旧同期 `searchProducts` と `MOCK_PRODUCTS` フィルタロジック。

## ビルド結果
- `npm run typecheck` ✓ エラーなし
- `npm run build` ✓ 成功（`/` ルート 17.5 kB / First Load 105 kB。font 取得は sandbox の DNS で stub されるが build 自体は成功）

## テスト結果
- `npm test` → **Test Files 14 passed (14) / Tests 82 passed (82)**
  - `lib/api/endpoints.test.ts`（5）/ `lib/api/searchClient.test.ts`（8）/ `app/page.test.tsx`（6）を含む全テストがパス。
  - 既存テスト（resolveProductImage / useImagePriority / ProductDossier / SearchResultsSection / sortListings / ProductThumbnail / effectivePrice / numbers / ImagePriorityControl / smoke / SearchForm）も全パスで波及影響なし。