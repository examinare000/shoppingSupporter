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
| `yahoo_premium` | boolean | NOT NULL (false) | Yahoo! プレミアム (LYP) 加入有無 |
| `default_card_id` | integer | FK(cards.id), NULL 許容 | 既定のクレジットカード |
| `updated_at` | datetime | NOT NULL | 更新日時 (Phase 1 で追加) |

- **カスケード**: `users.id` 削除時に紐づく `user_profiles` 行を自動削除する（`ON DELETE CASCADE`）。
- **updated_at**: Alembic マイグレーションにより新規追加し、`onupdate=datetime.utcnow` で自動更新を担保する。

### 2.2. ワイヤフォーマット (Enum)
- `RakutenRank` の Enum 値は Pydantic の既定挙動に従い、**value（小文字）** を JSON 表現として使用する（例: `"diamond"`）。

## 3. API 仕様

### 3.1. 取得 (GET /api/me/profile)
認証済みユーザー（`Depends(get_current_user)`）自身のプロファイルを取得する。未認証時は 401 を返却する。
- **レコード未作成時**: 404 ではなく **HTTP 200** を返却する。
    - 返却値はデフォルト値（`rakutenRank: "regular"`, all false, `defaultCardId: null`）とする。
    - `updated_at` にはリクエスト時点の日時（`YYYY-mm-dd HH:MM:SS` 形式）をセットして返す。
    - この時点では DB へのレコード作成は行わない。
- **レスポンス**: `UserProfileResponse` (camelCase)

### 3.2. 更新 (PUT /api/me/profile)
プロファイルを更新（または初回作成）する。認証必須。
- **更新セマンティクス**: **全フィールド必須の PUT (全置換)** に統一する。将来的に一部フィールドのみの更新が必要になった場合は PATCH エンドポイントを別途検討する。
- **バリデーション**:
    - `default_card_id` が指定された場合、リポジトリ層で `SELECT 1 FROM cards WHERE id=:id` を実行し、存在確認を行う。存在しない場合は **422 Unprocessable Entity** を返却する（DB の外部キー違反を待たずに検証する）。
- **エラーレスポンス**: 422 発生時は FastAPI 既定の `{"detail": [...]}` 形式で返却する。

### 3.3. スキーマ定義 (擬似コード)

```python
class UserProfileBase(BaseModel):
    rakuten_rank: RakutenRank  # JSON では小文字
    is_amazon_prime: bool
    yahoo_premium: bool
    default_card_id: Optional[int]

class UserProfileUpdate(UserProfileBase):
    # PUT 用: 全フィールド必須
    pass

class UserProfileResponse(UserProfileBase):
    updated_at: datetime
    
    class Config:
        alias_generator = to_camel
        populate_by_name = True
```

## 4. 実装上の留意点

### 4.1. リポジトリ層の責務
- `get_profile_by_user_id`: レコードがなければ `None` を返す（上位でデフォルト値に変換）。
- `upsert_profile`: `user_id` をキーに、存在すれば UPDATE、なければ INSERT を行う。

### 4.2. キャッシュ戦略
- **Phase 1**: パフォーマンス要件に基づき、検索ごとに DB 参照を行う。
- **将来検討**: JWT クレームへの情報埋め込みは、トークン肥大化や無効化の困難さ（`agent-rules/12-security-guidelines.md` 参照）のリスクがあるため、Phase 2 以降に必要性が生じた段階で別途 ADR を起票して比較検討する。

## 5. 関連タスク
- Phase 1 T-05: UserProfile API の実装
