# 修正プラン: UserProfile および Card マスタの拡張

最終更新: 2026-05-05

## 1. 背景
T-06「ポイント算出ロジック」の詳細設計（2025/2026年最新基準）において、現在の `UserProfile` モデルおよび `Card` マスタのデータでは、正確な還元率を算出するための情報が不足していることが判明した。本プランでは、これらのギャップを埋めるための拡張を実施する。

## 2. 変更内容

### 2.1. UserProfile モデルの拡張
以下のフィールドを `user_profiles` テーブルに追加する。
- `is_rakuten_mobile` (Boolean): 楽天 SPU (+4%) の判定に使用。
- `is_paypay_linked` (Boolean): Yahoo! ショッピングの LINE 連携 + 指定支払特典 (+4%) の判定に使用。

### 2.2. Card マスタ（シードデータ）の校正
最新の SPU 仕様および各サイトの還元率に基づき、`api/common/seed/cards.py` のデータを更新する。
- **楽天カード**: `special_rewards` を `{"rakuten": 2.0}` に引き上げ（通常カード特典）。
- **楽天プレミアムカード**: 新規追加。`base_reward_rate: 1.0`, `annual_fee: 11000`, `special_rewards: {"rakuten": 4.0}`。
- **Amazon Mastercard**: `special_rewards` を `{"amazon": 1.5}`（一般会員ベース）とし、プライム加算分はロジック側で処理する方針を徹底。

## 3. 実施タスク

### 3.1. バックエンド
1.  **DB マイグレーション**: `alembic revision -m "add_mobile_and_paypay_flags_to_profile"` を実行し、カラムを追加。
2.  **モデル更新**: `api/common/models.py` の `UserProfile` クラスにフィールド追加。
3.  **スキーマ更新**: `api/schemas.py` の `UserProfileUpdate` / `UserProfileResponse` にフィールド追加。
4.  **リポジトリ更新**: `api/repositories/user_profiles.py` の `upsert_profile` 引数と更新処理を修正。
5.  **ルーター更新**: `api/routers/profile.py` のデフォルト値およびハンドラを修正。
6.  **シード更新**: `api/common/seed/cards.py` の `CARDS_SEED_DATA` を校正。

### 3.2. フロントエンド（T-09 型同期にて対応）
- `UserProfile` の型定義が自動更新されることを確認。
- 設定画面（`UserProfile` 編集 UI）への新規トグルの追加（将来タスク）。

## 4. 影響範囲
- 既存ユーザーのプロフィール取得時に新規フィールドが `false`（デフォルト）で返されるようになる。
- ポイント算出ロジック（T-06）において、これらのフラグを参照して正確な計算が可能になる。
