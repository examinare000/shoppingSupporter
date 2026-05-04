# タスク計画

## 元の要求

`.takt/runs/20260503-155409-api-searchclient-ts-fetch-hom/context/task/order.md` に基づき、フロントエンドを API 接続へ移行する。具体的には次の 3 点。

1. `searchClient.ts` を fetch ベースの非同期実装に切り替える
2. `HomePage` のレンダリングを SWR による非同期取得に対応させる
3. ローディング（スピナー）・エラー（リトライボタン付き）の UI を実装する

技術選定は確定済み（SWR / スピナー / リトライボタン付きエラー画面）。後方互換コードは持たせない。

## 分析結果

### 目的

フロントエンドのデータ取得経路を、クライアント側の同期 mock filter から、バックエンド API への非同期 fetch に置き換える。これにより以下を達成する。

- 検索結果の出処をバックエンド DB（将来の OpenAPI 同期対象）に集約
- フロント側のドメインロジック（フィルタ・大文字小文字無視・空クエリ全件返し）をサーバー責務へ移譲
- 非同期取得の 3 状態（ローディング／エラー／成功）を SWR でハンドリング
- 旧 `useMemo` 同期実装を残さず削除（後方互換ゼロ）

### 参照資料の調査結果

タスク指示書が「唯一のソース・オブ・トゥルース」と明記した `docs/design/backend-api-spec.md` は **存在しない**。

```
docs/ 配下: adr/ と system-design.md のみ。design/ ディレクトリ自体が無い
Glob で **/backend-api-spec* → ヒット 0
```

代替候補として `docs/adr/005-mock-to-backend-migration.md`（提案中ステータス）があり、以下を提示している。

- 検索エンドポイント候補: `GET /api/products/search?q=...`
- DB 主導検索（公式 API はフロントから直叩きしない）
- `searchProducts` を `Promise<Product[]>` 返しに変更し、`app/page.tsx` を `useEffect`/React Query 等に切り替える前提
- `lib/mock/products.ts` はテスト用フィクスチャとして残す

ただし ADR-005 は task 指示書が指定したファイルではないため、Planner ポリシー上「参照資料の代用」として確定情報には使えない。本計画は ADR-005 を **暫定根拠** として扱い、確認事項#1 で SoT の取り扱いを確認する。

現在の実装との主要な差異:

| 観点 | 現状 | 期待 |
|---|---|---|
| `searchClient` シグネチャ | `searchProducts(q): Product[]`（同期） | `searchProducts(q): Promise<Product[]>` |
| データソース | `MOCK_PRODUCTS` をクライアント filter | バックエンド `GET /api/products/search?q=...`（暫定） |
| `app/page.tsx` のデータ取得 | `useMemo(() => searchProducts(query), [query])` | `useSWR(key, fetcher)` |
| ローディング表示 | 無し（同期なので発生しない） | スピナー |
| エラー表示 | 無し | エラー文言＋リトライボタン |
| エンドポイント定数 | 無し | `lib/api/endpoints.ts` に集約 |

### デザイン要素の判定

タスク指示書には UI 要素として「スピナー」「リトライボタン付きエラー画面」が明記されている。デザイン仕様書ファイルは存在しないため、棚卸しは task 文言と現行実装ベースで行う。

| 要素 | 変更要/不要 | 根拠 |
|------|-------------|------|
| Masthead 表示 | 不要 | `app/page.tsx:37` で既存。task は触らない |
| HeroSearch（h1 + 検索フォーム） | 不要 | `app/page.tsx:39` で既存 |
| Hits N 件 / Query 表示 | 不要 | `SearchResultsSection.tsx:85-87` で既存 |
| ImagePriorityControl（折りたたみ） | 不要 | `SearchResultsSection.tsx:91-103` で既存 |
| SortControl | 不要 | `SearchResultsSection.tsx:88` で既存 |
| ProductDossier 一覧 | 不要 | `SearchResultsSection.tsx:108-115` で既存 |
| EmptyState（ヒット 0 件） | 不要 | `SearchResultsSection.tsx:78-80` で既存。`Product[]` を受ける契約のまま再利用 |
| **ローディング表示（スピナー）** | **新規追加** | task 明示。現行に該当 UI 無し |
| **エラー表示（リトライボタン）** | **新規追加** | task 明示。現行に該当 UI 無し |
| Footer | 不要 | `app/page.tsx:55-59` で既存 |
| 既存 `app/loading.tsx` | 不要（スコープ外） | Next.js App Router のルート遷移用。SWR の loading 状態とは別レイヤーのため差し替え対象外 |
| `globals.css` の `prefers-reduced-motion` 規則 | 不要 | `globals.css:48-55` で全アニメ抑制が定義済み。スピナーもこの規則の対象 |

