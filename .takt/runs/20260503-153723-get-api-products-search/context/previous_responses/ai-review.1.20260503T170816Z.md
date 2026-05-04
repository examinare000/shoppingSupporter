レビューを完了しました。AI生成コード特有の問題を 4 件検出しました。すべて REJECT 該当です。

---

## 判定: REJECT

ブロッキング指摘 4 件あり。`new` 状態。

---

## 指摘事項

### finding_id: AI-DEAD-PRODUCTOUT — `ProductOut` がデッドコード化（new / REJECT）

**ファイル**: `backend/schemas.py:21-34`（および `backend/schemas.py:1-4` の docstring 1-3 行）

**事実**:
- `backend/schemas.py` に `ProductOut` クラスが残存している（21-34 行）。
- `grep -r ProductOut backend analysis frontend` の結果、ソースコード上の参照は `backend/schemas.py` の定義行のみ。
- 旧 `backend/routers/products.py` は `from schemas import ProductOut` と `response_model=list[ProductOut]` を保持していたが、本変更で完全置換され、両者とも削除された（diff で確認）。
- `backend/schemas.py` は今回変更ファイルに含まれている（`ProductSummary` / `ProductSearchEnvelope` 追加）。

**問題**: 今回の変更で `ProductOut` の唯一の利用元（旧 router）が削除され、`ProductOut` は未使用コードになった。policy「今回の変更により未使用になったコード（引数、import、変数、関数）」「変更ファイル内の既存問題（ボーイスカウト）」の両方に該当する。さらに `schemas.py:1-3` のモジュール docstring も `ProductOut` を中心に説明している。

**修正**:
- `backend/schemas.py` から `ProductOut` クラス（21-34 行）を削除。
- 同ファイル冒頭 docstring 3-4 行の `ProductOut` の言及（"`ProductOut` mirrors the existing `Product` ORM columns ..."）を削除し、`ProductSummary` / `ProductSearchEnvelope` のみを説明する形に書き直す。
- import から不要になる `datetime` も削除（`ProductOut.created_at` 用にだけ使われている）。

---

### finding_id: AI-DEAD-DEFENSE-SORT — sort allowlist の二重チェックが論理的に到達不能（new / REJECT）

**ファイル**: `backend/routers/products.py:90-94`（および付随する `ALLOWED_SORTS` の import: 24 行、定義: `backend/repositories/products.py:36`）

**事実**:
- `sort: SortKey = Query(default="relevance")`（products.py:81）の `SortKey` は `Literal["relevance", "price_asc", "price_desc", "newest"]`（repositories/products.py:35）。
- FastAPI / pydantic v2 は `Literal` 型の Query 引数を **ハンドラ本体実行前** にバリデートし、不正値は 422 を返す（テスト `test_should_return_422_when_sort_value_not_in_allowed_set` で確認）。
- したがって `if sort not in ALLOWED_SORTS:` ブロック（93-94 行）に到達する経路は存在しない。
- 当該コードのコメント「Allowlist double-check: Literal in the type hint already enforces this, but keeping the constant lookup means the contract is explicit ...」自体が、これが「念のため」の防御コードであることを認めている。

**問題**: policy「論理的に到達不能な防御コード（呼び出し元の制約で絶対に通らない分岐）」に該当する REJECT 事項。「念のため」「二重チェック」を理由にした到達不能コードは policy で明示的に排除対象。

**修正**:
- `backend/routers/products.py:90-94`（コメント含む 5 行）を削除。
- 削除に伴い `from repositories.products import ALLOWED_SORTS, ...`（24 行）から `ALLOWED_SORTS` を削除。
- 結果、`backend/repositories/products.py:36` の `ALLOWED_SORTS: tuple[SortKey, ...] = ...` が未使用 export になるため、これも削除する（`SortKey` 自体は `SearchParams.sort` の型と handler の Query 型として継続使用されるので残す）。

---

### finding_id: AI-DEAD-DEFENSE-PAGE — リポジトリの `page < 1` 防御が到達不能かつ未テスト（new / REJECT）

**ファイル**: `backend/repositories/products.py:129-131`

**事実**:
- 当該コードは `if params.page < 1: raise ValueError("page must be >= 1")` でコメント「Defense-in-depth; the handler already enforces ge=1 via Query.」と自認。
- 唯一の本番呼び出し元（`backend/routers/products.py:106`）は `page: int = Query(default=1, ge=1)` で `page < 1` を 422 で弾く。
- `grep "page=0\|page=-" backend/tests/` 該当テストは存在せず、リポジトリ単体テスト（`TestRepositoryPagination`）でも `page=99`（範囲外だが正の整数）しか扱わない。すなわち **このブランチを通すテストが 0 件**。

