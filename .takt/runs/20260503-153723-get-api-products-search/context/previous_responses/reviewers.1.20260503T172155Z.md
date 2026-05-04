## arch-review
調査が完了しました。設計レビューを行います。

## レビュー結果: APPROVE

### サマリー

このランの初回 arch-review。前回の arch-review レポートは存在しない。AI レビュー（2回目）で APPROVE 済みの状態に対し、構造・設計の観点で独立検証を実施。ブロッキング問題は検出されない。

### 検証した観点

| 観点 | 結果 | 確認内容 |
|------|------|------|
| ファイル行数 | ✅ | 全実装ファイル200行未満（repositories 148・routers 110・schemas 35・models 117・main 11・migration 0001 132・migration 0002 145）。test_product_search.py 729行は警告域だが `TestRepository*`/`TestEndpoint*` のクラス単位で責務分離されており構造的に妥当 |
| レイヤー設計 | ✅ | routers → repositories → models の単方向。逆参照・水平参照なし。routers は SQLAlchemy 直接操作なし（`Depends(get_db)` のみ）、repositories は FastAPI 非依存 |
| 1関数1責務 | ✅ | router 側 `_validate_price_range`/`_build_envelope`/`search_products_endpoint`、repository 側 `_searchable_text`/`_build_filters`/`_relevance_score`/`_order_by`/`search_products` がそれぞれ単一責務。どれも30行以内 |
| 操作の一覧性 | ✅ | 検索 SQL 構築は repository の `search_products` 一箇所に集約。汎用 `func.coalesce`/`func.similarity` 等が散在せずプライベート関数で目的別に名前付けされている |
| 高凝集・低結合 | ✅ | `SearchParams`（frozen dataclass）が handler ↔ repository の唯一の契約。circular import なし。`repositories/__init__.py` 空でも `from repositories.products import ...` で問題なし |
| 配線チェーン | ✅ | `main.py:6` `app.include_router(products_router)` → `routers/products.py:40` `APIRouter(prefix="/api/products")` → `:75` `@router.get("/search")` で `GET /api/products/search` に到達。プラン記載の旧 `_request_validation_exception_handler`/`SEARCH_FULL_PATH` は `main.py` から削除済み |
| 契約文字列のハードコード | ✅ | router 側で `ROUTER_PREFIX = "/api/products"`/`SEARCH_PATH = "/search"` 定数化。テスト側 `ENDPOINT = "/api/products/search"`/`EXPECTED_ITEM_KEYS`/`EXPECTED_ENVELOPE_KEYS` はテストの source-of-truth として独立（prod 側定数に依存させると本末転倒）で妥当 |
| 未使用 import / デッドコード | ✅ | `schemas.py`（uuid/List/Optional/BaseModel/ConfigDict/Field 全使用）、`routers/products.py`（logging/math/time/Optional/FastAPI/SQLAlchemy 全使用）、`repositories/products.py`（Sequence/dataclass/Literal/Optional/Tuple/SQLAlchemy 全使用）、`models.py`（ARRAY/TSVECTOR/UUID 全使用）。デッドコードなし |
| DRY 違反 | △ | migration 0002 の `_TSVECTOR_BODY` と `_TRIGRAM_EXPRESSION` および repository の `_searchable_text()` が同一の concat 式を3箇所で定義。ただし (a) SQL 文字列（trigger / index expression）と SQLAlchemy 式は別レイヤーで自然な共通化先がない (b) `NEW.` プレフィックス有無で SQL 内ですら完全共通化不可 (c) `repositories/products.py:54-67` のコメントで「Must match the trigram GIN index expression in 0002 migration」と相互参照が明記。ブロッキング不該当 |
| ADR-002 同期 | ✅ | `backend/models.py` と `analysis/models.py` の `Product` クラスが完全同期（`tags`/`in_stock`/`current_price`/`search_vector`）。analysis 側のコメントは「backend/alembic/versions/0002 を参照」と明記 |
| テストカバレッジ | ✅ | 43 テスト（リポジトリ 18 + エンドポイント 25）。FTS/Trigram/フィルタ/ソート/ページネーション/envelope/422 検証/クエリ文字列契約を網羅。NULL `current_price` 除外、`page=999` の越境、`totalPages=0` 境界、relevance vs sort=relevance 同値性、body 経由入力の無視、いずれも検証済み |
| 設計判断の妥当性（coder-decisions.md） | ✅ | (1) 生成カラム → トリガー：`to_tsvector` の STABLE 制約に対する Postgres FTS の標準対応、副作用最小 (2) `immutable_array_to_string` ラッパー：`array_to_string` の元 STABLE を破らずインデックス式に使える、ラッパー1つで完結 (3) enum 重複回避を `DO $$ ... duplicate_object ... END $$`：alembic の冪等再適用に耐える適切な対処 (4) `serialization_alias` での camelCase：差分フィールドのみ alias で snake_case ↔ camelCase の二重メンテ回避 (5) `total_pages` 0件時の明示 0：算術的には自動だが読みやすさで優位。いずれも documented で妥当 |
| インフラ実装の漏洩 | ✅ | repositories は public API としては `SearchParams`/`SortKey`/`PAGE_SIZE`/`search_products` のみエクスポート。internal helper（`_searchable_text` 等）はアンダースコアでカプセル化 |

