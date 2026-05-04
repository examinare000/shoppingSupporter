# 変更スコープ宣言

## タスク
Amazon PA-API 5.0 GetItems の本格実装（SigV4 署名 + リトライ + 共通シェイプ整形）にスタブを置き換える。

## 変更予定
| 種別 | ファイル |
|------|---------|
| 作成 | `api/lib/aws_sigv4.py` |
| 変更 | `api/lib/amazon.py`（全面書き換え） |
| 変更 | `api/cron/update_prices.py`（Amazon 分岐の try/except 追加） |
| 変更 | `.env.example`（`AMAZON_*` 雛形追記） |

## 推定規模
Medium

## 影響範囲
- `api/lib/amazon.py`: スタブから本実装へ。戻り値契約が `Optional[Dict]` から `Dict | raise AmazonAPIError` に変わる破壊的変更。
- `api/lib/aws_sigv4.py`: 新規モジュール。AWS SigV4 純粋関数群（標準ライブラリのみ依存）。
- `api/cron/update_prices.py`: Amazon 分岐のみ `try/except AmazonAPIError` で包み、cron loop が 1 商品の失敗で止まらないように配線。楽天/Yahoo 分岐は無修正。
- `api/main.py`: 既存の cron エンドポイント `/api/cron/update-prices` 経由で `update_site_product` を間接利用。配線変更なし。
- `.env.example`: `AMAZON_ACCESS_KEY` / `AMAZON_SECRET_KEY` / `AMAZON_PARTNER_TAG` を追記（`AmazonAPI.__init__` が必須として読む）。
- テスト: `tests/unit/test_amazon.py`、`tests/unit/test_aws_sigv4.py`、`tests/integration/test_update_prices_amazon.py` が対象モジュールに依存（実装後 53 件全件 pass を確認済み）。