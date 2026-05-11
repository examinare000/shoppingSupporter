# 最適購買パターンサジェスト機能 要件定義書 (Suggestion Engine)

最終更新: 2026-05-05（ユーザーフィードバック反映版）

## 概要

ユーザーの会員ステータス・所有カード・キャンペーン上限への到達状況・セールカレンダーを統合し、「**今この商品をどのサイトでいつ買うのが最も得か**」を根拠付きで提示する機能。

`docs/prd/price-comparison.md`（単一商品の実質価格比較）を時間軸とユーザー実績軸に拡張するもので、以下を 1 機能として束ねる:

1. ユーザー個別の **真の還元率**（キャンペーン上限を超えない範囲で実際に得られる還元）の算出
2. **セールカレンダー**を踏まえた「今買う / 待つ」の判定
3. **算出根拠の可視化**（なぜこの推奨か、内訳でユーザーが検証できる）

## 背景

EC サイトの還元率は、ユーザー属性（楽天ランク・LYP / Yahoo プレミアム・Amazon Prime・所有カード）だけでなく、当月の利用実績にも依存する。代表例:

- 楽天お買い物マラソンの **獲得上限 7,000pt**：上限到達後は還元率が実質 1% に戻る
- 楽天 SPU の月間獲得上限（プログラム別）
- Amazon ポイントアップキャンペーン（Prime Day / 年末等）の **対象金額上限**
- Yahoo / LYP の超 PayPay 祭などの **付与上限**

さらに、価格自体もセール周期で変動するため、「現時点の最安サイト」と「来週セールを待った場合の実質最安」を比較できる必要がある。本機能はこれら**複数次元の最適化**を代行する。

## 既存 ADR との関係（制約）

本機能は以下の決定の上に積み上げる。**逸脱が必要な場合は新規 ADR で正当化する**。

| 制約 | 出典 | 本 PRD への影響 |
|---|---|---|
| データ取得は公式 API 経由のみ。スクレイピングは廃止 | ADR-003 | EC サイトに対する **代理ログイン / クレデンシャル預かりは行わない**。利用実績の取得手段は § 2.1 を参照 |
| 計算ロジックの主導権はバックエンド | ADR-006 | フロントは API 結果の表示に徹する |
| 予測アルゴリズムは透明性の高いルールベースから開始、ML は将来検討 | ADR-006 | Phase 1 で **ML を導入しない**。移動平均と構造化されたセールカレンダーで初期実装する |
| デプロイは Vercel Functions + Neon に集約 | ADR-002 / ADR-009 | 専用 Scraping Worker / ML Server は持たない。バッチは Vercel Cron で実行 |

## 用語

| 用語 | 定義 |
|---|---|
| **基本還元率** | サイト × カード × 会員ランクのみで決まる、利用実績に依存しない還元率（Phase 1 / T-06 が算出） |
| **真の還元率（effective rate）** | 当月の利用実績とキャンペーン上限を考慮した、**追加で 1 円使ったときに実際に得られる**還元率。上限到達後は基本還元率まで落ちる |
| **セールカレンダー** | 各サイトの **構造化された** キャンペーンマスタ（5・0 付きの日 / マラソン / Prime Day 等） |
| **真の実質価格** | `price + shipping − (price × 真の還元率)` |
| **サジェスト** | 「今 A サイトで買う」「N 日後の B サイトのセールまで待つ」のような **行動提案** |

## スコープ

### 含む
- 「真の還元率」の算出（上限・利用実績を反映）
- セールカレンダーのマスタ化と日次の倍率適用
- 単品商品ページでの「今買う / 待つ」サジェスト
- 利用実績の **手動入力 UI**（自己申告）と、それに基づく上限残量計算
- 算出根拠の構造化されたレスポンス（`breakdown`）

### 含まない（将来検討）
- 複数商品をまたぐ **バスケット最適化**（楽天マラソン 10 店舗回遊の組み立て等）
- ML による価格予測（本 PRD は移動平均 + セールカレンダーで開始）
- 利用実績の自動取得（ブラウザ拡張・メール解析・公式 API による購入履歴連携など、いずれも別 ADR で評価）
- 楽天 SPU のサブプログラム個別最適化（楽天モバイル契約推奨など、ライフスタイル変更を伴う提案）
- ポイントの円換算レート変動（楽天 1pt = 1 円固定で開始、後続でマスタ化）

