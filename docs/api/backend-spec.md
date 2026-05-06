# バックエンド API 仕様

最終更新: 2026-05-06（T-05 UserProfile API 実装反映）

実装は `api/main.py`（FastAPI）配下。ルートは `vercel.json` のリライトで `/api/(.*) → /api/main.py` に集約され、FastAPI 内部でパスマッチする。

## 1. 概要

- **Base URL**: `/api`
- **形式**: JSON（フィールド名は camelCase）
- **認証**: 検索系・Card マスタは公開エンドポイント。ユーザー文脈付きの API は `Authorization: Bearer <JWT>`（ADR-007）。JWT の発行は `/api/auth/login`（§2.6）。

## 2. 実装済みエンドポイント

### 2.1. ヘルスチェック
`GET /api/health`

レスポンス: `{"status": "ok"}`

### 2.2. 商品検索
`GET /api/products/search`

実装: `api/routers/products.py` + `api/repositories/products.py`。Postgres FTS（`tsvector` + `websearch_to_tsquery`）と pg_trgm（trigram 類似度）を OR で結合し、relevance はその合算でランキングする。スキーマは `alembic/versions/0002_product_search_columns.py` 参照。

**Query Parameters:**

| 名前 | 型 | 必須 | 制約 | 説明 |
|---|---|---|---|---|
| `q` | string | ○ | 1〜100 文字 | 検索キーワード |
| `inStock` | boolean | × | true / false | 在庫フィルタ。未指定なら無効 |
| `priceMin` | int | × | 0 以上 | 価格下限（包含） |
| `priceMax` | int | × | 0 以上、`priceMin` 以上 | 価格上限（包含） |
| `sort` | string | × | `relevance`（既定）/ `price_asc` / `price_desc` / `newest` | 並び順 |
| `page` | int | × | 1 以上 | ページ番号（1 始まり） |

ページサイズは固定 10 件（`api/repositories/products.py` の `PAGE_SIZE`）。

**Response (200 OK):**
```json
{
  "items": [
    {
      "id": "uuid",
      "name": "商品名",
      "description": "...",
      "imageUrl": "https://...",
      "tags": ["tag1", "tag2"],
      "inStock": true,
      "currentPrice": 1500
    }
  ],
  "page": 1,
  "totalPages": 3,
  "totalCount": 25
}
```

`totalPages` は `ceil(totalCount / 10)`。`totalCount` は 0 のとき `totalPages` も 0。

**バリデーション失敗 (422):**

以下はすべて `422 Unprocessable Entity` で返る（200 + 空配列にはならない）。

- `q` 欠落 / 空文字列 / 101 文字以上
- `priceMin > priceMax`
- `priceMin` / `priceMax` が非数または負数
- `sort` が許容値以外
- `page` が 0 / 負数 / 非数

レスポンスボディは FastAPI 標準の `{"detail": [...]}` 形式。

**設計メモ:**

- `q` は SQL バインドパラメタ経由でしか DB に届かないため、SQL インジェクションは構造的に発生しない。
- 価格範囲のクロスフィールド検証はハンドラ側（`_validate_price_range`）。pydantic Query では表現できないため。
- 操作ログには `q_len` / `hits` / `elapsed_ms` のみを残し、生の `q` は出力しない（ユーザー入力をログに混ぜない方針）。

**現状の整合性メモ:**

API は上記の envelope `{items, page, totalPages, totalCount}` を返すが、フロント `frontend/lib/api/searchClient.ts` 側はレスポンスを `Product[]` と仮定してキャストしている。そのため `data.items` を取り損ね、ランタイムでは描画不能になる。T-08（Listing 同梱）でレスポンス形を拡張する際、暫定的に envelope 形を維持するか、フロント側で `data.items` を取り出すかは T-09（OpenAPI 型同期）で確定する。

### 2.3. 商品全件取得（暫定）
`GET /api/products`

`api/main.py` 直下に残置されたレガシー互換のエンドポイント。検索の正本は 2.2 を使用すること。

### 2.4. 価格更新 Cron
`GET /api/cron/update-prices`

Vercel Cron Jobs が 1 時間ごとに叩く（`vercel.json` の `0 * * * *`）。各 `EcSiteProduct` について Amazon / 楽天 / Yahoo の公式 API を呼び、`PriceHistory` を追記する。

### 2.5. Card マスタ
`GET /api/cards` / `GET /api/cards/{id}`