### スコープ

**変更**:
- `frontend/app/page.tsx`（`useMemo` 削除、`useSWR` 導入、状態別レンダリング分岐）
- `frontend/app/page.test.tsx`（非同期テストへ更新）
- `frontend/package.json`（`swr` 依存追加）

**新規**:
- `frontend/lib/api/endpoints.ts`（エンドポイント定数）
- `frontend/lib/api/searchClient.ts`（fetch 版 `searchProducts`）
- `frontend/lib/api/searchClient.test.ts`（fetch のユニットテスト）
- `frontend/components/feedback/Spinner.tsx`
- `frontend/components/feedback/SearchErrorState.tsx`

**削除**:
- `frontend/lib/mock/searchClient.ts`（旧同期実装）
- `frontend/lib/mock/searchClient.test.ts`（旧同期テスト）

**維持**:
- `frontend/lib/mock/products.ts`（ADR-005 §2 によりテスト用フィクスチャとして保持）
- `frontend/components/search/*`（`SearchResultsSection` 等の既存 props 契約は維持）
- `frontend/app/loading.tsx`（ルート遷移用、別レイヤー）

呼び出しチェーン検証: `searchProducts` の参照は `searchClient.ts`／`searchClient.test.ts`／`app/page.tsx` の 3 箇所のみ（grep 確認済み）。アプリ本体の呼び出し元は `app/page.tsx` 1 箇所だけで、影響は閉じている。

### 検討したアプローチ

| アプローチ | 採否 | 理由 |
|-----------|------|------|
| `lib/mock/searchClient.ts` を直接書き換えて fetch 版にする | 不採用 | 「mock」配下に実 API クライアントを置くのは責務名と齟齬。新ファイル `lib/api/searchClient.ts` で置換する方が読みやすい |
| `lib/api/searchClient.ts` への配置（採用） | 採用 | task の「searchClient.ts を fetch ベースに変更」の自然な解釈。同名概念を責務に合った場所に移動 |
| ルートを薄くし `HomeView` コンポーネントを切る | 不採用 | フロント知識は React Router 想定。Next.js App Router では `app/page.tsx` 自体がルート兼ページ。task の「3 点以外の変更は行わない」に従い、route と view の構造分離は別タスクとする |
| `useEffect` ＋ 自前 state で fetch | 不採用 | task が SWR を確定指定。再取得・キャッシュ・エラー伝播を自前で書くより SWR のほうがアンチパターン回避になる |
| MSW でテスト時のモック | 不採用 | ADR-005 §3 で MSW 不採用が確定。`global.fetch` を vitest でスタブする |
| クライアント側 trim/lowercase/全件返しを残す | 不採用 | task 「同期前提でのみ使われていたコード」削除指示。フィルタ責務はサーバー側に移譲（フロント・バックの責務分離知識に整合） |
| ローディングを既存 `app/loading.tsx` で代用 | 不採用 | `app/loading.tsx` は Next.js のルート遷移時 UI で、SWR の画面内 loading とは別レイヤー。task は「スピナー」と明示しているため新規 UI を作る |
| レスポンス body を `Product[]` 直返しと仮定 | 暫定採用 | SoT が無いため ADR-005 と既存型定義 (`frontend/types/product.ts`) から推測。確認事項#1 が解決されたら `endpoints.ts` と `searchClient.ts` �� URL アサーションのみで吸収できる構造にする |

### 実装アプローチ

