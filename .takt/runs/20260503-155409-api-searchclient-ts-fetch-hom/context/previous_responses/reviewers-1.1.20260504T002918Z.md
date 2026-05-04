## arch-review
# 設計レビュー（arch-review.1）

## 結果: APPROVE

## サマリー
本タスクのスコープ（searchClient の fetch 化／HomePage の SWR 化／ローディング・エラー UI）について、構造・モジュール化・呼び出しチェーン・契約文字列集約・デッドコード除去・テストカバレッジを検証した。スコープ外の構造リファクタは要求せず、ナレッジの REJECT 基準（DRY違反／インフラ層公開／旧コード残存／関連フィールド整合性／巨大ファイル）にも該当なし。`coder-decisions.md` に記録された 5 件の決定はいずれも plan / Policy と整合し、再考を要する判断は無い。

## 検証した項目

| 観点 | 結果 | 根拠 |
|------|------|------|
| ファイル分割 | ✅ | 全変更ファイルが 200 行以下（最大は `page.test.tsx` 193 行）。1 ファイル 1 責務 |
| モジュール構成（高凝集・低結合） | ✅ | `lib/api/` 配下に endpoints + searchClient + 各テストが集約。SWR 経由で View から fetch まで一方向依存。`searchClient` は `endpoints.ts` のみに依存 |
| 循環依存 | ✅ | `app → lib/api`、`app → components/feedback`、`components/feedback → components/editorial` の単方向のみ |
| レイヤー設計 | ✅ | View（`app/page.tsx`）→ API クライアント（`lib/api/searchClient.ts`）→ `fetch`。逆方向参照無し |
| 呼び出しチェーン | ✅ | `HomePage` が `useSWR(buildProductsSearchUrl(query), () => searchProducts(query))` で配線。`searchProducts` も内部で `buildProductsSearchUrl` を使い、URL は単一 SoT に集約 |
| 契約文字列の集約 | ✅ | `PRODUCTS_SEARCH_PATH` / `PRODUCTS_SEARCH_QUERY_PARAM` / `buildProductsSearchUrl` が `endpoints.ts` のみ。`/api/products/search` の grep ヒットは `endpoints.ts` 1 ファイルに局所化 |
| 操作の一覧性 | ✅ | `searchProducts` は `app/page.tsx` の 1 箇所のみから呼ばれ、目的単位で命名された関数経由。汎用関数が散在する状況にない |
| パブリック API 公開範囲 | ✅ | `lib/api/` から公開されるのは `searchProducts` / `buildProductsSearchUrl` / 定数のみ。インフラ詳細（`fetch` 引数構造体など）は漏れていない |
| 関数設計（1関数1責務） | ✅ | `buildProductsSearchUrl`（純関数・URL組立）／`searchProducts`（HTTP呼び出し）／`Spinner`／`SearchErrorState`／`HomePage` がそれぞれ単一責務。最大関数 `HomePage` も 60 行弱 |
| デッドコード | ✅ | `lib/mock/` ディレクトリ消滅、旧同期 `searchClient.ts` / `MOCK_PRODUCTS` / 旧テスト削除。`useMemo` 同期分岐は消失。grep で残存参照ゼロ |
| 旧コード・旧エクスポート残存 | ✅ | `git status` で 3 ファイル削除を確認。旧 `import` の残存無し |
| フォールバック値の乱用 | ✅ | `describeError` の `'原因不明のエラーが発生しました'` は SWR の `error: unknown` 仕様（非 Error 例外も流れ得る）に対する正規分岐。値マスクではなくユーザーに状態を伝える文言 |
| 関連フィールドのクロスバリデーション | ✅ | `swrKey = hasQuery ? URL : null` と fetcher の `query` closure が同じ `query` ステートから派生。`hasQuery` で UI を gating する分岐も `query !== ''` の同一判定で揃っている |
| テストカバレッジ | ✅ | `endpoints` (5 ケース：URL契約)、`searchClient` (8 ケース：正常/URL/メソッド/エンコード/空応答/4xx/5xx/ネットワーク失敗)、`page` (6 ケース：初期表示/ローディング/成功/エラー/リトライ/0件) で 4 状態 + リトライを網羅 |
| スコープ適切性 | ✅ | Plan の 3 点要件以外への波及なし。zod や OpenAPI 生成等の追加抽象化は導入していない |

## 設計判断の妥当性確認（`coder-decisions.md` 5 件）

| # | 判断 | 妥当性 |
|---|------|--------|
| 1 | SWR key を URL 文字列、fetcher は closure | ✅ URL をキーにすることでエンドポイント差替えがキャッシュ名前空間に自然反映。代替案（query 文字列キー）の衝突リスクを正しく回避 |
| 2 | リトライは `mutate()` のみ | ✅ SWR v2 既定動作で再検証。冗長な明示は Policy「デフォルト引数の冗長明示」と相反するため正解 |
| 3 | `MOCK_PRODUCTS` 削除 | ✅ Plan §「同期前提でのみ使われていたコード」削除指示と整合。grep で参照 0 件確認済み |
| 4 | `Spinner` の `label` props 削除 | ✅ Policy「全呼び出し元が省略 → 必須化」を一段進め、単一用途のため固定文言化。値の出処が 1 箇所に固定された |
| 5 | レスポンスを `as Product[]` で受ける | ✅ ADR-005 §5 の OpenAPI 同期方針と整合。SoT 確定後は `endpoints.ts` / `searchClient.ts` のみで吸収可能な構造を維持 |

