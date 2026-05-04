import type { Product } from '@/types/product';
import { buildProductsSearchUrl } from '@/lib/api/endpoints';

/**
 * 商品検索 API クライアント。
 *
 * 設計意図:
 * - 境界は `global.fetch`。HTTP 呼び出しの責務はここに閉じ、SWR には fetcher として渡す。
 * - エラーハンドリングは「Response.ok でなければ Error を throw、ネットワーク例外はそのまま伝播」。
 *   try/catch で握りつぶさないことで SWR にエラーを伝え、画面側でリトライ UI を出せるようにする
 *   （Fail Fast / 横断的関心事を API クライアント層に閉じ込める）。
 * - URL 組み立ては `buildProductsSearchUrl` に委譲する。検索パスやクエリパラメータ名の散在を防ぐ。
 * - レスポンス body は `Product[]` 直返しを前提とする。型ガードを挟まないのは、サーバー応答信頼の前提
 *   （バックエンドは OpenAPI で型同期する設計。ADR-005 §5）。
 */
export async function searchProducts(query: string): Promise<Product[]> {
  const response = await fetch(buildProductsSearchUrl(query), { method: 'GET' });

  if (!response.ok) {
    // status / statusText の両方を含めて、原因切り分けできるエラーメッセージにする
    throw new Error(
      `Failed to fetch products: ${response.status} ${response.statusText}`,
    );
  }

  return (await response.json()) as Product[];
}