実装: `api/routers/cards.py`。仕様の正本は `docs/api/cards.md`（`special_rewards` の構造、初期 5 件のシード内容、投入手順を集約）。

公開エンドポイント（認証不要）。書き込み系（POST/PUT/DELETE）は Phase 1 では実装せず、行の投入は `python -m api.common.seed.cards` で行う。

**Response 概要:**

- 一覧は bare array（envelope ではない）。並び順は `id ASC` 固定
- 詳細は単一オブジェクト。存在しない `id` で `404`、非整数 `id` で `422`
- フィールド: `id` / `name` / `baseRewardRate` / `annualFee` / `specialRewards`

### 2.6. 認証
`POST /api/auth/signup` / `POST /api/auth/login` / `GET /api/auth/me`

実装: `api/routers/auth.py`（HTTP 境界）、`api/common/security.py`（bcrypt / JWT / `Depends(get_current_user)` の集約）、`api/repositories/users.py`（永続化）。仕様の正本は `docs/api/auth.md`。

ADR-007 の決定どおり、ステートレスな JWT（HS256 / `JWT_SECRET` 署名）を発行し、以降の認証必須エンドポイントは `Authorization: Bearer <token>` で受け付ける。トークン失効は今は実装せず、有効期限（60 分）に依る。

**Response 概要:**

- `signup` は `201 Created` で `UserResponse`（`id` / `email` / `createdAt`）。`hashedPassword` は返さない
- `login` は `200` で `TokenResponse`（`accessToken` / `tokenType="bearer"`）
- `/me` は `200` で `UserResponse`。`Authorization: Bearer <token>` 必須
- `signup` の email 重複は `409`（状態競合の意味的表現として `IntegrityError` 救済より優先）
- `login` 失敗（未登録 email / パスワード違い）と `/me` の認証失敗は **すべて同一の 401 + 共通メッセージ**。ユーザー存在有無の漏洩を避けるため意図的に区別しない
- リクエストボディは `extra="forbid"`。`accessToken` 等のレスポンス envelope を body に流用すると `422`

### 2.7. UserProfile
`GET /api/me/profile` / `PUT /api/me/profile`

実装: `api/routers/profile.py`（HTTP 境界）、`api/repositories/user_profiles.py`（永続化、`joinedload` で `default_card` を eager load）、`api/schemas.py`（`UserProfileUpdate` / `UserProfileResponse`）。仕様の正本は `docs/api/profile.md`。

認証必須（`Authorization: Bearer <token>`）。GET は未保存ユーザーに対して 200 + デフォルト値 + `updatedAt: null` を返し、DB レコードは作成しない（GET の冪等性）。PUT は全フィールド必須の全置換で、`defaultCardId: null` を「カード未設定への戻し」として受理する。

**Response 概要:**

- レスポンスは camelCase（`rakutenRank` / `isAmazonPrime` / `isRakutenMobile` / `yahooPremium` / `isPayPayLinked` / `defaultCardId` / `defaultCard` / `updatedAt`）
- `defaultCard` は `CardResponse` 形を nested 同梱
- リクエストボディは `extra="forbid"`。GET レスポンス形（`updatedAt` / `defaultCard`）や `accessToken` 等の envelope 流用は 422
- バリデーション順序は (1) Pydantic（型・Enum・`extra="forbid"` / bool `strict=True`）→ (2) 認証 401 →(3) `card_exists` 422。順序を固定するためハンドラは `Depends(get_current_user)` を使わず `Header` 経由で受けて body 検証通過後に呼ぶ
- `defaultCardId` が存在しないカードを参照した場合は 422（FK IntegrityError 経由ではなく事前 SELECT）

## 3. 未実装（Phase 1 で着手予定）

詳細は `docs/plans/phase1-foundation.md` を参照。

- OpenAPI → TypeScript 型生成パイプライン（T-09）

## 4. 共通エラーレスポンス

| コード | 用途 |
|---|---|
| `200` | 正常 |
| `401` | 認証必須エンドポイントでトークン無効・欠落 |
| `404` | リソース未発見 |
| `422` | クエリ・ボディのバリデーション失敗（FastAPI 標準形式） |
| `500` | サーバー内部エラー |

## 5. 型同期（Phase 1 完了後）

ADR-005 の方針どおり、Phase 1 終了時点で `api/main.py` の OpenAPI スキーマから `frontend/types/api.ts` を生成する CI を組む（T-09）。それ以前は本仕様書を正本とし、フロントの手書き型と整合させる。
