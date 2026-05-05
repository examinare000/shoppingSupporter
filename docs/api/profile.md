# UserProfile API

最終更新: 2026-05-05（T-05 実装反映）

認証ユーザーが自身の楽天会員ランク・Amazon Prime / Yahoo! プレミアム加入状態・既定カードを保存し、検索結果のパーソナライズ計算（T-08 / T-06）に供する API。設計の正本は `docs/design/user-profile.md`、本ドキュメントは HTTP 境界の契約を集約する。

## 1. 構成

| レイヤー | ファイル | 責務 |
|---|---|---|
| HTTP 境界 | `api/routers/profile.py` | 入力バリデーションの順序固定と HTTP レスポンス整形 |
| 永続化 | `api/repositories/user_profiles.py` | `get_profile_by_user_id` / `card_exists` / `upsert_profile`。`default_card` は `joinedload` で eager 取得 |
| スキーマ | `api/schemas.py` | `UserProfileUpdate`（リクエスト）/ `UserProfileResponse`（レスポンス） |
| マイグレーション | `alembic/versions/0003_user_profile_updated_at.py` | `updated_at` を 3 ステップで追加し、`user_id` FK を `ON DELETE CASCADE` に張り替え |

`bcrypt` / `pyjwt` などの認証実装は触れず、認証は `api/common/security.py` の公開関数 `get_current_user` 経由で確認する（既存 `auth.md` §1 と同じ責務分離）。

## 2. データモデル

| カラム | 型 | 制約 | 説明 |
|---|---|---|---|
| `user_id` | UUID | PK, FK(`users.id`) `ON DELETE CASCADE` | ユーザー ID |
| `rakuten_rank` | Enum | NOT NULL（既定 `regular`） | 楽天会員ランク（`regular` / `silver` / `gold` / `platinum` / `diamond`） |
| `is_amazon_prime` | boolean | NOT NULL（既定 false） | Amazon Prime 加入有無 |
| `yahoo_premium` | boolean | NOT NULL（既定 false） | Yahoo! プレミアム（LYP）加入有無 |
| `default_card_id` | integer | FK(`cards.id`) NULL 許容 | 既定のクレジットカード（未設定可） |
| `updated_at` | datetime | NOT NULL（`onupdate=datetime.utcnow`） | 更新日時。Phase 2 の `If-Unmodified-Since` 楽観ロックの伏線 |

ワイヤフォーマット上の Enum 値は **小文字（value）**（`RakutenRank.DIAMOND.value == "diamond"`）。ADR-013 §5。

## 3. エンドポイント

レスポンスは camelCase（`rakutenRank` / `isAmazonPrime` / `yahooPremium` / `defaultCardId` / `defaultCard` / `updatedAt`）。`response_model_by_alias=True` で wire format を camelCase に固定する。リクエスト body も camelCase で受け付ける（`Field(validation_alias=...)`）。

### 3.1. 取得 `GET /api/me/profile`

**Request header:** `Authorization: Bearer <jwt>`

**Response (200 OK):** `UserProfileResponse`

```json
{
  "rakutenRank": "regular",
  "isAmazonPrime": false,
  "yahooPremium": false,
  "defaultCardId": null,
  "defaultCard": null,
  "updatedAt": null
}
```

| ステータス | 条件 |
|---|---|
| `200` | 認証済み（保存済み・未保存いずれも 200） |
| `401` | ヘッダ欠落 / `Bearer` 以外のスキーム / 改ざん / 期限切れ / `sub` 不正 / 対応 User 不在（`auth.md` §5 と同じ正規化） |

**未保存時の挙動**（docs/design/user-profile.md §3.1）:

- 404 ではなく **200** を返す。フロントは「保存済みデフォルト」と区別せずに描画できる。
- 値はすべて型レベルのデフォルト（`rakutenRank: "regular"`、bool は `false`、`defaultCardId: null`、`defaultCard: null`）。
- `updatedAt` は **`null`**。「未保存マーカー」として保存済み（datetime 値）と区別する。
- DB へのレコード作成は行わない（GET の冪等性）。

