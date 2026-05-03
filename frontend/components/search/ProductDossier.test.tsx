import { describe, it, expect } from 'vitest';
import { render, screen, within } from '@testing-library/react';
import { ProductDossier } from './ProductDossier';
import type { Product, ImagePriority } from '@/types/product';

const PRIORITY: ImagePriority = ['amazon', 'rakuten', 'yahoo'];

// 実質価格が rakuten=8000 < amazon=10000 < yahoo=12000 となる構成。
// 並び替えロジックの結果を検証するための故意の差をつけている。
const product: Product = {
  id: 'p-test-dossier',
  name: '万年筆 Heritage 14K',
  category: '文具',
  listings: [
    {
      site: 'amazon',
      siteProductId: 'A',
      url: 'https://example.com/amazon-pen',
      price: 10000,
      shippingFee: 0,
      points: 0,
      pointRate: 0,
      imageUrl: 'https://img.example.com/amazon.jpg',
      inStock: true,
    },
    {
      site: 'rakuten',
      siteProductId: 'R',
      url: 'https://example.com/rakuten-pen',
      price: 9000,
      shippingFee: 0,
      points: 1000,
      pointRate: 0.10,
      imageUrl: 'https://img.example.com/rakuten.jpg',
      inStock: true,
    },
    {
      site: 'yahoo',
      siteProductId: 'Y',
      url: 'https://example.com/yahoo-pen',
      price: 12000,
      shippingFee: 0,
      points: 0,
      pointRate: 0,
      imageUrl: 'https://img.example.com/yahoo.jpg',
      inStock: true,
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

  it('出品行が実質価格昇順で表示される', () => {
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
