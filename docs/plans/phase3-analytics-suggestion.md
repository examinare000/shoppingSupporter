# Phase 3 実装計画: データ分析と予測インテリジェンス (Analytics & Suggestion)

## 1. 概要
本ドキュメントは、`pricehack.net` Phase 3 の重点目標である「データ分析と予測インテリジェンス」に関する詳細な実装計画を定義する。
ユーザーの利用実績とセールカレンダーを統合し、「今買うべきか、待つべきか」という問いにデータに基づいた回答（サジェスト）を提供する。

## 2. 実装スコープ

### 2.1. バックエンド (API & Logic)
- **F-18: セール予測とカレンダー (`sale_campaigns`)**
  - 各 EC サイトの定期・不定期セールを構造化して管理。
  - 周期的なルール（5と0のつく日等）に加え、**過去の実施履歴から次回セール（お買い物マラソン等）を推定する予測ロジック**を実装。
- **F-19: 利用実績管理 (`monthly_usage`)**
  - ユーザーごとのサイト別月次利用額・獲得ポイント上限の管理。
  - 当月の「真の還元率」を算出するための基礎データ。
- **F-20: サジェストエンジン (`GET /api/products/{id}/suggestion`)**
  - 価格履歴（移動平均）とセール予測を組み合わせた最適購買タイミングの提示。

### 2.2. フロントエンド (UI & UX)
- **利用実績入力 UI**: **ユーザープロフィールページ内**に設置。ユーザーが当月の利用状況を簡単に更新できるフォーム。
- **サジェスト表示**: 商品詳細ページ（Dossier）での「今買う / 待つ」の強調表示と根拠（Breakdown）の提示。

## 3. データベース設計 (Schema)

### 3.1. `sale_campaigns` テーブル
| カラム | 型 | 説明 |
|---|---|---|
| `id` | Integer (PK) | |
| `site` | Enum (SiteType) | |
| `name` | String | セール名称 |
| `kind` | Enum | `recurring` / `oneshot` |
| `recurrence_rule` | JSONB | `{type: "day_of_month", days: [5, 10, ...]}` 等 |
| `start_at` / `end_at` | DateTime | `oneshot` の期間 |
| `bonus` | JSONB | 加算ルール `{type: "additive_rate", rate: 0.04}` 等 |
| `cap` | JSONB | 上限設定 `{type: "points", value: 7000}` 等 |
| `conditions` | JSONB | 適用条件（楽天カード保有者限定等） |

### 3.2. `monthly_usage` テーブル
| カラム | 型 | 説明 |
|---|---|---|
| `user_id` | UUID (PK, FK) | |
| `site` | Enum (SiteType, PK) | |
| `recorded_month` | String (PK) | `YYYY-MM` 形式 |
| `amount_spent` | Integer | 当月の累計利用額 |
| `points_earned` | Integer | 当月の既獲得ポイント数（上限計算用） |
| `shop_count` | Integer | 買いまわり店舗数（楽天マラソン等用） |

## 4. 詳細タスクリスト

### Phase 3-a: 基盤整備と利用実績 API ✅ 完了 (2026-05-10)
- [x] **T-16: セールカレンダー・利用実績のモデル定義とマイグレーション**
  - `api/common/models.py` に `CampaignKind` enum, `SaleCampaign`, `MonthlyUsage` を追加。
  - Alembic マイグレーションでテーブル作成。
- [x] **T-17: 利用実績 API (`GET / PUT /api/me/usage`)**
  - `api/routers/usage.py` を実装。未記録サイトは 200 + 0 デフォルト返却。
  - 月境界は `recorded_month = "YYYY-MM"` の複合 PK + UPSERT で管理。
- [x] **T-18: PricingEngine の拡張**
  - `api/lib/pricing/engine.py` の `compute_pricing` に `campaigns` / `usage` 引数を追加。
  - 上限到達時のポイントカット・セール加算を実装（詳細は ADR-014）。

### Phase 3-b: サジェストエンジン実装 ✅ 完了 (2026-05-11)
- [x] **T-19: 価格予測ロジックの実装**
  - `api/lib/pricing/forecaster.py` (新規) の作成。
  - 直近 30/90 日の移動平均・中央値を用いた価格推移の推定。
- [x] **T-20: サジェスト API (`GET /api/products/{id}/suggestion`)**
  - 現時点の最安と、未来（セール時）の期待実質価格を比較。
  - 推奨アクション（今買う / 待つ）と日本語の根拠（Rationale）の生成。
- [x] **T-21: サジェスト結果のフロントエンド表示**
  - `ProductDossier` へのサジェストセクション追加。
  - 待機推奨時の期待節約額の表示。

## 5. テスト戦略
- **PricingEngine (Unit)**: 上限到達時、上限間際、セール重畳時の還元率計算を網羅。
- **Forecaster (Unit)**: 履歴データに基づいた予測値が期待される統計値（中央値等）と一致するか。
- **Suggestion API (Integration)**: 特定のユーザー状態・履歴状態において、意図した推奨アクションが返るか。

## 6. スケジュール（目安）
- Phase 3-a (基盤・API): ✅ 完了 (2026-05-10)
- Phase 3-b (ロジック・UI): ✅ 完了 (2026-05-11)
- 結合テスト・調整: ✅ 完了 (2026-05-11)
