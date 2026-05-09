/**
 * バックエンド API のエンドポイント契約を 1 箇所に集約する。
 *
 * 設計意図:
 * - パス文字列を呼び出し側に直書きさせず、本ファイルだけが「契約文字列」を知る正本となる。
 *   仕様（パス・クエリパラメータ名）が変わったときの修正点を局所化する。
 * - クエリ値のエンコーディングは encodeURIComponent（RFC3986 準拠）で行う。
 *   `+` ではなく `%20` で空白を表現するため、`URLSearchParams` ではなく明示エンコードを採用する。
 * - 暫定 SoT: ADR-005「`GET /api/products/search?q=...`」。バックエンド API 仕様書
 *   (`docs/design/backend-api-spec.md`) が確定したら、本ファイルの定数だけを差し替えれば追従できる。
 */

/** 商品検索エンドポイントの相対パス（クエリ文字列を含まない）。 */
export const PRODUCTS_SEARCH_PATH = '/api/products/search';

/** 検索クエリのパラメータ名。 */
export const PRODUCTS_SEARCH_QUERY_PARAM = 'q';

/**
 * 商品検索エンドポイントの URL を組み立てる純関数。
 *
 * 副作用は持たず、空クエリでもそのまま `?q=` 付きの URL を返す。
 * 「空クエリでは fetch を発火しない」分岐は呼び出し側（HomePage の SWR key）で扱う責務分離。
 */
export function buildProductsSearchUrl(query: string): string {
  return `${PRODUCTS_SEARCH_PATH}?${PRODUCTS_SEARCH_QUERY_PARAM}=${encodeURIComponent(query)}`;
}

/**
 * 価格履歴取得エンドポイントの URL を組み立てる純関数。
 */
export function buildProductHistoryUrl(id: string, days: number = 30): string {
  return `/api/products/${encodeURIComponent(id)}/history?days=${days}`;
}
