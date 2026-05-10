# プロジェクト・ロードマップ

本ドキュメントでは、`pricehack.net` の開発ロードマップと各フェーズの目標、および現在の進捗状況を整理する。

## 1. 全体ロードマップ

| フェーズ | タイトル | 状態 | 重点領域 |
|---|---|---|---|
| Phase 1 | 基盤整備と UserProfile 連携 | 完了 (100%) | バックエンド基盤、認証、パーソナライズ計算 |
| Phase 2 | 価格履歴の可視化 | 完了 (100%) | 履歴 API、チャート UI、フロントエンド強化 |
| Phase 3 | データ分析と予測インテリジェンス | 進行中 (Phase 3-a 完了) | セール予測、サジェストエンジン、UX 最適化 |
| Phase 4 | 自動データ取得の高度化 | 長期 | 外部連携、公式 API 以外のデータ取得（要 ADR） |

## 2. フェーズ別詳細と進捗

### Phase 1: 基盤整備と UserProfile 連携 (Backend First)
**目標**: ユーザー属性に基づいた「真の実質価格」をバックエンドで算出し、フロントエンドに届ける。

- [x] T-01: Alembic 導入と初期マイグレーション
- [x] T-02: API テスト基盤（pytest + testcontainers）
- [x] T-03: JWT 認証基盤（signup / login / me）
- [x] T-04: Card マスタ API と初期シード（最新還元率に校正済み）
- [x] T-05: UserProfile API（モバイル・PayPay 連携フラグ拡張済み）
- [x] T-07: DB 主導の商品検索 API（FTS + pg_trgm）
- [x] T-06: サイト別ポイント算出ロジックの純粋関数化（api/lib/pricing/engine.py）
- [x] T-08: 検索 API への UserProfile / Card 統合
- [x] T-09: OpenAPI → TypeScript 型生成パイプライン

### Phase 2: 価格履歴の可視化 (Frontend Focus)
**目標**: 過去の価格推移を可視化し、現在の価格の妥当性をユーザーが判断できるようにする。

- [x] F-16: 価格履歴取得 API（JAN / EcSiteProduct 単位）
- [x] F-17: 価格推移チャート UI（エディトリアルデザイン準拠）
- [x] B-3: 検索レスポンスのエンベロープ形とフロント型の整合（T-09 にて解消済み）

### Phase 3: データ分析と予測インテリジェンス (Analytics)
**目標**: 「今買うべきか、待つべきか」という問いに、データに基づいた回答を出す。

#### Phase 3-a: 基盤整備と利用実績 API (完了)
- [x] F-18 / T-16: セールカレンダー（`sale_campaigns` マスタ）の実装 — ORM モデル・マイグレーション・PricingEngine 統合
- [x] F-19 / T-17: 利用実績（マラソン店舗数等）の手動入力機能 — `GET/PUT /api/me/usage`
- [x] T-18: PricingEngine の拡張（キャンペーン割引・ポイント倍率上限計算）

#### Phase 3-b: サジェストエンジン実装 (未着手)
- [ ] T-19: 価格予測ロジック (`api/lib/pricing/forecaster.py` — 移動平均・中央値)
- [ ] T-20: サジェスト API (`GET /api/products/{id}/suggestion`)
- [ ] T-21 / F-20: フロントエンド サジェスト表示（`ProductDossier` 統合）

## 3. 残タスク・アクションアイテム（直近）

Phase 1〜3-a のタスクはすべて完了。次のアクションは Phase 3-b の着手。

1. **価格予測ロジックの実装 (T-19)**: `api/lib/pricing/forecaster.py` を新規作成し、直近 30/90 日の移動平均・中央値による価格推移推定を実装する。
2. **サジェスト API の実装 (T-20)**: `GET /api/products/{id}/suggestion` で現在実質価格と次回セール時期待価格を比較し、推奨アクションと根拠を返す。
3. **フロントエンド サジェスト UI の実装 (T-21)**: `ProductDossier` にサジェストセクションを追加し、期待節約額を表示する。

## 4. 参照ドキュメント

- プロダクト PRD: `docs/prd/pricehack.md`
- 詳細実装プラン (Phase 1): `docs/plans/phase1-foundation.md`
- 詳細実装プラン (Phase 2): `docs/plans/phase2-price-history.md`
- 詳細実装プラン (Phase 3): `docs/plans/phase3-analytics-suggestion.md`
- システム設計書: `docs/design/system-design.md`
- 意思決定記録 (ADR): `docs/adr/` (特に 010:検索、011:テスト、012:型同期)
