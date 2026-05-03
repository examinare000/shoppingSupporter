import { describe, it, expect } from 'vitest';
import { calculateEffectivePrice } from '@/lib/pricing/effectivePrice';
import type { Listing } from '@/types/product';

const baseListing: Listing = {
  site: 'amazon',
  siteProductId: 'B000TEST',
  url: 'https://example.com/item',
  price: 1000,
  shippingFee: 300,
  points: 100,
  pointRate: 0.01,
  inStock: true,
};

describe('calculateEffectivePrice', () => {
  it('通常ケース: 本体価格 + 送料 - ポイントが返る', () => {
    expect(calculateEffectivePrice(baseListing)).toBe(1200);
  });

  it('送料無料の場合は本体価格 - ポイントが返る', () => {
    const listing: Listing = { ...baseListing, shippingFee: 0 };
    expect(calculateEffectivePrice(listing)).toBe(900);
  });

  it('ポイントが価格を上回る場合は0を返す（負数を許容しない）', () => {
    const listing: Listing = { ...baseListing, price: 100, shippingFee: 0, points: 500 };
    expect(calculateEffectivePrice(listing)).toBe(0);
  });

  it('価格・送料・ポイントが全て0の場合は0を返す', () => {
    const listing: Listing = { ...baseListing, price: 0, shippingFee: 0, points: 0 };
    expect(calculateEffectivePrice(listing)).toBe(0);
  });

  it('入力オブジェクトを変更しない（純粋関数）', () => {
    const listing: Listing = { ...baseListing };
    const snapshot = { ...listing };
    calculateEffectivePrice(listing);
    expect(listing).toEqual(snapshot);
  });
});
