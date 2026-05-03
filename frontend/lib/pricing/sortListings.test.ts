import { describe, it, expect } from 'vitest';
import { sortListings } from '@/lib/pricing/sortListings';
import type { Listing } from '@/types/product';

const makeListing = (override: Partial<Listing>): Listing => ({
  site: 'amazon',
  siteProductId: 'X',
  url: 'https://example.com',
  price: 1000,
  shippingFee: 0,
  points: 0,
  pointRate: 0,
  inStock: true,
  ...override,
});

// effectivePrice = price + shippingFee - points
const a = makeListing({ siteProductId: 'A', price: 1000, shippingFee: 300, points: 100, pointRate: 0.01 }); // 1200
const b = makeListing({ siteProductId: 'B', price: 1100, shippingFee: 0, points: 110, pointRate: 0.10 }); //  990
const c = makeListing({ siteProductId: 'C', price: 1500, shippingFee: 0, points: 0, pointRate: 0.05 }); // 1500

describe('sortListings', () => {
  it('effectivePriceAsc: 実質価格の昇順に並ぶ', () => {
    const result = sortListings([a, b, c], 'effectivePriceAsc');
    expect(result.map((l) => l.siteProductId)).toEqual(['B', 'A', 'C']);
  });

  it('priceAsc: 本体価格の昇順に並ぶ', () => {
    const result = sortListings([c, a, b], 'priceAsc');
    expect(result.map((l) => l.siteProductId)).toEqual(['A', 'B', 'C']);
  });

  it('pointRateDesc: 還元率の降順に並ぶ', () => {
    const result = sortListings([a, b, c], 'pointRateDesc');
    expect(result.map((l) => l.siteProductId)).toEqual(['B', 'C', 'A']);
  });

  it('同値の場合は安定ソート（入力順を保つ）', () => {
    const x = makeListing({ siteProductId: 'X', price: 1000, pointRate: 0.05 });
    const y = makeListing({ siteProductId: 'Y', price: 1000, pointRate: 0.05 });
    const z = makeListing({ siteProductId: 'Z', price: 1000, pointRate: 0.05 });
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
