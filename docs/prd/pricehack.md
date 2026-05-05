# pricehack 製品要件定義書（プロダクト PRD）

最終更新: 2026-05-05（初版）

> 本ドキュメントはプロダクト全体の要件定義の **傘** となる文書。機能単位の詳細仕様は `docs/prd/price-comparison.md`（実質価格比較）と `docs/prd/suggestion-engine.md`（最適購買サジェスト）に委ねる。

## 1. プロダクト概要

### 1.1. ビジョン

**Where To Buy That?** ──「どこで買えばいいか」を、**送料・ポイント・会員ステータスを含めた本当の安さ** で即答するためのツール。表示価格だけでは判断できない複雑な計算を代行し、ユーザーが最小コストで最適な購入決定を行える状態をつくる。

ドメイン: `pricehack.net`。

### 1.2. 解決する課題

現代の EC 比較において、ユーザーは以下の複数次元を頭の中で同時計算しないと「本当の最安」が分からない:

| 次元 | 例 |
|---|---|
| 表示価格 | 同じ商品でも Amazon / 楽天 / Yahoo で異なる |
| 送料 | サイト・店舗・購入金額条件で変動 |
| 還元率（属性依存） | 楽天ランク / Amazon Prime / LYP / 所有カード |
| 還元率（実績依存） | お買い物マラソン上限 7,000pt 等、当月利用状況で実効値が変わる |
| 時間軸 | セール直前なら待つ価値があるか |

本プロダクトはこれを **「真の実質価格」** と **「今買う / 待つ」のサジェスト** という 2 つの出力に集約する。

### 1.3. 想定ユーザー

- **コア**: Amazon / 楽天 / Yahoo を併用しており、ポイント・送料・キャンペーン上限まで意識して買い物する個人
- **拡張**: 比較は面倒で諦めていたが「正解だけ見たい」ライト層

### 1.4. 競合との差別化

- **「真の還元率」算出**: 単なる名目還元率ではなく、上限到達状況を反映した「次の 1 円で実際に得られる」率を示す
- **エディトリアルデザイン**: バナーで埋め尽くされた既存比較サイトとは対照的に、新聞 / 雑誌的な落ち着いた紙面（ADR-004）
- **算出根拠の透明性**: ML ブラックボックスではなく、ルールベースの `breakdown` をユーザーが検証できる

## 2. アーキテクチャ概観

詳細は `docs/tech/system-design.md` および ADR 群（`docs/adr/`）参照。本 PRD では要件に直接効く決定のみ列挙する。

| レイヤー | 採用技術 | 出典 |
|---|---|---|
| Frontend | Next.js 14 App Router + Tailwind CSS、SWR + fetch | ADR-004 / ADR-005 |
| Backend | FastAPI on Vercel Functions（`api/` 集約） | ADR-002 / ADR-009 |
| DB | PostgreSQL on Neon（Serverless / pooler） | ADR-008 |
| Migrations | Alembic（リポジトリルート、CI / 手動 upgrade） | ADR-009 |
| Data Source | Amazon PA-API / 楽天商品検索 API / Yahoo! ショッピング API | ADR-003 |
| Auth | FastAPI 内発行の JWT（HS256・60 分） | ADR-007 |
| Schedule | Vercel Cron Jobs | ADR-002 |

**追加のホスティング層は持たない**（Scraping Worker や ML Server を新設しない方針）。

## 3. 機能スコープ

3 段階に分けて整理する。各機能は本 PRD では概観のみ示し、詳細は機能別 PRD と `docs/plans/phase1-foundation.md` を正本とする。

### 3.1. 実装済機能（Released）