## 前回 findings の追跡

| finding_id | 前回状態 | 今回判定 | 根拠 |
|------------|---------|---------|------|
| AI-NEW-frontend-lib-mock-products-L17 | resolved（ai-review.2） | resolved（継続） | `frontend/lib/mock/` ディレクトリ不在、grep `MOCK_PRODUCTS` / `@/lib/mock` の frontend 配下ヒット 0、`git status` で削除確認 |

※ 本ステップ（arch-review）の過去履歴は無し（step iteration 1）。AI レビューの履歴を補助情報として参照。

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
| AI-NEW-frontend-lib-mock-products-L17 | 削除済み状態が継続（ai-review.2 で確認済みの解消が維持されている） |

## 再開指摘（reopened）

| # | finding_id | family_tag | 解消根拠（前回） | 再発根拠 | 問題 | 修正案 |
|---|------------|------------|----------------|---------|------|--------|
| - | - | - | - | - | 該当なし | - |

## 参考メモ（非ブロッキング）

以下は今回 REJECT としない事項。スコープ外あるいは設計判断として既に妥当に処理されているが、将来の拡張時に再考の余地があるものとして記録する。

- `components/feedback/Spinner.tsx` と `components/feedback/SearchErrorState.tsx` は実体としては検索用途専用（Spinner は `aria-label` 固定、SearchErrorState は `query` prop と検索文脈の文言を持つ）。将来的に他用途のローディング/エラーが追加される際、汎用化（label/copy の外部注入）か `components/search/` への移設のいずれかに整理する余地はある。本タスクでは plan で `feedback/` 配置が確定し、Decision #4 でも単一用途として固定されているため、現状の構造を維持するのが正しい判断。
- `SearchErrorState` の `describeError` 内 `'原因不明のエラーが発生しました'` フォールバック分岐は `error instanceof Error === false` のケース。現時点で `searchProducts` が throw する値は `Error` のみだが、SWR 経由で React tree から流入する非 Error 例外も理論的には到達し得るため、分岐自体は正当。本分岐の専用テストは未整備だが、HomePage の統合テストでエラー UI 表示が検証されており致命的欠落ではない。

---

## frontend-review
フロントエンドレビューを完了し、レポートを `frontend-review.md` に出力しました。

## 結果: APPROVE

### サマリー
3点のスコープ要件（searchClient の fetch 化 / HomePage の SWR 化 / ローディング・エラー UI）が満たされており、フロントエンド観点でのブロッキング問題は検出されませんでした。

### 主要な確認結果
- **コンポーネント設計**: `Spinner`/`SearchErrorState` は単一責務、HomePage が View としてデータ取得を担当
- **データ取得**: SWR `key=null` による空クエリ時の fetch スキップ、closure による query の引き渡し
- **a11y**: Spinner に `role="status"` + `aria-live="polite"`、リトライは `<button type="button">` でテキストラベル付き
- **配線**: 新規ルート追加なし、既存 `/` の `HeroSearch` フォーム送信が唯一の入口で完結
- **TypeScript**: `any` なし、`SearchErrorState` で `instanceof Error` の型ガードあり
- **デッドコード**: `frontend/lib/mock/` 一式が完全削除済み

### 非ブロッキングの参考メモ（3件）
- エラー画面の `role="alert"` 未付与（支援技術への自動アナウンス強化余地）
- リトライ中のローディング表示なし（SWR の `isLoading` が revalidation で false になる挙動）
- `SearchErrorState` の配置（`feedback/` vs `search/`）

これらは task 指示書のスコープ外のため記録のみとし、APPROVE と判定しました。

---

## testing-review
テスト品質レビューを完了しました。

## 結果: APPROVE

### サマリー
タスクの3点スコープ（searchClient の fetch 化／HomePage の3状態描画／ローディング・エラー UI）に対し、必要な振る舞いはすべて単体・統合テストでカバーされている。

**主要な確認事項:**
- **境界の置き方**: `global.fetch` のみモック。SWR 本体・SearchResultsSection・Spinner などは実マウントしており、shallow モック起因のマウント時破綻も検出可能
- **外部契約**: path（`/api/products/search`）、method（GET）、query 入力位置（`q=...`）、エンコード規約（`%20` / encodeURIComponent）すべて検証済み
- **Envelope 流用検出**: レスポンスは `Product[]` 直返しを `toEqual` 完全一致で固定。`{data: [...]}` 形式は通らない
- **再取得ループ**: 初期表示 0 回／成功時 1 回／リトライ時 2 回を `toHaveBeenCalledTimes` で固定
- **到達経路**: searchbox → 検索する ボタンの実 UI 経由で検索発火を検証
- **UI ライブラリ統合**: SWR の loading→error→mutate→loading→success の実 state machine をリトライテストで通している
- **独立性**: `vi.unstubAllGlobals` ＋ `provider: () => new Map()` ＋ `localStorage.clear()` でテスト間状態漏れを断つ

### 指摘
- **新規 (new)**: 0 件
- **継続 (persists)**: 0 件（前回 testing-review レポート不在＝初回実行）
- **解消 (resolved)**: 対象なし
- **再開 (reopened)**: 0 件

REJECT 基準該当なし、`new` / `persists` が 0 件のため APPROVE。
レポートは `reports/testing-review.md` に出力済み。