1. **境界の固定**: `lib/api/endpoints.ts` にエンドポイント定数とクエリ URL ビルダを定義し、文字列リテラルの散在を防ぐ。
2. **API クライアント層**: `lib/api/searchClient.ts` で `fetch` を呼び、`Response.ok` チェック後に JSON を `Product[]` で返す。失敗時は `Error` を throw し、SWR にキャッチさせる（横断的関心事を API クライアント層に閉じ込める）。
3. **View での取得**: `app/page.tsx` の `useMemo` を削除し、`useSWR<Product[]>(key, fetcher)` で取得。`key` は `query !== ''` のときのみ URL 文字列、空クエリでは `null` にして fetch をスキップ（既存の「空クエリは結果セクション非表示」挙動を維持）。
4. **状態別分岐**: `hasQuery && isLoading` → `<Spinner />`、`hasQuery && error` → `<SearchErrorState error onRetry={() => mutate()} />`、`hasQuery && data` → `<SearchResultsSection products={data} ...>`（既存の 0 件分岐は `SearchResultsSection` 内の `EmptyState` で吸収）。
5. **新規 UI コンポーネント**: `Spinner`（CSS-only、`role="status"`、`aria-label`）と `SearchErrorState`（既存 `EmptyState` と同トーンの二重罫線、`<button>` で `onRetry` を呼ぶ）を `components/feedback/` に追加。
6. **依存追加**: `package.json` に `swr` を追加。
7. **削除**: 旧 `lib/mock/searchClient.ts`／`lib/mock/searchClient.test.ts` と `app/page.tsx` の同期 import／`useMemo` を完全削除。
8. **テスト**: `lib/api/searchClient.test.ts` で `global.fetch` をスタブし URL・正常系・HTTP エラー・ネットワークエラーを検証。`app/page.test.tsx` を `findBy*`／`waitFor` ベースの非同期テストに更新し、ローディング／成功／エラー／リトライ動作を網羅。

## 実装ガイドライン

### 参照すべき既存実装パターン

- 既存ローディング系プレースホルダのトーン: `frontend/app/loading.tsx:11-37`（罫線＋スモールキャプスのエディトリアル）。Spinner は同テーマで馴染ませる
- 既存エラー風セクションのトーン: `frontend/components/search/EmptyState.tsx:16-41`（二重罫線＋センター寄せ＋`MarginalNote`）。`SearchErrorState` はこの構成を踏襲
- View でデータ取得 → 子に props で渡すパターン: `frontend/app/page.tsx:24-53` の現行構造を維持しつつ、データ取得を `useMemo` から `useSWR` に置換
- 既存テストの非同期パターン参考: `frontend/app/page.test.tsx` 内の `userEvent.setup()` ＋ `await user.click(...)` の流れを継承し、後段に `findByRole`／`findByText` を組み合わせる
- カラートークン: `frontend/app/globals.css:11-19`（`--ink-primary` `--rule-line` `--accent-vermilion` 等）。直書き 16 進カラー禁止、トークン参照のみ

### 変更の影響範囲（配線確認チェックリスト）

- `searchProducts` の import 元を `@/lib/mock/searchClient` → `@/lib/api/searchClient` に切り替える箇所: `app/page.tsx` のみ（grep 確認済み）
- `SearchResultsSection` の props 契約は変更しない（`products: Product[]` のまま）。子コンポーネントの修正は不要
- 新規 props（`onRetry` 等）は新規コンポーネント `SearchErrorState` に閉じる。既存コンポーネントへの新規パラメータ追加は無い
- `package.json` 更新後、ロックファイル（`package-lock.json`）の追従が必要

### このタスクで特に注意すべきアンチパターン

- **Magic Strings**: `'/api/products/search'` を `searchClient.ts` 内に直書きしない。`endpoints.ts` の定数経由のみ
- **エラー握りつぶし**: `searchClient` の `try/catch` で空 `catch` を作らない。例外は SWR に伝播させる
- **TODO コメント**: 「SoT 待ち」等の文言で TODO を残さない。仕様未確定箇所は `endpoints.ts` 1 ファイルに局所化することで対応
- **Hidden Dependencies**: `Spinner` `SearchErrorState` `EmptyState` 内で fetch しない。fetch トリガーは `HomePage` の `useSWR` のみ
- **`any` 型**: レスポンスは `Product[]` で受ける。`unknown` → 型ガードまで踏み込まず、サーバー応答信頼の前提（フロント・バック責務分離知識に従う）
- **useEffect 地獄**: SWR が effect を抽象化するため、自前 `useEffect(...fetch...)` を書かない
- **MOCK_PRODUCTS の本番混入**: `lib/api/searchClient.ts` から `MOCK_PRODUCTS` を import しない。本番バンドルに mock データが混入しないことを確認
- **不要なメモ化**: SWR の `data` をさらに `useMemo` でラップしない。`SearchResultsSection` 内の既存 `useMemo`（ソート責務）はそのまま維持

