# AI生成コードレビュー（2回目）

## 結果: APPROVE

## サマリー
前回 REJECT の唯一の指摘 `AI-NEW-frontend-lib-mock-products-L17`（`MOCK_PRODUCTS` のデッドコード化）は実体削除＋空ディレクトリ除去で完全解消。新規 `new` / `persists` 指摘は無し。残りの本番ソース／テストの実装内容に変化はなく、機能実装本体・スコープ整合・幻覚 API・既存パターン整合は良好。

## 検証した項目

| 観点 | 結果 | 備考 |
|------|------|------|
| 前回指摘の修正確認（最優先） | ✅ | `frontend/lib/mock/products.ts` 不在、`frontend/lib/mock/` ディレクトリ消失、`Grep "MOCK_PRODUCTS\|@/lib/mock"` で frontend 配下ヒット 0 を確認 |
| 仮定の妥当性 | ✅ | SoT (`docs/design/backend-api-spec.md`) 不在を `endpoints.ts` への局所化で吸収（ADR-005 §5 と整合） |
| API/ライブラリの実在 | ✅ | `useSWR`/`mutate`/`SWRConfig`/`provider`/`dedupingInterval`/`focusThrottleInterval`/`errorRetryCount` は SWR v2.4 の実 API |
| 配線（HomePage → searchClient → endpoints） | ✅ | `swrKey` が `hasQuery` で null 切替、closure で `query` を fetcher へ伝搬。fetch の URL は `buildProductsSearchUrl` に統一 |
| コンテキスト適合 | ✅ | `EmptyState` 系の二重罫線トーン継承、`RuledDivider`/`MarginalNote` 再利用、Tailwind カラートークン整合 |
| スコープ | ✅ | クリープ無し（zod 等の追加抽象化なし）。縮小無し（searchClient/HomePage/ローディング/エラーUI の3点完備） |
| デッドコード | ✅ | 旧同期実装（`lib/mock/searchClient.ts`）、孤立データ（`MOCK_PRODUCTS`）、空ディレクトリの全てが削除済み |

## 今回の指摘（new）

| # | finding_id | family_tag | カテゴリ | 場所 | 問題 | 修正案 |
|---|------------|------------|---------|------|------|--------|
| - | - | - | - | - | 該当なし | - |

## 継続指摘（persists）

| # | finding_id | family_tag | 前回根拠 | 今回根拠 | 問題 | 修正案 |
|---|------------|------------|----------|----------|------|--------|
| - | - | - | - | - | 該当なし | - |

## 解消済み（resolved）

| finding_id | 解消根拠 |
|------------|----------|
| AI-NEW-frontend-lib-mock-products-L17 | `git status` で `deleted: frontend/lib/mock/products.ts`、`ls frontend/lib/mock/` で「No such file or directory」、`Grep MOCK_PRODUCTS` / `Grep @/lib/mock` で frontend 配下ヒット 0。`coder-decisions.md` Decision #3 で削除採用判断と理由が明記され、`coder-scope.md` の削除欄に追記済み |

## 再開指摘（reopened）

| # | finding_id | family_tag | 解消根拠（前回） | 再発根拠 | 問題 | 修正案 |
|---|------------|------------|----------------|---------|------|--------|
| - | - | - | - | - | 該当なし | - |

## 参考（非ブロッキング・Warning／前回から継続）

前回レビューで Warning として記録済みの以下 4 点は未対応だが、いずれも本タスクの3点スコープ（searchClient.ts 切替・HomePage 非同期化・ローディング/エラーUI）を逸脱せず、Policy のスコープ判定上「タスクスコープを大きく逸脱するリファクタリング」に該当するため非ブロッキング。

- `frontend/lib/api/searchClient.ts:26` `as Product[]` の runtime 検証なし。decision-log #5 の判断（SoT 確定後に zod 検討）は妥当。
- `frontend/components/feedback/SearchErrorState.tsx:24-27` `describeError` の `'原因不明のエラーが発生しました'` フォールバックは現状の呼び出し元 (`searchProducts` は必ず `Error` を throw) では論理的に到達しないが、`error: unknown` を受ける UI 防御として許容範囲。専用テストなし（`page.test.tsx` の `Error('network down')` ケースで第1分岐のみカバー）。
- `frontend/lib/api/searchClient.ts:17` `{ method: 'GET' }` は fetch の既定値と重複（実害なし。テスト側 `(init?.method ?? 'GET').toUpperCase()` も明示・省略どちらでも通る設計）。
- `frontend/package.json` の `dependencies`/`devDependencies` がアルファベット順に並び替わっている（`npm install` の副作用）。本タスクのコード差分には影響なし。

## 判定根拠

Policy「REJECT は `new` または `persists` の問題が1件以上ある場合のみ許可する」に従い、今回は両方ゼロのため **APPROVE**。前回唯一の REJECT (`AI-NEW-frontend-lib-mock-products-L17`) は実コード・grep 結果で resolved を確認。Policy「前回指摘を解消済みとする場合、別の構造問題や契約悪化を新たに導入していないか確認する」の観点でも、今回の差分は純削除（`products.ts` ファイル削除＋空ディレクトリ除去＋`coder-decisions.md`/`coder-scope.md` のレポート更新）のみで、新たな構造問題・契約悪化は導入されていない。