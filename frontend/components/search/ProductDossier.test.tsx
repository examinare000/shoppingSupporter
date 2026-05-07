import { describe, it, expect } from 'vitest';
import { render, screen, within } from '@testing-library/react';
import { ProductDossier } from './ProductDossier';
import type { Product, ImagePriority } from '@/types/product';

const PRIORITY: ImagePriority = ['amazon', 'rakuten', 'yahoo'];

/**
 * フィクスチャ設計:
 * 実質価格が rakuten(8000) < amazon(10000) < yahoo(12000) となる構成。
 * effectivePrice フィールド（バックエンド算出済み）を直接セットすることで
 * sortListings → calculateEffectivePrice の連鎖をテスト可能にする。
 */
const product: Product = {
  id: 'p-test-dossier',
  name: '万年筆 Heritage 14K',
  description: null,
  imageUrl: 'https://img.example.com/product.jpg',
  tags: ['文具'],
  inStock: true,
  currentPrice: 8000,
  listings: [
    {
      siteType: 'amazon',
      siteProductId: 'A',
      url: 'https://example.com/amazon-pen',
      points: 0,
      effectivePrice: 10000,
      breakdown: null,
    },
    {
      siteType: 'rakuten',
      siteProductId: 'R',
      url: 'https://example.com/rakuten-pen',
      points: 1000,
      effectivePrice: 8000,
      breakdown: null,
    },
    {
      siteType: 'yahoo',
      siteProductId: 'Y',
      url: 'https://example.com/yahoo-pen',
      points: 0,
      effectivePrice: 12000,
      breakdown: null,
    },
  ],
};

describe('ProductDossier', () => {
  it('h2 に商品名が表示される', () => {
    render(<ProductDossier product={product} index={0} priority={PRIORITY} />);
    const heading = screen.getByRole('heading', { level: 2 });
    expect(heading).toHaveTextContent('万年筆 Heritage 14K');
  });

  it('序数が "{index + 1}." 形式で表示される', () => {
    render(<ProductDossier product={product} index={4} priority={PRIORITY} />);
    expect(screen.getByText('05.')).toBeInTheDocument();
  });

  it('出品行が実質価格昇順（effectivePrice 昇順）で表示される', () => {
    render(<ProductDossier product={product} index={0} priority={PRIORITY} />);
    // table の各 row 内に <a> があるので、リンクの順序で検証
    const rows = screen.getAllByRole('row');
    const links = rows
      .map((row) => within(row).queryByRole('link'))
      .filter((l): l is HTMLAnchorElement => l !== null);
    // 実質価格: rakuten(8000) < amazon(10000) < yahoo(12000)
    expect(links[0]?.href).toContain('rakuten-pen');
    expect(links[1]?.href).toContain('amazon-pen');
    expect(links[2]?.href).toContain('yahoo-pen');
  });

  it('全ての外部リンクに rel="noopener noreferrer" target="_blank" が付与される', () => {
    render(<ProductDossier product={product} index={0} priority={PRIORITY} />);
    const links = screen.getAllByRole('link');
    expect(links.length).toBeGreaterThanOrEqual(3);
    for (const link of links) {
      expect(link).toHaveAttribute('target', '_blank');
      expect(link.getAttribute('rel')).toMatch(/noopener/);
      expect(link.getAttribute('rel')).toMatch(/noreferrer/);
    }
  });
});
