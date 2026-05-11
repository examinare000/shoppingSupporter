# ADR-014: Phase 3-a キャンペーンモデルと月次利用実績管理の設計

## ステータス
採用済み

## 背景

EC サイトのポイント還元率は、ユーザーの月次利用状況（楽天マラソンの買いまわり店舗数、累積獲得ポイント上限等）と、その月に開催されているキャンペーンの組み合わせによって決まる。Phase 1 の PricingEngine（ADR-006）はユーザー属性（カード・会員ランク）を考慮した静的還元率の計算には対応していたが、以下の 2 つのダイナミックな要素が未対応だった。

1. **セールキャンペーン**: 楽天お買い物マラソン（店舗数に応じたポイント倍率）、Yahoo 超 PayPay 祭（ポイント上限あり）等、ECサイトが不定期・定期に実施する加算ルール。
2. **月次利用実績**: ユーザーごとの当月累積利用額・既獲得ポイント数・買いまわり店舗数。上限に達したキャンペーンのボーナスを正確にカットするために必要。

これらを管理するデータモデルと、PricingEngine への統合方針を決定する。

## 決定

### 1. `SaleCampaign` の JSONB 設計

`bonus` / `cap` / `conditions` の 3 カラムを `JSONB` 型とする。

```text
SaleCampaign
├── id            UUID PK
├── site          Enum(SiteType)
├── name          String
├── kind          Enum(CampaignKind)  # recurring | oneshot
├── recurrence_rule  JSONB nullable   # {type: "day_of_month", days: [5,10,...]}
├── start_at      DateTime nullable   # oneshot の開始日
├── end_at        DateTime nullable   # oneshot の終了日
├── bonus         JSONB               # {type: "additive_rate", rate: 0.04}
├── cap           JSONB nullable      # {type: "points", value: 7000}
└── conditions    JSONB nullable      # {requires_rakuten_card: true}
```

**理由**: ECサイトのキャンペーン条件はサービスごとにスキーマが多様で、追加・変更頻度も高い。固定カラムで正規化すると新しいキャンペーン種別ごとにマイグレーションが必要になり、保守コストが高い。JSONB にすることでスキーマ変更なしに新条件タイプを追加できる。Postgres の JSONB は GIN インデックスによる検索も可能で、クエリ性能上の懸念も低い。

### 2. `CampaignKind` enum

`recurring`（定期：5と0のつく日等）と `oneshot`（単発：お買い物マラソン等）の 2 種類のみとする。

**理由**: 現時点の EC サイトキャンペーンはこの 2 パターンで網羅できる。追加の種類が出た場合は enum 値を拡張する（DB マイグレーション不要な `create_constraint=False` を採用）。

### 3. `MonthlyUsage` の自己申告方式

ユーザーが手動で当月利用実績を入力する方式とし、スクレイピングや公式 API による自動取得は行わない。

```text
MonthlyUsage
├── user_id         UUID PK, FK → users.id
├── site            Enum(SiteType) PK
├── recorded_month  String(7) PK        # "YYYY-MM" 形式
├── amount_spent    Integer             # 当月累計利用額（円）
├── points_earned   Integer             # 当月既獲得ポイント数（上限計算用）
└── shop_count      Integer             # 買いまわり店舗数（楽天マラソン用）
```

**理由**:
- 楽天・Yahoo の公式 API は利用実績のリアルタイム取得エンドポイントを提供していない。
- スクレイピングは ToS 違反リスクがあり、ADR-003 の判断（公式 API 以外を廃止）と矛盾する。
- ユーザーは自身の利用状況を把握しており、手動入力のハードルは低い（マラソン中に「今月○店舗目」という意識を持って使うのが一般的な使い方）。

### 4. 複合主キーと UPSERT による月次データ管理

`(user_id, site, recorded_month)` を複合 PK とし、同月・同サイトへの書き込みは INSERT ON CONFLICT DO UPDATE（UPSERT）で処理する。

**理由**: 月次データは「1ユーザー × 1サイト × 1ヶ月で1レコード」という制約が自然。複合 PK により一意性をDB層で保証でき、月が変わると自然に新レコードが作られる。`recorded_month` を `Date` 型ではなく `String("YYYY-MM")` とするのは、フロントエンドの wire format（JSON 文字列）と同形にすることで変換処理をなくすため。

### 5. PricingEngine への統合方法

`compute_pricing` 関数に `campaigns: list[SaleCampaign]` と `usage: MonthlyUsage | None` を引数として追加する。

- キャンペーン加算率を基本還元率に積み上げる。
- `cap` が設定されているキャンペーンは、`usage.points_earned` が上限に達している場合はそのキャンペーンのボーナスを除外する。
- `usage` が `None` の場合（未記録）は上限チェックをスキップして楽観的に計算する。

**理由**: PricingEngine を純粋関数として維持し、DB アクセスを含まない設計を守る。キャンペーン・利用実績の取得責務はルーター層・リポジトリ層に留め、Engine には計算に必要なデータのみを渡す。

## 代替案と却下理由

| 代替案 | 却下理由 |
|---|---|
| `bonus`/`cap` を固定カラムに正規化 | キャンペーン種別ごとに異なるカラム群が必要になり、スキーマが肥大化する。新キャンペーン追加のたびにマイグレーションが必要。 |
| 利用実績の自動取得（スクレイピング） | ToS 違反リスク。ADR-003 の方針に反する。 |
| 月単位の日付型 (`DATE`) を PK に使用 | `YYYY-MM` 文字列の方が月単位の範囲クエリが単純で、フロントエンドとの型変換が不要。 |
| `usage` が未記録時に計算拒否（エラー） | 未設定ユーザーが多いリリース初期に使い勝手が悪い。上限チェックをスキップする楽観計算の方がUX上自然。 |

## 影響

- **`/api/pricing` 公開 API**: キャンペーン一覧の取得（`GET /api/pricing/campaigns`）と、キャンペーン適用後の実質価格計算（`POST /api/pricing/apply`）が提供可能になった。
- **`/api/me/usage` API**: 認証ユーザーが当月の利用実績を `GET`（参照）・`PUT`（更新）できるエンドポイントを追加。未登録サイトは 200 + 0 デフォルトで返す（404 にしない）。
- **PricingEngine の純粋関数性**: DB アクセスを含まない設計を維持。テスト容易性を保つ。
- **Phase 3-b への橋渡し**: `SaleCampaign.recurrence_rule` と `SaleCampaign.start_at/end_at` は、Phase 3-b のサジェストエンジン（`forecaster.py`）が次回セール開催日を推定する際に使用する。
