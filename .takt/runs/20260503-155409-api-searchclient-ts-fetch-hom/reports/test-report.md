# テスト作成レポート

## 作成テスト
| ファイル | 種別 | テスト数 | 概要 |
|---------|------|---------|------|
| `frontend/lib/api/endpoints.test.ts` | 単体 | 5 | `buildProductsSearchUrl` の URL 組み立て契約を検証（ASCII / 日本語 encodeURIComponent / 空白 `%20` / 特殊文字 `& = ? #` / 空文字でも URL 生成） |
| `frontend/lib/api/searchClient.test.ts` | 単体 | 9 | fetch 版 `searchProducts` の HTTP 呼び出し契約を検証（正常系 `Product[]` 解決 / URL は `buildProductsSearchUrl` 一致 / GET メソッド / クエリエンコード / 空配列応答 / HTTP 4xx・5xx で throw / ネットワーク例外の伝播） |
| `frontend/app/page.test.tsx`（更新） | 統合 | 6 | SWR 経由のレンダリングを 6 状態で検証（初期表示で fetch 不発火 / ローディング `role="status"` / 成功時の Hits・article / fetch 失敗時のリトライボタン / リトライで再 fetch して成功描画 / ヒット 0 件で EmptyState） |
| `frontend/lib/mock/searchClient.test.ts`（削除） | 単体 | -8 | 旧同期 `searchProducts` 用テスト。実装ステップで対象モジュール本体が削除される計画に追従して削除 |

## 実行結果（参考）
実装前のためテスト失敗・import エラーは想定内。

| 状態 | 件数 | 備考 |
|------|------|------|
| Pass | 63 | 既存 11 テストファイル（resolveProductImage / useImagePriority / ProductDossier / SearchResultsSection / sortListings / ProductThumbnail / effectivePrice / numbers / ImagePriorityControl / smoke / SearchForm）は全パス。`lib/mock/searchClient.test.ts` 削除による波及影響なし |
| Fail / Import Error（想定内） | 3 suites | `lib/api/endpoints.test.ts` → `@/lib/api/endpoints` 未作成、`lib/api/searchClient.test.ts` → `@/lib/api/searchClient` 未作成、`app/page.test.tsx` → `swr` 未インストール。いずれも implement ステップで解消される設計 |
| Error（要対応） | 0 | 既存モジュールの import パスミス等、実装後も残るエラーは無し |

## 備考（判断がある場合のみ）
- **境界の置き方**: SWR 本体はモックせず、`global.fetch` を `vi.stubGlobal` でスタブする方針（フロント知識「外部UIライブラリとの統合」: shallow モックでマウント時破綻を見逃すリスク回避）。これにより SWR の実 state machine（loading → error → mutate → loading → success）を実コードでカバーできる。
- **SWR キャッシュ分離**: `<SWRConfig value={{ provider: () => new Map(), dedupingInterval: 0, errorRetryCount: 0, focusThrottleInterval: 0, revalidateOnFocus: false, revalidateOnReconnect: false }}>` でテスト毎にキャッシュを完全分離。SWR の「同 key で前回成功データが見える」現象とテスト間の状態漏れを断つ。
- **エラー UI のリトライ命名**: `name: /リトライ/` の正規表現マッチで判定（タスク指示書／計画レポートが「リトライボタン」と明記しているため）。実装ステップでこの命名に整合させること。
- **空クエリ時の fetch 不発火**: 計画レポートの「`query !== ''` のときのみ URL 文字列、空クエリでは `null` にして fetch をスキップ」という SWR key 設計を、初期表示テストで `expect(fetchMock).not.toHaveBeenCalled()` として固定化。
- **ヒット 0 件の責務分離**: `SearchResultsSection` 内の既存 `EmptyState` で吸収される設計のため、ページレベルでは「`該当記事はありません` テキスト＋article 0 件＋リトライボタン非表示」のみ確認し、内部実装の二重カバーを避ける。
- **API 契約の暫定値局所化**: `docs/design/backend-api-spec.md` 不在のため、計画レポート暫定値（`GET /api/products/search?q=...` / レスポンス `Product[]` 直返し / HTTP エラーで throw）を採用。SoT 確定時の差分は `endpoints.test.ts` の URL アサーションと `searchClient.test.ts` のレスポンス形だけで吸収できる構造。
- **削除判断**: `frontend/lib/mock/searchClient.test.ts` の削除は計画レポート §スコープ「削除」に明記。テストファイルなので write_tests ステップで処理し、`lib/mock/searchClient.ts`（プロダクションコード）の削除は implement ステップに委ねる。
- **インテグレーションテスト要否**: HomePage は「ルート ↔ View ↔ SWR ↔ fetch ↔ SearchResultsSection」を横断するデータフローを持ち、新たにローディング／エラー／成功の状態がワークフローへ合流するため、`app/page.test.tsx` を統合テストとして拡充（純粋な単体テスト + 統合テストの 2 段構え）。