import type { Product } from '@/types/product';
import { MOCK_PRODUCTS } from '@/lib/mock/products';

/**
 * モック商品データに対する大文字小文字無視の部分一致検索。
 * 検索対象は name と category。
 * 純粋関数: MOCK_PRODUCTS は変更しない。空クエリは全件を返すことで、
 * 初期表示や「クリア時に全件に戻す」UI動線を簡潔に書けるようにする。
 */
export function searchProducts(query: string): Product[] {
  const normalized = query.trim().toLowerCase();
  if (normalized === '') return [...MOCK_PRODUCTS];

  return MOCK_PRODUCTS.filter((product) => {
    const haystack = `${product.name} ${product.category}`.toLowerCase();
    return haystack.includes(normalized);
  });
}
