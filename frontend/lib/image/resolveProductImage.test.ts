import { describe, it, expect } from 'vitest';
import { resolveProductImage } from '@/lib/image/resolveProductImage';
import { DEFAULT_IMAGE_PRIORITY } from '@/lib/image/imagePriorityDefaults';
import type { ImagePriority, Listing, Product, SiteType } from '@/types/product';

const makeListing = (site: SiteType, imageUrl?: string): Listing => ({
  site,
  siteProductId: `${site}-id`,
  url: `https://example.com/${site}`,
  price: 1000,
  shippingFee: 0,
  points: 0,
  pointRate: 0,
  imageUrl,
  inStock: true,
});

const makeProduct = (listings: Listing[]): Product => ({
  id: 'p1',
  name: 'テスト商品',
  category: 'test',
  listings,
});

describe('resolveProductImage', () => {
  it('全 Listing に画像があればデフォルト優先度で Amazon を返す', () => {
    const product = makeProduct([
      makeListing('amazon', 'https://img/amazon.jpg'),
      makeListing('rakuten', 'https://img/rakuten.jpg'),
      makeListing('yahoo', 'https://img/yahoo.jpg'),
    ]);
    const result = resolveProductImage(product, DEFAULT_IMAGE_PRIORITY);
    expect(result).toEqual({ url: 'https://img/amazon.jpg', from: 'amazon' });
  });

  it('Amazon に画像が無い場合は Rakuten にフォールバックする', () => {
    const product = makeProduct([
      makeListing('amazon', undefined),
      makeListing('rakuten', 'https://img/rakuten.jpg'),
      makeListing('yahoo', 'https://img/yahoo.jpg'),
    ]);
    const result = resolveProductImage(product, DEFAULT_IMAGE_PRIORITY);
    expect(result).toEqual({ url: 'https://img/rakuten.jpg', from: 'rakuten' });
  });

  it('Amazon・Rakuten 両方欠落で Yahoo にフォールバックする', () => {
    const product = makeProduct([
      makeListing('amazon', undefined),
      makeListing('rakuten', undefined),
      makeListing('yahoo', 'https://img/yahoo.jpg'),
    ]);
    const result = resolveProductImage(product, DEFAULT_IMAGE_PRIORITY);
    expect(result).toEqual({ url: 'https://img/yahoo.jpg', from: 'yahoo' });
  });

  it('全 Listing で画像が欠落していれば null を返す', () => {
    const product = makeProduct([
      makeListing('amazon', undefined),
      makeListing('rakuten', undefined),
      makeListing('yahoo', undefined),
    ]);
    expect(resolveProductImage(product, DEFAULT_IMAGE_PRIORITY)).toBeNull();
  });

  it('カスタム優先度では Yahoo を最優先で返せる', () => {
    const priority: ImagePriority = ['yahoo', 'amazon', 'rakuten'];
    const product = makeProduct([
      makeListing('amazon', 'https://img/amazon.jpg'),
      makeListing('rakuten', 'https://img/rakuten.jpg'),
      makeListing('yahoo', 'https://img/yahoo.jpg'),
    ]);
    const result = resolveProductImage(product, priority);
    expect(result).toEqual({ url: 'https://img/yahoo.jpg', from: 'yahoo' });
  });

  it('listings が空配列なら null を返す', () => {
    const product = makeProduct([]);
    expect(resolveProductImage(product, DEFAULT_IMAGE_PRIORITY)).toBeNull();
  });

  it('優先サイトに該当する Listing が存在しなければ次の候補に進む', () => {
    // Amazon と Rakuten の Listing 自体が無く、Yahoo のみ
    const product = makeProduct([makeListing('yahoo', 'https://img/yahoo.jpg')]);
    const result = resolveProductImage(product, DEFAULT_IMAGE_PRIORITY);
    expect(result).toEqual({ url: 'https://img/yahoo.jpg', from: 'yahoo' });
  });

  it('imageUrl が空文字列の場合は欠落とみなし次の候補に進む', () => {
    const product = makeProduct([
      makeListing('amazon', ''),
      makeListing('rakuten', 'https://img/rakuten.jpg'),
      makeListing('yahoo', 'https://img/yahoo.jpg'),
    ]);
    const result = resolveProductImage(product, DEFAULT_IMAGE_PRIORITY);
    expect(result).toEqual({ url: 'https://img/rakuten.jpg', from: 'rakuten' });
  });
});
