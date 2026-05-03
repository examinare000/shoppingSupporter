import type { Listing, SortKey } from '@/types/product';
import { calculateEffectivePrice } from '@/lib/pricing/effectivePrice';

/**
 * Listing 配列をソートする純粋関数。
 * Array.prototype.sort は in-place なので、コピーしてからソートすることで入力を保護する。
 * Array.prototype.sort は ECMAScript 2019 以降で安定ソートが保証されているため、
 * 同値時の入力順保持はそれに依存する。
 */
export function sortListings(listings: Listing[], key: SortKey): Listing[] {
  const copy = [...listings];
  copy.sort((a, b) => compareByKey(a, b, key));
  return copy;
}

function compareByKey(a: Listing, b: Listing, key: SortKey): number {
  if (key === 'effectivePriceAsc') {
    return calculateEffectivePrice(a) - calculateEffectivePrice(b);
  }
  if (key === 'priceAsc') {
    return a.price - b.price;
  }
  // pointRateDesc
  return b.pointRate - a.pointRate;
}
