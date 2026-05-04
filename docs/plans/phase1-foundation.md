# Phase 1 実装計画: 基盤整備と UserProfile 連携

最終更新日: 2026-05-04（ADR-009 / T-01・T-02・T-07 完了反映）

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

各タスクは 1 ブランチ = 1 目的の単位（`agent-rules/10-git-strategy.md`）。並列着手可否と依存は「依存」欄を参照。状態欄は 2026-05-04 時点。

| ID | タスクゴール | 状態 | 依存 | 並列可 |
|----|--------------|------|------|--------|
| T-01 | Alembic 導入と初期マイグレーション | ✅ 完了（0001 初期 + 0002 検索カラム） | なし | ○ |
| T-02 | API テスト基盤（pytest + テスト用 DB）整備 | ✅ 完了（unit + integration / testcontainers Postgres） | なし | ○ |
| T-03 | JWT 最小認証の実装 | ⏳ 未着手 | T-01, T-02 | × |
| T-04 | `Card` マスタ API と初期シード | ⏳ 未着手 | T-01, T-02 | T-05 と並列可 |
| T-05 | `UserProfile` API（参照・更新） | ⏳ 未着手 | T-03 | T-04 と並列可 |
| T-06 | サイト別ポイント算出ロジックの純粋関数モジュール化 | ⏳ 未着手 | T-02 | T-04, T-05 と並列可 |
| T-07 | DB 主導の商品検索 API（匿名向け最小版） | ✅ 完了（FTS+trigram で当初予定よりリッチ。`/api/products/search`） | T-01, T-02 | T-06 と並列可 |
| T-08 | 検索 API への UserProfile / Card 統合 | ⏳ 未着手 | T-05, T-06, T-07 | × |
| T-09 | OpenAPI スキーマ公開と TypeScript 型生成パイプライン | ⏳ 未着手 | T-04〜T-08 のうち API 形が確定したもの | × |

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
- `pytest`, `pytest-asyncio`, `httpx`, `testcontainers` を `requirements-dev.txt` に追加。
- `tests/unit/` — 外部 API クライアント（Amazon PA-API 署名 / レスポンス処理）の単体テスト 48 件。
- `tests/integration/` — `update_prices` × `AmazonAPI` の結合 5 件と、`/api/products/search` 全 52 件（リポジトリ unit + エンドポイント integration）。
- `tests/integration/conftest.py` で testcontainers Postgres + Alembic 適用 + `app.dependency_overrides[get_db]` を提供。
- 当初予定していた SQLite in-memory 戦略は破棄（T-07 で FTS / pg_trgm / ARRAY を使うため Postgres 互換が必須になった）。

**完了条件**: 全 105 件の `pytest -q` が緑（integration は Docker 必須）。

---

### T-03. JWT 最小認証の実装

**なぜ**: `UserProfile` をユーザーに紐付けて返すには、リクエスト主体の特定が必要。ADR-007 で決定した JWT 方式を実装する。

**やること**:
1. **エンドポイント実装**:
   - `POST /api/auth/signup` — メアド + パスワード（bcrypt ハッシュ化）
   - `POST /api/auth/login` — 認証成功で JWT を返す
   - `GET /api/auth/me` — 認証ユーザー情報の確認
   - `Depends(get_current_user)` を `api/common/security.py` に切り出す
2. **シークレット管理**: `JWT_SECRET` を環境変数で受ける。`.env.example` を追加（`agent-rules/12-security-guidelines.md` 準拠でハードコード禁止）。なお `.env.example` への `JWT_SECRET` 列挙はドキュメント同期 PR で先行追加済み。

**完了条件**: signup → login → /me のテストが緑。誤パスワード時 401、未認証 /me で 401。

---

### T-04. `Card` マスタ API と初期シード

**なぜ**: `UserProfile.default_card_id` は `cards.id` を参照する FK のため、Card 行が無いと Profile を完成させられない。Phase 1 のポイント加算ロジックも Card の `special_rewards` を読む。

**やること**:
- `GET /api/cards`（一覧）と `GET /api/cards/{id}`（詳細）を実装。書き込み系は管理者専用に限定し、Phase 1 では起票のみ（実装は seed スクリプトで賄う）
- `api/common/seed/cards.py` に楽天カード / Amazon Mastercard / Yahoo! JAPAN カード / 一般 1% 還元カード の 4 件を投入
- `special_rewards` の JSON スキーマを `docs/api/cards.md` に記載（サイト名 → 倍率の dict）
- TDD: 一覧の並び・取得・404 を網羅

**完了条件**: シード後に `GET /api/cards` が 4 件返す。`special_rewards` の構造がドキュメントと一致する。

---

### T-05. `UserProfile` API（参照・更新）

**なぜ**: Phase 1 のゴールである「ユーザー個別の実質価格」を出すために、ユーザーが楽天ランク・Prime 加入・既定カードを登録できる必要がある。

**やること**:
- `GET /api/me/profile` — 認証ユーザーの Profile を返す。未作成ならデフォルト値（`REGULAR` / 全フラグ false / `default_card_id=null`）で返す
- `PUT /api/me/profile` — `rakuten_rank` / `is_amazon_prime` / `yahoo_premium` / `default_card_id` を更新（部分更新 or 全置換のどちらかに統一し、ADR-007 と整合させる）
- 入力バリデーション: `default_card_id` は `cards` に存在することを確認（外部キー違反より前に 422 で返す）
- TDD: 未認証 401 / 不正カード ID 422 / 正常更新の往復確認

**完了条件**: `PUT` 後に `GET` で同値が返る。401/422 が網羅される。

---

### T-06. サイト別ポイント算出ロジックの純粋関数モジュール化

