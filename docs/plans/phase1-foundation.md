# Phase 1 実装計画: 基盤整備と UserProfile 連携

最終更新日: 2026-05-06（T-05, T-06 完了反映）

## 位置づけ

本計画は ADR-006「高度な機能（還元率反映・履歴・予測）のロードマップ」のフェーズ 1（基盤整備と UserProfile 連携 / Backend First）を、ブランチ単位で着手可能なタスクゴールへ分解したもの。ADR-005「モック駆動フロントから実バックエンドへの移行戦略」で示された制約（DB 主導検索 / OpenAPI 型同期 / 実質価格計算はバックエンド主導）を前提とする。

**目的**: バックエンドで「ユーザー文脈付きの実質価格」を算出して返す土台を組み、フロントが SWR + fetch ベースの `searchClient` で安定して結果を描画できる状態を維持する（B-1 は当初プランの `useEffect` 化ではなく fetch + SWR で代替する形で完了済み）。

## スコープ

### 含む（Backend First）
- DB マイグレーション基盤（**Neon** 採用）と API 側テスト基盤
- 認証コンテキスト（**JWT** 採用）
- `Card` マスタおよび `UserProfile` 操作 API
- サイト別ポイント算出ロジック（SPU / Yahoo! プレミアム / カード加算）
- DB 主導の商品検索 API
- 検索結果へのユーザー個別実質価格の同梱
- OpenAPI から TypeScript 型を生成するパイプライン

### 含まない（Phase 2 以降に送る）
- フロント `searchClient` の `Promise` 化と `app/page.tsx` の非同期化（ブリッジタスクとして末尾に明記）
- 価格履歴チャート UI、価格予測ロジック
- 公式 API の本番キー取得・本番 Cron 化（既存スタブの動作で十分）

## 前提と決定事項

- **認証方式**: ADR-007 に基づき「FastAPI 内発行の JWT（ステートレス）」を採用。
- **データベース**: ADR-008 に基づき 「Neon (Serverless Postgres)」を採用。
- **バックエンド配置**: ADR-009 により `backend/` を廃止し、すべて `api/` 配下に統合。Alembic はリポジトリルート（`alembic/`）。テストは `tests/{unit,integration}/`。
- **全文検索**: 当初プランでは `ILIKE` 部分一致を予定していたが、T-07 着手時点で Postgres FTS（`tsvector` + `websearch_to_tsquery`）+ pg_trgm（trigram 類似度）を採用し、誤字耐性とランキングを両立する実装にスケールアップ済み。
- **ポイント円換算レート**: 楽天 1pt = 1 円、Amazon ポイント = 1 円、PayPay ポイント = 1 円を初期値として固定値で持つ（後続でマスタ化）。

## タスクゴール一覧

| ID | タスクゴール | 状態 | 依存 | 並列可 |
|----|--------------|------|------|--------|
| T-01 | Alembic 導入と初期マイグレーション | ✅ 完了 | なし | ○ |
| T-02 | API テスト基盤（pytest + テスト用 DB）整備 | ✅ 完了 | なし | ○ |
| T-03 | JWT 最小認証の実装 | ✅ 完了 | T-01, T-02 | × |
| T-04 | `Card` マスタ API と初期シード | ✅ 完了 | T-01, T-02 | T-05 と並列可 |
| T-05 | `UserProfile` API（参照・更新） | ✅ 完了 | T-03 | T-04 と並列可 |
| T-06 | サイト別ポイント算出ロジックの純粋関数モジュール化 | ✅ 完了 | T-02 | T-04, T-05 と並列可 |
| T-07 | DB 主導の商品検索 API（匿名向け最小版） | ✅ 完了 | T-01, T-02 | T-06 と並列可 |
| T-08 | 検索 API への UserProfile / Card 統合 | ✅ 完了 | T-05, T-06, T-07 | × |
| T-09 | OpenAPI スキーマ公開と TypeScript 型生成パイプライン | ✅ 完了 | T-04〜T-08 のうち API 形が確定したもの | × |

---

### T-01. Alembic 導入と初期マイグレーション ✅

**なぜ**: 現状 `api/main.py` の `Base.metadata.create_all` はコメントアウトされており、スキーマ変更が破壊的に効く。Phase 1 で `UserProfile` / `Card` 周りに手を入れるため、宣言的マイグレーションを先に立てる必要がある。

