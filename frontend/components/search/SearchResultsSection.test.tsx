import { describe, it, expect, vi } from 'vitest';
import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { SearchResultsSection } from './SearchResultsSection';
import type { Product, ImagePriority } from '@/types/product';

const PRIORITY: ImagePriority = ['amazon', 'rakuten', 'yahoo'];

/**
 * フィクスチャ設計（T-09 以降）:
 * ListingOut に price / pointRate が存在しないため、代替フィールドで設計する:
 *   effectivePriceAsc ソート → effectivePrice 昇順 (A < B)
 *   pointRateDesc ソート     → points 降順       (B > A)
 */

// product-A: 実質価格安い、ポイント少ない
const productA: Product = {
  id: 'p-a',
  name: 'Product A',
  description: null,
  imageUrl: 'https://img.example.com/a.jpg',
  tags: ['cat'],
  inStock: true,
  currentPrice: 1000,
  listings: [
    {
      siteType: 'amazon',
      siteProductId: 'A1',
      url: 'https://example.com/a1',
      points: 0,
      effectivePrice: 1000,
      breakdown: null,
    },
    {
      siteType: 'rakuten',
      siteProductId: 'A2',
      url: 'https://example.com/a2',
      points: 0,
      effectivePrice: 1100,
      breakdown: null,
    },
    {
      siteType: 'yahoo',
      siteProductId: 'A3',
      url: 'https://example.com/a3',
      points: 0,
      effectivePrice: 1200,
      breakdown: null,
    },
  ],
};

// product-B: 実質価格高い、ポイント多い
const productB: Product = {
  id: 'p-b',
  name: 'Product B',
  description: null,
  imageUrl: 'https://img.example.com/b.jpg',
  tags: ['cat'],
  inStock: true,
  currentPrice: 4900,
  listings: [
    {
      siteType: 'amazon',
      siteProductId: 'B1',
      url: 'https://example.com/b1',
      points: 100,
      effectivePrice: 4900,
      breakdown: null,
    },
    {
      siteType: 'rakuten',
      siteProductId: 'B2',
      url: 'https://example.com/b2',
      points: 100,
      effectivePrice: 5000,
      breakdown: null,
    },
    {
      siteType: 'yahoo',
      siteProductId: 'B3',
      url: 'https://example.com/b3',
      points: 100,
      effectivePrice: 5100,
      breakdown: null,
    },
  ],
};

const noopHandlers = {
  onMoveUp: () => {},
  onMoveDown: () => {},
  onResetPriority: () => {},
};

describe('SearchResultsSection', () => {
  it('件数表示が正しい', () => {
    render(
      <SearchResultsSection
        query="abc"
        products={[productA, productB]}
        priority={PRIORITY}
        {...noopHandlers}
      />,
    );
    expect(screen.getByText(/Hits 2 件/)).toBeInTheDocument();
    expect(screen.getByText(/"abc"/)).toBeInTheDocument();
  });

  it('0 件時は EmptyState を表示する', () => {
    render(
      <SearchResultsSection
        query="zzz"
        products={[]}
        priority={PRIORITY}
        {...noopHandlers}
      />,
    );
    expect(screen.getByText(/該当記事はありません/)).toBeInTheDocument();
  });

  it('SortControl 切替で表示順が変わる（実質価格昇順 → 還元率降順）', async () => {
    const user = userEvent.setup();
    render(
      <SearchResultsSection
        query="x"
        products={[productA, productB]}
        priority={PRIORITY}
        {...noopHandlers}
      />,
    );
    // 初期状態（effectivePriceAsc）: A の最安 effectivePrice(1000) < B の最安 effectivePrice(4900)
    let articles = screen.getAllByRole('article');
    expect(within(articles[0]!).getByRole('heading', { level: 2 })).toHaveTextContent(
      'Product A',
    );

    // 還元率降順に切替: B の最大 points(100) > A の最大 points(0) → B が先
    await user.click(screen.getByLabelText(/還元率 降順/));
    articles = screen.getAllByRole('article');
    expect(within(articles[0]!).getByRole('heading', { level: 2 })).toHaveTextContent(
      'Product B',
    );
  });

  it('priority と handlers が ImagePriorityControl に届いている', async () => {
    const onMoveUp = vi.fn();
    const onMoveDown = vi.fn();
    const onResetPriority = vi.fn();
    const user = userEvent.setup();
    render(
      <SearchResultsSection
        query="x"
        products={[productA]}
        priority={['rakuten', 'amazon', 'yahoo']}
        onMoveUp={onMoveUp}
        onMoveDown={onMoveDown}
        onResetPriority={onResetPriority}
      />,
    );
    // ImagePriorityControl は <details>/<summary> に包まれている。<summary> 要素を直接掴んで開く
    const summaries = document.querySelectorAll('summary');
    if (summaries.length > 0) {
      await user.click(summaries[0]!);
    }
    // 1番目（rakuten）を下へ → handler が呼ばれる
    await user.click(screen.getByRole('button', { name: 'Rakuten を下へ' }));
    expect(onMoveDown).toHaveBeenCalledWith('rakuten');
  });
});
