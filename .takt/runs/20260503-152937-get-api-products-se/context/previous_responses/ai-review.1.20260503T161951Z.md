I've completed my review of the implementation. Let me organize my findings.

---

# AI Antipattern Review — `GET /api/products/search` 実装

## レビュー対象

- 変更ファイル: `backend/main.py`, `backend/models.py`, `analysis/models.py`, `backend/requirements.txt`
- 新規ファイル: `backend/routers/__init__.py`, `backend/routers/products.py`, `backend/schemas.py`, `backend/pytest.ini`, `backend/tests/__init__.py`, `backend/tests/conftest.py`, `backend/tests/test_product_search.py`

## 判定: **REJECT**

ブロッキング問題が 1 件存在するため REJECT。

---

## ブロッキング問題

### B1. `limit` の `Optional[int]` 型と `is None` 分岐がデッドコード

**ファイル**: `backend/routers/products.py:94, 104`

```python
@router.get(SEARCH_PATH, response_model=list[ProductOut])
def search_products_endpoint(
    q: Optional[str] = Query(default=None),
    limit: Optional[int] = Query(default=LIMIT_DEFAULT),  # ← LIMIT_DEFAULT = 10 (非None)
    db: Session = Depends(get_db),
) -> list[Product]:
    if q is None:
        return []

    normalized_q = q.strip()
    if not normalized_q or len(normalized_q) > Q_MAX_LENGTH:
        return []

    if limit is None or limit < 1:   # ← `limit is None` は到達不能
        return []
```

**問題点**:
- `Query(default=LIMIT_DEFAULT)` の既定値が `int (=10)` なので、パラメータ省略時に `limit` は `10` であり `None` にはならない。
- `?limit=abc` / `?limit=` 等の不正値は `RequestValidationError` で握り潰されて 200+`[]` に変換されるため、関数本体までは到達しない。
- 結果として `limit is None` 分岐は実行経路上どのケースでも到達しない「念のためのコード」。
- 加えて型注釈 `Optional[int]` は実際の振る舞いと一致しないため OpenAPI 仕様と契約意図がずれる。

**根拠（Policy）**: 「未使用コード（「念のため」のコード）」は REJECT 基準。

**推奨修正**:
```python
limit: int = Query(default=LIMIT_DEFAULT),
...
if limit < 1:
    return []
```

`q` 側の `Optional[str] = Query(default=None)` は既定値が `None` なので問題なし、`limit` のみ修正対象。

---

## Warning（非ブロッキング）

### W1. `list(...)` ラッパが冗長

**ファイル**: `backend/routers/products.py:88`

```python
return list(db.execute(stmt).scalars().all())
```

`ScalarResult.all()` は SQLAlchemy 2.0 で既に `list` を返す。`list(...)` で再度コピーしており、要素 0〜100 件規模なので実害は無いが、AI コードでよくみる「型を揃えるための念のため変換」パターン。

**推奨**:
```python
return db.execute(stmt).scalars().all()
```

### W2. `ProductOut` の `Optional[str] = None` 既定値が不要

**ファイル**: `backend/schemas.py:23-25`

```python
description: Optional[str] = None
jan_code: Optional[str] = None
image_url: Optional[str] = None
```

レスポンスは `from_attributes=True` 経由で ORM 行から直接生成され、これらの列は常に存在する（NULL 値であっても属性自体は存在）。`Optional[str]` だけで NULL は許容されるため `= None` は無駄な既定値。

**推奨**: 既定値を削除し型のみで NULL 許容を表現する。優先度低い（動作影響なし、可読性のみ）。

---

## 確認した観点（問題なし）

| 観点 | 結果 |
|---|---|
| 仮定の検証 | `description` カラム追加は order.md「説明文を対象に検索」「説明文のみマッチ」テスト要件から正当に導出。ADR-002 同期済み。 |
| 幻覚 API | 使用 API（FastAPI `APIRouter`/`Query`/`Depends`、SQLAlchemy 2.0 `select`/`case`/`func.lower`/`ilike`/`scalars`、Pydantic `ConfigDict(from_attributes=True)`）はすべて実在し正しいシグネチャで使用。 |
| 既存コードベース整合 | `Depends(get_db)` 再利用、`Mapped[Optional[str]] = mapped_column(Text, ...)` の既存命名・カラム宣言形式を踏襲。`backend/Dockerfile` が Python 3.11 のため `list[ProductOut]` ランタイム評価可。 |
| スコープクリープ | 検出なし。Alembic / 認証 / 他エンドポイント / フロントエンド配線などは plan.md スコープ外通り未実装。`pytest.ini` 追加は `from main import app` 成立のための最小限テスト基盤。 |
| スコープ縮小 | order.md 検索ロジック（name + description あいまい・関連度順）、エラー時 `[]`、認証不要、既存スキーマ準拠 — 全て充足。境界値テスト（0/負/非数値/上限超過/空白/101文字）も網羅。 |
| エラー握りつぶしの妥当性 | `try/except Exception` は order.md 仕様（エラー時 `[]`）に直接準拠し、`logger.warning(..., exc_info=True)` でスタックは保存。q を含めない判断は security-guidelines に合致。 |
| LIKE エスケープ順序 | `\` → `%` → `_` の順で `_escape_like` 実装済み。バックスラッシュ二重置換問題は回避されている。テスト `test_should_treat_percent_in_q_as_literal_not_wildcard` / `..._underscore_in_q_...` で挙動固定。 |
| `RequestValidationError` ハンドラのパスガード | `request.url.path == SEARCH_FULL_PATH` （`/api/products/search`、クエリ文字列除外）。他パスは `await request_validation_exception_handler(...)` で標準動作維持。`SEARCH_FULL_PATH` を router 側で 1 箇所定義し main.py が import する設計で文字列ドリフトを構造的に排除。 |
| 設定ファイル定数源 | `ROUTER_PREFIX` / `SEARCH_PATH` / `SEARCH_FULL_PATH` / `Q_MAX_LENGTH` / `LIMIT_DEFAULT` / `LIMIT_MAX` / `LIKE_ESCAPE` を全てモジュール先頭で定義。マジックナンバー散在なし。 |
| `httpx` API 整合 | `client.request("GET", ENDPOINT, json=...)` への書き換えは coder-decisions.md に正当化記録あり。負契約（GET ボディ無視）を保持しつつテスト崩壊回避は妥当。 |
| ADR-002 同期 | `analysis/models.py` も同一の `description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)` で更新確認。 |

---

## サマリ

| 種別 | 件数 |
|---|---|
| Blocking (REJECT) | 1 |
| Warning | 2 |
| OK | 多数 |

**B1**（`limit is None` のデッドディフェンシブコード）を修正することで承認可能なクオリティに到達できる見込みです。修正は型注釈を `int` に絞り、`if limit is None or limit < 1:` を `if limit < 1:` に置き換えるだけの軽微な変更で済みます。