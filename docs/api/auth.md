# 認証 API（JWT）

最終更新: 2026-05-06（T-03 実装反映）

`User` テーブルに対するサインアップ・ログインと、`Authorization: Bearer <JWT>` で認証済みユーザーを引く `/me` を提供する。ADR-007 で決定した「FastAPI 内発行のステートレス JWT」方針を最小実装したもの。

## 1. 構成

| レイヤー | ファイル | 責務 |
|---|---|---|
| HTTP 境界 | `api/routers/auth.py` | 入力バリデーションと HTTP レスポンス整形のみ |
| 共通基盤 | `api/common/security.py` | bcrypt / JWT / `Depends(get_current_user)` |
| 永続化 | `api/repositories/users.py` | `get_user_by_email` / `get_user_by_id` / `create_user` |
| スキーマ | `api/schemas.py` | `SignupRequest` / `LoginRequest` / `TokenResponse` / `UserResponse` |

`bcrypt` / `pyjwt` の import は `api/common/security.py` の 1 モジュールに閉じる。ルーター・リポジトリは公開関数経由でのみ認証操作を行う。

## 2. JWT 仕様

- アルゴリズム: `HS256`（ADR-007「秘密鍵 (`JWT_SECRET`) で署名を検証」に対応）
- 有効期限: 発行から 60 分（`ACCESS_TOKEN_EXPIRES_MINUTES`）。失効リスト等は持たず、期限切れによる自然失効に依る
- クレーム: `sub`（user id を string 化した UUID）/ `iat` / `exp`
- 署名鍵: 環境変数 `JWT_SECRET`。空文字も「未設定」として扱い `RuntimeError`
- 鍵の解決は遅延（モジュール import 時には raise しない）。`conftest.py` の `os.environ.setdefault("JWT_SECRET", ...)` がアプリ import より後に評価されるケースで誤って失敗しないようにする

## 3. パスワード

- ハッシュ化: bcrypt（`bcrypt.gensalt()` + `bcrypt.hashpw`）
- 最小長: 8 文字（`agent-rules/12-security-guidelines.md`「最小 8 文字以上」）。`SignupRequest` / `LoginRequest` の `Field(min_length=PASSWORD_MIN_LENGTH)` で 422 に変換
- 比較: `bcrypt.checkpw`。レスポンスや例外メッセージにハッシュを露出させない

## 4. エンドポイント

レスポンスは camelCase（`accessToken` / `tokenType` / `createdAt`）。SQLAlchemy / リポジトリ側は snake_case。`response_model_by_alias=True` で wire format を camelCase に固定する。

### 4.1. サインアップ `POST /api/auth/signup`

**Request body (`extra="forbid"`):**

```json
{ "email": "user@example.com", "password": "p@ssw0rd!" }
```

**Response (201 Created):**

```json
{ "id": "<uuid>", "email": "user@example.com", "createdAt": "2026-05-05T12:34:56Z" }
```

| ステータス | 条件 |
|---|---|
| `201` | 正常作成 |
| `409` | 既に登録済みの email（先行 SELECT で重複検出。`IntegrityError` 救済より状態競合の意味的表現を優先） |
| `422` | email が無効 / password が 8 文字未満 / 余計なフィールドが含まれる（`extra="forbid"`） |

`hashedPassword` 等の内部状態はレスポンスに含まれない。

### 4.2. ログイン `POST /api/auth/login`

**Request body (`extra="forbid"`):**

```json
{ "email": "user@example.com", "password": "p@ssw0rd!" }
```

**Response (200 OK):**

```json
{ "accessToken": "<jwt>", "tokenType": "bearer" }
```

| ステータス | 条件 |
|---|---|
| `200` | 認証成功 |
| `401` | 未登録 email / パスワード違い（**両者を区別しない共通メッセージ**） |
| `422` | バリデーション失敗（4.1 と同様） |

`tokenType` は OAuth2 慣習に合わせ常に `"bearer"`。`Authorization: Bearer <token>` の `Bearer ` スキームと一致させる責務はクライアント側にある。

### 4.3. 認証ユーザー取得 `GET /api/auth/me`

**Request header:**

```
Authorization: Bearer <jwt>
```

**Response (200 OK):** `UserResponse`（4.1 と同形）。

| ステータス | 条件 |
|---|---|
| `200` | 有効なトークン |
| `401` | ヘッダ欠落 / `Bearer` 以外のスキーム / 改ざん / 期限切れ / `sub` 不正 / sub に対応する User が存在しない |

## 5. 401 の正規化

`get_current_user` 経路で発生し得るすべての失敗は、`api/common/security.py` の `_unauthorized()` ヘルパが返す **同一の `(401, "Invalid credentials")` 応答** に集約する。login も未登録 email とパスワード違いを区別しない。

**理由**:

- ユーザー存在有無の漏洩防止（plan.md「内部詳細を露出しない」）
- 将来 `WWW-Authenticate: Bearer` を付与する／detail を構造化する等の変更を 1 箇所の修正で済ませる

## 6. テストレイヤー

| ファイル | 件数 | 観点 |
|---|---|---|
| `tests/unit/test_security.py` | 13 | hash 往復 / JWT round-trip / tampered / expired / 異なる秘密鍵 / `JWT_SECRET` 未設定で `RuntimeError` |
| `tests/integration/test_auth.py` | 27 | signup→login→/me の HTTP 契約 / 重複 409 / 401 共通化 / camelCase / `extra="forbid"` / Bearer ヘッダ解釈 |

## 7. 環境変数

`.env.example` に列挙済み:

```
# Auth (JWT / ADR-007)
JWT_SECRET=
```

本番では十分な長さのランダム値を使い、リポジトリには絶対に置かない（`agent-rules/12-security-guidelines.md`）。テスト環境では `tests/integration/conftest.py` で `os.environ.setdefault` 経由のプレースホルダを注入する。
