テストファースト作業を完了しました。実装前のため、新規テスト 3 ファイルは想定どおり import 解決エラーで failing（実装ステップで `@/lib/api/*` 配下のモジュールと `swr` 依存を追加すれば通る）。既存テスト 11 ファイル（63 件）は引き続き全パスし、`lib/mock/searchClient.test.ts` 削除による波及影響がないことを確認しました。

## 作成・変更内容

### 新規: `frontend/lib/api/endpoints.test.ts`
`buildProductsSearchUrl` の純関数仕様を 5 ケースで保証。
- ASCII クエリで `/api/products/search?q=<value>` を返す
- 日本語は `encodeURIComponent` でパーセントエンコード（生のまま現れない）
- 空白は `%20`（`+` ではない）
- `& = ? #` などの特殊文字をエスケープ
- 空文字でも URL を生成（fetch スキップ責務はビルダではなく呼び出し側）

### 新規: `frontend/lib/api/searchClient.test.ts`
`global.fetch` を境界としてスタブし、9 ケースで HTTP 呼び出し契約を検証。
- 正常系で `Product[]` を解決
- `buildProductsSearchUrl` と同一 URL に fetch する整合性
- HTTP メソッドは GET（明示／省略どちらでも GET）
- 日本語・空白・特殊文字が URL クエリ部分で生のまま現れない
- 空配列応答は成功扱い
- HTTP 4xx / 5xx で `Error` throw（握りつぶさず SWR に伝播）
- ネットワーク例外（fetch reject）の伝播

### 更新: `frontend/app/page.test.tsx`
SWR 本体はモックせず、`SWRConfig` でテスト毎にキャッシュ分離（`provider: () => new Map()`、`dedupingInterval: 0`、`errorRetryCount: 0`、`revalidateOnFocus: false`）。fetch のみスタブ。
- 初期表示: フォームのみ。スピナー／結果／エラーは出ず、fetch も呼ばれない（空クエリで key=null の設計）
- 検索 → ローディング: `role="status"` のスピナー表示
- 検索 → 成功: `Hits 1 件` 表示と該当 article 描画
- 検索 → 失敗: リトライボタン表示、結果セクションは描画されない
- リトライボタン押下: 再 fetch（計 2 回）→ 成功で結果描画、エラー画面は消える
- ヒット 0 件: `EmptyState`（「該当記事はありません」）表示

### 削除: `frontend/lib/mock/searchClient.test.ts`
旧同期実装 `searchProducts` 用テスト。実装ステップで対象モジュール本体が削除される計画に追従（タスク指示書「同期前提のテストは新仕様に追従して更新」）。

## テスト実行結果
```
Test Files  3 failed | 11 passed (14)
     Tests  63 passed (63)
```

failing 3 件はすべて実装待ちの import 解決失敗（`@/lib/api/endpoints` / `@/lib/api/searchClient` / `swr`）で、実装ステップ完了後にパスする前提。