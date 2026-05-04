# バックエンド API 設計書 (Phase 0)

フロントエンドのモック駆動から実バックエンド接続への移行に必要な、主要エンドポイントの設計を定義する。

## 1. 概要

- **Base URL**: `/api`
- **形式**: JSON
- **認証**: 現時点では検索等は認証不要。将来的に `Authorization: Bearer <token>` を使用。

## 2. エンドポイント

### 2.1. 商品検索
`GET /api/products/search`

クエリに基づいて DB から商品を検索し、各 EC サイトの出品情報を含めて返却する。

**Query Parameters:**
- `q` (string, required): 検索キーワード。JAN コードまたは商品名。
- `sort` (string, optional): ソート順。 `effectivePriceAsc` (デフォルト), `priceAsc`, `pointsDesc`。

**Response (200 OK):**
```json
{
  "results": [
    {
      "id": "uuid",
      "name": "商品名",
      "janCode": "45XXXXXXXXXXX",
      "imageUrl": "https://...",
      "category": "Electronics",
      "listings": [
        {
          "site": "amazon",
          "url": "https://amazon.co.jp/...",
          "price": 10000,
          "shippingFee": 0,
          "points": 100,
          "isAvailable": true
        },
        {
          "site": "rakuten",
          "url": "https://item.rakuten.co.jp/...",
          "price": 10500,
          "shippingFee": 0,
          "points": 500,
          "isAvailable": true
        }
      ]
    }
  ],
  "total": 1
}
```

### 2.2. 商品詳細 (価格推移含む)
`GET /api/products/{id}`

特定の商品（UUID または JAN）の詳細情報と、現在の最新価格情報を取得する。

**Response (200 OK):**
```json
{
  "id": "uuid",
  "name": "商品名",
  "janCode": "45XXXXXXXXXXX",
  "listings": [...],
  "description": "..."
}
```

## 3. データ構造 (TypeScript 型定義との整合)

フロントエンドの `frontend/types/product.ts` と整合性を保つ。

### Listing (出品)
| フィールド | 型 | 説明 |
|---|---|---|
| `site` | `"amazon" | "rakuten" | "yahoo"` | 販売サイト |
| `url` | `string` | 商品ページ URL |
| `price` | `number` | 本体価格 (税込) |
| `shippingFee` | `number` | 送料 |
| `points` | `number` | 獲得予定ポイント (円換算) |
| `isAvailable` | `boolean` | 在庫ありフラグ |

### Product (商品)
| フィールド | 型 | 説明 |
|---|---|---|
| `id` | `string` | 内部 ID (UUID) |
| `name` | `string` | 商品名 |
| `janCode` | `string?` | JAN コード |
| `imageUrl` | `string?` | 代表画像 URL |
| `category` | `string?` | カテゴリ名 |
| `listings` | `Listing[]` | 各サイトの出品リスト |

## 4. エラーレスポンス

標準的な HTTP ステータスコードを使用する。

- `400 Bad Request`: パラメータ不正
- `404 Not Found`: 商品が見つからない
- `500 Internal Server Error`: サーバー内部エラー

```json
{
  "error": {
    "code": "ERROR_CODE",
    "message": "人間が読めるエラーメッセージ"
  }
}
```
