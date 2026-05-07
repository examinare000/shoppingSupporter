# ADR-005: モック駆動フロントから実バックエンドへの移行戦略

## ステータス
採用済み

## 背景
ADR-004 でフロントエンドは `frontend/lib/mock/` のモックデータ駆動で先行構築する判断を行った。現状の構成は以下のとおり。

- フロントは `searchProducts(query)` という純粋関数（`lib/mock/searchClient.ts`）に依存し、`MOCK_PRODUCTS` 配列をクライアント側でフィルタする。
- バックエンド (`api/main.py`) には `/api/health` と全件返す `/api/products` のみが存在し、検索エンドポイントや実質価格 API はまだ無い。
- 公式 API の実呼び出し・Cron 連携・DB の本番運用は未着手で、`UserProfile` を加味した実質価格計算もまだコード化されていない。

このまま機能追加を続けるとモック前提の API 形状がフロント側に固着し、後から差し替える際に破壊的変更が連鎖するリスクが高い。一方で「公式 API・DB・Cron が全部揃ってから一気にスワップ」する big-bang 移行はリスクが大きく、UI 開発も止まる。

## 検討した選択肢

1. **Big-bang 切替**: 公式 API 連携と DB 投入が揃った時点で `lib/mock/` を一括削除し、`fetch` ベースの実装に置き換える。
2. **アダプター層 + 段階的差し替え**: `searchClient` を抽象化し、ビルド時 / 実行時フラグで「モック実装」と「HTTP 実装」を切り替えられる構造にしてから、機能単位で実装を移行する。
3. **MSW (Mock Service Worker) でネットワーク層をモック化**: 早期から `fetch('/api/...')` ベースで書き、開発・テスト時のみ MSW でモックレスポンスを返す。

## 決定（提案）

選択肢 **2 をベースに、テストでは選択肢 3 の手法を併用**する。具体的には：

1. **フロントは `searchClient` を関数シグネチャごと `fetch` 版に差し替えられる純粋なインターフェースとして扱い続ける。**
   - 現行の `searchProducts(query: string): Product[]` はそのまま残し、バックエンド接続版は `searchProducts(query: string): Promise<Product[]>` の async 版として導入する。
   - 呼び出し側 (`app/page.tsx`) は `useMemo` から `useEffect`（または React Query 等）に切り替える前提。

2. **`lib/mock/` は削除せず、テスト用フィクスチャとして残す。**
   - `MOCK_PRODUCTS` は単体テストやストーリー用の固定データセットとしての価値が高い。
   - 本番ビルドのバンドルから外すには、`lib/mock/` をテストコードからのみ import される配置にするか、Tree-shaking の効くエクスポート構造を保つ。

3. **ユーザー文脈を加味した実質価格計算はバックエンドに移譲する。**
   - 楽天ランク・Prime / Premium 加入・所有カードによるサイト別倍率は、フロントから `UserProfile` を投げて API 側で算出し、計算済みの `effectivePrice` を返す。
   - フロントの `lib/pricing/effectivePrice.ts` は「素の式 + 0 下限」のままで残す（ログイン無し / ゲスト時のフォールバック計算として価値がある）。

4. **検索は DB 主導とする。**
   - 公式 API は Cron で叩いて DB に格納する片方向流。検索リクエストごとに公式 API を叩かない。
   - 理由: 公式 API のレート制限を消費しない、レスポンス時間の予測がつく、検索結果の一貫性。

5. **API コントラクトは OpenAPI 経由で型同期する。**
   - FastAPI が生成する OpenAPI を取り込んで TypeScript 型を生成する（`openapi-typescript` 等）。
   - `frontend/types/product.ts` のうちサーバ由来の型はジェネレート版に置き換え、フロント固有の型 (`ImagePriority` / `SortKey` / `ResolvedImage`) は手書きで残す。

6. **画像取得優先度はクライアント側のままにする。**
   - 出品データには 3 サイト分の画像 URL を全て載せて返し、どれを表示するかはクライアントで決める。
   - 設定はユーザー個別の好みであり、`localStorage` 永続化のままで運用上十分。サーバ側に保存する必要が出るのは「複数端末で同期したい」要望が出た時点で再検討。

## 理由

- **段階的差し替え (選択肢 2)**: モックを残しつつ実装をスワップできるので、UI 開発と API 開発を並行できる。big-bang はリスクが高く、フィーチャー開発を止める期間が発生する。
- **MSW (選択肢 3) を採用しない**: 本番と異なるネットワーク層が挟まることでハイドレーション・キャッシュ周りの落とし穴が増える。今は純粋関数のスワップで十分シンプル。テスト時の HTTP モックが必要になった時点で改めて検討する。
- **DB 主導の検索**: 公式 API のレート制限と応答遅延を検索クリティカルパスに乗せたくない。Cron で取り込んで Postgres の全文検索 / trigram で検索するほうが運用が読める。
- **OpenAPI 型同期**: ADR-001 で「型定義の同期に注意」と明記済みの課題への具体的解決策。手動で型を二重管理する負債を防ぐ。

## 影響

- `searchProducts` を `Promise` 返しに変えるタイミングで、トップページのレンダリング戦略を「`useMemo` 同期」から「`useEffect` 非同期 + ローディング表示」に書き換える必要がある。既存の `loading.tsx` を使い回せる。
- バックエンドに新エンドポイントが必要：
  - `GET /api/products/search?q=...` — 検索結果のリスト
  - `POST /api/products/effective-price` — ユーザー文脈付きの実質価格計算（または Cookie / セッションから `UserProfile` を引いて検索結果に同梱する設計でも可）
- `api/main.py` の `title="Shopping Supporter API"` を `"pricehack API"` に修正する必要がある（本 ADR の対象外。別タスクで処理）。
- `MOCK_PRODUCTS` が本番バンドルに混入しないか、移行時にバンドル分析で確認する。
- OpenAPI からの型生成スクリプトを `package.json` の `scripts` に追加し、CI で型ドリフトを検出できるようにする。

## 未決事項

- **ユーザー認証・セッションの方式**（Cookie / JWT / NextAuth.js など）— `UserProfile` を API に渡す手段はこの選択に依存する。別途 ADR を起票する。
- **検索の全文検索バックエンド**（Postgres trigram / GIN / 外部の全文検索サービス）— データ量が見えてから決める。

## 進捗（2026-05-05 時点）

- 決定 1（`searchClient` の async 化）: ✅ 完了。SWR 採用により `fetch` ベースの実装へ移行済み（`frontend/lib/api/searchClient.ts`）。
- 決定 2（`lib/mock/` のテストフィクスチャ残置）: 撤回。コードベースのクリーンアップのため `frontend/lib/mock/` は削除済み。
- 未決事項「ユーザー認証」: ✅ 完了。ADR-007 に基づき JWT 認証（signup/login/me）が実装済み。
- 未決事項「全文検索バックエンド」: ✅ 完了。Postgres FTS + pg_trgm が実装済み（ADR-010）。
- フェーズ 1 タスク:
    - T-03: JWT 認証基盤 ✅ 完了
    - T-04: Card マスタ API ✅ 完了
    - T-05: UserProfile API ✅ 完了
    - T-07: 商品検索 API（匿名版） ✅ 完了
- 残課題: フロント `Product` 型と API `ProductSummary` の型契約整合（T-08 で `Listing` 同梱、T-09 で OpenAPI 経由の型生成へ寄せる）。現状、API 側の envelope 形式とフロントの期待値に乖離があるため、結合の最終フェーズで解消する。
