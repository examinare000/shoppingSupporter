実装をレビューしました。以下の調査結果を報告します。

## レビュー結果

実装はほぼ仕様通りだが、AI特有のいくつかの問題（論理的デッドコード、未使用引数、冗長な再代入、コードベース慣習からの逸脱）を検出しました。

## 判定: REJECT

`new` 状態の指摘が4件あります。

## 指摘事項

### REJECT対象（ブロッキング）

#### AI-001 (new): `api/lib/amazon.py:183-184` 論理的に到達不能な防御コード

```python
        # 到達しない（ループ内で必ず return / raise する）が、型解析のため保険として残す
        raise AmazonAPIError(f"PA-API retry loop exited unexpectedly for ASIN={asin}")
```

**問題**:
- コメント自身が「到達しない」と明記している。`for attempt in range(MAX_RETRIES + 1)` の各イテレーションで必ず `return / raise / continue` のいずれかに分岐するため、ループを抜けて line 184 に到達する経路は存在しない。
- これは Policy の「論理的に到達不能な防御コード | 呼び出し元の制約で絶対に通らない分岐」に該当（AI Antipattern: 「念のため」コード）。
- 「型解析のため」という Why も、本リポジトリは mypy を構成しておらず（`pyproject.toml`/`mypy.ini` 不在）、根拠が成立していない。

**修正案**:
- line 183-184 を削除する。`async def fetch_product` の戻り値型 `Dict[str, Any]` は控除可能（Python 標準のフロー解析）。
- 万一の保険が必要なら `raise` ではなく開発者向けの構造的ガード（`assert False, "unreachable"`）に置き換えるのが慣用だが、本ケースでは削除で十分。

---

#### AI-002 (new): `api/lib/aws_sigv4.py:122` `sign_request` の `host` 引数が未使用

```python
def sign_request(
    *,
    method: str,
    host: str,         # <-- 受け取るが関数本体で一切参照されていない
    path: str,
    headers: Mapping[str, str],
    ...
```

**問題**:
- 関数本体で `host` 変数が一度も参照されない。`canonical_request` 構築には `headers["Host"]` を使う設計（line 138 のコメント `# host は headers に必ず含まれる前提（呼び出し元責務）` がそれを明示）。
- 呼び出し元 `api/lib/amazon.py:136` は `host=PAAPI_HOST` を渡しているが、何も起きない。
- Policy「今回の変更により未使用になったコード（引数、import、変数、関数）| ブロッキング | REJECT」に該当。

**修正案**:
- `sign_request` のシグネチャから `host: str` を削除する。
- 呼び出し側 `api/lib/amazon.py:136` の `host=PAAPI_HOST,` を削除する。
- 必要なら docstring に「`Host` ヘッダは `headers` に含めて呼び出すこと」と明記する。

---

#### AI-003 (new): `api/cron/update_prices.py:28` 冗長な `result = None` 再代入

```python
async def update_site_product(db: Session, site_product: EcSiteProduct):
    """個別のサイト商品の価格を更新する"""
    result = None       # line 16: 初期化
    
    if site_product.site_type == SiteType.AMAZON:
        try:
            api = AmazonAPI()
            result = await api.fetch_product(site_product.site_product_id)
        except AmazonAPIError as e:
            logger.warning(...)
            result = None   # line 28: 冗長
```

**問題**:
- `await api.fetch_product(...)` は値が返ってきた時のみ `result` に代入されるため、例外時には line 16 で初期化された `None` のまま残る。line 28 の `result = None` は同値の冗長代入。
- Policy「冗長な式（同値の短い書き方がある）| REJECT」に該当。

**修正案**:
- line 28 の `result = None` を削除する。except ブロックは `logger.warning(...)` のみで意図が明確に保たれる。

---

#### AI-004 (new): `api/lib/amazon.py:120` 関数内 `import json`（コードベース慣習との非整合）

```python
    @staticmethod
    def _serialize_payload(payload: Dict[str, Any]) -> bytes:
        # Why json.dumps の separators 固定: ...
        import json

        return json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
```

**問題**:
- `api/lib/rakuten.py`, `api/lib/yahoo.py` は全て **モジュール先頭で全 import** する慣習。`amazon.py` だけが関数内 import を採用している。
- Policy「コンテキスト適合性評価: プロジェクト規則からの説明のない逸脱」/「インテグレーションパターンの一貫性」に該当。
- `_serialize_payload` は `fetch_product` のホットパス（毎リクエスト呼び出し）で、関数内 import はキャッシュされるとはいえコードベースの慣習を破る合理的理由が無い。

**修正案**:
- line 16-22 の import 群に `import json` を追加し、line 120 の関数内 import を削除する。

---

### Warning（非ブロッキング・記録のみ）

#### W-001: `api/lib/amazon.py:86-88` `# type: ignore[assignment]` に理由コメントなし

```python
self._access_key: str = access_key  # type: ignore[assignment]
self._secret_key: str = secret_key  # type: ignore[assignment]
self._partner_tag: str = partner_tag  # type: ignore[assignment]
```

`if missing` チェック後に narrowing が効かない理由を Why コメントで添える方が望ましい（Policy: 「理由なしの `@ts-ignore`、`eslint-disable`」相当）。本リポジトリは mypy を運用していないため即修正は不要だが、将来的に型チェックを導入した際の負債になる。

#### W-002: `api/lib/amazon.py:104, 153, 208` セパレータコメント

`# ----- 内部: リクエスト組み立て --------------------------------------` のような区切りコメントは「次のコードが何か（What）」を述べる説明コメントに近い。Pythonの慣習ではクラス／メソッドの構造で表現する方が望ましいが、可読性向上のための装飾として許容範囲ではある。

#### W-003: `tests/integration/test_update_prices_amazon.py` の追加

order.md は「テストはモックによる単体テストのみ。実 API を叩く統合テストは作成しない」と明示。本テストは Mock のみで実 API を叩かないが、文言を厳密解釈するとスコープクリープにあたる可能性がある。Decision log では「破壊的契約変更を呼び出し元と突き合わせる目的」と根拠が記載されているため、今回は記録のみとする。

#### W-004: `tests/unit/test_amazon.py:388, 411` でジッター上限を `0.1` ハードコード

`amazon_module.RETRY_BASE_DELAY` は参照しているのに、ジッター上限 `0.1` だけハードコードしている。`amazon_module.RETRY_JITTER_MAX` を参照する方がドリフト耐性が高い。テストの実装詳細結合を弱める観点では Warning。

---

## まとめ

| ID | 状態 | 種別 | ファイル/行 |
|---|---|---|---|
| AI-001 | new | REJECT | api/lib/amazon.py:183-184（論理的デッドコード） |
| AI-002 | new | REJECT | api/lib/aws_sigv4.py:122（未使用引数 `host`） |
| AI-003 | new | REJECT | api/cron/update_prices.py:28（冗長な `result = None`） |
| AI-004 | new | REJECT | api/lib/amazon.py:120（関数内 import） |
| W-001 | new | Warning | api/lib/amazon.py:86-88 |
| W-002 | new | Warning | api/lib/amazon.py:104, 153, 208 |
| W-003 | new | Warning | tests/integration/ |
| W-004 | new | Warning | tests/unit/test_amazon.py:388, 411 |

**判定: REJECT**（new の REJECT 指摘 4 件あり）

次の `ai_fix` ステップで AI-001〜AI-004 を修正してください。