| # | 機能 | 概要 | 主な実装場所 | 状態 |
|---|---|---|---|---|
| F-01 | エディトリアル UI（ヒーロー検索） | 紙面メタファのトップページ・SearchForm・装飾コンポーネント | `frontend/components/{branding,editorial,search}/` | ✅ |
| F-02 | 商品検索 API（匿名・envelope 形） | `GET /api/products/search`。Postgres FTS（`tsvector` + `websearch_to_tsquery`）+ pg_trgm の OR 合算でランキング。`q` / `inStock` / `priceMin` / `priceMax` / `sort` / `page` を受け、`{items, page, totalPages, totalCount}` を返す。422 系のバリデーション網羅 | `api/routers/products.py` / `api/repositories/products.py` | ✅ |
| F-03 | 検索結果フロント描画 | SWR + fetch でバックエンド検索を呼び、ローディング / エラー UI を切替 | `frontend/lib/api/searchClient.ts` / `components/feedback/` | ✅ |
| F-04 | 商品ドシエ表示・出品行ソート | 出品（`Listing[]`）の実質価格 / 価格 / 還元率による並び替え | `frontend/components/search/{ProductDossier,SortControl,ListingRow}.tsx` / `frontend/lib/pricing/` | ✅ |
| F-05 | 画像取得優先度 | 各商品の画像をサイト優先度に応じて解決し、`localStorage` に永続化（SSR ハイドレーション不一致を回避） | `frontend/components/settings/ImagePriorityControl.tsx` / `lib/hooks/useImagePriority.ts` / `lib/image/` | ✅ |
| F-06 | DB スキーマ基盤 | 6 テーブル（users / cards / user_profiles / products / ec_site_products / price_histories）と検索カラム / pg_trgm 拡張 / GIN インデックス / TSVECTOR トリガ | `alembic/versions/0001_*` / `0002_*` | ✅ |
| F-07 | 価格更新 Cron | Vercel Cron（毎時）で各 `EcSiteProduct` を Amazon PA-API / 楽天 API / Yahoo API から更新し `PriceHistory` に追記 | `api/cron/update_prices.py` / `api/lib/{amazon,rakuten,yahoo,aws_sigv4}.py` | ✅ |
| F-08 | JWT 認証（signup / login / me） | `POST /api/auth/signup`（重複 409）/ `POST /api/auth/login`（401 共通化）/ `GET /api/auth/me`（Bearer 必須）。bcrypt + HS256 / 60 分。`extra="forbid"` でリクエスト検証強化 | `api/routers/auth.py` / `api/common/security.py` / `api/repositories/users.py` | ✅ |
| F-09 | カードマスタ API | `GET /api/cards`（bare array / `id ASC`）/ `GET /api/cards/{id}`（404 / 422）。`special_rewards` を `{site: rate}` で構造化。初期 4 件の seed と冪等投入スクリプト | `api/routers/cards.py` / `api/common/seed/cards.py` | ✅ |
| F-10 | API 契約のドキュメント正本 | `docs/api/{backend-spec,auth,cards}.md` を契約の出典に。OpenAPI 自動生成（T-09）までの繋ぎ | `docs/api/` | ✅ |
| F-11 | テスト基盤 | unit + integration の 2 段。integration は testcontainers で実 Postgres を立て、`alembic upgrade head` を適用してから `app.dependency_overrides[get_db]` で注入。auth / cards / search / cron / 外部 API クライアント / security を網羅。総数 162 件 | `tests/{unit,integration}/` | ✅ |

実装済機能の API 契約は `docs/api/backend-spec.md`、フロント挙動は `docs/tech/system-design.md` を参照。

### 3.2. 進行中（Phase 1 残）

`docs/plans/phase1-foundation.md` の T-05 / T-06 / T-08 / T-09 が該当。

| # | 機能 | 概要 | 関連タスク |
|---|---|---|---|
| F-12 | UserProfile API | 楽天ランク / Prime / LYP（yahoo_premium）/ デフォルトカードの参照・更新（`GET / PUT /api/me/profile`） | T-05 |
| F-13 | ポイント算出純粋関数 | `api/lib/pricing/`。サイト × ランク × カード × Prime × LYP の組み合わせで還元率と実質価格を算出。テーブル駆動テストで網羅 | T-06 |
| F-14 | 検索 API へのパーソナライズ統合 | `Depends(get_current_user_optional)` を導入し、認証ありで `Listing` に `points` / `effectivePrice` / `breakdown` を載せる。匿名でも 200 を返しフォールバック | T-08 |
| F-15 | OpenAPI → TS 型生成 | `frontend/types/api.ts` を `openapi-typescript` で生成し、CI で diff ガード | T-09 |

### 3.3. 計画中（Phase 2 以降）

ADR-006 のロードマップに沿う。

| # | 機能 | フェーズ | 詳細出典 |
|---|---|---|---|
| F-16 | 価格履歴 API | Phase 2 | ADR-006 |
| F-17 | 価格推移チャート（紙面トーンの単色ミニマル） | Phase 2 | ADR-006 |
| F-18 | セールカレンダー（`sale_campaigns` マスタ） | Phase 3-a | `docs/prd/suggestion-engine.md` |
| F-19 | 利用実績の手動入力 + 真の還元率 | Phase 3-a | `docs/prd/suggestion-engine.md` |
| F-20 | 「今買う / 待つ」サジェスト（移動平均 + カレンダー） | Phase 3-b | `docs/prd/suggestion-engine.md` |
| F-21 | 利用実績の自動取得（公式 API / 拡張機能 / メール解析のいずれか） | Phase 4（要 ADR） | `docs/prd/suggestion-engine.md` § 1.2 |

