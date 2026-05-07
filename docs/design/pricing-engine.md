# 詳細設計: ポイント算出エンジン (Pricing Engine)

EC サイトごとの複雑な還元ルールを抽象化し、正確な実質価格を算出するコアロジックの設計。

## 1. 概要
`api/lib/pricing/engine.py` に集約される純粋関数群。外部依存（DB や API）を持たず、入力データ（価格、送料、プロフィール、カード情報）からポイント数と内訳（breakdown）を算出する。

## 2. コア・データ構造

### 2.1. `UserContext` (入力)
ポイント算出に必要なユーザー属性をカプセル化したデータ構造。
```python
@dataclass(frozen=True)
class UserContext:
    rakuten_rank: RakutenRank
    is_amazon_prime: bool
    is_rakuten_mobile: bool
    yahoo_premium: bool
    is_paypay_linked: bool
    card_base_rate: float
    card_special_rewards: Dict[str, float]
```

### 2.2. `PricingResult` (算出結果)
```python
@dataclass(frozen=True)
class PricingResult:
    total_points: int            # 円換算された総ポイント
    effective_price: int         # 実質価格 (price + shipping - total_points)
    breakdown: List[RewardEntry] # 内訳
```

### 2.3. `RewardEntry` (内訳項目)
```python
@dataclass(frozen=True)
class RewardEntry:
    label: str    # 表示名 (例: "楽天SPU", "Amazonポイント")
    rate: float   # 倍率 (例: 0.01)
    points: int   # 算出されたポイント数
    note: str     # 補足情報
```

## 3. 算出アルゴリズム

### 3.1. 共通ルール
1.  **端数処理**: ポイント算出時の端数は `math.floor` で切り捨てとする（各サイトの挙動に準拠）。
2.  **実質価格の下限**: `max(0, ...)` で処理し、負数にならないようにする。
3.  **計算対象金額**: 初期実装では API の `currentPrice` をそのままベースとする。

### 3.2. サイト別ロジック（2025/2026 基準）

#### **Amazon.co.jp**
- **基本還元率**: 一律 1% と仮定。
- **Amazon Mastercard 特典**:
    - `card_special_rewards["amazon"]` が 1.5% かつ `is_amazon_prime` が true の場合、自動的に **2.0%** へ昇格させる。
- **Amazon Prime 特典**: `is_amazon_prime` が true の場合、実質価格算出時の `shipping_fee` を強制的に **0** として扱う。

#### **楽天市場 (SPU)**
- **ストアポイント**: 1% (固定)
- **楽天カード利用特典 (SPU)**: `card_special_rewards["rakuten"]` の値をそのまま加算（2% または 4%）。
- **楽天モバイル特典 (SPU)**: `is_rakuten_mobile` が true の場合、**+4%** 加算。

#### **Yahoo! ショッピング (LYP プレミアム)**
- **ストアポイント**: 1% (固定)
- **LYP プレミアム会員特典**: `yahoo_premium` が true の場合、**+2%** 加算。
- **PayPay 支払特典**: `is_paypay_linked` が true の場合、**+4%** 加算。

## 4. クレジットカード連携
`UserContext.card_special_rewards` を介して `Card` テーブルのデータを注入する。
- 楽天カード系: SPU 加算分として扱う。
- Amazon Mastercard: 会員状態によるレート変動（1.5% -> 2.0%）をエンジン内部で吸収する。
- 非提携カード: `card_base_rate`（通常 1.0%）が全サイトの基本還元として適用される。

## 5. テスト
`tests/unit/pricing/test_engine.py` にて、ゲスト/会員/特定カードの各組み合わせに対する期待値を検証済み。

## 6. 関連タスク
- Phase 1 T-06: サイト別ポイント算出ロジックの純粋関数化