### 明示的に行わないこと
- **EC サイトへの代理ログイン**（規約・法務・セキュリティの三重リスク。ADR-003 と矛盾するため一切採用しない）
- **クレデンシャル（ID/PW）の預かり**（メモリ上一時保持も含めて行わない）

## 機能要件

### 1. ユーザー利用実績の取得

#### 1.1. 手動入力（Phase 1 で実装）

ユーザーが当月の累計利用額・現在ランク・上限到達状況を **自己申告** で登録できる。

- **入力精度の選択**: `UserProfile` に `input_precision_preference`（`EXACT` / `ROUGH`）を設ける。
    - `EXACT`: 1 円単位での正確な利用額入力を求める。
    - `ROUGH`: 「〜1 万円」「1〜3 万円」といったレンジ選択、または「上限まで余裕あり / まもなく上限 / 上限到達」といった概算選択を許容する。
- `PUT /api/me/usage` でサイト別月次利用額を更新。
- 楽天マラソンの **当月既獲得ポイント** も保持。上限との残差から算出。
- **買い回り数の扱い**: サジェスト時点での **「現在の実績（すでに N 店舗）」** に基づいて計算し、架空の店舗完走を前提とした過大なサジェストは行わない。
- 月次リセット: `recorded_month`（YYYY-MM）をキーにし、月境界で自動的に 0 起算。過去月のレコードは保持（推移検証用）
- バリデーション: 負数 / 上限を超える非現実的な値は 422

#### 1.2. 自動取得（将来 / Phase 4 以降）

下記いずれの方式も **別 ADR で正当性・規約適合性・セキュリティを評価** してから着手する。本 PRD では設計余地のみ示す。

- 各 EC サイトの **公式 API による購入履歴連携**（提供されるサイトのみ）
- ユーザー自身が運用するブラウザ拡張機能からのインポート（クレデンシャルはユーザー端末から出ない）
- メール購入レシートの解析（OAuth で受信箱権限を最小限取得）

**いずれの場合も、本サービスのバックエンドが EC サイトの ID/PW を保持・利用することは無い**。

### 2. セールカレンダー

#### 2.1. データモデル要件

新規テーブル `sale_campaigns`:

| カラム | 型 | 説明 |
|---|---|---|
| `id` | int | PK |
| `site` | `SiteType` | キャンペーン主催サイト |
| `name` | string | 表示名（例: `お買い物マラソン`、`5と0のつく日`） |
| `kind` | enum | `recurring`（毎月 X 日など） / `oneshot`（Prime Day 等の単発） |
| `recurrence_rule` | jsonb | 周期定義（`{type: "day_of_month", days: [5, 10, 15, 20, 25, 30]}` 等） |
| `start_at` / `end_at` | timestamptz | `oneshot` のみ使用。`recurring` は当日 0:00〜23:59 を生成側で展開 |
| `bonus` | jsonb | `{type: "multiplier", factor: 1.05}` または `{type: "additive_rate", rate: 0.04}` 等の構造化されたボーナス定義 |
| `cap` | jsonb? | 上限定義（例: `{type: "points", value: 7000}` / `{type: "amount", value: 100000}`） |
| `conditions` | jsonb? | 適用条件（`{rakuten_card_holder: true}` 等。空なら無条件） |
| `source_url` | string | 仕様の出典 URL（ユーザー検証用 / 後追い更新用） |
| `verified_at` | timestamptz | 仕様確認日。3 ヶ月以上経過したものは UI で「要再確認」フラグを立てる |

メンテナンスは **運営者向けに届く各 EC サイトからの公式お知らせメール（メルマガ等）の解析** を主軸とする。
- スクレイピングに依存せず、運営アカウントに届く情報を構造化して `sale_campaigns` に反映する。
- 運用者がメール内容を確認し、`verified_at` を更新する。

