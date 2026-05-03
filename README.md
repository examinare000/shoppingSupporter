# Shopping Supporter

ショッピングの実質価格（価格 - ポイント）を比較し、最適な購入先を提案するツール。

## アーキテクチャ

Vercel へのデプロイに最適化されたサーバーレス構成を採用しています。

- **Frontend**: Next.js (Vercel)
- **Backend (API)**: FastAPI (Vercel Functions)
- **Database**: PostgreSQL (Managed service like Neon, Supabase, or Vercel Postgres)
- **Data Source**: Amazon PA-API, 楽天商品検索API, Yahoo!ショッピング商品検索API

## プロジェクト構造

```
/
├── api/                # Backend logic (FastAPI)
│   ├── common/         # DB models and connection
│   ├── cron/           # Price update tasks
│   └── lib/            # External API clients (Amazon, Rakuten, Yahoo)
├── frontend/           # Frontend (Next.js)
├── docs/               # Documentation (ADRs, System Design)
├── vercel.json         # Vercel configuration
└── requirements.txt    # Python dependencies
```

## セットアップ

### 環境変数の設定

`.env` ファイルを作成し、以下の情報を設定してください。

- `DATABASE_URL`: PostgreSQLの接続文字列
- `RAKUTEN_APP_ID`: 楽天アプリID
- `YAHOO_CLIENT_ID`: Yahoo! JAPAN Client ID
- `AMAZON_ACCESS_KEY`: Amazon PA-API アクセスキー
- `AMAZON_SECRET_KEY`: Amazon PA-API シークレットキー
- `AMAZON_PARTNER_TAG`: Amazon アソシエイト・プログラムのトラッキングID

### ローカル開発

```bash
# API
pip install -r requirements.txt
uvicorn api.main:app --reload

# Frontend
cd frontend
npm install
npm run dev
```

## デプロイ

Vercel に GitHub リポジトリを連携するだけで自動的にデプロイされます。
Cron Jobs は `vercel.json` で定義されており、Vercel ダッシュボードで有効化してください。
