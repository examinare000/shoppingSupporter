調査結果をまとめます。重要な発見として、参照資料の `docs/design/backend-api-spec.md` が存在しないことが判明したため、これをまず確認事項として明記します。

# 計画レポート: フロントエンド API接続への移行

## 1. 参照資料の状態（重要）

タスク指示書の参照資料 `docs/design/backend-api-spec.md` は**存在しない**。

```
$ docs/ 配下: adr/ と system-design.md のみ。design/ ディレクトリ自体が無い
$ Glob で **/backend-api-spec* を探索 → ヒット 0
```

リポジトリに残る関連情報は `docs/adr/005-mock-to-backend-migration.md`（提案中）のみ。ADR-005 には以下の言及がある:
- エンドポイント候補: `GET /api/products/search?q=...`
- 検索結果は DB 主導でリストを返す（公式 API はフロントから直接叩かない）
- OpenAPI による型同期を方針として提示（未着手）

ただし ADR-005 はタスク指示書が「唯一のソース・オブ・トゥルース」として指定したファイルではない。Planner ポリシー上、**参照資料が無い場合に別ファイルで代用することは禁止**されているため、本計画では ADR-005 の内容は「実装ガイドラインの暫定根拠」として扱うに留め、確定仕様としては扱わない。

→ **確認事項#1（最優先）**: `docs/design/backend-api-spec.md` を提供するか、ADR-005 を SoT として承認するか、別の確定仕様を提示してほしい。

以下の計画は、上記が解決されることを前提に、ADR-005 と既存型定義を暫定基盤として組み立てている。仕様確定後に「エンドポイントパス」「クエリパラメータ名」「エラーレスポンス body の形」のみ調整可能な構造にしておく。

## 2. 現状コードの棚卸し

| ファイル | 現状 | 行数 |
|---|---|---|
| `frontend/lib/mock/searchClient.ts` | 同期関数 `searchProducts(q): Product[]`。MOCK_PRODUCTS をクライアント filter | 19 |
| `frontend/lib/mock/searchClient.test.ts` | 同期前提のユニットテスト 8 件 | 55 |
| `frontend/lib/mock/products.ts` | MOCK_PRODUCTS 配列。8 商品 × 3 サイトの出品データ | 369 |
| `frontend/app/page.tsx` | `useMemo(() => searchProducts(query), [query])` で同期データ取得 | 64 |
| `frontend/app/page.test.tsx` | 同期前提の HomePage 統合テスト 2 件 | 53 |
| `frontend/app/loading.tsx` | Next.js App Router のルート遷移用 loading UI（エディトリアル静的プレースホルダ） | 39 |
| `frontend/package.json` | SWR は未インストール（`react`, `next` のみ） | 38 |

`searchProducts`/`searchClient` の参照箇所:
- `frontend/lib/mock/searchClient.ts`（実装）
- `frontend/lib/mock/searchClient.test.ts`（テスト）
- `frontend/app/page.tsx`（唯一の呼び出し元）

→ 影響範囲は閉じている。アプリ本体での使用箇所は `app/page.tsx` 1 箇所のみ。

## 3. 要件 → 変更要否マトリクス

| # | 要件 | 変更要否 | 根拠 |
|---|------|---------|------|
| R1 | searchClient の fetch 化 | **変更要** | 現在は `searchClient.ts:10-18` で `MOCK_PRODUCTS.filter(...)` の同期処理 |
| R2 | エンドポイント定数を 1 箇所定義 | **追加要** | 現状そのような定数は存在しない |
| R3 | 旧同期 `searchProducts` の削除 | **削除要** | task 明示「後方互換は持たせない」 |
| R4 | HomePage の SWR 化 | **変更要** | 現在は `app/page.tsx:29` で `useMemo` 同期 |
| R5 | 旧 useMemo の削除 | **削除要** | task 明示「後方互換コードは入れない」 |
| R6 | ローディング UI（スピナー） | **追加要** | 既存 `app/loading.tsx` はルート遷移用で、SWR の loading 状態とは別レイヤー |
| R7 | エラー UI（リトライボタン付き） | **追加要** | 現状は無い |
| R8 | リトライボタンで再取得（SWR の `mutate`） | **追加要** | エラー画面と一体で実装 |
| R9 | 正常時レンダリング | **既存維持** | `SearchResultsSection` `EmptyState` は `Product[]` を受ける契約のままで再利用可 (`SearchResultsSection.tsx:62-79`) |

