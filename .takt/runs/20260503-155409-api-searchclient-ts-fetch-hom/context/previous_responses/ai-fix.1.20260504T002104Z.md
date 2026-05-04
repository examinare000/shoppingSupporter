Typecheck clean, all 82 tests pass, lint clean. Reporting:

---

## 確認したファイル
- `frontend/lib/mock/products.ts:17-368` — `MOCK_PRODUCTS` の定義本体（368 行）。ファイル全体を Read で開いて確認。
- `frontend/app/page.test.tsx:16-33` — `productEarbuds` を inline 定義しており `MOCK_PRODUCTS` を import していないことを確認。
- `frontend/lib/api/searchClient.test.ts:14-33` — `sampleProduct` を inline 定義しており `MOCK_PRODUCTS` を import していないことを確認。
- `frontend/lib/api/searchClient.ts` — `lib/mock/*` への参照なしを確認。
- `frontend/app/page.tsx` — `lib/mock/*` への参照なしを確認。
- `.takt/runs/.../context/task/order.md:24-50` — 「同期前提でのみ使われていたコード」の削除と「関連デッドコードが残っていない」が受け入れ条件であることを確認。
- `.takt/runs/.../context/policy/ai-fix.1.20260504T001714Z.md:486-498` — 「未使用コード」「リファクタリング後の旧コード残存」が禁止事項であることを確認。

## 実行した検索
- `Grep MOCK_PRODUCTS`（リポ全体）→ 本番・テストコードにヒットなし。`frontend/lib/mock/products.ts:17` の export 定義のみ。残りはレポート・ADR・docs。
- `Grep "lib/mock|@/lib/mock"`（リポ全体）→ frontend ソース／テスト側からの参照ゼロ（docs と reports のみ）。
- `find frontend -name '*.stories.*'` → storybook ファイルなし（ADR-005 が掲げる「ストーリー用途」も実体不存在）。
- `Grep "products"`（frontend 配下）→ `MOCK_PRODUCTS` への import が一切ないことを再確認。

## 修正内容
- 削除: `frontend/lib/mock/products.ts`（368 行のデッドコード `MOCK_PRODUCTS`）。
- 削除: `frontend/lib/mock/`（中身が消えた空ディレクトリ）。
- 更新: `.takt/runs/.../reports/coder-scope.md` — 削除対象に products.ts と空ディレクトリを追記、影響範囲記述を修正。
- 更新: `.takt/runs/.../reports/coder-decisions.md` の Decision #3 — 当初の「保持」判断を反転。order.md と Policy の優先順位を取り違えていたことを明記し、新たな根拠（grep 結果ゼロ／storybook 不在／order.md の「関連デッドコード残存禁止」要件）を記載。

修正方針として AI Reviewer 提示の (A)「`frontend/lib/mock/products.ts` を削除する」を採用。(B)「テスト側を MOCK_PRODUCTS 利用に書き換え」は 8 件中 1〜2 件しか使わず、テスト最小フィクスチャの粒度を崩すスコープ拡張になるため不採用。

## テスト結果
- `npm run typecheck --prefix frontend` → 成功（エラー 0）。
- `npm test --prefix frontend` → 14 ファイル / 82 テスト全パス。
- `npm run lint --prefix frontend` → 警告・エラーなし。