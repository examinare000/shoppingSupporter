import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { ProductThumbnail } from './ProductThumbnail';
import type { Product, ImagePriority } from '@/types/product';

const DEFAULT_PRIORITY: ImagePriority = ['amazon', 'rakuten', 'yahoo'];

const baseProduct: Product = {
  id: 'p-test',
  name: 'テスト商品',
  category: 'カテゴリ',
  listings: [
    {
      site: 'amazon',
      siteProductId: 'A',
      url: 'https://example.com/a',
      price: 1000,
      shippingFee: 0,
      points: 10,
      pointRate: 0.01,
      imageUrl: 'https://img.example.com/amazon.jpg',
      inStock: true,
    },
    {
      site: 'rakuten',
      siteProductId: 'R',
      url: 'https://example.com/r',
      price: 1100,
      shippingFee: 0,
      points: 110,
      pointRate: 0.10,
      imageUrl: 'https://img.example.com/rakuten.jpg',
      inStock: true,
    },
    {
      site: 'yahoo',
      siteProductId: 'Y',
      url: 'https://example.com/y',
      price: 1200,
      shippingFee: 0,
      points: 60,
      pointRate: 0.05,
      imageUrl: 'https://img.example.com/yahoo.jpg',
      inStock: true,
    },
  ],
};

describe('ProductThumbnail', () => {
  it('優先度先頭の Listing の imageUrl を src に使う', () => {
    render(<ProductThumbnail product={baseProduct} priority={DEFAULT_PRIORITY} />);
    const img = screen.getByRole('img') as HTMLImageElement;
    expect(img.src).toBe('https://img.example.com/amazon.jpg');
    expect(img.alt).toBe('テスト商品');
  });

  it('キャプションに出典サイトラベルが含まれる', () => {
    render(<ProductThumbnail product={baseProduct} priority={DEFAULT_PRIORITY} />);
    expect(screen.getByText(/Photo: Amazon/)).toBeInTheDocument();
  });

  it('カスタム priority で出典が変わる', () => {
    const customPriority: ImagePriority = ['yahoo', 'rakuten', 'amazon'];
    render(<ProductThumbnail product={baseProduct} priority={customPriority} />);
    const img = screen.getByRole('img') as HTMLImageElement;
    expect(img.src).toBe('https://img.example.com/yahoo.jpg');
    expect(screen.getByText(/Photo: Yahoo!/)).toBeInTheDocument();
  });

  it('全 listing 画像欠落のとき "No image on file" フォールバック表示', () => {
    const noImageProduct: Product = {
      ...baseProduct,
      listings: baseProduct.listings.map((l) => ({ ...l, imageUrl: undefined })),
    };
    render(<ProductThumbnail product={noImageProduct} priority={DEFAULT_PRIORITY} />);
    expect(screen.queryByRole('img')).not.toBeInTheDocument();
    expect(screen.getByText(/No image on file/)).toBeInTheDocument();
  });
});