**実装結果**（ADR-009 で `backend/` から `api/` に統合済み）:
- `alembic.ini` と `alembic/` をリポジトリルートに配置（`script_location = alembic`）。`env.py` は `api.common.models.Base` を参照。
- `alembic/versions/0001_initial_schema.py` — 6 テーブル（users / cards / user_profiles / products / ec_site_products / price_histories）。
- `alembic/versions/0002_product_search_columns.py` — products の `tags` / `in_stock` / `current_price` / `search_vector`、`pg_trgm` 拡張、tsvector 維持トリガ、GIN/B-tree インデックス。
- `requirements-dev.txt` に `alembic` を追加（ランタイムでは不要）。
- `README.md` に Neon 直接接続での `alembic upgrade head` 手順を追記済み。

**運用**: スキーマ変更は **デプロイ前に** Neon に対して `alembic upgrade head` を実行する。Vercel Functions 起動時の自動 upgrade は行わない。

---

### T-02. API テスト基盤の整備 ✅

**なぜ**: 現状バックエンドにテストが存在せず、TDD（`agent-rules/11-testing-strategy.md`）を成立させられない。Phase 1 の検算系ロジックは TDD で進める前提のため、最初に枠を作る。

**実装結果**:
- `pytest`, `pytest-asyncio`, `httpx`, `testcontainers` を `requirements-dev.txt` に追加.
- `tests/unit/` — 外部 API クライアント（Amazon PA-API 署名 / レスポンス処理）の単体テスト 48 件.
- `tests/integration/` — `update_prices` × `AmazonAPI` の結合 5 件と、`/api/products/search` 全 52 件（リポジトリ unit + エンドポイント integration）.
- `tests/integration/conftest.py` で testcontainers Postgres + Alembic 適用 + `app.dependency_overrides[get_db]` を提供.
- 当初予定していた SQLite in-memory 戦略は破棄（T-07 で FTS / pg_trgm / ARRAY を使うため Postgres 互換が必須になった）.

**完了条件**: 全 105 件の `pytest -q` が緑（integration は Docker 必須）.

---

### T-03. JWT 最小認証の実装 ✅

**なぜ**: `UserProfile` をユーザーに紐付けて返すには、リクエスト主体の特定が必要。ADR-007 で決定した JWT 方式を実装する。

**実装結果**:
- `api/routers/auth.py` を新設し `POST /api/auth/signup` / `POST /api/auth/login` / `GET /api/auth/me` を実装。`api/main.py` で include。
- `api/common/security.py` に bcrypt（`hash_password` / `verify_password`）と JWT（HS256 / 60 分有効期限の `create_access_token` / `decode_access_token`）、および `Depends(get_current_user)` を集約。`bcrypt` / `pyjwt` の import は this 1 module に閉じる。
- `api/repositories/users.py` で `get_user_by_email` / `get_user_by_id` / `create_user` を実装。ルーターは ORM を直接触らない。
- `api/schemas.py` に `SignupRequest` / `LoginRequest` / `TokenResponse` / `UserResponse` を追加。レスポンスは camelCase（`accessToken` / `tokenType` / `createdAt`）、`response_model_by_alias=True` で配信。`SignupRequest` / `LoginRequest` は `extra="forbid"` で envelope 形（`accessToken` 等）の流用を 422 で弾く。
- 401 の正規化: `get_current_user` 経由の失敗（ヘッダ欠落・スキーム違い・改ざん・期限切れ・sub 不正・ユーザー不在）はすべて `INVALID_CREDENTIALS_MESSAGE` の 401 に集約。login も未登録 email とパスワード違いを区別せず同一 401 を返す（ユーザー存在有無の漏洩防止）。
- 重複 email は signup 側で先行 SELECT して 409（IntegrityError 救済より状態競合の意味的表現を優先）。
- `JWT_SECRET` は `_get_jwt_secret()` で遅延参照（モジュール import 時に raise しないことで conftest の `setdefault` 注入順序と両立）。空文字も「未設定」として `RuntimeError`。
- 依存追加: `pyjwt` / `bcrypt` / `email-validator` を `requirements.txt` に追加。
- 仕様の正本: `docs/api/auth.md`（contract と 401 共通化の意図、テスト観点を集約）。`docs/api/backend-spec.md` §2.6 に Auth 節を追加。
- TDD: `tests/unit/test_security.py` 13 件（hash 往復 / JWT round-trip / tampered / expired / fail-fast）と `tests/integration/test_auth.py` 27 件（signup→login→/me の HTTP 契約 / 重複 409 / 401 共通化 / camelCase）。全 162 件の `pytest -q` 緑。