#### 2.2. 適用ロジック

ある日 `D` におけるサイト `S` の追加倍率は、`sale_campaigns` から:

```
∑ (active_campaigns_for(S, D, user) → bonus を合算)
```

合算順は `base_rate → SPU/Premium 加算 → カード加算 → セールカレンダー加算 → 上限キャップ` の固定順序とする。順序差で結果が変わる組み合わせ（乗算と加算の混在）は `bonus.type` の評価ルールで一意化する（詳細は T-06 / T-08 の設計時に確定）。

### 3. 真の還元率（Effective Rate）

`api/lib/pricing/` 配下の純粋関数として実装する（T-06 拡張）。

```python
def compute_effective_rate(
    *,
    site: SiteType,
    profile: UserProfile | None,
    card: Card | None,
    monthly_usage: MonthlyUsage | None,
    campaigns: list[SaleCampaign],
    today: date,
) -> EffectiveRate:
    ...
```

戻り値:

```
EffectiveRate = {
    rate: float,                 # 当該購入で得られる実効還元率（%）
    breakdown: list[Reward],     # base / spu / card / campaign の内訳
    cap_status: CapStatus,       # ok / near_cap / capped
    cap_remaining: int | None,   # 残り何ポイントで上限か
}
```

- `cap_status = capped` のとき `rate` は基本還元率まで落ちる
- `cap_status = near_cap` は UI で警告（残り N ポイントで上限）
- `breakdown` は `[{source: "base", rate: 1.0}, {source: "spu_rakuten_card", rate: 1.0}, {source: "marathon", rate: 9.0, capped_to: 7.5}]` のような構造で、ユーザーが算出根拠を検証できる

### 4. 「今買う / 待つ」サジェスト

#### 4.1. 入力

- 商品（`Product` / 紐づく `EcSiteProduct[]`）
- 認証ユーザーの `UserProfile` + `MonthlyUsage`（未認証なら `None`）
- 向こう N 日（既定 14 日）の **価格推移シナリオ**（§ 4.2）
- 今後 N 日のアクティブな `sale_campaigns`

#### 4.2. 価格・セール推移シナリオ（初期実装）

ML を使わず、以下のルールで「N 日後の想定ベース価格およびセール」を推定する:

- **想定ベース価格**:
  - 直近 30/90 日の最安値・中央値を `PriceHistory` から算出。
  - セール期間中は **過去同種セール時の中央値** を採用（例: 過去のお買い物マラソン中の同 EcSiteProduct 平均値）。
- **セール予測**:
  - `sale_campaigns` に登録された確定スケジュール（oneshot）および固定周期ルール（recurring: 5と0のつく日等）を優先。
  - それ以外の不定期セール（楽天お買い物マラソン等）については、**過去の実施履歴（実施周期・開始曜日等）に基づき近日中の開催可能性を推定**する。
- **予測精度の保証**:
  - 履歴が不足する商品（14 日未満のデータ）は **予測を返さず**、`forecast_available: false` を立てる（信頼度の偽装を避ける）。

将来 ML を導入する場合は別 ADR を起票し、本セクションの推定ロジックを差し替える。

#### 4.3. スコアリング

シナリオごとの **真の実質価格** を算出し、最良候補上位 N 件を返す:

```
score(scenario) = 真の実質価格(scenario)  # 小さいほど良い
```

タイブレーク順:
1. 真の実質価格が最も低い
2. 待機日数が短い（同価格なら今買う方を優先）
3. 信頼度が高い（履歴の厚みで判定）

#### 4.4. レスポンス例

```json
{
  "product_id": "...",
  "today_best": {
    "site": "amazon",
    "effective_price": 4820,
    "rate": { "rate": 4.5, "cap_status": "ok", ... },
    "rationale": "Amazon が現時点の真の最安。Prime 加算 + Mastercard 加算が反映済み"
  },
  "wait_candidates": [
    {
      "site": "rakuten",
      "wait_days": 3,
      "expected_effective_price": 4510,
      "expected_savings": 310,
      "confidence": "medium",
      "rationale": "3 日後にお買い物マラソン開始。直近 90 日の同種セール中央値ベースで 5,200→4,900 円程度の値下げを想定。現在の買い回り実績（N 店舗）に基づいて算出"
    }
  ],
  "forecast_available": true
}
```