## 4. 機能別 PRD への参照

本 PRD は傘文書のため、要件レベルの詳細は以下に委ねる。**矛盾時は機能別 PRD を優先**。

| 範囲 | 文書 |
|---|---|
| 単一商品の実質価格比較（F-01〜F-15 の大半） | `docs/prd/price-comparison.md` |
| 「今買う / 待つ」サジェスト・真の還元率（F-18〜F-20） | `docs/prd/suggestion-engine.md` |

## 5. 非機能要件

### 5.1. デザイン性（Editorial Design）

ADR-004 の決定どおり、新聞 / 雑誌的な紙面メタファを採用する。バナーで賑わせず、活字の美しさと情報の読みやすさを最優先する。

- フォント: Fraunces / Newsreader / JetBrains Mono
- カラー: 紙色 / 濃インク / 罫線 / 朱赤・芥子色アクセント
- 紙の質感は SVG `fractalNoise` で全画面に薄く敷く

### 5.2. パフォーマンス

- **コールドスタート**: Vercel Functions の Python ランタイム制約に合わせ、`requirements.txt` を必要最小限に保つ（dev 依存は `requirements-dev.txt` に分離）
- **検索クリティカルパス**: 公式 API の遅延をユーザーに見せない。検索は **DB キャッシュ前提**（Cron 主導で価格を更新）
- **検索 API 目標**: p95 で 500ms 以内（実装後計測）
- **サジェスト API 目標**: p95 で 500ms 以内（同期 / 単一商品単位）

### 5.3. セキュリティ

- **クレデンシャル管理**: `JWT_SECRET` / 各種 API キーは環境変数のみ。リポジトリには `.env.example` でキー名のみ列挙
- **EC サイトのユーザークレデンシャル**: 預からない（一時保持も含めて行わない）。利用実績は自己申告 or 規約適合の自動取得（Phase 4 / 別 ADR）
- **JWT**: HS256 / 60 分有効期限 / 失効リスト持たず期限切れに依る
- **401 の正規化**: ヘッダ欠落 / 改ざん / 期限切れ / sub 不在をすべて同一 401 にし、内部状態を露出させない（`docs/api/auth.md`）
- **入力検証**: Pydantic `extra="forbid"` で envelope 形のリクエスト流用を 422 で弾く

### 5.4. 正確性

- **還元ルール**: SPU / Premium / カード加算を最新仕様に追従。`sale_campaigns.verified_at` の 90 日ルールで運用劣化を検知
- **算出根拠の検証可能性**: `breakdown` を構造化で返し、UI で展開可能にする
- **ポイント円換算レート**: 楽天 1pt = 1 円、Amazon ポイント = 1 円、PayPay ポイント = 1 円を初期固定。後続でマスタ化可能な構造に閉じ込める

### 5.5. インフラ

- **デプロイ単位は一つ**（Vercel Functions に集約）。専用 Worker / ML Server を新設しない
- **DB マイグレーション**: Vercel 起動時 auto-upgrade は廃止。デプロイ前に CI / 手動で `alembic upgrade head`（ADR-009）
- **Neon ブランチ機能**: PR ごとに DB 環境を切り出せる前提。テストは pooler なしの直接接続を推奨

### 5.6. テスト戦略

- **TDD**: t-wada 方針。実装より先にテストを書く（`agent-rules/11-testing-strategy.md`）
- **ユニット**: 純粋関数 / 外部 API クライアント / セキュリティ基盤
- **インテグレーション**: testcontainers Postgres + `alembic upgrade head` + `app.dependency_overrides[get_db]`
- **テスト自体を仕様書として保守**（カバレッジは副産物）

### 5.7. 型同期

- Phase 1 完了時に `frontend/types/api.ts` を OpenAPI から自動生成（F-15 / T-09）
- それ以前は `docs/api/*.md` を契約の正本として、フロント手書き型と整合させる

### 5.8. アクセシビリティ

- `prefers-reduced-motion: reduce` で全アニメーションを実質無効化
- セマンティック HTML（`h1` / `main` / `section` 等）を `editorial/` コンポーネントで担保

## 6. 利用シナリオ（受け入れ基準のスナップショット）

