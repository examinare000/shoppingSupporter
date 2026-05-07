import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { ProductThumbnail } from './ProductThumbnail';
import type { Product, ImagePriority } from '@/types/product';

const DEFAULT_PRIORITY: ImagePriority = ['amazon', 'rakuten', 'yahoo'];

/**
 * フィクスチャ設計（T-09 以降）:
 * 旧実装: resolveProductImage は Listing.imageUrl（per-listing）を使用。
 * 新実装: resolveProductImage は Product.imageUrl（プロダクトレベル）を使用。
 *         from は priority[0] が使われる（API が画像の出典情報を返さないため）。
 */
const baseProduct: Product = {
  id: 'p-test',
  name: 'テスト商品',
  description: null,
  imageUrl: 'https://img.example.com/product.jpg',
  tags: ['カテゴリ'],
  inStock: true,
  currentPrice: 1000,
  listings: [
    {
      siteType: 'amazon',
      siteProductId: 'A',
      url: 'https://example.com/a',
      points: 10,
      effectivePrice: 990,
      breakdown: null,
    },
  ],
};

describe('ProductThumbnail', () => {
  it('product.imageUrl を img src に使う', () => {
    // Given: product.imageUrl に画像がある
    render(<ProductThumbnail product={baseProduct} priority={DEFAULT_PRIORITY} />);
    const img = screen.getByRole('img') as HTMLImageElement;
    // Then: product.imageUrl が src になる
    expect(img.src).toBe('https://img.example.com/product.jpg');
    expect(img.alt).toBe('テスト商品');
  });

  it('キャプションに priority[0] のサイトラベルが含まれる', () => {
    // Given: デフォルト優先度 (amazon, rakuten, yahoo)
    render(<ProductThumbnail product={baseProduct} priority={DEFAULT_PRIORITY} />);
    // Then: from = priority[0] = 'amazon' → "Photo: Amazon"
    expect(screen.getByText(/Photo: Amazon/)).toBeInTheDocument();
  });

  it('カスタム priority で from が変わる（priority[0] が from になる）', () => {
    // Given: Yahoo を最優先にした priority
    const customPriority: ImagePriority = ['yahoo', 'rakuten', 'amazon'];
    render(<ProductThumbnail product={baseProduct} priority={customPriority} />);
    // Then: from = priority[0] = 'yahoo' → "Photo: Yahoo!"
    expect(screen.getByText(/Photo: Yahoo!/)).toBeInTheDocument();
  });

  it('product.imageUrl が null のとき "No image on file" フォールバック表示', () => {
    // Given: プロダクトレベルに画像がない（listings の内容は関係しない）
    const noImageProduct: Product = {
      ...baseProduct,
      imageUrl: null,
    };
    render(<ProductThumbnail product={noImageProduct} priority={DEFAULT_PRIORITY} />);
    // Then: img タグは描画されず、フォールバック表示
    expect(screen.queryByRole('img')).not.toBeInTheDocument();
    expect(screen.getByText(/No image on file/)).toBeInTheDocument();
  });
});
