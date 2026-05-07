# API 型同期ガイド

FastAPI が自動生成する OpenAPI スキーマを正本として、`openapi-typescript` でフロントエンドの TypeScript 型定義を自動生成するパイプラインの説明。

**設計決定の背景**: [ADR-012: OpenAPI スキーマを活用したフロントエンド型同期戦略](../adr/012-openapi-type-sync-strategy.md)

---

## 型生成の手順

```bash
# 1. バックエンドを起動する
cd api && uvicorn main:app --reload

# 2. フロントエンドディレクトリに移動して型生成を実行する
cd frontend && npm run gen:api
# → frontend/types/api.ts が生成される

# 3. ビルドを確認する
npm run typecheck
```

バックエンドを起動できない環境では、Python スクリプトで OpenAPI JSON を直接取得できる:

```bash
python -c "from api.main import app; import json; print(json.dumps(app.openapi()))" > /tmp/openapi.json
cd frontend && npx openapi-typescript /tmp/openapi.json -o ./types/api.ts
```

---

## 型ドリフト検知

`npm run check:api-types` スクリプトで型ドリフトを検知する。

```bash
cd frontend && npm run check:api-types
```

動作:
1. `openapi-typescript` で `frontend/types/api.ts` を再生成する
2. `git diff --exit-code types/api.ts` で差分を確認する
3. 差分がある場合（バックエンドのスキーマ変更が型ファイルに反映されていない）はコマンドが非ゼロで終了する

**完了条件**: `npm run gen:api` 実行後に `git status frontend/types/api.ts` がクリーンであること。

---

## 手書きのまま残す型

`frontend/types/product.ts` では以下の型を手書きで維持する。これらはバックエンド API には存在せず、フロント表示ロジック専用の型のため。

| 型名 | 理由 |
|------|------|
| `SiteType` | バックエンドの `SiteType` Enum と対応するが、フロントで文字列リテラル型として定義する。`SiteGlyph` コンポーネントの prop 型に使用 |
| `ImagePriority` | 画像取得優先順位の UI 設定。バックエンドに相当する概念なし |
| `ResolvedImage` | 画像解決結果（URL + 出典サイト）。フロント描画専用 |
| `SortKey` | 商品ソートキー。フロント UI 専用 |

---

## 生成型の利用方法

`frontend/types/product.ts` から再エクスポートされているため、コンポーネントは `product.ts` からインポートする:

```typescript
import type { Listing, Product, ProductSearchEnvelope } from '@/types/product';
```

`api.ts` を直接インポートする必要はない。`components["schemas"]` アクセスは `product.ts` が隠蔽する。

---

## 注意事項

- `frontend/types/api.ts` は自動生成ファイルのため手書き変更禁止。`npm run gen:api` で上書きされる
- `openapi-typescript` は `devDependencies` に追加済み (`frontend/package.json`)
- バックエンドのスキーマを変更した場合は `npm run gen:api` を再実行してコミットする
