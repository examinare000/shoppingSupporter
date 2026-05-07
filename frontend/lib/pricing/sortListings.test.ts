import { describe, it, expect } from 'vitest';
import { sortListings } from '@/lib/pricing/sortListings';
import type { Listing } from '@/types/product';

/**
 * sortListings のテスト仕様（T-09 以降）
 *
 * ListingOut には price / shippingFee / pointRate フィールドが存在しないため:
 *   priceAsc     → effectivePrice 昇順で代替（price フィールド不在）
 *   pointRateDesc → points 降順で代替（pointRate フィールド不在）
 * null 値の扱い:
 *   effectivePrice=null → Infinity として扱い末尾に送る
 *   points=null         → 0 として扱う
 */
const makeListing = (override: Partial<Listing>): Listing => ({
  siteType: 'amazon',
  siteProductId: 'X',
  url: 'https://example.com',
  points: 0,
  effectivePrice: 1000,
  breakdown: null,
  ...override,
});

// 実質価格: A=1200, B=990, C=1500
// ポイント:  A=10,   B=110, C=50
const a = makeListing({ siteProductId: 'A', effectivePrice: 1200, points: 10 });
const b = makeListing({ siteProductId: 'B', effectivePrice: 990, points: 110 });
const c = makeListing({ siteProductId: 'C', effectivePrice: 1500, points: 50 });

describe('sortListings', () => {
  it('effectivePriceAsc: 実質価格の昇順に並ぶ', () => {
    const result = sortListings([a, b, c], 'effectivePriceAsc');
    expect(result.map((l) => l.siteProductId)).toEqual(['B', 'A', 'C']);
  });

  it('priceAsc: effectivePrice の昇順に並ぶ（ListingOut に price フィールドが存在しないため effectivePrice で代替）', () => {
    const result = sortListings([c, a, b], 'priceAsc');
    expect(result.map((l) => l.siteProductId)).toEqual(['B', 'A', 'C']);
  });

  it('pointRateDesc: ポイント降順に並ぶ（ListingOut に pointRate が存在しないため points で代替）', () => {
    const result = sortListings([a, b, c], 'pointRateDesc');
    expect(result.map((l) => l.siteProductId)).toEqual(['B', 'C', 'A']);
  });

  it('effectivePrice が null の出品は末尾になる', () => {
    // null → Infinity 扱い → 最後
    const nullPrice = makeListing({ siteProductId: 'N', effectivePrice: null });
    const result = sortListings([nullPrice, b, a], 'effectivePriceAsc');
    expect(result.map((l) => l.siteProductId)).toEqual(['B', 'A', 'N']);
  });

  it('points が null の出品は pointRateDesc ソートで末尾になる', () => {
    // null → 0 扱い → a(10) より低い
    const nullPoints = makeListing({ siteProductId: 'N', points: null });
    const result = sortListings([nullPoints, a, b], 'pointRateDesc');
    expect(result.map((l) => l.siteProductId)).toEqual(['B', 'A', 'N']);
  });

  it('同値の場合は安定ソート（入力順を保つ）', () => {
    const x = makeListing({ siteProductId: 'X', effectivePrice: 1000 });
    const y = makeListing({ siteProductId: 'Y', effectivePrice: 1000 });
    const z = makeListing({ siteProductId: 'Z', effectivePrice: 1000 });
    const result = sortListings([x, y, z], 'priceAsc');
    expect(result.map((l) => l.siteProductId)).toEqual(['X', 'Y', 'Z']);
  });

  it('元配列を変更しない', () => {
    const input = [a, b, c];
    const snapshot = [...input];
    sortListings(input, 'effectivePriceAsc');
    expect(input).toEqual(snapshot);
  });

  it('空配列を渡すと空配列を返す', () => {
    expect(sortListings([], 'effectivePriceAsc')).toEqual([]);
  });

  it('1件のみの配列はそのまま返す', () => {
    const result = sortListings([a], 'effectivePriceAsc');
    expect(result).toEqual([a]);
  });
});
