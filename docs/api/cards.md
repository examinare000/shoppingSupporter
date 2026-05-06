# Card マスタ API

最終更新: 2026-05-06（T-04 実装反映）

`Card` テーブルが保持する「クレジットカードの還元率マスタ」を公開する読み取り専用 API。Phase 1 では書き込み系 API を持たず、行の投入は seed スクリプト（`api/common/seed/cards.py`）で行う。

## 1. データモデル

| フィールド | 型 | 説明 |
|---|---|---|
| `id` | `int` | 主キー（autoincrement） |
| `name` | `string` | カード名（仕様文言。例: `楽天カード`） |
| `base_reward_rate` | `float` | 基本還元率（%）。サイト非依存の購入時還元率 |
| `annual_fee` | `int` | 年会費（円）。無料カードは `0` |
| `special_rewards` | `dict[string, float]` | サイト別の **追加還元率**（%）。後述 |

API レスポンスは camelCase（`baseRewardRate` / `annualFee` / `specialRewards`）。SQLAlchemy / seed 側は snake_case。

## 2. `special_rewards` の構造

形式は `{ <site>: <rate>, ... }` の dict。

- **キー**: `SiteType` enum の値文字列（`"amazon"` / `"rakuten"` / `"yahoo"`）。それ以外のキーは未定義（将来拡張時に enum を追加）
- **値**: `float`。当該サイトでこのカードを使用したときに **基本還元率に加算される追加還元率（%）**
- **キー不在**: そのサイトでは加算なし。読み出し側は `special_rewards.get(site, 0.0)` でフォールバックする

例: `base_reward_rate: 1.0` のカードに `{"rakuten": 1.0}` がある場合、楽天での実効還元率は 2.0%（基本 1% + 加算 1%）。

> ポイント計算の最終ロジック（SPU・Yahoo! プレミアム・カード加算の合算順）の確定は T-06 の責務。本ドキュメントは構造とセマンティクスの最低限の合意のみ定める。

## 3. エンドポイント

認証不要（公開）。書き込み系（POST/PUT/DELETE）は Phase 1 では実装しない。

### 3.1. 一覧 `GET /api/cards`

**Response (200 OK):**

```json
[
  {
    "id": 1,
    "name": "楽天カード",
    "baseRewardRate": 1.0,
    "annualFee": 0,
    "specialRewards": { "rakuten": 1.0 }
  }
]
```

- bare array（envelope ではない）。件数固定 ~10 のためページングは持たない
- 並び順は `id ASC` 固定

### 3.2. 詳細 `GET /api/cards/{id}`

**Response (200 OK):** 単一の Card オブジェクト（一覧要素と同形）。

| ステータス | 条件 |
|---|---|
| `200` | 正常（指定 id のカードが存在） |
| `404` | 指定 id のカードが存在しない |
| `422` | `id` が非整数（FastAPI のパスパラメタ型バリデーション） |

## 4. 初期投入カード

`api/common/seed/cards.py` の `CARDS_SEED_DATA` で投入される 5 件。

| name | base_reward_rate | annual_fee | special_rewards | 設定根拠 |
|---|---|---|---|---|
| `楽天カード` | 1.0 | 0 | `{"rakuten": 2.0}` | 楽天市場利用時に SPU で加算される代表的な無料カード。校正済み |
| `楽天プレミアムカード` | 1.0 | 11000 | `{"rakuten": 4.0}` | 楽天カードの上位。プライオリティパス特典等は対象外だが還元率は最高 |
| `Amazon Mastercard` | 1.0 | 0 | `{"amazon": 1.5}` | Amazon 利用時の一般会員ベース。プライム加算は T-06 で合算 |
| `Yahoo! JAPAN カード` | 1.0 | 0 | `{"yahoo": 1.0}` | PayPay カード前身。Yahoo! ショッピングで +1% の倍率加算 |
| `一般 1% 還元カード` | 1.0 | 0 | `{}` | サイト別加算を持たないベースライン用ダミー |

> 各値は 2026 年時点の代表値。T-06 のポイント計算実装に向けてシードデータを校正済み。実値・適用条件の最終確定は T-06 実装時に行う。

## 5. 投入手順

```bash
# DATABASE_URL を設定してから（README の Neon 接続手順を参照）
python -m api.common.seed.cards
```

冪等性: `name` をキーとして既存行を検索し、存在すればフィールドを更新（UPDATE）、存在しなければ新規挿入（INSERT）を行う。`UserProfile.default_card_id` の参照を破壊せずに最新の還元率を反映できる。

## 6. テストレイヤー

| ファイル | 件数 | 観点 |
|---|---|---|
| `tests/integration/test_cards.py` | 18 | 一覧の並び・空配列・camelCase 完全一致 / 詳細の 200・404・422 / 公開エンドポイント / seed の冪等性・名称一致 |
