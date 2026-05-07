# ADR-012: OpenAPI スキーマを活用したフロントエンド型同期戦略

## ステータス
採用済み

## 背景
バックエンド（FastAPI/Python）とフロントエンド（Next.js/TypeScript）で異なる言語を採用しているため、API のリクエスト・レスポンスの型定義が二重管理になりやすく、実装の乖離による実行時エラーのリスクがある。特に Phase 1 の T-08 以降、複雑な `Listing` 型や `breakdown`（計算内訳）が導入されるため、手動での型同期は限界に近づいている。

## 決定
**FastAPI が自動生成する OpenAPI スキーマを正本とし、`openapi-typescript` を用いてフロントエンドの型定義を自動生成する。**

### 具体的なワークフロー
1.  **スキーマのエクスポート**:
    *   バックエンドの CI または開発コマンドにより、`openapi.json` をファイルとして出力する。
2.  **型生成**:
    *   `frontend/` ディレクトリにて `npm run gen:api` を実行し、`openapi-typescript` を介して `frontend/types/api.ts` を生成する。
3.  **型利用**:
    *   手書きの型定義（`frontend/types/product.ts` 等）を廃止し、生成された `api.ts` から必要な型（`Product`, `Listing` 等）を再エクスポートして利用する。
4.  **ドリフト検知**:
    *   CI において「スキーマの再生成と型生成」を行い、Git に差分が発生していないかチェックする。差分がある場合はビルドを失敗させ、型同期を強制する。

## 理由
- **単一の真実 (Single Source of Truth)**: FastAPI の Pydantic モデルがそのまま API 仕様とフロントエンドの型になるため、不整合が構造的に発生しなくなる。
- **開発効率**: バックエンド側でモデルを変更するだけで、フロントエンド側の型エラーとして即座に通知されるため、リファクタリングの安全性が向上する。
- **ドキュメントの副産物**: 正確な OpenAPI スキーマが維持されることで、Swagger UI 等のドキュメントも常に最新の状態に保たれる。

## 影響
- **ビルドプロセス**: フロントエンドのビルド前にバックエンドの型生成が必要になる（または生成物を Git 管理する）。
- **型の表現力**: Pydantic の `Field(alias=...)` や `extra="forbid"` 等の設定が正しく OpenAPI に反映されている必要がある。
- **フロントエンドの修正**: 既存の手書き型定義を生成された型に移行する作業が発生する（Phase 1 T-09）。

## 関連ドキュメント
- `docs/plans/phase1-foundation.md` (T-09)
- `docs/adr/005-mock-to-backend-migration.md`
- `frontend/package.json`