## 4. UI 要素の棚卸し（デザイン参照ポリシー適用）

タスク指示書には UI 要件として「スピナー」「リトライボタン付きエラー画面」が明記されている。デザイン仕様書としての参照ファイルは存在しないため、棚卸しは task 文言ベースで行う。

| 要素 | 現行 | 期待 | 変更要否 | 備考 |
|------|------|------|---------|------|
| Masthead 表示 | あり | 維持 | 不要 | `page.tsx:37` |
| HeroSearch（h1 + 検索フォーム） | あり | 維持 | 不要 | `page.tsx:39` |
| Hits N 件 / Query 表示 | `SearchResultsSection` 内 | 維持 | 不要 | `SearchResultsSection.tsx:85-87` |
| ImagePriorityControl（折りたたみ） | あり | 維持 | 不要 | `SearchResultsSection.tsx:91-103` |
| SortControl | あり | 維持 | 不要 | `SearchResultsSection.tsx:88` |
| ProductDossier 一覧 | あり | 維持 | 不要 | `SearchResultsSection.tsx:108-115` |
| EmptyState（ヒット 0 件） | あり | 維持 | 不要 | `SearchResultsSection.tsx:78-80` |
| **ローディング表示** | **無し** | **スピナー** | **新規** | クエリ送信後・データ未到着時 |
| **エラー表示** | **無し** | **エラー文言 + リトライボタン** | **新規** | fetch 失敗時 |
| Footer | あり | 維持 | 不要 | `page.tsx:55-59` |
| 既存 `app/loading.tsx` | エディトリアル静的プレースホルダ | **このタスクでは触らない** | 不要 | Next.js のルート遷移用 loading で、SWR の loading 状態とは別レイヤー |

**スコープ外要素の明示:**
- 既存 `app/loading.tsx`: Next.js App Router のルート遷移時 UI。SWR による画面内データ取得とは別レイヤーであり、本タスクの「スピナー」は HomePage 内の SWR loading 状態に対するもの。`loading.tsx` の差し替えは不要。
- prefers-reduced-motion: `globals.css:48-55` で既に全アニメーション抑制が定義済み。スピナーもこの規則の対象になる前提で CSS-only 実装にする。

## 5. アーキテクチャ判断

### 5.1 ディレクトリ・モジュール配置

**現状の問題**: ファイルが `frontend/lib/mock/searchClient.ts` にある。fetch ベースで実 API を呼ぶようになると、もはや「モック」ではない。

**判断**: モジュール移動は task の「searchClient.ts を fetch ベースに変更」の自然な解釈に含まれる（同名の概念物を、責務に合った場所に置く）。次の構造を採用する。

```
frontend/
├── lib/
│   ├── api/
│   │   ├── endpoints.ts        # 新規: エンドポイント定数
│   │   ├── searchClient.ts     # 新規: fetch ベース。旧 mock/searchClient.ts を置換
│   │   └── searchClient.test.ts# 新規: fetch のユニットテスト
│   ├── mock/
│   │   └── products.ts         # 維持: MOCK_PRODUCTS をテスト用フィクスチャとして保持（ADR-005 §2 に整合）
│   └── ...（他は変更なし）
├── components/
│   └── feedback/
│       ├── Spinner.tsx              # 新規
│       └── SearchErrorState.tsx     # 新規（リトライボタン付きエラー画面）
└── app/
    └── page.tsx                # 既存を SWR 化
```

旧 `lib/mock/searchClient.ts` と `lib/mock/searchClient.test.ts` は削除する。
ナレッジ「画面追加時のルーティング配線」: 新規 URL は追加されないため Router 配線の確認は対象外（既存 `app/page.tsx` の中身を変えるだけ）。

### 5.2 知識ベースとの整合性チェック

