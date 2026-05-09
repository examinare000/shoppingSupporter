import { render, screen } from '@testing-library/react';
import PriceChart from './PriceChart';
import { expect, it, describe, vi } from 'vitest';

// Recharts ResponsiveContainer needs mocking for jsdom as it relies on element dimensions
vi.mock('recharts', async () => {
  const original = (await vi.importActual('recharts')) as any;
  return {
    ...original,
    ResponsiveContainer: ({ children }: any) => <div data-testid="responsive-container">{children}</div>,
  };
});

describe('PriceChart', () => {
  it('renders "no data" message when data is empty', () => {
    render(<PriceChart data={[]} />);
    expect(screen.getByText('価格履歴データがありません')).toBeInTheDocument();
  });

  it('renders chart container when data is provided', () => {
    const data = [
      {
        date: '2024-05-01',
        sites: {
          amazon: { price: 1000, points: 10 },
          rakuten: { price: 1100, points: 110 },
        },
      },
    ];
    render(<PriceChart data={data} />);
    
    // "No data" message should not be present
    expect(screen.queryByText('価格履歴データがありません')).not.toBeInTheDocument();
    
    // Responsive container should be present
    expect(screen.getByTestId('responsive-container')).toBeInTheDocument();
  });
});
