# システム設計書

## アーキテクチャ概要

本システムは、責務ごとに分割されたマイクロサービス（コンテナ）構成を採用しています。

### コンテナ構成

1.  **Frontend (Next.js)**:
    - ユーザーインターフェース。
    - SSR/Client-side Rendering を使い分け、高速な表示を実現。
2.  **Backend (FastAPI)**:
    - ビジネスロジックのコア。
    - ユーザー認証、DB操作、Analysisサービスへの指示。
3.  **Analysis (Python/Playwright)**:
    - スクレイピングおよびデータ分析。
    - 非同期ワーカーとして動作し、ECサイトから情報を収集。
4.  **Database (PostgreSQL)**:
    - 永続データの管理。

## データフロー

1.  ユーザーが商品を検索。
2.  BackendがDBの既存データを確認。
3.  データが古い場合、Analysisサービスが各ECサイトをスクレイピング。
4.  取得したデータをDBに保存し、ユーザーの会員情報に基づいて実質価格を算出。
5.  Frontendに結果を表示。

## データモデル

詳細は `backend/models.py` を参照。主要エンティティは以下の通り。

- `User`: ユーザー認証情報
- `UserProfile`: 会員ランク、所有カード等
- `Product`: 商品基本情報（JANコード等）
- `EcSiteProduct`: サイトごとの商品詳細
- `PriceHistory`: 日次価格・ポイント履歴
