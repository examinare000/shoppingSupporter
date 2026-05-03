## 作業結果
- `api/lib/aws_sigv4.py` を新設し、AWS Signature V4 の各ステップ（CanonicalRequest / SignedHeaders / StringToSign / SigningKey / Signature / Authorization Header）を純粋関数として実装。`sign_request` で 5 ステップを束ねて Authorization ヘッダを返す高レベル API も提供。標準ライブラリ `hmac` / `hashlib` のみ使用。
- `api/lib/amazon.py` を全面書き換え。スタブの `print` + `return None` を削除し、PA-API 5.0 GetItems の本通信（POST + JSON + SigV4 署名 + 必須ヘッダ）+ 429 限定の指数バックオフ+jitter リトライ + レスポンス整形（共通シェイプ）+ 失敗時 `AmazonAPIError` 送出 を実装。境界での解決原則に従い `__init__` で認証情報をバリデーションし、欠落時はシークレットを漏らさないメッセージで即例外。
- `api/cron/update_prices.py` の Amazon 分岐を `try/except AmazonAPIError` でラップし、1 商品の Amazon 失敗で cron 全体を止めないように配線。
- `.env.example` に `AMAZON_ACCESS_KEY` / `AMAZON_SECRET_KEY` / `AMAZON_PARTNER_TAG` を追記。

## 変更内容
| 種別 | パス |
|------|------|
| 新規 | `api/lib/aws_sigv4.py` |
| 変更 | `api/lib/amazon.py`（全面書き換え） |
| 変更 | `api/cron/update_prices.py`（`AmazonAPIError` import + Amazon 分岐 try/except 追加） |
| 変更 | `.env.example`（`AMAZON_*` 雛形追記） |
| 新規 | `.takt/runs/.../reports/coder-scope.md` / `coder-decisions.md` |

## ビルド結果
- `python -m py_compile api/lib/amazon.py api/lib/aws_sigv4.py api/cron/update_prices.py` → 構文エラーなし
- `python -c "from api.lib import amazon, aws_sigv4; from api.cron import update_prices"` → import エラーなし

## テスト結果
- コマンド: `python -m pytest`
- 結果: **53 passed in 0.22s**（全件パス）
  - `tests/unit/test_aws_sigv4.py` 22 件: AWS 公式 `get-vanilla` テストベクター（CR / CR hash / SigningKey hex / Signature / Authorization）一致、PA-API JP 用 credential scope の検証、決定論性
  - `tests/unit/test_amazon.py` 26 件: 認証情報バリデーション（シークレット非漏洩含む）、リクエスト組立（POST / URL / 必須ヘッダ / SigV4 SignedHeaders / JSON ペイロード）、レスポンス整形（共通シェイプ・price int 化・image 欠落時 None）、異常系（400/404/500/`Errors`/空 Items/シークレット非漏洩）、リトライ（429 指数バックオフ、上限到達、5xx/4xx 非リトライ、`MAX_RETRIES + 1` 回リクエスト）、定数存在
  - `tests/integration/test_update_prices_amazon.py` 5 件: 成功時の PriceHistory 追加・URL 更新、`AmazonAPIError` の cron 内封じ込め、認証エラー時の継続、複数商品ループの継続