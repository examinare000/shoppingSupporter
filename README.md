# pricehack

> Where To Buy That? — Amazon・楽天・Yahoo! ショッピングを横断し、送料・ポイントを差し引いた**実質価格**で比較するためのツール。

ドメインは `pricehack.net`。エディトリアル（紙面）デザインを採用したフロントエンドと、Vercel サーバーレスで動く FastAPI バックエンドで構成される。

## アーキテクチャ

Vercel へのデプロイに最適化されたサーバーレス構成。

- **Frontend**: Next.js 14（App Router）+ Tailwind CSS / Vitest + Testing Library
- **Backend (API)**: FastAPI on Vercel Functions
- **Database**: PostgreSQL（Neon / Supabase / Vercel Postgres などのマネージド）
- **Data Source**: Amazon PA-API、楽天商品検索 API、Yahoo! ショッピング商品検索 API
- **Scheduled Tasks**: Vercel Cron Jobs（`vercel.json`）

設計の詳細は `docs/tech/system-design.md`、要件定義は `docs/prd/price-comparison.md`、意思決定の経緯は `docs/adr/` を参照。

## 現在の進捗

- フロントエンド UI（ヒーロー検索 / 検索結果 / 画像優先度設定）は実装済み
- バックエンド側のモデル定義・公式 API クライアント雛形・Cron 構造は配置済み
- **Next Step**: Phase 1 実装（DB 構築・認証・パーソナライズロジック）に着手予定

## 今後のロードマップ

詳細は `docs/adr/006-advanced-features-roadmap.md` および `docs/plans/phase1-foundation.md` を参照。


### Phase 1: モック脱却とパーソナライズ基盤
- `lib/mock/` から実バックエンド API への接続
- `UserProfile` / `Card` 連携によるユーザー固有の還元率反映
- バックエンドでの実質価格計算ロジックの実装

### Phase 2: 価格履歴と可視化
- `PriceHistory` データの蓄積と取得 API の実装
- `ProductDossier` へのミニマルな価格推移チャートの導入

### Phase 3: セール予測とインテリジェンス
- 過去データに基づくセール時期・「買い時」予測アルゴリズムの実装
- エディトリアルな注釈（Marginal Note）による購入アドバイス表示

## プロジェクト構造

```
/
├── api/                       # Backend (FastAPI / Vercel Functions)
│   ├── common/                #   DB モデル・接続
│   ├── cron/                  #   定期価格更新タスク
│   └── lib/                   #   外部 API クライアント (amazon/rakuten/yahoo)
├── frontend/                  # Frontend (Next.js 14 App Router)
│   ├── app/                   #   ルートレイアウト・ページ・グローバル CSS・フォント
│   ├── components/
│   │   ├── branding/          #     pricehack ワードマーク
│   │   ├── editorial/         #     新聞メタファのエディトリアル装飾
│   │   ├── icons/             #     サイト識別グリフ
│   │   ├── results/           #     商品サムネイル等の結果表示
│   │   ├── search/            #     ヒーロー・検索フォーム・結果セクション・出品行
│   │   └── settings/          #     画像取得優先度の並び替え UI
│   ├── lib/
│   │   ├── format/            #     通貨・ポイント・%の日本語ロケール整形
│   │   ├── hooks/             #     useImagePriority（LocalStorage 永続化）
│   │   ├── image/             #     画像取得優先度の解決ロジック
│   │   ├── mock/              #     モック商品とクライアントサイド検索
│   │   └── pricing/           #     実質価格算出・出品ソート
│   ├── types/                 #   フロントエンド共通型 (Product / Listing 等)
│   └── test/                  #   Vitest セットアップ
├── docs/
│   ├── adr/                   #   アーキテクチャ決定記録
│   └── system-design.md       #   システム設計書
├── agent-rules/               # エージェント運用ルール
├── vercel.json                # Vercel ルーティング・Cron 設定
└── requirements.txt           # Python 依存
```

## セットアップ

### 環境変数

`.env` を作成し、以下を設定する（`.env.example` 参照）。

- `DATABASE_URL` — PostgreSQL 接続文字列
- `RAKUTEN_APP_ID` — 楽天アプリ ID
- `YAHOO_CLIENT_ID` — Yahoo! JAPAN Client ID
- `AMAZON_ACCESS_KEY` / `AMAZON_SECRET_KEY` / `AMAZON_PARTNER_TAG` — Amazon PA-API 認証情報

> フロントエンド単体（モック駆動）で UI を確認するだけなら、上記の環境変数は不要。

### ローカル開発

```bash
# Backend (FastAPI)
pip install -r requirements.txt
uvicorn api.main:app --reload

# Frontend (Next.js)
cd frontend
npm install
npm run dev          # 開発サーバ
npm test             # Vitest 単体テスト
npm run typecheck    # TypeScript 型チェック
npm run lint         # ESLint
```

## デプロイ

Vercel に GitHub リポジトリを連携するだけで自動的にデプロイされる。Cron Jobs は `vercel.json` で定義しており、Vercel ダッシュボードで有効化する。