### 今回の指摘

#### new
（なし）

#### persists
（なし - 前回 arch-review レポートなし）

#### resolved
（なし - 前回 arch-review レポートなし）

#### reopened
（なし）

### 参考情報（非ブロッキング）

- migration 0002 の `_TSVECTOR_BODY`/`_TRIGRAM_EXPRESSION` および repository `_searchable_text()` の concat 式は3箇所に存在する。`NEW.` プレフィックス有無・SQL 文字列 vs SQLAlchemy 式という根本的な層差により完全共通化は不自然で、相互参照コメントによるドリフト抑止が現実的な落としどころ。現状コードはコメント記載済みで方針として妥当。

### 判定理由

- ブロッキング問題（new/persists/reopened）が0件
- 構造（レイヤー・凝集・依存方向）が clean
- テストが repository 層と endpoint 層で適切に分離され、43 ケースで網羅
- 設計判断は coder-decisions.md にすべて documented で、いずれも妥当
- スコープが order.md / plan.md / coder-scope.md と整合
- DRY 違反候補1件は構造的に共通化不能で、相互参照コメントによる対処済み

→ **APPROVE**

---

## supervise
## 最終検証結果: APPROVE

タスク指示書（`order.md`）から 33 個の検証可能な最小要件を抽出し、`plan.md` の判断を鵜呑みにせず実コードで個別照合した結果、すべて充足を確認しました。

**主な検証結果:**

| 観点 | 結果 |
|------|------|
| 要件充足 | 33/33 すべて実コードで根拠確認 |
| 前段 finding | AI レビュー指摘 4 件すべて `resolved` の妥当性を grep + コード読みで再確認 |
| テスト | 52 passed（implement 段階の証跡）。ai-fix 修正は dead-code 削除のみで観測振る舞いに影響なし |
| ビルド/import | 全モジュール正常ロード、AST syntax OK |
| スコープクリープ | なし。削除はすべて plan に明記 |

**注記（⚠️ ではあるが REJECT 要件には該当せず）:**
- ai-fix 後の pytest 再実行は環境制約で未実施（`ai-fix.1.20260503T171136Z.md:38`）。ただし削除されたのは (a) 未参照 `ProductOut` クラス、(b) 到達不能な `if sort not in ALLOWED_SORTS` 防御、(c) 到達不能な `if params.page < 1` 防御、(d) 無効効 `populate_by_name=True` のみで、いずれも既存 52 テストが観測するパスを通らないため回帰なしと判断

レポート 2 ファイル（`supervisor-validation.md`、`summary.md`）を Report Directory に出力しました。