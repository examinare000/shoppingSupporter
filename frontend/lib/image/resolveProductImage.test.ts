import { describe, it, expect } from 'vitest';
import { resolveProductImage } from '@/lib/image/resolveProductImage';
import { DEFAULT_IMAGE_PRIORITY } from '@/lib/image/imagePriorityDefaults';
import type { ImagePriority, Listing, Product } from '@/types/product';

/**
 * resolveProductImage のテスト仕様（T-09 以降）
 *
 * 旧実装: ImagePriority の順に product.listings を走査し、最初に見つかった
 *         Listing.imageUrl を返す（per-listing 画像フォールバック）。
 *
 * 新実装: ProductSummary は imageUrl をプロダクトレベルで 1 件持つのみ。
 *         listings に imageUrl フィールドが存在しないため、product.imageUrl を直接返す。
 *         画像出典情報が API から提供されないため from は priority[0] を使用する。
 *
 * テスト対象の観点（plan.md §実装ガイドライン より）:
 *   1. product.imageUrl が null のとき null を返す
 *   2. product.imageUrl が文字列のとき { url, from: priority[0] } を返す
 *   3. priority[0] が変わると from が変わる
 *   4. product.listings の内容に関わらず product.imageUrl が参照される
 *   5. 空文字列は null 同様に扱う
 */

const baseListing: Listing = {
  siteType: 'amazon',
  siteProductId: 'A',
  url: 'https://example.com/a',
  points: 0,
  effectivePrice: 1000,
  breakdown: null,
};

const makeProduct = (imageUrl: string | null): Product => ({
  id: 'p1',
  name: 'テスト商品',
  description: null,
  imageUrl,
  tags: [],
  inStock: true,
  currentPrice: null,
  listings: [],
});

describe('resolveProductImage', () => {
  it('product.imageUrl が文字列のとき { url, from: priority[0] } を返す', () => {
    // Given: product レベルに画像がある
    const product = makeProduct('https://img/test.jpg');
    // When: デフォルト優先度 (amazon, rakuten, yahoo) を渡す
    const result = resolveProductImage(product, DEFAULT_IMAGE_PRIORITY);
    // Then: url は product.imageUrl、from は priority[0] = 'amazon'
    expect(result).toEqual({ url: 'https://img/test.jpg', from: 'amazon' });
  });

  it('product.imageUrl が null のとき null を返す', () => {
    const product = makeProduct(null);
    expect(resolveProductImage(product, DEFAULT_IMAGE_PRIORITY)).toBeNull();
  });

  it('product.imageUrl が空文字列のとき null を返す（空文字も「画像なし」として扱う）', () => {
    const product = makeProduct('');
    expect(resolveProductImage(product, DEFAULT_IMAGE_PRIORITY)).toBeNull();
  });

  it('priority[0] が変わると from が変わる', () => {
    // Given: Yahoo を最優先にした priority
    const priority: ImagePriority = ['yahoo', 'amazon', 'rakuten'];
    const product = makeProduct('https://img/test.jpg');
    const result = resolveProductImage(product, priority);
    // Then: from = priority[0] = 'yahoo'
    expect(result).toEqual({ url: 'https://img/test.jpg', from: 'yahoo' });
  });

  it('product.listings の内容に関わらず product.imageUrl が参照される', () => {
    // Why: ListingOut に imageUrl フィールドが存在しないため
    //      listings の中身を見ず product.imageUrl だけを使う実装を保証する
    const product: Product = {
      id: 'p1',
      name: 'テスト商品',
      description: null,
      imageUrl: 'https://img/product-level.jpg',
      tags: [],
      inStock: true,
      currentPrice: null,
      listings: [baseListing],
    };
    const result = resolveProductImage(product, DEFAULT_IMAGE_PRIORITY);
    expect(result).toEqual({ url: 'https://img/product-level.jpg', from: 'amazon' });
  });

  it('listings が空配列でも product.imageUrl があれば返す', () => {
    const product = makeProduct('https://img/test.jpg');
    // listings: [] （makeProduct のデフォルト）
    const result = resolveProductImage(product, DEFAULT_IMAGE_PRIORITY);
    expect(result).toEqual({ url: 'https://img/test.jpg', from: 'amazon' });
  });
});
