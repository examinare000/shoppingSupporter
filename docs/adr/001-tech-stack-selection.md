# ADR-001: 基本技術スタックの選定

## ステータス
承認済み

## 背景
ECサイト横断検索・分析サービスを開発するにあたり、フロントエンドの高度なインタラクション、バックエンドの高速な処理、およびデータ収集・分析の親和性が求められる。

## 検討された選択肢
1.  **Next.js (TypeScript) + FastAPI (Python)**
2.  **Next.js (TypeScript) + Node.js (Express/NestJS)**
3.  **Ruby on Rails**

## 決定
選択肢1（Next.js + FastAPI）を採用する。

## 理由
- **Next.js**: App RouterやSSRの機能が、商品情報の表示やSEOにおいて強力。
- **FastAPI**: 非常に高速であり、型安全な開発が可能。また、スクレイピングやデータ分析を行う `analysis` サービス（Python）とモデルやライブラリを共有しやすい。
- **Pythonエコシステム**: BeautifulSoupやPlaywright等のスクレイピングツール、および将来的な価格予測（機械学習）への拡張性が高い。

## 影響
- フロントエンドとバックエンドで言語が異なるため、型定義の同期（OpenAPIの活用等）に注意が必要。
- Python環境の依存関係管理を適切に行う必要がある。