**完了条件**: signup → login → /me のテストが緑。誤パスワード時 401、未認証 /me で 401。

---

### T-04. `Card` マスタ API と初期シード ✅

**なぜ**: `UserProfile.default_card_id` は `cards.id` を参照する FK のため、Card 行が無いと Profile を完成させられない。Phase 1 のポイント加算ロジックも Card の `special_rewards` を読む。

**実装結果**:
- `api/routers/cards.py` を新設し `GET /api/cards`（一覧）と `GET /api/cards/{id}`（詳細）を実装。`api/main.py` で include。
- レスポンスは camelCase（`baseRewardRate` / `annualFee` / `specialRewards`）。`api/schemas.py` に `CardResponse` を追加し `response_model_by_alias=True` で配信。
- 一覧は bare array（envelope なし）、`id ASC` 固定。詳細は存在しない id で 404、非整数 id で 422。
- 認証不要（公開）。書き込み系は Phase 1 では実装せず、行の投入は `python -m api.common.seed.cards` で行う。
- `api/common/seed/cards.py` に `CARDS_SEED_DATA`（楽天カード / Amazon Mastercard / Yahoo! JAPAN カード / 一般 1% 還元カード）と `seed_cards(db)` を実装。`cards` テーブルが空のときのみ 4 件投入する冪等な実装（`name` ユニーク制約はスキーマ変更を伴うためスコープ外）。
- `docs/api/cards.md` に `special_rewards` の JSON スキーマと初期 4 件の設定根拠、投入手順を記載。`docs/api/backend-spec.md` §2.5 に Cards 節を追加。
- TDD: `tests/integration/test_cards.py` で 17 件（一覧の並び・空配列・camelCase 完全一致 / 詳細の 200・404・422 / 公開エンドポイント / seed の冪等性・名称一致）。全 122 件の `pytest -q` 緑。

**完了条件**: シード後に `GET /api/cards` が 4 件返す。`special_rewards` の構造がドキュメントと一致する。

---

### T-05. `UserProfile` API（参照・更新） ✅

**なぜ**: Phase 1 のゴールである「ユーザー個別の実質価格」を出すために、ユーザーが楽天ランク・Prime 加入・既定カードを登録できる必要がある。

**実装結果**:
- `api/routers/profile.py` および `api/repositories/user_profiles.py` を実装。
- `GET /api/me/profile` — 認証ユーザーの Profile を返す。未作成なら 200 OK でデフォルト値（`regular` / 全フラグ false / `default_card_id=null`）を返す。
- `PUT /api/me/profile` — `rakuten_rank` / `is_amazon_prime` / `yahoo_premium` / `is_rakuten_mobile` / `is_paypay_linked` / `default_card_id` を一括更新。全フィールド必須。
- 入力バリデーション: `default_card_id` の存在確認をリポジトリ層で行い、存在しない場合は 422 を返す。
- 順序制御: バリデーション順序（Pydantic -> 認証 401 -> カード存在 422）を維持するため、`Header(default=None)` でトークンを受け取り手動で `get_current_user` を呼ぶ実装を採用。
- TDD: `tests/integration/test_profile.py` 18 件（GET/PUT 往復、未認証 401、不正カード 422、default_card の joinedload 返却等）が緑。

**完了条件**: `PUT` 後に `GET` で同値が返る。401/422 が網羅される。`updated_at` が正しく更新される。

---

### T-06. サイト別ポイント算出ロジックの純粋関数モジュール化 ✅

**なぜ**: HTTP 層から切り離した純粋関数として書くことで、TDD でケースを大量に網羅できる。検索 API と単発の見積 API（将来の `POST /api/products/effective-price`）の両方から再利用したい。

**実装結果**:
- `api/lib/pricing/engine.py` を実装。
- Amazon, 楽天, Yahoo! ショッピングそれぞれのポイント算出ロジックを独立した関数（`calculate_points_amazon` 等）として定義。
- `UserContext` データクラスを介してユーザー属性（Prime 有無、モバイル契約、PayPay 連携等）を渡し、倍率加算をシミュレートする。
- 算出結果は `PricingResult`（総ポイント、実質価格、計算内訳 `breakdown`）として返す。
- TDD: `tests/unit/pricing/test_engine.py` 14 件。楽天ダイヤモンド、Amazon プライム + Mastercard、Yahoo! プレミアム等、主要な組み合わせを網羅。フロントエンドの `effectivePrice.ts` との回帰テストも含む。