| 知識・ポリシー | 適用 | 計画との整合 |
|-----|------|------|
| データ取得は View で行い、子に props で渡す | 適用 | `HomePage` で `useSWR` を呼び、`SearchResultsSection` に `Product[]` を props で渡す（既存契約のまま） |
| ローディング/エラー表示は View 層で早期リターン | 適用 | `HomePage` 内で `isLoading` → Spinner、`error` → SearchErrorState、それ以外は SearchResultsSection |
| TanStack Query 等のキャッシュ適性 | 適用 | 検索結果は「クエリに対する read-only な一覧」。ページングなし。SWR デフォルトキャッシュは適合する |
| 横断的関心事は API クライアント層に置く | 適用 | エラー応答ハンドリングは `searchClient.ts` 内で `Response.ok` を見て例外化、SWR でキャッチさせる |
| 機能（バリデーション・在庫判定）はバックエンドに | 適用 | フロント側ロジックの追加なし。`searchProducts` は I/O のみ |
| 「ルートは薄く、View でデータ取得」 | **部分適用に留める** | 知識は `app/routes/` 構成を想定。Next.js App Router の `app/page.tsx` 自体がルートかつ唯一のページ。今回は構造の大改造はせず、`page.tsx` 内で `useSWR` を呼ぶ最小修正に留める。route と view を分離する大規模リファクタはタスクのスコープ外（task 「これ以外の変更は行わない」） |
| API クライアント生成ツール (Orval/openapi-typescript) | 該当なし | プロジェクトに生成設定なし。手書き fetch で OK |
| useEffect 地獄・mount-only effect | 該当なし | SWR が effect を抽象化するため、自前 effect は書かない |
| any 型禁止 | 適用 | レスポンスの型を `Product[]` にする。エラーは `Error` サブクラスにする |

### 5.3 SWR 採用の確認

| 観点 | 判定 |
|------|------|
| データ特性 | 単一クエリに対する read-only リスト。ページングなし |
| キャッシュ適性 | OK（同じクエリでの再表示が即座に出る） |
| 再取得トリガー | クエリ文字列変化（key 変化）/ リトライ（mutate）/ ウィンドウフォーカス（SWR デフォルト挙動。検索結果なら許容） |
| クエリ空文字の扱い | SWR の `key: null` で fetch をスキップ。HomePage 側で「空クエリは結果セクション自体描画しない」既存仕様を維持できる |

→ SWR 採用は適合。新規依存追加は task に明記の技術選定なので OK。

## 6. 実装ガイドライン（Coder/write_tests 向け）

### 6.1 `frontend/lib/api/endpoints.ts`（新規）

```ts
// バックエンドの検索エンドポイント。SoT は docs/design/backend-api-spec.md（未提供時は ADR-005 暫定）。
// 同一定数を複数箇所で文字列リテラル化しない。
export const API_BASE = '/api'; // Vercel rewrite で /api/(.*) → /api/main.py
export const PRODUCTS_SEARCH_PATH = '/products/search';

export const buildProductsSearchUrl = (query: string): string => {
  const params = new URLSearchParams({ q: query });
  return `${API_BASE}${PRODUCTS_SEARCH_PATH}?${params.toString()}`;
};
```

仕様確定後に変える可能性がある箇所:
- `PRODUCTS_SEARCH_PATH`（パス変更）
- クエリパラメータ名 `q`（仕様で異なれば変更）
- レスポンス body のラップ有無（`{items: Product[]}` 等の場合は searchClient 側で剥がす）

### 6.2 `frontend/lib/api/searchClient.ts`（新規）

責務:
1. `buildProductsSearchUrl(query)` を呼んで `fetch`
2. `Response.ok` チェックし、失敗時は `Error` を throw（SWR でキャッチ）
3. JSON を `Product[]` として返す（型ガードまで踏み込まない方針：バックエンドが信頼できる前提。ナレッジ「ドメインロジックの配置」より、型整形はサーバー側責務）

シグネチャ:
```ts
export async function searchProducts(query: string): Promise<Product[]>
```

エラー扱い:
- HTTP 4xx/5xx → `Error('検索に失敗しました (HTTP {status})')` を throw
- ネットワーク失敗 → fetch 自体が reject。そのまま伝播
- パースエラー → `await res.json()` の reject をそのまま伝播

備考: 旧 `lib/mock/searchClient.ts` の「空クエリで全件返す」「trim」「大文字小文字無視」のクライアント側ロジックは**削除**。これらは**サーバー側責務に移譲**される（task 「同期前提でのみ使われていたコード」削除指示、ナレッジ「ドメインロジック・フィルタはバックエンド」）。

