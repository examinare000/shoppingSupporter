# ADR-002: Vercel への移行とサーバーレスアーキテクチャへの刷新

## ステータス
刷新 (Superceded by Vercel Migration)

## 背景
Docker Compose ベースのマルチコンテナ構成は柔軟だが、インフラの管理コストが高く、スケーリングやデプロイの自動化に手間がかかる。また、個人開発や小規模運用においてはオーバースペックであった。

## 決定
Docker Compose によるマルチコンテナ構成を廃止し、Vercel への移行を決定した。
- Backend: Vercel Functions (FastAPI)
- Frontend: Vercel (Next.js)
- Database: マネージド PostgreSQL (Neon/Supabase/Vercel Postgres)
- Cron: Vercel Cron Jobs

## 理由
- **運用コストの削減**: インフラ管理が不要になり、デプロイが自動化される。
- **パフォーマンス**: Vercel のエッジネットワークとサーバーレス関数の恩恵を受けられる。
- **コスト効率**: 使用した分だけ支払うサーバーレスモデルが適している。

## 影響
- `backend` と `analysis` のロジックを `api/` ディレクトリに統合。
- サーバーレス環境の制限（実行時間制限等）に合わせた実装が必要。
- DBを外部のマネージドサービスへ移行。
