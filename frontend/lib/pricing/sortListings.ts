import type { Listing, SortKey } from '@/types/product';

/**
 * Listing 配列をソートする純粋関数。
 * Array.prototype.sort は in-place なので、コピーしてからソートすることで入力を保護する。
 * Array.prototype.sort は ECMAScript 2019 以降で安定ソートが保証されているため、
 * 同値時の入力順保持はそれに依存する。
 *
 * T-09 以降: ListingOut に price / pointRate フィールドが存在しないため代替を使う。
 *   priceAsc      → effectivePrice 昇順（price フィールド不在のため）
 *   pointRateDesc → points 降順（pointRate フィールド不在のため）
 */
export function sortListings(listings: Listing[], key: SortKey): Listing[] {
  const copy = [...listings];
  copy.sort((a, b) => compareByKey(a, b, key));
  return copy;
}

function compareByKey(a: Listing, b: Listing, key: SortKey): number {
  if (key === 'effectivePriceAsc' || key === 'priceAsc') {
    // null は「未計算」として末尾に送る（calculateEffectivePrice は表示用の ?? 0 を使うが、
    // ソートでは null を Infinity 扱いにして最後尾に配置する）
    // priceAsc は ListingOut に price フィールドが存在しないため effectivePrice で代替
    return (a.effectivePrice ?? Infinity) - (b.effectivePrice ?? Infinity);
  }
  // pointRateDesc: ListingOut に pointRate が存在しないため points 絶対値降順で代替
  return (b.points ?? 0) - (a.points ?? 0);
}
