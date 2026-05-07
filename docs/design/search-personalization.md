# 詳細設計: 検索結果のパーソナライズ統合

検索 API にユーザーのコンテキストを統合し、個別の実質価格を効率的に返却するための設計。

## 1. 概要
`GET /api/products/search` において、認証トークンがある場合に `UserProfile` を読み込み、各検索結果（`Listing`）に対してポイント計算を適用する。

## 2. 処理フロー

1.  **コンテキスト取得**: `Depends(get_current_user_optional)` により、認証済みであれば `User` オブジェクトを取得。
2.  **プロファイル読み込み**: `User` に紐づく `UserProfile` と `default_card` を DB から Eager Load (joined load) する。
3.  **検索実行**: 通常のキーワード検索（FTS + Trigram）を実行し、`Product` および `EcSiteProduct` (Listing) のリストを取得。
4.  **パーソナライズ計算**:
    - 取得した `Listing` ごとに、`PricingEngine` を呼び出す。
    - 匿名ユーザーの場合は、デフォルトのプロファイル値を使用して計算。
5.  **レスポンス構築**: 計算結果（points, effectivePrice, breakdown）を各 `Listing` オブジェクトにマッピングして返却。

## 3. レスポンス・スキーマの拡張

### 3.1. `Listing` オブジェクト
```json
{
  "site": "amazon",
  "price": 1000,
  "shipping": 0,
  "points": 10,
  "effectivePrice": 990,
  "breakdown": [ ... ]
}
```

### 3.2. `PersonalizationMeta` (追加)
レスポンス全体のエンベロープに、どのような設定で計算されたかを示すメタ情報を追加する。フィールド名は camelCase 統一。
```json
{
  "items": [ ... ],
  "meta": {
    "personalization": {
      "applied": true,
      "rakutenRank": "diamond",
      "hasCard": true
    }
  }
}
```

## 4. パフォーマンス考慮事項

### 4.1. N+1 問題の回避
検索結果の各 Listing に対してプロフィールを参照するため、以下の対策を行う。
- プロフィール情報はリクエストごとに 1 回だけ取得し、メモリ上に保持して使い回す。
- `EcSiteProduct` の取得は `selectinload` 等を使用して一括で行う。

### 4.2. 計算コスト
Python 側での数値計算は Listing 数（最大数十件）に対しては無視できるほど高速だが、ループ内での複雑な分岐は避け、`PricingEngine` の純粋関数化を徹底する。

## 5. 関連タスク
- Phase 1 T-08: 検索 API への UserProfile / Card 統合
