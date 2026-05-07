import type { ImagePriority, Product, ResolvedImage } from '@/types/product';

/**
 * 商品サムネイル画像を解決する。
 *
 * T-09 以降: ProductSummary は imageUrl をプロダクトレベルで 1 件持つのみ。
 * ListingOut に imageUrl フィールドが存在しないため、per-listing フォールバック探索は廃止した。
 * 画像出典情報が API から提供されないため、from は priority[0] を固定で使用する。
 *
 * 空文字列も「画像なし」として扱う（CMSから空文字が混入することがあるため）。
 */
export function resolveProductImage(
  product: Product,
  priority: ImagePriority,
): ResolvedImage | null {
  if (!product.imageUrl) return null;
  // ProductSummary は imageUrl を 1 件だけ持つため、from は priority[0] 固定
  return { url: product.imageUrl, from: priority[0] };
}
