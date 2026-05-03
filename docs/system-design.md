# システム設計書

## アーキテクチャ概要

本システムは、Vercel へのデプロイに最適化されたサーバーレスアーキテクチャを採用しています。

### 構成要素

1.  **Frontend (Next.js)**:
    - ユーザーインターフェース。
    - SSR/Client-side Rendering を使い分け、高速な表示を実現。
2.  **API / Backend (FastAPI)**:
    - ビジネスロジックのコア。Vercel Functions 上で動作。
    - ユーザー認証、DB操作、公式APIからのデータ取得。
3.  **Database (PostgreSQL)**:
    - 永続データの管理（Neon, Supabase, または Vercel Postgres を利用）。
4.  **Scheduled Tasks (Vercel Cron Jobs)**:
    - 定期的な価格更新処理。HTTPエンドポイントをトリガーに実行。

## データフロー

1.  ユーザーが商品を検索または一覧を表示。
2.  APIがデータベースから既存の商品情報を取得。
3.  Vercel Cron Jobs が定期的に各ECサイトの公式API（Amazon, 楽天, Yahoo）を呼び出し、最新の価格・ポイント情報をデータベースに保存。
4.  ユーザーの会員情報（楽天ランク、所有カード等）に基づいて実質価格を動的に算出。
5.  Frontendに結果を表示。

## データモデル

詳細は `api/common/models.py` を参照。主要エンティティは以下の通り。

- `User`: ユーザー認証情報
- `UserProfile`: 会員ランク、所有カード、各種サービスの利用状況
- `Product`: 商品基本情報（JANコード等、全サイト共通）
- `EcSiteProduct`: サイトごとの商品詳細（ASIN, ItemCode 等）
- `PriceHistory`: 日次価格・ポイント履歴