### 利用者向け機能の到達経路

- 新規 URL の追加なし。既存 `/`（`app/page.tsx`）からの検索フォーム送信が唯一の入口
- 検索 → ローディング → 結果（または EmptyState）／エラー（リトライ）の状態遷移を、HomePage 内で完結させる
- リトライ導線は `SearchErrorState` の `<button>`。SWR の `mutate()` を呼び、key（クエリ）を保持したまま再取得が走る
- Next.js Router 配線・メニュー・外部リンクの変更は無し（既存の単一ページ構成のまま）

### テスト指針

- `frontend/lib/api/searchClient.test.ts`: `global.fetch` を `vi.fn()` でスタブ。検証ケース: ① 正常系（`Product[]` 返却）／② URL アサーション（`buildProductsSearchUrl` 通りのパス・クエリ）／③ 日本語・空白・特殊文字のエンコーディング／④ HTTP 4xx で `Error` throw／⑤ HTTP 5xx で `Error` throw／⑥ ネットワーク失敗の伝播
- `frontend/app/page.test.tsx`: 既存 2 ケースを更新。検証ケース: ① 初期表示（フォームのみ、Hits・article 無し）／② 検索 → スピナー（`role="status"`）／③ 検索 → 成功（Hits と article）／④ 検索 → エラー画面とリトライボタン／⑤ リトライで再 fetch → 成功描画
- 旧 `frontend/lib/mock/searchClient.test.ts` は削除
- SWR 本体はモックしない（外部 UI ライブラリと同様、shallow モックでマウント時破綻を見逃すリスクを避ける）。境界は `fetch`

## スコープ外

| 項目 | 除外理由 |
|------|---------|
| `app/loading.tsx` の差し替え | Next.js App Router のルート遷移用 UI で、SWR の画面内 loading 状態とは別レイヤー。task の「ローディング UI（スピナー）」は HomePage 内の SWR loading に対する要求であり、`loading.tsx` は対象外 |
| `frontend/lib/mock/products.ts`（MOCK_PRODUCTS）の削除 | ADR-005 §2 で「テスト用フィクスチャとして保持」が方針。task も削除を指示していない |
| route と View の構造分離（`HomeView` コンポーネント抽出） | フロント知識は React Router 想定。Next.js App Router では `app/page.tsx` 自体がルート兼ページ。task 「これ以外の変更は行わない」に従い、構造リファクタは別タスクとする |
| `POST /api/products/effective-price`（ADR-005 で言及される実質価格計算 API）の利用 | task のスコープは「searchClient.ts／HomePage／ローディングエラー UI」の 3 点のみ。実質価格 API は別エンドポイントで、現行 `effectivePrice.ts` のクライアント計算を即時置換する指示も無い |
| OpenAPI 型生成パイプラインの導入 | ADR-005 で別途方針として提示されているが、task の確定指定に含まれない。手書きの `Product[]` 型で進める |
| バックエンド API 本体の実装／実 API との結合確認 | task 「やらないこと」で明示 |
| SWR 採用以外のキャッシュチューニング（`staleTime` 等の最適化） | task の確定仕様に含まれない。デフォルト挙動で進める |

## 確認事項

1. **（最優先・必須）** `docs/design/backend-api-spec.md` が存在しない。次のいずれかで確定してほしい。
   - (a) ファイルを提供する
   - (b) ADR-005 (`docs/adr/005-mock-to-backend-migration.md`) を SoT として承認する
   - (c) この計画内で API 契約を直接確定する（パス／HTTP メソッド／クエリパラメータ名／レスポンス body 形／エラー時 HTTP ステータス／エラー body 形）

   解決されない場合、本計画では暫定値として「`GET /api/products/search?q={query}`、レスポンス `Product[]` 直返し、エラー時は HTTP 4xx/5xx で `Error` を throw」で進める。確定後の差分は `endpoints.ts` の定数と `searchClient.test.ts` の URL/レスポンスアサーションのみで吸収できる構造にしている。

2. 確認事項#1 で API 契約が確定した際、`POST /api/products/effective-price` 等の追加エンドポイントが必要になっても、本タスクのスコープは search のみで進めてよいか。task 文言からは search のみだが、SoT 提示時に依存関係が判明する可能性がある。