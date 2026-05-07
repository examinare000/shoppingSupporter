import { describe, it, expect, vi } from 'vitest';
import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { SearchResultsSection } from './SearchResultsSection';
import type { Product, ImagePriority } from '@/types/product';

const PRIORITY: ImagePriority = ['amazon', 'rakuten', 'yahoo'];

// product-A: 実質価格安い、還元率低い
const productA: Product = {
  id: 'p-a',
  name: 'Product A',
  category: 'cat',
  listings: [
    {
      site: 'amazon',
      siteProductId: 'A1',
      url: 'https://example.com/a1',
      price: 1000,
      shippingFee: 0,
      points: 0,
      pointRate: 0.01,
      imageUrl: 'https://img.example.com/a.jpg',
      inStock: true,
    },
    {
      site: 'rakuten',
      siteProductId: 'A2',
      url: 'https://example.com/a2',
      price: 1100,
      shippingFee: 0,
      points: 0,
      pointRate: 0.01,
      imageUrl: 'https://img.example.com/a2.jpg',
      inStock: true,
    },
    {
      site: 'yahoo',
      siteProductId: 'A3',
      url: 'https://example.com/a3',
      price: 1200,
      shippingFee: 0,
      points: 0,
      pointRate: 0.01,
      imageUrl: 'https://img.example.com/a3.jpg',
      inStock: true,
    },
  ],
};

// product-B: 実質価格高い、還元率高い
const productB: Product = {
  id: 'p-b',
  name: 'Product B',
  category: 'cat',
  listings: [
    {
      site: 'amazon',
      siteProductId: 'B1',
      url: 'https://example.com/b1',
      price: 5000,
      shippingFee: 0,
      points: 100,
      pointRate: 0.20,
      imageUrl: 'https://img.example.com/b.jpg',
      inStock: true,
    },
    {
      site: 'rakuten',
      siteProductId: 'B2',
      url: 'https://example.com/b2',
      price: 5100,
      shippingFee: 0,
      points: 100,
      pointRate: 0.20,
      imageUrl: 'https://img.example.com/b2.jpg',
      inStock: true,
    },
    {
      site: 'yahoo',
      siteProductId: 'B3',
      url: 'https://example.com/b3',
      price: 5200,
      shippingFee: 0,
      points: 100,
      pointRate: 0.20,
      imageUrl: 'https://img.example.com/b3.jpg',
      inStock: true,
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
        totalCount={2}
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
        totalCount={0}
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
        totalCount={2}
        priority={PRIORITY}
        {...noopHandlers}
      />,
    );
    // 初期状態（effectivePriceAsc）: A が先に出る
    let articles = screen.getAllByRole('article');
    expect(within(articles[0]!).getByRole('heading', { level: 2 })).toHaveTextContent(
      'Product A',
    );

    // 還元率降順に切替: B が先に出る
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
        totalCount={1}
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