**`defaultCard` の同梱**: 保存済みかつ `defaultCardId` 指定時、`CardResponse` 形を nested で同梱する（`docs/api/cards.md` と同形）。リポジトリ層で `joinedload(UserProfile.default_card)` を適用しているため N+1 は発生しない。

### 3.2. 更新 `PUT /api/me/profile`

**Request header:** `Authorization: Bearer <jwt>`

**Request body (`extra="forbid"`):**

```json
{
  "rakutenRank": "diamond",
  "isAmazonPrime": true,
  "yahooPremium": false,
  "defaultCardId": 1
}
```

**Response (200 OK):** `UserProfileResponse`（GET と同形。`updatedAt` は ISO 8601 datetime）

| ステータス | 条件 |
|---|---|
| `200` | 初回 INSERT / 既存行 UPDATE どちらでも 200 |
| `401` | 認証失敗（`auth.md` §5 と同じ正規化） |
| `422` | Pydantic バリデーション失敗 / `defaultCardId` が存在しないカードを参照 |

**更新セマンティクス**: **全フィールド必須の全置換 (PUT)**。`defaultCardId` のみ `null` を許容（カード未設定状態への戻し。422 にしない）。PATCH は将来検討（`docs/design/user-profile.md` §3.2）。

**バリデーション順序**:

1. **Pydantic**（型・Enum 値・`extra="forbid"` / `strict=True`）→ 422
2. **認証**（`get_current_user`）→ 401
3. **リポジトリ層 `card_exists`**（`SELECT 1 FROM cards WHERE id=:id`）→ 422

順序を固定するために、ハンドラは `Depends(get_current_user)` を使わず、`Header` で `authorization` を生で受けて body 検証通過後に `get_current_user` を直接呼ぶ。これにより「不正 body + 未認証」の組み合わせが期待どおり 422 になる（401 にならない）。`auth.md` §5 と同じ 401 正規化は維持される。

**Pydantic 422 の代表ケース**:

- `rakutenRank` / `isAmazonPrime` / `yahooPremium` / `defaultCardId` のいずれかが欠落（PUT 全置換）
- `rakutenRank` が大文字（`"REGULAR"`）/ 未知値（`"legendary"`）
- `isAmazonPrime` / `yahooPremium` に `"yes"` などの文字列（`strict=True` で bool 強制を無効化）
- 未知フィールド（`accessToken` などレスポンス envelope の流用）

**`default_card_id` の存在確認**: 指定された場合、リポジトリ層で `card_exists` を呼ぶ。FK IntegrityError を 500 から 422 に救済するより、状態整合性を意味的に正しい 422 として表現する方が API 利用者に分かりやすい（`auth.md` §4.1 重複 email 409 と同じ判断）。

## 4. 同時更新の扱い

Phase 1 は **last-write-wins**。楽観ロックは持たない。`updated_at` は将来の `If-Unmodified-Since` 等の種として保持する（`docs/design/user-profile.md` §3.2）。

## 5. テストレイヤー

| ファイル | 件数 | 観点 |
|---|---|---|
| `tests/integration/test_profile.py` | 46 | GET/PUT の HTTP 契約 / 401 共通化 / camelCase / `extra="forbid"` / Pydantic→401→422 順序 / nested CardResponse / 5 ランクの round trip / `users.id` 削除での CASCADE / リポジトリ単体（`joinedload` / `card_exists` / `upsert_profile`） |

リポジトリの単体テストも Postgres 固有挙動（`joinedload`、FK CASCADE）を観測する必要があるため `tests/integration/` に同居する（`test_product_search.py` と同じ判断）。

## 6. マイグレーション

`alembic/versions/0003_user_profile_updated_at.py` は以下を実施:

1. `updated_at` カラムを `nullable=True` で追加
2. `UPDATE user_profiles SET updated_at = now() WHERE updated_at IS NULL` で backfill
3. `ALTER COLUMN updated_at SET NOT NULL` で確定
4. `user_id` FK を drop し、`ON DELETE CASCADE` 付きで再作成（PostgreSQL は `ondelete` のインプレース ALTER を持たないため）

3 ステップ分割は既存行の存在下でも安全に適用するため。テスト環境では fresh container なので 1 ステップで等価だが、本番運用での無停止適用を優先して分割する。
