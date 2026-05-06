# pricehack

> Where To Buy That? — Amazon・楽天・Yahoo! ショッピングを横断し、送料・ポイントを差し引いた**実質価格**で比較するためのツール。

ドメインは `pricehack.net`。エディトリアル（紙面）デザインを採用したフロントエンドと、Vercel サーバーレスで動く FastAPI バックエンドで構成される。

## アーキテクチャ

Vercel へのデプロイに最適化されたサーバーレス構成。

- **Frontend**: Next.js 14（App Router）+ Tailwind CSS / Vitest + Testing Library
- **Backend (API)**: FastAPI on Vercel Functions（`api/` 配下に集約）
- **Database**: PostgreSQL — **Neon (Serverless Postgres)** 採用（ADR-008 / ADR-009）
- **Migrations**: Alembic（リポジトリルートの `alembic/`、CI / 手動で Neon に対して `upgrade head`）
- **Data Source**: Amazon PA-API、楽天商品検索 API、Yahoo! ショッピング商品検索 API
- **Scheduled Tasks**: Vercel Cron Jobs（`vercel.json`）

設計の詳細は `docs/design/system-design.md`、要件定義は `docs/prd/price-comparison.md`、意思決定の経緯は `docs/adr/` を参照。

## 現在の進捗

- フロントエンド UI（ヒーロー検索 / 検索結果 / 画像優先度設定）は実装済み
- バックエンド: モデル定義・公式 API クライアント・Cron・検索 API・認証基盤・カードマスタ API・UserProfile API・ポイント算出エンジン（T-06）を実装済み
- **Next Step**: Phase 1 残タスク（検索結果へのユーザー属性反映・OpenAPI 型同期）。詳細は `docs/plans/roadmap.md` を参照

## 今後のロードマップ

詳細は `docs/adr/006-advanced-features-roadmap.md` および `docs/plans/phase1-foundation.md` を参照。


### Phase 1: モック脱却とパーソナライズ基盤
- フロント fetch 接続は完了済み（残: 検索レスポンスへの `Listing` 同梱／T-08）
- `UserProfile` / `Card` 連携によるユーザー固有の還元率反映（UserProfile API / 算出エンジン実装済み）
- バックエンドでの実質価格計算ロジックの検索 API への統合（T-08）

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
│   ├── main.py                #   FastAPI エントリポイント・ルータ統合
│   ├── common/                #   DB モデル・接続
│   ├── cron/                  #   定期価格更新タスク
│   ├── lib/                   #   外部 API クライアント (amazon/rakuten/yahoo)
│   ├── repositories/          #   DB アクセス層（products 検索など）
│   ├── routers/               #   HTTP ルータ（products 等）
│   └── schemas.py             #   API レスポンス用 Pydantic スキーマ
├── alembic/                   # DB マイグレーション（Neon 向け）
│   ├── env.py
│   └── versions/              #   0001_initial_schema, 0002_product_search_columns 等
├── alembic.ini                # Alembic 設定（`script_location = alembic`）
├── frontend/                  # Frontend (Next.js 14 App Router)
│   ├── app/                   #   ルートレイアウト・ページ・グローバル CSS・フォント
│   ├── components/
│   │   ├── branding/          #     pricehack ワードマーク
│   │   ├── editorial/         #     新聞メタファのエディトリアル装飾
│   │   ├── feedback/          #     ローディング / エラー UI（Spinner / SearchErrorState）
│   │   ├── icons/             #     サイト識別グリフ
│   │   ├── results/           #     商品サムネイル等の結果表示
│   │   ├── search/            #     ヒーロー・検索フォーム・結果セクション・出品行
│   │   └── settings/          #     画像取得優先度の並び替え UI
│   ├── lib/
│   │   ├── api/               #     HTTP 検索クライアント（fetch + URL 組み立て）
│   │   ├── format/            #     通貨・ポイント・%の日本語ロケール整形
│   │   ├── hooks/             #     useImagePriority（LocalStorage 永続化）
│   │   ├── image/             #     画像取得優先度の解決ロジック
│   │   └── pricing/           #     実質価格算出・出品ソート
│   ├── types/                 #   フロントエンド共通型 (Product / Listing 等)
│   └── test/                  #   Vitest セットアップ
├── tests/                     # Python テスト
│   ├── unit/                  #   外部 API クライアントのユニット
│   └── integration/           #   cron 結合 / 検索エンドポイント (testcontainers Postgres)
├── docs/
│   ├── adr/                   #   アーキテクチャ決定記録（001〜009）
│   ├── api/                   #   API 仕様書
│   ├── plans/                 #   フェーズ別実装計画
│   ├── prd/                   #   要件定義
│   └── tech/                  #   システム設計書
├── agent-rules/               # エージェント運用ルール
├── pytest.ini                 # pytest 設定（testpaths=tests/unit tests/integration）
├── vercel.json                # Vercel ルーティング・Cron 設定
├── requirements.txt           # Python ランタイム依存
└── requirements-dev.txt       # 開発・テスト用依存（alembic / pytest / testcontainers）
```

## セットアップ

### 環境変数

`.env` を作成し、以下を設定する（`.env.example` 参照）。

- `DATABASE_URL` — Neon の Postgres 接続文字列。アプリ側は **pooler 付き**（`*-pooler...`）を使用。Alembic マイグレーション実行時のみ pooler なしの直接接続を推奨
- `JWT_SECRET` — JWT 署名鍵（ADR-007）
- `RAKUTEN_APP_ID` — 楽天アプリ ID
- `YAHOO_CLIENT_ID` — Yahoo! JAPAN Client ID
- `AMAZON_ACCESS_KEY` / `AMAZON_SECRET_KEY` / `AMAZON_PARTNER_TAG` — Amazon PA-API 認証情報

> フロントエンド単体（`/api/products/search` を fetch しない場合）で UI を確認するだけなら、上記の環境変数は不要。

### ローカル開発

```bash
# Backend (FastAPI) — ランタイム
pip install -r requirements.txt
uvicorn api.main:app --reload

# Backend — テスト・マイグレーション（dev 依存）
pip install -r requirements-dev.txt
pytest -q                               # 全テスト（integration は Docker 必須）
DATABASE_URL=<neon-direct-url> alembic upgrade head   # スキーマ適用

# Frontend (Next.js)
cd frontend
npm install
npm run dev          # 開発サーバ
npm test             # Vitest 単体テスト
npm run typecheck    # TypeScript 型チェック
npm run lint         # ESLint
```

## デプロイ

Vercel に GitHub リポジトリを連携するだけで自動的にデプロイされる。Cron Jobs は `vercel.json` で定義しており、Vercel ダッシュボードで有効化する。Neon は別途プロビジョニングし、`DATABASE_URL`（pooler 付き）を Vercel の環境変数に登録する。

DB スキーマ変更時は `alembic upgrade head` を **デプロイの前に** Neon に対して実行する（Vercel Functions の起動時自動 upgrade は行わない）。