**問題**: policy「論理的に到達不能な防御コード」「未使用コード（『念のため』のコード）」「テストがない新しい振る舞い」のいずれにも該当する。

**修正**:
- 129-131 行（`if` 〜 `raise ValueError(...)` ＋ コメント 130 行）を削除する。直後の `q_param = bindparam(...)` 以降はそのまま。
- リポジトリを公開API として `page < 1` を validate したい意思があるなら、SearchParams の `__post_init__` で一元化し、それに対応するテストを追加する（が、現状その必要性は plan / order どちらにも記載なく、過剰実装になるため削除を推奨）。

---

### finding_id: AI-MISLEADING-COMMENT-PBN — `populate_by_name=True` が無意味で、コメントが pydantic v2 セマンティクスを誤って説明（new / REJECT）

**ファイル**: `backend/schemas.py:38-41`

**事実**:
- `ProductSummary` の各フィールド（`image_url`, `in_stock`, `current_price`）は `Field(serialization_alias="imageUrl")` のように **`serialization_alias` のみ**を設定している。`alias` も `validation_alias` も指定していない。
- pydantic v2 において `populate_by_name=True` は、`Field(alias=...)` または `validation_alias=...` で **検証時のエイリアス**が設定されている場合に「フィールド名でも入力可」を許可するスイッチ。`serialization_alias` だけの場合、もともと検証側はフィールド名のみ受け付けるため、`populate_by_name` の有無は挙動に影響しない。
- すなわち `populate_by_name=True` は **何もしていない設定**。
- かつコメント「`populate_by_name=True` allows constructing the model from ORM attribute names (snake_case); ...」は事実と異なる（`populate_by_name` がそれを許可しているわけではない）。

**問題**: policy「未使用コード」（dead config）に加え、policy「説明コメント（What/How のコメント）」かつ事実誤認の説明コメント。AI 特有の「もっともらしいが間違っているコード」パターン。

**修正**:
- `backend/schemas.py:41` の `ConfigDict(from_attributes=True, populate_by_name=True)` から `populate_by_name=True` を削除し、`ConfigDict(from_attributes=True)` に戻す。
- 38-40 行の説明コメント（`populate_by_name=True allows ...` から `... HTTP contract requires.` まで）を削除する。代替コメントを残すなら、`response_model_by_alias=True` 側の働きは router 側で既に説明されているため、ここでは **不要**（無コメントが望ましい）。

---

## その他観察（非ブロッキング・参考）

- `repositories/products.py:20` で `Tuple`（`from typing`）と `tuple[SortKey, ...]`（PEP 585 風）が混在。Python 3.10+ なら `tuple[Sequence[Product], int]` に統一可能。スタイル warning。
- `repositories/products.py:_relevance_score` が `_searchable_text()` を再度呼び出すため、生成 SQL に同一式が 2 回現れる（WHERE で 1 回、ORDER BY で 1 回）。Postgres オプティマイザは式を共通化しないことがあるが、トリガラム GIN が WHERE に効けば ORDER BY 行数は十分絞られているため���計測なき最適化は不要。Warning レベル。
- `backend/main.py` のシバン以外問題なし。旧 422→200 ハンドラ削除と `SEARCH_FULL_PATH` import 削除は確実に反映済み。
- マイグレーション `0002` の `_TSVECTOR_BODY` / `_TRIGRAM_EXPRESSION` とリポジトリ `_searchable_text()` の 3 箇所同期は、コメントでドリフト警戒を明記している。式が重複しているが、Python 式と raw SQL（trigger 関数体・index 式）は同一抽象化が困難で、決定としては妥当。

---

## 再アプローチ提案

4 件すべて「念のため／対称性／説明的になりすぎる」の傾向。次の `ai_fix` ステップでは、

1. ハンドラの Query 引数バリデーション（FastAPI 側）と pydantic v2 の挙動を `信頼する` 設計に揃え、ハンドラ本体・リポジトリ本体に **入力前提の二重防御を書かない**。
2. コメントは「なぜ」のみに限定し、「なに／どう」は型と命名で表現する（AI が陥りがちな冗長コメントを抑制）。
3. 削除した import / 定数 / 設定は、grep で他参照ゼロを確認してから削除する。

この 3 点を方針として `ai_fix` 担当に渡してください。