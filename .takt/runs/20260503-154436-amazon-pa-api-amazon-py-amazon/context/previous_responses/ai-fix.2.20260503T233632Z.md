All 53 tests pass. Let me provide the required report.

## 確認したファイル
- `api/lib/amazon.py:85-94`（`self.host` / `self.region` / `# type: ignore` の存在を確認、修正済み）
- `api/lib/amazon.py:117-121`（`_serialize_payload` の Why コメントの実装乖離を確認、修正済み）
- `api/lib/amazon.py:131-149`（`sign_request` の戻り値消費箇所を確認、修正済み）
- `api/lib/aws_sigv4.py:119-172`（`sign_request` の戻り値型 `dict[str, str]` を確認、`str` に変更済み）
- `tests/unit/test_amazon.py:127-133`（`api.host` / `api.region` のアサーション存在を確認、定数アサートに置換）
- `tests/unit/test_amazon.py:495-499`（`api.host` / `api.region` のアサーション存在を確認、定数アサートに置換）
- `tests/unit/test_aws_sigv4.py:374-451`（3 テスト中の `signed["Authorization"]` 抽出を確認、戻り値直接利用に変更）
- `requirements.txt` / `requirements-dev.txt`（mypy 未導入を確認 → `# type: ignore` は機能しない）
- リポジトリルート（`mypy.ini` / `pyproject.toml` / `setup.cfg` 不在を確認）

## 実行した検索
- `Grep "self\.(host|region)" api/lib/amazon.py` → 91-92 行のみ（production 参照ゼロ）
- `Grep "api\.host|api\.region|self\.host|self\.region"` 全 .py → production 0、test 4 箇所
- `Grep "type: ignore"` 全 .py → 修正対象 3 行のみ
- `Grep "sign_request"` 全 .py → 呼び出し元（amazon.py / test_aws_sigv4.py）を全件把握
- `ls mypy.ini pyproject.toml setup.cfg` → すべて不在を確認
- 修正後 `Grep "api\.host|api\.region|self\.host|self\.region|type: ignore|signed\["` → No matches found（残存ゼロ確認）

## 修正内容
1. **AI-NEW-amazon-L91-host-region**: `api/lib/amazon.py` から `self.host = PAAPI_HOST` / `self.region = PAAPI_REGION` を削除。`tests/unit/test_amazon.py:127-133` および `:495-499` の `api.host` / `api.region` アサーションを `amazon_module.PAAPI_HOST` / `PAAPI_REGION` への直接アサートに変更（指摘 (a)+(b) の (b) を採用）。
2. **AI-NEW-amazon-L87-typeignore**: 3 行の `# type: ignore[assignment]` と冗長な `: str` 型注釈を削除し、`self._access_key = access_key` 等のシンプルな代入に変更（指摘 (a) を採用）。直前の `if missing: raise` で None 排除済みである旨をコメントで明記。
3. **AI-NEW-aws_sigv4-L130-dictwrap**: `aws_sigv4.sign_request` の戻り値型を `dict[str, str]` から `str`（Authorization ヘッダ値そのもの）に変更し、誤った Why コメント（「返却辞書を request headers にマージすれば…」）を削除。`api/lib/amazon.py:146` の呼び出し側を `authorization = aws_sigv4.sign_request(...)` 形に変更し、`tests/unit/test_aws_sigv4.py` の 3 テスト（`test_returns_authorization_header_with_correct_credential_scope` / `test_signature_is_deterministic_for_same_inputs` / `test_different_payload_yields_different_signature`）から `["Authorization"]` 抽出を撤去。
4. **AI-NEW-amazon-L119-comment**: `_serialize_payload` の Why コメントを「SigV4 の署名対象は HTTP ボディとバイト一致が必須。json.dumps のデフォルトは空白入り `(", ", ": ")` なので空白なしを明示する」に書き換え（指摘文の修正案そのまま）。

## テスト結果
- `python -m pytest tests/unit/test_amazon.py tests/unit/test_aws_sigv4.py -x` → **48 passed in 0.09s**
- `python -m pytest tests/` → **53 passed in 0.21s**（integration 5 件含むフルスイート）