`rationale` は **構造化された breakdown** から日本語に整形して返す。テンプレート方式とし、ML / LLM による文章生成は行わない。

### 5. 透明性とユーザー検証

ユーザーが「なぜこの推奨か」を検証できることを必須要件とする。

- `breakdown` を UI で展開可能に表示する（`MarginalNote` または専用コンポーネント）
- `sale_campaigns` の `source_url` を当該推奨の根拠として参照可能にする
- 上限到達済みの場合、「上限到達済 → これ以上ポイント加算なし」を明示

## 非機能要件

### 1. セキュリティ

- **EC サイトのクレデンシャルは一切預からない**（§ 1 の方針）。本サービスの DB に該当カラムを設けない
- `JWT_SECRET` はじめ既存の認証スキームを継承（ADR-007）
- `MonthlyUsage` は本サービス由来の自己申告データ。第三者には漏らさず、`/api/me/usage` の参照は本人のみ（`get_current_user` 必須）

### 2. インフラ

- **追加のホスティングコンポーネントを持たない**。バッチは Vercel Cron、データは Neon に集約（ADR-002 / ADR-009）
- セールカレンダーの `verified_at` 期限切れチェックは Vercel Cron（日次）で `verified_at + 90 日` を超えたものを Slack / メール通知

### 3. 性能

- 単品サジェスト API は p95 で 500ms 以内を目標（同期 / 単一クエリ前提。本要件は T-08 の延長線で計測する）
- `sale_campaigns` の評価は当該日 `D` のアクティブ件数のみを引く（`recurrence_rule` / SQL で展開すると複雑化するため、Python 側でフィルタする）

### 4. 正確性とメンテナンス性

- `sale_campaigns.verified_at` を 3 ヶ月以内に保つ運用ルール
- ポイント円換算レートは `pricing` モジュール内の定数として管理し、後続でマスタ化可能な構造にする
- すべての加算 / 上限ロジックは純粋関数として `tests/unit/test_pricing/` で網羅テスト（ADR-006 の透明性方針）

### 5. UX

- 信頼度が低い（履歴不足）ときは **推奨を返さない**。「分からない」を表示する選択肢を持つ
- 待機推奨の場合、待機期間中の価格上昇リスクは breakdown で明示（「過去 90 日のうち X% で値下がり」等）

## システム構成

```
[Frontend]
    │
    ▼ /api/products/{id}/suggestion など
[Vercel Functions: api/]
    │  ├─ api/lib/pricing/        # 純粋関数（既存 T-06 を拡張）
    │  └─ api/routers/suggestion.py
    │
    ├──► [Neon: sale_campaigns / monthly_usage / price_histories ...]
    │
    └──► [Vercel Cron]
           ├─ 価格更新（既存 /api/cron/update-prices）
           └─ sale_campaigns 検証期限通知（新規）
```

ADR-009 の構成を維持し、新規ホスティング層は追加しない。

## 段階導入

ADR-006 のフェーズ分けに揃える。

| Phase | 含む | 主な前提タスク |
|---|---|---|
| Phase 1（既存） | 基本還元率（属性＋カード）の算出と検索 API への同梱 | T-06（純粋関数）/ T-08（検索同梱） |
| Phase 2 | 価格履歴の可視化 | ADR-006 Phase 2 |
| Phase 3-a | `sale_campaigns` マスタと真の還元率（手動利用実績） | 本 PRD のコア |
| Phase 3-b | 「今買う / 待つ」サジェスト（移動平均 + セールカレンダー） | Phase 3-a + 履歴蓄積 |
| Phase 4（将来） | 利用実績の自動取得（別 ADR）/ バスケット最適化 / ML 化 | 別途 ADR を起票 |

Phase 3-a は Phase 1 完了後すぐに着手可能。Phase 3-b は `PriceHistory` が直近 90 日以上の厚みを持つ商品が一定数蓄積されてから着手する。

## 受け入れ基準

