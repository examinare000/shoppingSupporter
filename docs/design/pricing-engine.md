# 詳細設計: ポイント算出エンジン (Pricing Engine)

EC サイトごとの複雑な還元ルールを抽象化し、正確な実質価格を算出するコアロジックの設計。

## 1. 概要
`api/lib/pricing/` 配下に集約される純粋関数群。外部依存（DB や API）を持たず、入力データ（価格、送料、プロフィール、カード情報）からポイント数と内訳（breakdown）を算出する。

## 2. コア・データ構造

### 2.1. `PricingResult` (算出結果)
```python
@dataclass
class PricingResult:
    total_points: int            # 円換算された総ポイント
    effective_price: int         # 実質価格 (price + shipping - total_points)
    breakdown: list[RewardEntry] # 内訳
```

### 2.2. `RewardEntry` (内訳項目)
```python
@dataclass
class RewardEntry:
    label: str    # 表示名 (例: "楽天SPU", "Amazonポイント")
    rate: float   # 倍率 (例: 0.01)
    points: int   # 算出されたポイント数
    note: str     # 補足情報
```

## 3. 算出アルゴリズム

### 3.1. 共通ルール
1.  **端数処理**: ポイント算出時の端数は切り捨てとする（各サイトの挙動に準拠）。
2.  **実質価格の下限**: `max(0, ...)` で処理し、負数にならないようにする。

### 3.2. サイト別ロジック
- **Amazon**:
    - 基本還元率（通常 1%）
    - Amazon Prime 加算（対象商品のみ、現状は固定 1% または 2% で検討）
    - Amazon Mastercard 加算（カード情報参照）
- **楽天 (SPU)**:
    - 基本 (1%)
    - ランク加算
    - 楽天カード利用加算（通常/ゴールド/プレミアムの区分）
- **Yahoo! ショッピング**:
    - 基本 (1%)
    - LYP (旧プレミアム) 加算 (+4%)
    - PayPay 支払い加算（要検討）

## 4. クレジットカード連携
`Card.special_rewards` フィールド（JSON）を活用する。
```json
{
  "amazon": 2.5,
  "rakuten": 1.0,
  "yahoo": 1.0
}
```
このマッピングに基づき、サイトごとの追加還元率を動的に加算する。

## 5. テスト戦略
- **テーブル駆動テスト**: 大量の組み合わせ（サイト × ランク × カード）を `pytest.mark.parametrize` で網羅する。
- **回帰テスト**: フロントエンドの旧実装（`effectivePrice.ts`）と同じ入力で同じ結果が出ることを保証する。

## 6. 関連タスク
- Phase 1 T-06: サイト別ポイント算出ロジックの純粋関数化
