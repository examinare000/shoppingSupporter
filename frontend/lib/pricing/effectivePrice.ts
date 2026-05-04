import type { Listing } from '@/types/product';

/**
 * 実質支払額を算出する。
 * 表示上、ポイント還元が価格を上回って負数になる商品は不自然なので 0 で下限を切る。
 */
export function calculateEffectivePrice(listing: Listing): number {
  const raw = listing.price + listing.shippingFee - listing.points;
  if (raw < 0) return 0;
  return raw;
}