詳細な受け入れ基準は機能別 PRD を参照。本セクションは **プロダクト全体として外せない動線** を 5 つに絞る。

| # | シナリオ | 期待 |
|---|---|---|
| S-01 | ゲストが商品を検索する | デフォルト還元率（1%）に基づく実質価格を含む結果が表示される |
| S-02 | ユーザーがサインアップ → ログイン → /me を呼ぶ | 201 → 200（JWT 取得） → 200（自分の `id` / `email` / `createdAt`）が camelCase で返る |
| S-03 | ログイン済みユーザーが楽天ダイヤモンド + 楽天カード保有を Profile に登録して検索 | 楽天サイト出品で SPU + カード加算が反映された高めの還元率と、それに基づく実質価格が表示される（F-12〜F-14 完了後） |
| S-04 | ユーザーが画像優先度を「Amazon 優先」に並び替える | 各商品で Amazon の画像があればメイン表示。設定はリロード後も保持 |
| S-05 | 楽天マラソン上限 7,000pt 到達済のユーザーが楽天商品の suggestion を見る | `cap_status = capped`、還元率は基本まで低下、`breakdown` で「marathon: capped」を確認できる（Phase 3-a 完了後） |

## 7. スコープ外（明示的に行わないこと）

- **EC サイトへの代理ログイン / クレデンシャル預かり**（規約 / 法務 / セキュリティの三重リスク。ADR-003 / `suggestion-engine.md` § 1）
- **Playwright 等によるスクレイピング**（ADR-003 で公式 API 縛り）
- **ML による価格予測（Phase 3-b 時点）**: 透明性を犠牲にしないため、ルールベース（移動平均 + セールカレンダー）から開始（ADR-006）
- **コンテナ運用 / 専用 ML Server**: ADR-002 / ADR-009 で Vercel + Neon に集約済み
- **複数商品のバスケット最適化**（楽天マラソン 10 店舗回遊の組み立て等）: Phase 4 以降の検討事項
- **楽天 SPU サブプログラムの個別最適化**（楽天モバイル契約推奨など、ライフスタイル変更を伴う提案）
- **ポイント円換算レートの動的化**: 初期は固定値で実装

## 8. 成功指標

定量指標は Phase 1 完了後の本番運用開始から計測する。本 PRD では **設計時に意識すべき North Star** を示すに留める。

- **「真の実質価格」が表示価格より低い結果を返したセッション割合**（差別化が機能している証跡）
- **suggestion 提示後の「今買う」/「待つ」割合の分布**（過度に「待つ」に寄ると UX 問題）
- **`breakdown` 展開率**（透明性が UX に効いているかの観察）
- **`sale_campaigns.verified_at` の中央値経過日数**（運用劣化の早期検知）

実数値しきい値は本番計測の後で Phase 別計画に転記する。

## 9. リスクと対応

主要なリスクは機能別 PRD で詳述している。プロダクト全体で見るべき横断リスクのみ挙げる。

| リスク | 兆候 | 対応 |
|---|---|---|
| 公式 API の利用制限・仕様変更 | 価格更新失敗 / 欠落データ増加 | 各 API クライアントに retry とエラーログ。代替データ取得は ADR-003 の方針上、別 ADR でしか進めない |
| `sale_campaigns` の運用劣化 | `verified_at` 期限切れの蓄積 | 日次 Cron で 90 日超を通知（運用者にメール解析を促す） |
| 仕様書（`docs/api/*.md`）とコードのドリフト | フロント描画不能 / 型不整合 | OpenAPI 自動同期（F-15 / T-09）で恒久解決。それまでは PR レビューで仕様書同時更新を強制 |
| Vercel Functions の Python コールドスタート | p95 劣化 | `requirements.txt` の最小化と、必要なら edge cache / SWR ヘッダで吸収 |
| 認証 ADR の決定が変動 | JWT 構成の刷新要求 | ADR-007 を出典に維持。変更は新規 ADR を要求する運用 |

## 10. 関連ドキュメント

- 機能別 PRD: `docs/prd/price-comparison.md` / `docs/prd/suggestion-engine.md`
- ADR: `docs/adr/001`〜`009`（インデックスは `docs/adr/README.md`）
- Phase 計画: `docs/plans/phase1-foundation.md`
- API 契約: `docs/api/backend-spec.md` / `docs/api/auth.md` / `docs/api/cards.md`
- システム設計: `docs/tech/system-design.md`
- エージェント運用: `agent-rules/`（ブランチ / TDD / フロント設計 / 文書管理）