**完了条件**: テーブル駆動テストが緑。`profile=None` のときフロントの `effectivePrice.ts` と同値になる回帰テストを 1 本以上含む。

---

### T-07. DB 主導の商品検索 API（匿名向け最小版） ✅

**なぜ**: ADR-005 の決定により、検索のクリティカルパスは DB に閉じる。フロントの `searchProducts(query)` の置き換え先となる API がまず必要。Phase 1 ではユーザー文脈なしのレスポンスを先に確定させ、T-08 で個別化を重ねる。

**実装結果**（当初予定よりリッチなマッチングを採用）:
- `GET /api/products/search` を実装。実装は `api/routers/products.py` + `api/repositories/products.py`。仕様の正本は `docs/api/backend-spec.md`。
- マッチング: 当初予定の `ILIKE` ではなく、Postgres FTS（`tsvector` + `websearch_to_tsquery`）と pg_trgm（trigram 類似度）の OR 合算。`name` / `description` / `tags` を結合した検索対象に対して FTS と trigram の両方をかけ、relevance ランクは `ts_rank + similarity` で合算する。
- クエリパラメタ: `q`（必須・1〜100 文字）/ `inStock` / `priceMin` / `priceMax` / `sort` / `page`。
- レスポンス: `{items, page, totalPages, totalCount}` のエンベロープ形。`items` は camelCase（`imageUrl` / `inStock` / `currentPrice`）。
- 入力エラーは 200+空配列ではなく 422（`q` 欠落・空・101 文字以上、`priceMin > priceMax`、非数 / 負数、不正な `sort`、`page` ≤ 0 など）。
- TDD: 105 件中 52 件が本機能のテスト（FTS / trigram / フィルタ / ソート / ページング / 422 / クエリストリング契約）。

**型不整合リスク（解消済み）**: T-09 にて `frontend/types/api.ts` を OpenAPI スキーマから自動生成し、`searchClient.ts` を `ProductSearchEnvelope`（`{items, page, totalPages, totalCount, meta}`）形式に修正済み。フロント `Product` 型は `api.ts` からの再エクスポートに移行し、手書き二重管理は解消された。

---

### T-08. 検索 API への UserProfile / Card 統合 ✅

**なぜ**: 「ユーザーごとの実質価格」を返すという Phase 1 の主目的を満たす最後のピース。匿名アクセス時のフォールバック挙動も同時に確定させる。

**実装結果**:
- `Depends(get_current_user_optional)` を使用し、未認証でも 200 を返すように実装。
- 認証ありの場合は `UserProfile` と `default_card` を引いて T-06 の関数群へ渡し、各 `Listing` に `points` / `effectivePrice` / `breakdown` を載せて返す。
- 認証なしの場合は `points` / `effectivePrice` / `breakdown` を `null` で返す（T-08 設計方針）。
- レスポンスの `meta` フィールドに `personalization: { applied: bool, rakutenRank?: string, hasCard: bool }` を追加。
- TDD: `tests/integration/test_product_search.py` にて認証あり/なし、プロフィール有無、カード有無の全パターンを網羅。

---

### T-09. OpenAPI スキーマ公開と TypeScript 型生成 ✅

**なぜ**: ADR-005 の決定。フロント側の `Product` / `Listing` 型を手書きで二重管理すると、Phase 2 移行で必ず崩れる。Phase 1 の API 形が固まる T-08 直後に組み込み、型ドリフトを検出できる状態にする。

**実装結果**:
- FastAPI の `/openapi.json` エンドポイントをそのまま利用（`api/main.py` のデフォルト動作）
- `frontend/package.json` に `openapi-typescript@^7.13.0` を追加し、`npm run gen:api` で `frontend/types/api.ts` を生成（700 行超の完全な型定義）
- `npm run check:api-types` スクリプトを整備：再生成 → `git diff --exit-code` で型ドリフトを検知（手元実行ベース）
- `frontend/types/product.ts` のサーバ由来型（`Product` / `Listing` など）を `api.ts` からの再エクスポート形式に切替。`ImagePriority` / `SortKey` / `ResolvedImage` は手書きのまま残す。フロント 27 ファイルの型参照を更新
- `searchClient.ts` を `ProductSearchEnvelope`（`{items, page, totalPages, totalCount, meta}`）形式に修正し、envelope 直返しに対応
- `docs/tech/api-type-sync.md` を新設し、型同期フローとコマンドリファレンスを文書化

