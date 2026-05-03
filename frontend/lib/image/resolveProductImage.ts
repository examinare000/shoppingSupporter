import type { ImagePriority, Product, ResolvedImage } from '@/types/product';

/**
 * 優先度配列の先頭から順に、対応する Listing.imageUrl を探す。
 * 空文字列も「画像なし」として扱う（CMSから空文字が混入することがあるため）。
 */
export function resolveProductImage(
  product: Product,
  priority: ImagePriority,
): ResolvedImage | null {
  for (const site of priority) {
    const listing = product.listings.find((l) => l.site === site);
    if (!listing) continue;
    if (!listing.imageUrl) continue;
    return { url: listing.imageUrl, from: site };
  }
  return null;
}
