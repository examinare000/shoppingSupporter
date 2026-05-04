# 変更スコープ宣言

## タスク
`searchClient.ts` を fetch ベースの非同期実装に切り替え、`HomePage` を SWR でローディング・エラー・成功の 3 状態描画に対応させる。

## 変更予定
| 種別 | ファイル |
|------|---------|
| 作成 | `frontend/lib/api/endpoints.ts` |
| 作成 | `frontend/lib/api/searchClient.ts` |
| 作成 | `frontend/components/feedback/Spinner.tsx` |
| 作成 | `frontend/components/feedback/SearchErrorState.tsx` |
| 変更 | `frontend/app/page.tsx`（`useMemo` → `useSWR` 置換、状態別分岐） |
| 変更 | `frontend/package.json`（`swr@^2.4.1` 追加） |
| 変更 | `frontend/package-lock.json`（依存追従） |
| 削除 | `frontend/lib/mock/searchClient.ts`（旧同期実装） |
| 削除 | `frontend/lib/mock/products.ts`（旧同期 `searchClient.ts` の唯一の依存先・参照元消滅でデッドコード化） |
| 削除 | `frontend/lib/mock/`（中身が消えたため空ディレクトリを除去） |

`frontend/app/loading.tsx` はルート遷移用の別レイヤーのため対象外。

## 推定規模
Small

## 影響範囲
- 検索データ取得経路: クライアント側 `MOCK_PRODUCTS` フィルタ → バックエンド `GET /api/products/search?q=...` 呼び出し（SWR 経由）。`MOCK_PRODUCTS` 自体は本タスクで参照元を失ったため削除した
- HomePage の描画: 同期 `useMemo` → 非同期 SWR の 3 状態（ローディング／エラー／成功）
- `searchProducts` の import 元: `@/lib/mock/searchClient` → `@/lib/api/searchClient`（grep 確認上、利用は `app/page.tsx` のみ）
- 既存の `SearchResultsSection` / `EmptyState` / `HeroSearch` / `Masthead` / `RuledDivider` の props 契約は変更しない
- リトライ導線は `SearchErrorState` 内の `<button>` から SWR の `mutate()` を起動し、同 key で再検証が走る