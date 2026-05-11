# 詳細設計: UserProfile API

ユーザーの属性情報（会員ランク、所有カード、加入サービス等）を管理し、パーソナライズされた計算の基盤となる UserProfile 機能の設計。

## 1. 概要
ユーザーごとに 1 つの `UserProfile` を保持する。ユーザーは自身の属性を API 経由で更新でき、その値は検索時のポイント計算に使用される。

## 2. データモデル

### 2.1. `user_profiles` テーブル
| カラム | 型 | 制約 | 説明 |
|---|---|---|---|
| `user_id` | UUID | PK, FK(users.id) ON DELETE CASCADE | ユーザー ID |
| `rakuten_rank` | Enum | NOT NULL | 楽天ランク (`regular`, `silver`, `gold`, `platinum`, `diamond`) |
| `is_amazon_prime` | boolean | NOT NULL (false) | Amazon Prime 加入有無 |
| `is_rakuten_mobile` | boolean | NOT NULL (false) | 楽天モバイル契約有無（SPU 判定用） |
| `yahoo_premium` | boolean | NOT NULL (false) | Yahoo! プレミアム (LYP) 加入有無 |
| `is_paypay_linked` | boolean | NOT NULL (false) | PayPay / LINE 連携有無（Yahoo! 特典判定用） |
| `default_card_id` | integer | FK(cards.id), NULL 許容 | 既定のクレジットカード |
| `updated_at` | datetime | NOT NULL | 更新日時 (Phase 1 で追加) |

- **カスケード**: `users.id` 削除時に紐づく `user_profiles` 行を自動削除する（`ON DELETE CASCADE`）。
- **updated_at**: Alembic マイグレーションにより新規追加し、`onupdate=datetime.utcnow` で自動更新を担保する。
- **マイグレーション手順**: 既存行への影響を避けるため、以下の 3 ステップで実施する。
    1. `nullable=True` で `updated_at` カラムを追加する。
    2. `UPDATE user_profiles SET updated_at = now() WHERE updated_at IS NULL` で backfill する。
    3. `ALTER COLUMN updated_at SET NOT NULL` を適用する。

### 2.2. ワイヤフォーマット (Enum)
- `RakutenRank` の Enum 値は Pydantic の既定挙動に従い、**value（小文字）** を JSON 表現として使用する（例: `"diamond"`）。

## 3. API 仕様

### 3.1. 取得 (GET /api/me/profile)
認証済みユーザー（`Depends(get_current_user)`）自身のプロファイルを取得する。未認証時は 401 を返却する。
- **レコード未作成時**: 404 ではなく **HTTP 200** を返却する。
    - 返却値はデフォルト値（`rakutenRank: "regular"`, all false, `defaultCardId: null`, `defaultCard: null`）とする。
    - `updatedAt` は **`null`** を返す（「未保存」と「保存済み」を区別するため。GET の冪等性も保つ）。
    - この時点では DB へのレコード作成は行わない。
- **日時のシリアライズ**: `updatedAt` は ISO 8601（既存 `UserResponse.createdAt` と同様、Pydantic `datetime` 既定挙動）で返却する。
- **レスポンス**: `UserProfileResponse` (camelCase)

### 3.2. 更新 (PUT /api/me/profile)
プロファイルを更新（または初回作成）する。認証必須。
- **更新セマンティクス**: **全フィールド必須の PUT (全置換)** に統一する。将来的に一部フィールドのみの更新が必要になった場合は PATCH エンドポイントを別途検討する。
- **`defaultCardId` の null 化**: `defaultCardId: null` の送信は許可し、**「カード未設定状態への戻し」** を意味する。422 にはしない。
- **バリデーション順序**: **(1) Pydantic（型・Enum 値・`extra="forbid"`）→ (2) ルーター層で認証（401）→ (3) リポジトリ層でカード存在確認（422）** の順に実施する。
- **`default_card_id` の存在確認**: 指定された場合、リポジトリ層で `SELECT 1 FROM cards WHERE id=:id` を実行する。存在しない場合は **422 Unprocessable Entity** を返却する（DB の外部キー違反を待たずに検証する）。
- **エラーレスポンス**: 422 発生時は FastAPI 既定の `{"detail": [...]}` 形式で返却する。
- **同時更新の扱い**: Phase 1 では **last-write-wins** とし、楽観ロックは実装しない。`updated_at` は将来 `If-Unmodified-Since` 等の楽観ロック種として使えるよう保持する。

