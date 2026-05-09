# Phase 2 実装計画: 価格履歴の可視化 (Price History Visualization)

## 1. 概要
本ドキュメントは、`pricehack.net` Phase 2 の重点目標である「価格履歴の可視化」に関する詳細な実装計画を定義する。
過去の価格推移を可視化することで、ユーザーが「今が買い時か」を客観的に判断できる情報を提供する。

## 2. 実装スコープ

### 2.1. バックエンド (API & Data)
- **F-16: 価格履歴取得 API**
  - エンドポイント: `GET /api/products/{id}/history`
  - 役割: 特定商品の過去（30/90/365日）の価格推移データを集計して返却する。
  - 最適化:
    - 日次ダウンサンプリング（1日1件の代表値を取得しレスポンスサイズを削減）。
    - インデックス最適化 (`ec_site_product_id`, `recorded_at`)。

### 2.2. フロントエンド (UI & UX)
- **F-17: 価格推移チャート UI**
  - エディトリアルデザインに基づいた、ミニマルで精緻なチャート。
  - ライブラリ: `recharts` を採用（React 親和性と軽量性のバランス）。
  - インタラクション: ツールチップによる特定日の詳細表示。

## 3. 詳細タスクリスト

### Phase 2-a: バックエンド基盤整備
- [ ] **T-10: スキーマ定義の追加 (`api/schemas.py`)**
  - `PriceHistoryEntry`, `SiteHistory`, `ProductHistoryResponse` の定義。
  - `recorded_at` の camelCase (recordedAt) 対応。
- [ ] **T-11: リポジトリ実装 (`api/repositories/products.py`)**
  - `get_product_history(db, product_id, days)` 関数の実装。
  - SQL で `DISTINCT ON (date_trunc('day', recorded_at))` 等を用いたダウンサンプリング。
- [ ] **T-12: ルーター実装 (`api/routers/products.py`)**
  - `GET /api/products/{id}/history` エンドポイントの追加。
  - JANコードまたは UUID の両方を受け入れ可能なバリデーション。

### Phase 2-b: フロントエンド実装
- [ ] **T-13: チャートライブラリ導入**
  - `npm install recharts`
- [ ] **T-14: チャートコンポーネント作成 (`frontend/components/results/PriceChart.tsx`)**
  - エディトリアルデザイン（Newsreader/JetBrains Mono）の適用。
  - 単色またはアクセントカラー（芥子色）を用いた配色。
- [ ] **T-15: 商品詳細ページへの統合**
  - `ProductDossier` コンポーネント等にチャートを組み込み。
  - `useSWR` による API 連携。

## 4. テスト戦略

### バックエンド
- **インテグレーションテスト (`tests/integration/test_product_history.py`)**
  - `PriceHistory` レコードを複数作成し、集計結果が正しい期間・件数で返ることを確認。
  - 存在しない商品 ID に対する 404 エラーの検証。

### フロントエンド
- **コンポーネントテスト (`frontend/components/results/PriceChart.test.tsx`)**
  - モックデータを用いたチャートのレンダリング検証。
  - 空データ時のフォールバック表示。

## 5. デザインガイドライン (Phase 2)
- **色**: 背景の紙色 (`#fdfcf8` 等) に馴染む、濃インク色 (`#1a1a1a`) の線。
- **グリッド**: 必要最小限。縦軸は価格（円）、横軸は日付。
- **活字**: 軸ラベルには `JetBrains Mono` を使用し、テクニカルな印象を与える。

## 6. スケジュール（目安）
- バックエンド実装: 2 days
- フロントエンド実装: 3 days
- テスト・リファクタリング: 1 day