**なぜ**: HTTP 層から切り離した純粋関数として書くことで、TDD でケースを大量に網羅できる。検索 API と単発の見積 API（将来の `POST /api/products/effective-price`）の両方から再利用したい。

**やること**:
- `api/lib/pricing/` を新設
  - `base_rates.py` — サイト別の基本還元率テーブル（Amazon 1%、楽天 1%、Yahoo! 1% など）
  - `rakuten_spu.py` — 楽天 SPU の段階加算（楽天カード 1%、楽天ゴールド 0.5%、Prime / Premium 等）
  - `yahoo_premium.py` — PayPay / プレミアム加算
  - `card_bonus.py` — `Card.special_rewards` を読んでサイト別倍率を引く
  - `effective_price.py` — `effective = max(0, price + shipping - points)` をバックエンド側で再実装
- 関数シグネチャは `(price: int, shipping: int, site: SiteType, profile: UserProfile | None, card: Card | None) -> Pricing` のように統一し、`Pricing = {points: int, effective_price: int, breakdown: list[Reward]}` を返す
- TDD: 各サイト × ランク × カード × Prime 有無のパラメタライズドテストを最低 12 ケース

**完了条件**: テーブル駆動 hostのテストが緑。`profile=None` のときフロントの `effectivePrice.ts` と同値になる回帰テストを 1 本以上含む。

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

**未着手の Phase 1 ギャップ**: 現在のレスポンスは `Product` 単体のサマリ（`ProductSummary`）のみで、`EcSiteProduct` / `Listing[]` の同梱は未実装。フロントが `types/product.ts` の `Listing` を要求する場面では T-08 と合わせてレスポンス形を再設計する。

**型不整合リスク**: フロント `Product` 型は `listings: Listing[]` を必須とするが、API `ProductSummary` には `listings` を含まない。さらに API は envelope `{items, page, totalPages, totalCount}` を返すのに対し、`searchClient` は `Product[]` 直返しを期待しており、現状の `/api/products/search` 結果はフロントで描画できない。T-08（Listing 同梱）と T-09（OpenAPI 型同期）でフロントクライアントを envelope 受け取りに修正する必要がある。

---

### T-08. 検索 API への UserProfile / Card 統合

**なぜ**: 「ユーザーごとの実質価格」を返すという Phase 1 の主目的を満たす最後のピース。匿名アクセス時のフォールバック挙動も同時に確定させる。

**やること**:
- `Depends(get_current_user_optional)` を新設し、未認証でも 200 を返す扱いにする
- 認証ありの場合は `UserProfile` と `default_card` を引いて T-06 の関数群へ渡し、各 `Listing` に `points` / `effectivePrice` / `breakdown` を載せる
- 認証なしの場合は `profile=None, card=None` でフォールバック計算（=現状フロントと同じ素の式）
- レスポンスに `personalization: { applied: bool, profile_summary?: ... }` を追加し、フロントの表示分岐を簡単にする
- TDD: 認証あり / なし両方で同じクエリの結果を比較し、`points` の差分が期待値どおりであること

**完了条件**: 楽天ダイヤモンド + 楽天カード保有ユーザーの楽天サイト商品で SPU 加算が反映される。匿名で同じリクエストを叩くと素の値に戻る。

---

### T-09. OpenAPI スキーマ公開と TypeScript 型生成

**なぜ**: ADR-005 の決定。フロント側の `Product` / `Listing` 型を手書きで二重管理すると、Phase 2 移行で必ず崩れる。Phase 1 の API 形が固まる T-08 直後に組み込み、CI で型ドリフトを検出できる状態にする。

**やること**:
- `api/main.py` で `openapi.json` のエクスポート手段を確立（FastAPI 既定の `/openapi.json` をそのまま使うか、ビルドスクリプターでファイル化）
- `frontend/package.json` に `openapi-typescript` を追加し、`npm run gen:api` で `frontend/types/api.ts` を生成
- `frontend/types/product.ts` のうちサーバ由来の型（`Product` / `Listing` など）は `api.ts` から再エクスポートする形に切替。`ImagePriority` / `SortKey` / `ResolvedImage` は手書きのまま残す
- CI（または `package.json` の `predev` / `pretest`）で再生成 → diff チェックを走らせ、型ドリフトを検知できるようにする
- ADR-005 の「OpenAPI 型同期」記述からのリンクを `docs/tech/api-type-sync.md`（新設）に追加

**完了条件**: `npm run gen:api` 実行後に `git status` がクリーン。`Product` / `Listing` の手書き定義が消えても `frontend/` のビルドが通る。

---

## ブリッジタスク（Phase 1 完了後すぐ着手）

これらは ADR-006 上は Phase 2 だが、Phase 1 の成果を腐らせないために連続で着手することを推奨する。本計画には含めず、Phase 2 計画起票時に細分化する。

- B-1. `frontend/lib/mock/searchClient.ts` の `Promise<Product[]>` 化と `app/page.tsx` の `useEffect` 化 — ✅ 完了（SWR を採用し fetch ベース化。`useEffect` ではなく SWR で扱う形に変更）
- B-2. `lib/mock/` をテストフィクスチャ専用に再配置（本番バンドルから除外） — 撤回（`frontend/lib/mock/` は既に削除済み）
- B-3. 検索レスポンスの envelope 形（`{items, page, totalPages, totalCount}`）とフロント `Product` 型の整合 — 未着手（T-08 / T-09 と歩調を合わせる）
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
| 検索 API の N+1 問題 | 商品 × 3 サイト × 価格履歴の eager load 不足 | T-07 の段階で `selectinload` を入れ、テストで SQL 発行回数を assert する（`sqlalchemy.event` で計測） |

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