**残件**: `.github/workflows/` への `check:api-types` 統合（CI 自動化）。現状は開発者の手元実行で運用。

---

## ブリッジタスク（Phase 1 完了後すぐ着手）

これらは ADR-006 上は Phase 2 だが、Phase 1 の成果を腐らせないために連続で着手することを推奨する。本計画には含めず、Phase 2 計画起票時に細分化する。

- B-1. `frontend/lib/mock/searchClient.ts` の `Promise<Product[]>` 化と `app/page.tsx` の `useEffect` 化 — ✅ 完了（SWR を採用し fetch ベース化。`useEffect` ではなく SWR で扱う形に変更）
- B-2. `lib/mock/` をテストフィクスチャ専用に再配置（本番バンドルから除外） — 撤回（`frontend/lib/mock/` は既に削除済み）
- B-3. 検索レスポンスの envelope 形（`{items, page, totalPages, totalCount}`）とフロント `Product` 型の整合 — ✅ 完了（T-09 にて `searchClient.ts` を `ProductSearchEnvelope` 形式に修正、型は `api.ts` から参照）
- B-4. ゲスト → ログイン後の表示切り替え UX（ADR-006「影響」節）

## 依存グラフ（要約）

```
T-01 ──┐
        ├──► T-04 ──┐
T-02 ──┤            ├──► T-08 ──► T-09
        ├──► T-05 ──┤
        ├──► T-06 ──┘
        └──► T-07 ──┘
T-03 ──► T-05
```

T-04 / T-05 / T-06 / T-07 は依存解消後に並列着手可能。サブエージェント協調モード（`agent-rules/91-claude-subagent-coding.md`）で分担しやすい構造を意識した。

## リスクと対応

| リスク | 兆候 | 対応 |
|--------|------|------|
| 認証 ADR の決定が長引き Phase 1 全体が止まる | T-03 で議論が分岐 | T-03 を「ADR 起票だけ」と「最小実装」に分割し、最小実装は ADR の暫定結論で先行可能にする |
| 楽天 SPU の倍率定義が変動して T-06 のテストが頻繁に壊れる | 倍率テーブルがハードコードされている | `api/lib/pricing/base_rates.py` をデータクラスに閉じ込め、将来 DB / 設定ファイル化できる構造にする |
| OpenAPI 生成の差分検知が CI コストを上げる | 生成 diff が CI で頻繁に出る | T-09 で `npm run gen:api -- --check` 形式の差分チェックモードを用意し、生成自体は開発者の手元で行う運用にする |
| 検索 API の N+1 問題 | 商品 × 3 サイト × 価格履歴の eager load 不足 | T-07 の段階で `selectinload` 入れ、テストで SQL 発行回数を assert する（`sqlalchemy.event` で計測） |

## 受け入れ基準（Phase 1 全体）

- 楽天ダイヤモンド + 楽天カード保有ユーザーが `GET /api/products/search?q=...` を叩くと、楽天サイトの listing で SPU 加算が反映された `points` / `effectivePrice` が返る
- 同じクエリを匿名で叩くと、フロントの `lib/pricing/effectivePrice.ts` と同値の素の計算結果が返る
- `alembic upgrade head` だけで空 DB から Phase 1 のスキーマが組み上がる
- バックエンドのテストカバレッジが `api/lib/pricing/` で 90% 以上、認証 / Profile / 検索の各エンドポイントで主要パスが緑
- フロント度は `frontend/types/api.ts`（生成物）を経由してサーバ由来の型を参照する状態になっている

## 関連ドキュメント

- `docs/adr/005-mock-to-backend-migration.md`
- `docs/adr/006-advanced-features-roadmap.md`
- `agent-rules/10-git-strategy.md`（ブランチ・コミット粒度）
- `agent-rules/11-testing-strategy.md`（TDD 実践）
- `agent-rules/12-security-guidelines.md`（シークレット・入力検証）
- `agent-rules/30-documentation-management.md`（ドキュメント配置規約）