| シナリオ | 条件 | 操作 | 期待結果 |
|---|---|---|---|
| 真の還元率（通常時） | 楽天ダイヤモンド + 楽天カード保有、当月利用 30,000 円、マラソン獲得 0pt | 楽天サイトの 5,000 円商品の suggestion を取得 | `rate` に SPU + カード + （該当日なら）マラソン加算が含まれ、`cap_status = ok`。`breakdown` 配列に各加算源が列挙される |
| 真の還元率（上限到達） | 同上、ただしマラソン獲得 7,000pt（上限到達済） | 同上 | `cap_status = capped`、`rate` は基本還元率まで低下、`breakdown` に「marathon: capped」が含まれる |
| 上限間際 | マラソン獲得 6,800pt | 同上 | `cap_status = near_cap`、`cap_remaining = 200`、UI で警告表示できる構造 |
| 「今買う」推奨 | アクティブセールが今日のみ、3 日後はセール無し | suggestion 取得 | `today_best` が選ばれ、`wait_candidates` に有意な代替なし |
| 「待つ」推奨 | 3 日後にお買い物マラソン開始予定（`sale_campaigns` に登録済み） | suggestion 取得 | `wait_candidates` に 3 日後楽天が含まれ、`expected_savings > 0`、`rationale` に「お買い物マラソン」の名称と source_url が含まれる |
| 履歴不足 | `PriceHistory` が 14 件未満の商品 | suggestion 取得 | `forecast_available: false`、`wait_candidates` 空配列。「分からない」を UI で表示できる |
| 未認証アクセス | トークン無し | suggestion 取得 | 200 で返る。`MonthlyUsage` を `None` として、基本還元率ベースの今買う推奨のみを返す |
| 利用実績の更新 | 認証済 | `PUT /api/me/usage` で当月楽天利用 80,000 円を登録 | 200。直後に同月 `GET /api/me/usage` で同値が返る。月境界では自動 0 リセットされる |
| キャンペーン期限切れ | `sale_campaigns.verified_at` が 90 日超のレコードあり | 日次 Cron 実行 | 通知が発火する。当該レコードは `forecast` から除外せず利用は継続するが、レスポンスに `stale_campaign_warning: true` を含む |
| クレデンシャル非保持の検証 | テスト | DB スキーマ確認 | `users` および周辺テーブルに EC サイトの ID / PW / トークンを保持するカラムが**存在しない** |

## リスクと対応

| リスク | 兆候 | 対応 |
|---|---|---|
| セールルール変更で `sale_campaigns` がドリフト | ユーザー報告と実値のズレ | `verified_at` 期限切れ通知 + 構造化された `bonus` 定義により修正コストを 1 行に抑える |
| 自己申告利用額の不正確さ | サジェストの精度低下 | `cap_status` の表示で「申告通りなら」を明示。実害は推奨の質低下のみ（金銭被害は無い） |
| `PriceHistory` の蓄積不足 | `forecast_available: false` が多発 | Phase 3-b 着手前に閾値（履歴厚み 30 日以上の商品が N 件以上）を満たすまで延期する判断を許容 |
| 推奨の根拠が不透明と批判される | ユーザーからの問い合わせ | `breakdown` と `source_url` を UI で必ず展開可能にする。文章生成は LLM 依存にしない |
| 利用規約違反のグレーゾーンに踏み込む議論が再燃 | 「代理ログインを実装したい」要望 | 本 PRD § 1.2 と ADR-003 を根拠に、別 ADR で正当化されない限り採用しないことを明文化 |

## 関連ドキュメント

- `docs/prd/price-comparison.md`（単一商品の実質価格比較。本 PRD の前提）
- `docs/adr/003-playwright-scraping.md`（公式 API 縛りの根拠）
- `docs/adr/006-advanced-features-roadmap.md`（フェーズ分けとルールベース方針）
- `docs/adr/007-authentication-strategy.md`（JWT 認証）
- `docs/adr/009-backend-to-api-consolidation.md`（Vercel + Neon 集約構成）
- `docs/plans/phase1-foundation.md`（T-06 / T-08 の現状）