### 3.3. スキーマ定義 (擬似コード)

既存 `api/schemas.py`（`SignupRequest` / `CardResponse` 等）の規約に揃え、Pydantic v2 の `ConfigDict` と `Field(serialization_alias=...)` の個別指定スタイルで記述する。`RakutenRank` は `api.common.models` から import する想定。

```python
from pydantic import BaseModel, ConfigDict, Field

class UserProfileUpdate(BaseModel):
    # 既存 SignupRequest と同じく、未知フィールドは 422 で弾く
    # (TokenResponse の流用やタイポを契約レベルで検出するため)
    model_config = ConfigDict(extra="forbid")

    rakuten_rank: RakutenRank
    is_amazon_prime: bool
    is_rakuten_mobile: bool
    yahoo_premium: bool
    is_paypay_linked: bool
    default_card_id: Optional[int]

class UserProfileResponse(BaseModel):
    # ORM の UserProfile 行をそのまま返却できるようにする
    # (リポジトリで joined load した結果を直接渡せる)
    model_config = ConfigDict(from_attributes=True)

    rakuten_rank: RakutenRank = Field(serialization_alias="rakutenRank")
    is_amazon_prime: bool = Field(serialization_alias="isAmazonPrime")
    is_rakuten_mobile: bool = Field(serialization_alias="isRakutenMobile")
    yahoo_premium: bool = Field(serialization_alias="yahooPremium")
    is_paypay_linked: bool = Field(serialization_alias="isPayPayLinked")
    default_card_id: Optional[int] = Field(serialization_alias="defaultCardId")
    # 検索パーソナライズ統合 (T-08) と方針を揃え、joined load で取得した
    # Card 情報を nested で返却する。フロント設定画面が ID から名前を引く
    # ための追加リクエストを不要にする。
    default_card: Optional[CardResponse] = Field(serialization_alias="defaultCard")
    # 未保存ユーザー (DB にレコードがない) の場合は null を返す。
    updated_at: Optional[datetime] = Field(serialization_alias="updatedAt")
```

### 3.4. 利用実績の統合 (Phase 3 拡張)
Phase 3 では、プロフィールページに「当月の利用実績」入力 UI を設ける。これに伴い、以下のエンドポイントを追加/拡張する。
- **`GET /api/me/usage`**: 当月のサイト別利用額・ポイント獲得状況を取得する。
- **`PUT /api/me/usage`**: 利用実績を更新する。プロフィール更新 (`PUT /api/me/profile`) とはエンドポイントを分離し、頻繁な更新（買い物直後の入力など）に対応する。

## 4. 実装上の留意点

### 4.1. リポジトリ層の責務
- `get_profile_by_user_id`: レコードがなければ `None` を返す（上位でデフォルト値に変換）。
- `upsert_profile`: `user_id` をキーに、存在すれば UPDATE、なければ INSERT を行う。

### 4.2. キャッシュ戦略
- **Phase 1**: パフォーマンス要件に基づき、検索ごとに DB 参照を行う。
- **将来検討**: JWT クレームへの情報埋め込みは、トークン肥大化や無効化の困難さ（`agent-rules/12-security-guidelines.md` 参照）のリスクがあるため、Phase 2 以降に必要性が生じた段階で別途 ADR を起票して比較検討する。

## 5. 関連タスク
- Phase 1 T-05: UserProfile API の実装（本仕様の対象）
- Phase 1 T-08: 検索 API への UserProfile / Card 統合（本仕様の下流。`UserProfileResponse` の構造は T-08 のレスポンスと整合させる）
