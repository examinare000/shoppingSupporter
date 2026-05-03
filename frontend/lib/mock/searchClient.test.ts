import { describe, it, expect } from 'vitest';
import { searchProducts } from '@/lib/mock/searchClient';
import { MOCK_PRODUCTS } from '@/lib/mock/products';

describe('searchProducts', () => {
  it('空クエリの場合は全件を返す', () => {
    const result = searchProducts('');
    expect(result).toHaveLength(MOCK_PRODUCTS.length);
  });

  it('空白のみのクエリも全件を返す（trim される）', () => {
    const result = searchProducts('   ');
    expect(result).toHaveLength(MOCK_PRODUCTS.length);
  });

  it('商品名の部分一致でヒットする', () => {
    const result = searchProducts('イヤホン');
    expect(result.some((p) => p.name.includes('イヤホン'))).toBe(true);
    expect(result.length).toBeGreaterThan(0);
  });

  it('カテゴリの部分一致でヒットする', () => {
    const result = searchProducts('キッチン');
    expect(result.every((p) => p.category.includes('キッチン') || p.name.includes('キッチン'))).toBe(true);
    expect(result.length).toBeGreaterThan(0);
  });

  it('大文字小文字を無視して一致する', () => {
    const lower = searchProducts('wireless');
    const upper = searchProducts('WIRELESS');
    const mixed = searchProducts('Wireless');
    expect(lower.length).toBeGreaterThan(0);
    expect(lower).toEqual(upper);
    expect(lower).toEqual(mixed);
  });

  it('ヒット0件のクエリは空配列を返す', () => {
    const result = searchProducts('絶対に存在しない不思議な商品名');
    expect(result).toEqual([]);
  });

  it('前後の空白はトリムされる', () => {
    const trimmed = searchProducts('イヤホン');
    const padded = searchProducts('  イヤホン  ');
    expect(padded).toEqual(trimmed);
  });

  it('純粋関数: MOCK_PRODUCTS を変更しない', () => {
    const snapshot = JSON.parse(JSON.stringify(MOCK_PRODUCTS));
    searchProducts('イヤホン');
    searchProducts('');
    expect(MOCK_PRODUCTS).toEqual(snapshot);
  });
});