### 6.3 `frontend/components/feedback/Spinner.tsx`（新規）

CSS-only スピナー。エディトリアル意匠と矛盾しないシンプルな円。`role="status"` と `aria-label` を付与（アクセシビリティ知識「フォーム要素にlabelなし → REJECT」と同様、フィードバック要素にも適用）。`prefers-reduced-motion` は globals.css のグローバルルールで自動的に静止する。

### 6.4 `frontend/components/feedback/SearchErrorState.tsx`（新規）

- 二重罫線で囲うエディトリアル風（既存 `EmptyState.tsx` と同じトーン）
- `<button>` 要素のリトライボタン
- props: `{ error: Error; onRetry: () => void }`
- ボタンクリックで `onRetry()` を呼ぶ。HomePage 側で SWR の `mutate()` を渡す

### 6.5 `frontend/app/page.tsx`（既存修正）

現状の `useMemo` を削除し、SWR を導入する:

```tsx
const swrKey = query !== '' ? buildProductsSearchUrl(query) : null;
const { data, error, isLoading, mutate } = useSWR<Product[]>(
  swrKey,
  () => searchProducts(query),
  // ※ fetcher 引数を使わず closure で query を読むのは SWR 的にも OK。
  //   ただし key を URL 文字列にしているため、key が変われば fetcher も新しい closure が使われる。
);
```

レンダリング分岐:
```
hasQuery が false → 結果セクション全体描画しない（既存挙動を維持）
hasQuery && isLoading → <Spinner />
hasQuery && error → <SearchErrorState error={error} onRetry={() => mutate()} />
hasQuery && data → <SearchResultsSection products={data} ... />（data.length === 0 は内部の <EmptyState /> に分岐する既存ロジック）
```

注意:
- 旧 `useMemo` は完全削除
- `searchProducts` の import 元は `@/lib/api/searchClient` に変更
- 既存の `useImagePriority` フックは無関係なのでそのまま

### 6.6 配線の確認（呼び出しチェーン検証）

| 接続先 | 渡す値 | 確認 |
|--------|--------|------|
| `useSWR` | `swrKey`, fetcher | ◯ |
| `searchProducts` | `query: string` | ◯ |
| `SearchResultsSection` | `products`, `query`, `priority`, `onMoveUp`, `onMoveDown`, `onResetPriority` | 既存契約のまま。`products` の供給元が data になるだけ |
| `Spinner` / `SearchErrorState` | （新規）error, onRetry | View で完結 |

新規パラメータの追加は無し（既存 props 契約を維持）。SearchResultsSection 等の子コンポーネントの修正は不要。

## 7. 削除すべきコード（後方互換禁止）

| 対象 | 理由 |
|------|------|
| `frontend/lib/mock/searchClient.ts` | 旧同期実装。新実装で置換 |
| `frontend/lib/mock/searchClient.test.ts` | 旧同期テスト。新テストで置換 |
| `app/page.tsx` の `useMemo` 呼び出しと `searchProducts` の同期 import | task 明示「旧 useMemo 同期処理は削除」 |
| 旧 `searchProducts` 内の trim・lowercase・filter ロジック | サーバー責務に移譲（クライアント側の重複ロジックは禁止） |

`frontend/lib/mock/products.ts`（MOCK_PRODUCTS）は ADR-005 §2 に従い**維持**する（テスト用フィクスチャ）。本タスクで未使用化はしない。

## 8. テスト方針（write_tests に渡すガイドライン）

### 8.1 `frontend/lib/api/searchClient.test.ts`（新規）

vitest の `vi.spyOn(global, 'fetch')` か、`globalThis.fetch = vi.fn()` でモック。MSW は不要（ADR-005 §3）。

ケース:
1. 正常系: `fetch` が `Response(JSON, status=200)` を返すと `Product[]` を返す
2. URL アサーション: `buildProductsSearchUrl('イヤホン')` が呼ばれた URL と一致
3. クエリパラメータのエンコーディング: 日本語/空白/特殊文字
4. HTTP 4xx エラー: `Error` が throw される（メッセージにステータスコードを含む）
5. HTTP 5xx エラー: `Error` が throw される
6. ネットワークエラー: `fetch` の reject がそのまま伝播
7. レスポンスの型: 返却値が `Product[]` 型として扱える（型レベル/最小フィールドの検証）

