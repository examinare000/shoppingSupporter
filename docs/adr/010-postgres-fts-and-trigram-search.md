# ADR-010: Postgres 全文検索 (FTS) と Trigram 類似度による商品検索の実装

## ステータス
採用済み

## 背景
`docs/prd/price-comparison.md` に定義された「商品検索と横断比較」要件において、キーワードによる柔軟な商品検索が求められている。当初は SQL の `ILIKE` による部分一致検索を検討していたが、以下の課題があった：
- **日本語検索の精度**: 単なる部分一致では、語順や助詞の有無に弱く、期待する結果が得られにくい。
- **誤字・脱字への耐性**: ユーザーが入力したキーワードに僅かな誤り（例: "strawbery" vs "strawberry"）がある場合、`ILIKE` ではヒットしない。
- **ランキング機能の欠如**: 検索結果が大量にある場合、関連性の高い順に並べる必要があるが、`ILIKE` では単純な一致・不一致しか判定できない。

## 決定
PostgreSQL (Neon) の標準機能である **全文検索 (Full-Text Search / FTS)** と **trigram 類似度 (`pg_trgm`)** を組み合わせた検索エンジンを実装する。

### 具体的な実装方針
1.  **FTS (`tsvector` + `websearch_to_tsquery`)**:
    *   商品名、説明文、タグを結合した `search_vector` カラムを `tsvector` 型で定義。
    *   GIN インデックスを付与し、高速な検索を可能にする。
    *   `websearch_to_tsquery` を用いて、ユーザーの自由入力クエリを安全かつ柔軟に解析する。
2.  **Trigram 類似度 (`pg_trgm`)**:
    *   `pg_trgm` 拡張を導入し、`similarity(column, query)` 関数を利用。
    *   FTS でヒットしないような僅かな誤字や、部分的な一致も拾えるようにする。
    *   閾値（`0.3`）を設け、関連性の低いノイズを排除する。
3.  **ハイブリッド・ランキング**:
    *   `ts_rank` (FTS の重要度) と `similarity` (類似度) を合算したスコアを算出。
    *   スコアの高い順に結果を並べることで、関連性の高い商品を上位に表示する。

## 理由
- **追加コストなし**: Neon (Postgres) の標準機能のみを利用するため、Elasticsearch や Algolia のような外部サービスの導入・運用コストが発生しない。
- **開発の単純化**: DB と検索エンジンが一体化しているため、データ同期（再インデックス）の管理が不要。
- **十分な機能性**: 数万件〜数百万件程度の商品データであれば、Postgres の FTS+GIN インデックスで十分に高速な応答（p95 < 500ms）が可能。

## 影響
- **マイグレーション**: `alembic/versions/0002_product_search_columns.py` で `pg_trgm` の有効化とインデックス作成が必要。
- **DB 負荷**: 全文検索用のインデックス更新により、データ挿入・更新時の負荷が僅かに上昇する。
- **日本語対応**: 現時点では `simple` 辞書（スペース区切り）ベースだが、将来的に形態素解析（`icu` 等）が必要になる可能性がある。

## 関連ドキュメント
- `docs/prd/price-comparison.md`
- `api/repositories/products.py`
- `alembic/versions/0002_product_search_columns.py`
