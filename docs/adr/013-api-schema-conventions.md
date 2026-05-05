# ADR-013: API スキーマ契約規約（Pydantic v2 ベース）

## ステータス
採用済み

## 背景
Phase 1 の API 層は FastAPI + Pydantic で HTTP コントラクトを定義しており、`api/schemas.py` の `SignupRequest` / `LoginRequest` / `UserResponse` / `CardResponse` / `ProductSummary` / `ProductSearchEnvelope` で慣習的な書き方が共有されていた。しかし、これらの規約はコードに散在するだけで成文化されていなかったため、`docs/design/user-profile.md` のレビュー時に Pydantic v1 系の `class Config:` 構文や `alias_generator` 一括変換が混入し、既存スキーマと非対称な擬似コードが提示される事故が起きた。

加えて ADR-012（OpenAPI 型同期戦略）は「Pydantic の `Field(alias=...)` や `extra="forbid"` 等の設定が正しく OpenAPI に反映されている必要がある」と前提しているが、その「設定」自体の正本がリポジトリ内に存在しなかった。新規エンドポイントを追加する際に、規約をコード読解で推測する負担と、レビューでの差し戻しコストが繰り返し発生していた。

## 決定
本リポジトリの全 Pydantic スキーマは以下 6 項目の規約に従う。既存スキーマは既に準拠しており、新規エンドポイント追加時のチェックリストとして機能させる。

### 1. Pydantic v2 構文を使用する
- `model_config = ConfigDict(...)` を用い、v1 系の `class Config:` 内部クラス構文は禁止する。
- 既存コードに v1 構文があれば段階的に v2 へ移行する。

### 2. リクエスト系には `extra="forbid"` を付与する
- `ConfigDict(extra="forbid")` を全リクエストモデルで必須とする。
- 既存例: `SignupRequest` / `LoginRequest`（`api/schemas.py:54-56`）。

### 3. レスポンス系には `from_attributes=True` を付与する
- `ConfigDict(from_attributes=True)` を全レスポンスモデルで必須とする。
- 既存例: `UserResponse` / `CardResponse` / `ProductSummary`（`api/schemas.py:26, 77, 88`）。

### 4. JSON は camelCase、Python は snake_case
- フィールド名は Python 側で snake_case を保ち、JSON 出力は `Field(serialization_alias="camelCase")` で**個別指定**する。
- `alias_generator` による一括変換は使用しない。

### 5. Enum の wire format は value（小文字）
- Python の Enum 定義は `value` を小文字（snake または kebab）で揃える。
    - 例: `RakutenRank.DIAMOND.value == "diamond"` / `SiteType.AMAZON.value == "amazon"`。
- Pydantic v2 の既定挙動（`value` がシリアライズされる）を変更しない。

### 6. datetime は ISO 8601
- Pydantic v2 の `datetime` 既定シリアライズに従い、ISO 8601 形式で出力する（例: `2026-05-05T12:34:56`）。
- 独自フォーマット（`YYYY-mm-dd HH:MM:SS` 等のスペース区切り）は禁止する。

## 理由

### Pydantic v2 一本化（項目 1）
v1 系の `class Config:` は v2 でも一部後方互換だが、`alias_generator` の挙動などで微妙な差があり混在は技術負債になる。`api/schemas.py` の既存実装は全て v2 で書かれており、設計書側だけ v1 で書かれると実装時に必ず書き直しが発生する。

### `extra="forbid"`（項目 2）
未知フィールドを 200 ではなく 422 で弾くことで、以下のクラスの事故を契約レベルで検出できる。
- レスポンス本文（`TokenResponse` 等）をクライアントがリクエスト本文として誤って流用するケース。
- フィールド名のタイポ（`is_amazon_prime` を `isAmazonPrime` で送る等）。

`tests/integration/test_auth.py` の `TestRequestBodyContract` パターンに揃え、新規エンドポイントごとに契約テストを追加する。

### `from_attributes=True`（項目 3）
SQLAlchemy ORM 行を FastAPI ハンドラから直接返却できるようにすると、リポジトリ層と API 層が直結し、変換中間オブジェクトを書く必要がなくなる。Phase 1 で複数のエンドポイントが ORM 行を直接返している（`UserResponse` / `CardResponse` / `ProductSummary`）規約と整合する。

### 個別 alias 指定（項目 4）
`alias_generator` の一括変換は便利だが以下の問題がある。
- フィールドごとの例外（alias 付与なしや別名）を扱いにくい。
- OpenAPI 出力で生成された型と Pydantic モデル間に意図しない差が出やすい（ADR-012 の型同期で問題になる）。
- 既存スキーマが個別指定で揃っており、混在は読み手の認知負荷を増やす。

### Enum value の小文字統一（項目 5）
DB 列値（SQLAlchemy の `Enum`）と JSON 値が同じ文字列になり、ログ・DB ダンプ・フロント側ストアのすべてで同じ表現を扱える。`name`（大文字）を JSON に出すと、DB 値とのマッピングテーブルが必要になり保守コストが増える。

### ISO 8601（項目 6）
TypeScript の `new Date()` はブラウザ実装に依存し、`YYYY-mm-dd HH:MM:SS`（スペース区切り）は Safari で `Invalid Date` を返すケースがある。ISO 8601 のみが全ブラウザで安全に解釈できる。

## 影響

- **既存スキーマ**: `api/schemas.py` 全モデルは本規約に準拠済み。改修不要。
- **新規エンドポイント**: 本 ADR をチェックリストとして実装する。レビュー時の差し戻し基準として機能する。
- **OpenAPI / フロント型同期**: ADR-012 の前提（`extra="forbid"` 等が正しく反映される）が成文化されたことで、ドリフト検知ロジックが本規約違反を間接的に検出できる構造になる。
- **テスト**: `extra="forbid"` 系の挙動は `TestRequestBodyContract` パターンに揃え、新規エンドポイントごとに最低 1 ケースの契約テストを追加する。

## 関連ドキュメント
- ADR-012: OpenAPI スキーマを活用したフロントエンド型同期戦略（本規約が前提を満たす）
- `docs/design/user-profile.md` §3.3: 本規約の最初の参照実装
- `api/schemas.py`: 本規約に従う既存スキーマ群
- `agent-rules/12-security-guidelines.md`: 入力検証方針の上位ルール
