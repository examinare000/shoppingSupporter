# Shopping Supporter

ECショッピングを賢くサポートするための、複数サイト横断価格比較・分析ツール。

## 概要

Amazon, 楽天市場, Yahoo!ショッピングなどの複数サイトを横断検索し、ユーザーの会員ステータスや所有カードに基づいた「実質価格」を算出・比較します。また、価格推移を分析し、最適な買い時を提案します。

## 機能（予定）

- **横断価格比較**: 複数サイトの実質価格（送料、ポイント還元込み）を一覧表示
- **ユーザー最適化**: 会員ランクや所有カードに応じた還元率計算
- **価格推移分析**: 過去の価格データを蓄積し、グラフ化
- **損益分岐点判定**: カード年会費に対して、獲得ポイントが上回っているかをシミュレーション

## 技術スタック

- **Frontend**: Next.js (TypeScript, Tailwind CSS)
- **Backend**: FastAPI (Python)
- **Database**: PostgreSQL
- **Data Collection**: Playwright (Python)
- **Infrastructure**: Docker Compose

## クイックスタート

```bash
# 環境変数の準備
cp .env.example .env

# コンテナの起動
docker compose up -d --build
```

## ドキュメント

詳細は `docs/` 配下を参照してください。

- [システム設計書](docs/system-design.md)
- [アーキテクチャ決定記録 (ADR)](docs/adr/README.md)
