All test failures are exactly the expected unimplemented-module imports. Let me summarize.

## テスト作成完了サマリー

### 作成したファイル

**テスト基盤（新規）**
- `pytest.ini` — `asyncio_mode=auto`、testpaths 指定
- `requirements-dev.txt` — `pytest`, `pytest-asyncio`（本番依存と分離）
- `tests/__init__.py` / `tests/unit/__init__.py` / `tests/integration/__init__.py`
- `tests/conftest.py` — Amazon 環境変数の autouse クリア + `amazon_env` フィクスチャ

**単体テスト（新規）**
- `tests/unit/test_aws_sigv4.py`（10+ テスト）
  - AWS 公式 `get-vanilla` テストベクター（IAM/GET）の期待値を直接ハードコード（CR / CR hash / SigningKey hex / Signature / Authorization 全段階）
  - 各 SigV4 ステップ（`build_canonical_request`、`build_signed_headers`、`build_string_to_sign`、`derive_signing_key`、`compute_signature`、`build_authorization_header`）を独立検証
  - `sign_request` でのエンドツーエンド：PA-API JP の credential scope、決定論性、payload 差分による署名差を確認
- `tests/unit/test_amazon.py`（20+ テスト）
  - `__init__` 段階での認証情報バリデーション（境界での解決） + シークレットを例外メッセージに載せない
  - リクエスト組立（POST、URL、必須ヘッダ、SigV4 SignedHeaders、JSON ペイロード形）
  - レスポンス整形（共通シェイプ `site/id/title/price/image_url/url`、price の int 化、image_url 欠落 → None）
  - 異常系（400/404/500、`Errors` 配列、空 `Items`、シークレット非漏洩）
  - リトライ（429 → 200 成功時の指数バックオフ、上限到達で例外、5xx/4xx は非リトライ、`MAX_RETRIES + 1` 回呼ばれる）
  - 定数 `MAX_RETRIES` / `RETRY_BASE_DELAY` の存在確認

**インテグレーションテスト（新規、3モジュール横断のため作成）**
- `tests/integration/test_update_prices_amazon.py`
  - 成功時: `PriceHistory.add` / `commit` / `site_product.url` 更新
  - `AmazonAPIError` が `update_site_product` 内で握られて伝播しないこと（cron が止まらない）
  - 認証情報欠落でも cron が継続すること
  - 1件失敗・1件成功で 2件目が処理されること

### テスト実行結果（write_tests RED 状態）

```
tests/unit/test_amazon.py        - ImportError: AmazonAPIError 未定義
tests/unit/test_aws_sigv4.py     - ImportError: aws_sigv4 モジュール未作成
tests/integration/...            - ImportError: AmazonAPIError 未定義（同上）
```

すべて **未実装モジュール／シンボルへの参照による期待された Red** であり、Plan で定義された implement ステップで `api/lib/aws_sigv4.py` 新設と `api/lib/amazon.py` 全面書き換えにより解消される。`psycopg2-binary` は `requirements.txt` に既存記載があったが dev 環境で未インストールだったため `pip install psycopg2-binary` を実行（本番ランタイムには既に依存定義済み）。