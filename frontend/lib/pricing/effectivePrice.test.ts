import { describe, it, expect } from 'vitest';
import { calculateEffectivePrice } from '@/lib/pricing/effectivePrice';
import type { Listing } from '@/types/product';

/**
 * calculateEffectivePrice のテスト仕様（T-09 以降）
 *
 * 旧実装: price + shippingFee - points で算出（フロント計算）
 * 新実装: バックエンドが算出済みの ListingOut.effectivePrice をそのまま返す。
 *         null の場合のみ 0 を返す（Fail Fast の例外: バックエンドが未計算でも画面を壊さない）。
 */
const baseListing: Listing = {
  siteType: 'amazon',
  siteProductId: 'B000TEST',
  url: 'https://example.com/item',
  points: 100,
  effectivePrice: 900,
  breakdown: null,
};

describe('calculateEffectivePrice', () => {
  it('effectivePrice が正の数値のとき、その値をそのまま返す', () => {
    // Given: バックエンドが算出した effectivePrice = 900
    // When: calculateEffectivePrice を呼ぶ
    // Then: 900 が返る（フロントで再計算しない）
    expect(calculateEffectivePrice(baseListing)).toBe(900);
  });

  it('effectivePrice が 0 のとき 0 を返す', () => {
    // Given: 完全無料（effectivePrice = 0）
    const listing: Listing = { ...baseListing, effectivePrice: 0 };
    expect(calculateEffectivePrice(listing)).toBe(0);
  });

  it('effectivePrice が null のとき 0 を返す', () => {
    // Given: 未認証・プロフィール未設定のとき null が返る（T-08 仕様）
    const listing: Listing = { ...baseListing, effectivePrice: null };
    // Then: 画面が壊れないよう 0 で下限を切る
    expect(calculateEffectivePrice(listing)).toBe(0);
  });

  it('入力オブジェクトを変更しない（純粋関数）', () => {
    const listing: Listing = { ...baseListing };
    const snapshot = { ...listing };
    calculateEffectivePrice(listing);
    expect(listing).toEqual(snapshot);
  });
});
