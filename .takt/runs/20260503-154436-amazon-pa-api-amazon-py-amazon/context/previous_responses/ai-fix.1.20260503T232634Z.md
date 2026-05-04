All 53 tests pass (48 unit + 5 integration). Let me provide the final report.

## 確認したファイル
- `api/lib/amazon.py:14-26` (import 群)
- `api/lib/amazon.py:117-122` (`_serialize_payload`)
- `api/lib/amazon.py:133-143` (`sign_request` 呼び出し)
- `api/lib/amazon.py:153-180` (`_post_with_retry` ループ末尾)
- `api/lib/aws_sigv4.py:119-145` (`sign_request` 関数定義)
- `api/cron/update_prices.py:14-35` (`update_site_product` 例外節)
- `tests/unit/test_aws_sigv4.py:374-453` (sign_request E2E テスト 3 件)
- `tests/unit/test_amazon.py` および `tests/unit/test_aws_sigv4.py` 全体

## 実行した検索
- `Grep "host="` (tests 配下) → `tests/unit/test_aws_sigv4.py` の 3 行 (379, 410, 435) と `tests/unit/test_amazon.py` の `api.host ==` を検出
- `Grep "sign_request|host=PAAPI_HOST"` (リポジトリ全体) → 修正後に runtime コードから `host=PAAPI_HOST` が消滅していることを確認
- `Grep "host\s*="` (tests 配下) → `api.host ==` のみ残存（`AmazonAPI` インスタンスのフィールド参照、影響なし）

## 修正内容

**指摘 #1 (AI-NEW-amazon-L184)**: `api/lib/amazon.py` の `_post_with_retry` ループ後の到達不能 `raise` (旧 L183-184) を削除。「型解析のため」という理由は `mypy` 未構成のため成立しない。

**指摘 #2 (AI-NEW-aws_sigv4-L122)**:
- `api/lib/aws_sigv4.py` の `sign_request` から未使用の `host: str` 引数を削除。Why コメントを `# host を独立引数として受けない:` 説明に置き換え。
- `api/lib/amazon.py:135` の `host=PAAPI_HOST,` を削除。
- `tests/unit/test_aws_sigv4.py` の 3 つのテスト (`test_returns_authorization_header_with_correct_credential_scope` / `test_signature_is_deterministic_for_same_inputs` / `test_different_payload_yields_different_signature`) から `host="webservices.amazon.co.jp",` を削除。

**指摘 #3 (AI-NEW-update_prices-L28)**: `api/cron/update_prices.py:28` の冗長な `result = None` を削除（L16 で初期化済み）。

**指摘 #4 (AI-NEW-amazon-L120)**: `api/lib/amazon.py` の関数内 `import json` を削除し、モジュール先頭 import 群 (L17) に `import json` を追加。`rakuten.py` / `yahoo.py` の慣習に整合。

## テスト結果
- `pytest tests/unit/ -v`: **48 passed in 0.08s**
- `pytest tests/ -v`: **53 passed in 0.22s** (unit + integration)

全ての AI Review 指摘 4 件を修正し、テストも全件パスしました。