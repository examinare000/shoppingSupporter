# システム設計書

`pricehack.net`（プロダクトコード上は `pricehack`）のシステム設計を記述する。Amazon・楽天・Yahoo! ショッピングを横断し、送料・ポイントを差し引いた実質価格で商品を比較する。

## アーキテクチャ概要

Vercel へのデプロイに最適化されたサーバーレスアーキテクチャ。

### 構成要素

1. **Frontend (Next.js 14 App Router)**
   - 紙面メタファのエディトリアルデザイン UI。
   - 現状はクライアントサイドのモックデータ駆動で動作（バックエンド API には未接続）。
2. **API / Backend (FastAPI)**
   - ビジネスロジックのコア。Vercel Functions 上で動作。
   - ユーザー認証、DB 操作、公式 API からのデータ取得を担う。
3. **Database (PostgreSQL)**
   - 永続データの管理（Neon / Supabase / Vercel Postgres を利用）。
4. **Scheduled Tasks (Vercel Cron Jobs)**
   - 定期的な価格更新処理。HTTP エンドポイントをトリガーに実行。

## データフロー（バックエンド接続後の想定）

1. ユーザーが商品を検索または一覧を表示。
2. API がデータベースから既存の商品情報を取得。
3. Vercel Cron Jobs が定期的に各 EC サイトの公式 API（Amazon・楽天・Yahoo）を呼び出し、最新の価格・ポイント情報をデータベースに保存。
4. ユーザーの会員情報（楽天ランク、所有カード等）に基づいて実質価格を動的に算出。
5. Frontend に結果を表示。

> 現状は手順 2 / 3 の API 連携が未実装で、Frontend は `frontend/lib/mock/products.ts` のモック商品を使ってクライアントサイドで完結している。

## データモデル

詳細は `api/common/models.py` を参照。主要エンティティは以下。

- `User` — 認証情報（email / hashed_password）
- `UserProfile` — 楽天ランク、Amazon Prime / Yahoo Premium 加入有無、デフォルトカード参照
- `Card` — クレジットカード（基本還元率、年会費、サイト別特典）
- `Product` — 商品基本情報（JAN コード等、サイト共通）
- `EcSiteProduct` — サイトごとの商品詳細（ASIN / ItemCode 等）
- `PriceHistory` — 日次価格・ポイント履歴

## 実質価格の算出

実質価格は以下の式で計算する（`frontend/lib/pricing/effectivePrice.ts`）。

```
effectivePrice = max(0, price + shippingFee - points)
```

- `points` は円換算済みの獲得ポイント。ポイント還元が価格を上回ると負数になり得るが、表示上不自然なので `0` で下限を切る。
- 将来的にユーザーの `UserProfile`（楽天ランク・Prime 加入・所有カード等）を加味してサイト別倍率を適用する想定。現在のフロントエンドはユーザー文脈なしの素の式で算出。

## フロントエンド設計

### 技術スタック

- **Next.js 14 App Router** + **Tailwind CSS**
- フォント: Fraunces（ディスプレイセリフ・見出し）/ Newsreader（本文セリフ）/ JetBrains Mono（数字・キャプション）
- カラートークン: 紙色（`paper`）+ 濃インク（`ink`）+ 罫線（`rule`）+ アクセントの朱赤（`vermilion`）/ 芥子色（`mustard`）。`globals.css` の CSS 変数経由で参照
- 紙の質感は SVG `fractalNoise` をビューポート全体に薄く敷くことで再現
- テスト: Vitest + Testing Library（jsdom）

### ページ構成

トップページ（`frontend/app/page.tsx`）は以下の縦積み構成。

```
Masthead（題字バー）
HeroSearch（h1「Where To Buy That?」+ リード文 + SearchForm）
[検索クエリがあるとき] SearchResultsSection
Footer（ロゴ + 年）
```

検索クエリが空の状態では `SearchResultsSection` を描画しない。「表紙ティザー」としてミニマルに見せる設計判断（ADR-004 参照）。

### 主要モジュール

| 関心事 | 場所 |
|---|---|
| ブランドワードマーク | `components/branding/Logo.tsx` |
| 紙面装飾（題字・ノンブル・罫線・余白注） | `components/editorial/` |
| 検索 UI（ヒーロー・フォーム・結果・出品行・ソート・空状態・商品ドシエ） | `components/search/` |
| 結果サムネイル | `components/results/ProductThumbnail.tsx` |
| 画像取得優先度 UI | `components/settings/ImagePriorityControl.tsx` |
| 実質価格・出品ソート | `lib/pricing/` |
| 通貨・ポイント・% 整形（日本語ロケール） | `lib/format/numbers.ts` |
| 画像取得優先度ロジック | `lib/image/` |
| 画像取得優先度の永続化フック | `lib/hooks/useImagePriority.ts` |
| モック商品・クライアントサイド検索 | `lib/mock/` |
| 共通型（`Product` / `Listing` / `ImagePriority` / `SortKey` 等） | `types/product.ts` |

### 画像取得優先度

- 各商品は最大 3 サイト分の出品（`Listing[]`）を持ち、画像 URL は出品ごとに任意。
- 「どのサイトの画像を優先して表示するか」をユーザーが並び替えられる（`ImagePriorityControl`）。
- 設定は `localStorage` に永続化（`useImagePriority`）。SSR 時は `localStorage` 不在のためデフォルト値で初期描画し、クライアントマウント後に復元してハイドレーション不一致を避ける。
- 画像が取れないサイトはフォールバック順に従って解決し、すべて欠落していれば活字フォールバック表示にする（`lib/image/resolveProductImage.ts`）。

### アクセシビリティ

- `prefers-reduced-motion: reduce` 指定時は全アニメーション・トランジションを実質無効化（`globals.css`）。
- ヒーローのスタッガー出現も上記グローバル設定で無効化される。

## 関連ドキュメント

- `docs/adr/` — アーキテクチャ決定記録（ADR-001〜004）
- `agent-rules/15-frontend-design.md` — フロントエンド設計の運用ルール
- `agent-rules/30-documentation-management.md` — ドキュメント管理ルール