### 8.2 `frontend/app/page.test.tsx`（既存更新）

既存 2 ケースは新仕様に追従する。`global.fetch` をモック化し、状態別に応答を切り替える。

ケース:
1. 初期表示: フォームのみ。Hits 表示・article は無い（既存と同じ）
2. 検索 → ローディング: 検索クリック直後に `role="status"` のスピナーが見える
3. 検索 → 成功: fetch が `[Product]` を返したあと、Hits 件数と該当 article が描画される
4. 検索 → エラー: fetch が 500 を返すとエラーメッセージとリトライボタンが見える
5. リトライ: エラー後にリトライボタンを押すと再 fetch が走り、成功時にデータが描画される

非同期描画は `findBy*` を使う。`waitFor` でスピナー消失を待つ。

### 8.3 既存 `frontend/lib/mock/searchClient.test.ts` は削除

旧モジュール削除と同時に削除する。

### 8.4 ナレッジ「外部UIライブラリとの統合」

SWR は UI ライブラリではないが、ライブラリ本体を完全モックすると壊れる懸念は同様。テストでは `useSWR` をモックせず、`fetch` を境界としてモックする方針で実マウントの破綻を検出する。

## 9. アンチパターンとして特に注意すること（Coder 向け）

| アンチパターン | 該当箇所 | 対策 |
|------|------|------|
| Magic Strings（エンドポイント文字列の散在） | `searchClient.ts` から直接 fetch しない | `endpoints.ts` の定数経由 |
| エラー握りつぶし | fetch 失敗時の `catch` で空処理しない | SWR に伝播させる |
| TODO コメント | 「後で実装」系のコメント禁止 | 仕様確定→今やる、または削除 |
| 隠れた依存（コンポーネント内 fetch） | `Spinner` `SearchErrorState` `EmptyState` 内で fetch しない | View（HomePage）が唯一の fetch トリガー |
| `any` 型 | レスポンスを `any` で受けない | `Product[]` で受ける |
| useEffect 地獄 | 自前 useEffect で fetch しない | SWR に任せる |
| MOCK_PRODUCTS の本番混入 | searchClient.ts から MOCK_PRODUCTS への参照を残さない | 旧 `lib/mock/searchClient.ts` の参照を完全に消す |
| 不要なメモ化 | SWR の data に対する `useMemo` ラッパは不要 | 既存の `SearchResultsSection` 内 useMemo は維持（ソート責務） |

## 10. 受け入れ条件（task のものを再掲し、検証手段を付記）

| 条件 | 検証 |
|------|------|
| `searchClient.ts` が fetch ベース | 8.1 のテスト |
| API 仕様に整合 | 仕様確定後、8.1 の URL アサーションと併せて確認 |
| HomePage が 3 状態を SWR 経由で描画 | 8.2 のケース 2/3/4 |
| リトライボタンで再取得 | 8.2 のケース 5 |
| 旧 useMemo・デッドコードが残っていない | grep `useMemo.*searchProducts`, `lib/mock/searchClient` がヒット 0 |
| 型チェックと全テストが pass | `npm run typecheck && npm test` |

## 11. 確認事項

| # | 内容 | 影響 |
|---|------|------|
| 1（必須） | `docs/design/backend-api-spec.md` を提供するか、ADR-005 を SoT として承認するか | エンドポイントパス・クエリパラメータ名・レスポンス body 形・エラー body 形が確定する |
| 2 | 仮に SoT が ADR-005 で確定する場合、`POST /api/products/effective-price` の同時利用は本タスクのスコープか | task は「searchClient.ts」「HomePage」「ローディング/エラーUI」の 3 点のみとしているため、現計画では search のみ対象。確認したい |

確認事項#1 が解決されるまで、`endpoints.ts` の値と `searchClient.ts` の URL アサーションは ADR-005 暫定（`GET /api/products/search?q=...`、レスポンス `Product[]`）で進めることを推奨する。確定後の差分は endpoints.ts と一部テストの URL アサーションのみで吸収できる構造にしてある。