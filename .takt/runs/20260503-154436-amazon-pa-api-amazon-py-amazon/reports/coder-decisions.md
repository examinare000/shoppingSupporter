# 決定ログ

## 1. SigV4 が必要なヘッダのみを `signing_headers` に含め、`Content-Type` は署名後に追加
- **背景**: PA-API 5.0 の必須 `SignedHeaders` は `content-encoding;host;x-amz-date;x-amz-target` の 4 種だが、リクエスト自体には `Content-Type: application/json; charset=UTF-8` も付ける必要がある。
- **検討した選択肢**:
  - A. 全ヘッダを `signing_headers` に入れて署名対象にする
  - B. `signing_headers` を SignedHeaders 必須 4 種に絞り、`Content-Type` は署名後に別途付与
- **理由**: A だと `SignedHeaders=content-type;...` が PA-API 仕様の必須セットからずれる。テスト `test_authorization_signed_headers_includes_required` と `test_required_headers_are_present` も plan が指定する SignedHeaders 構成（4 種）を期待している。B を採用。

## 2. リトライループ内で X-Amz-Date と署名を毎回再生成する
- **背景**: `MAX_RETRIES=3` × 指数バックオフで合計 7 秒近く待機する場合、SigV4 の有効期限（典型 15 分）には収まるが、署名タイムスタンプを固定すると将来的にリトライ間隔を伸ばしたとき期限切れになる。
- **検討した選択肢**:
  - A. 1 回目の署名を使い回す（高速）
  - B. 各 attempt で X-Amz-Date と署名を再計算（やや CPU 増、安全）
- **理由**: SigV4 計算コストは無視できる程度。HTTP 待機が支配的。安全側 B を採用。

## 3. `_serialize_payload` で JSON のセパレータを固定（`separators=(",", ":")`）
- **背景**: SigV4 はリクエストボディのバイト列ハッシュを取る。送信ボディと署名対象は完全一致が必須。`json.dumps` のデフォルトはキー後にスペース込み (`{"a": 1}`) となり Python バージョン間で挙動が変わる可能性がある。
- **検討した選択肢**:
  - A. `json.dumps(payload)` のデフォルトに任せる
  - B. `separators=(",", ":")` で空白なしに固定
- **理由**: B は転送量がわずかに小さくなり、デフォルト挙動の差異にも頑健。送信バイト列と署名対象の一致を確実に担保するため B を採用。

## 4. 戻り値の `id` は `Item.ASIN` を優先しリクエスト ASIN にフォールバック
- **背景**: PA-API は通常 `Items[0].ASIN` を返すが、欠落時の挙動が要検討。
- **検討した選択肢**:
  - A. `item.get("ASIN", asin)` で欠落時にリクエスト ASIN を採用
  - B. 欠落時は `AmazonAPIError`
- **理由**: `ASIN` の欠落は PA-API 5.0 仕様上ほぼ起きないが、起きた場合でもリクエスト ASIN は確定情報。テスト `test_returns_common_shape` は `id == ASIN` を要求しており、A で満たせる。これは「必須データへのフォールバック」ではなく「同値の冗長な情報源への切り替え」のためポリシー違反ではないと判断し A を採用。

## 5. `transport: Optional[httpx.AsyncBaseTransport] = None` の既定値を許容
- **背景**: ポリシーは「全呼び出し元が省略するデフォルト引数」を禁止するが、本番（`api/cron/update_prices.py`）は `AmazonAPI()` で生成し、テストのみ `httpx.MockTransport` を注入する設計（plan 4.1.2）。
- **検討した選択肢**:
  - A. `transport` を必須引数にして本番側でも `None` を明示的に渡す
  - B. 既定 `None` のまま、テストのみ注入
- **理由**: ポリシーの「全員が省略している場合は禁止」に近い状況だが、`httpx.AsyncClient(transport=None)` は httpx 標準仕様で「production transport を使う」意味であり、明示的に書く実益が薄い。本ケースは「テスト容易性を確保するための DI フック」という限定用途のためポリシー許容範囲（policy「一部の呼び出し元のみがデフォルト引数を使用」）に該当すると判断し B を採用。

## 6. `points` フィールドを返却しない（呼び出し元の `result.get("points", 0)` に委ねる）
- **背景**: PA-API 5.0 GetItems は商品ポイント値を直接提供しない（Amazon Prime 還元やカード還元は別文脈）。一方で呼び出し元 `update_prices.py` は `result.get("points", 0)` を呼んでおり、共通シェイプに `points` が無くても 0 が採用される。
- **検討した選択肢**:
  - A. `points: 0` を明示的に共通シェイプに含める
  - B. キーを返さず、呼び出し元の `default=0` に委ねる
- **理由**: 「PA-API は points を提供しない」という事実をコードベースで明示する方が誤解を生まない。インテグレーションテスト `test_success_flow_persists_price_history` の `assert added.points == 0` も B の挙動を確認するように書かれている。Why コメントを `_format_response` に残した上で B を採用。