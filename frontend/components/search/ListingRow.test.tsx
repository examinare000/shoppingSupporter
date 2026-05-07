import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { ListingRow } from './ListingRow';
import type { Listing } from '@/types/product';

/**
 * フィクスチャ設計:
 * ListingRow の T-09 変更（points ?? 0 null ガード・isCheapest CSS 分岐）をカバーする。
 * SiteGlyph が <tr> の直下に存在するため、テーブル構造は省略して <table><tbody> でラップする
 * （jsdom 環境では <tr> を直接レンダリングすると警告が出る）。
 */
const baseListing: Listing = {
  siteType: 'amazon',
  siteProductId: 'A1',
  url: 'https://example.com/product',
  points: 500,
  effectivePrice: 9800,
  breakdown: null,
};

function renderRow(listing: Listing, isCheapest?: boolean) {
  return render(
    <table>
      <tbody>
        <ListingRow listing={listing} isCheapest={isCheapest} />
      </tbody>
    </table>,
  );
}

describe('ListingRow', () => {
  describe('points null ガード', () => {
    it('points が null のとき "− 0 pt" を表示する', () => {
      const listing: Listing = { ...baseListing, points: null };
      renderRow(listing);
      // listing.points ?? 0 → formatPoints(0) → "0 pt"
      expect(screen.getByText(/−\s*0\s*pt/)).toBeInTheDocument();
    });

    it('points が 0 のとき "− 0 pt" を表示する', () => {
      const listing: Listing = { ...baseListing, points: 0 };
      renderRow(listing);
      expect(screen.getByText(/−\s*0\s*pt/)).toBeInTheDocument();
    });
  });

  describe('isCheapest CSS 分岐', () => {
    it('isCheapest=true のとき <tr> に border-vermilion クラスが付く', () => {
      renderRow(baseListing, true);
      const row = screen.getByRole('row');
      expect(row.className).toContain('border-vermilion');
    });

    it('isCheapest=false のとき <tr> に border-vermilion クラスが付かない', () => {
      renderRow(baseListing, false);
      const row = screen.getByRole('row');
      expect(row.className).not.toContain('border-vermilion');
    });

    it('isCheapest=true のとき 実質価格テキストに text-vermilion クラスが付く', () => {
      renderRow(baseListing, true);
      // effectivePrice セル（¥9,800）の <td>
      const priceCells = document.querySelectorAll('td');
      // 3列目が価格セル（サイトグリフ / ポイント / 実質価格 / リンク）
      const priceCell = Array.from(priceCells).find((td) =>
        td.className.includes('font-bold'),
      );
      expect(priceCell).toBeDefined();
      expect(priceCell!.className).toContain('text-vermilion');
    });

    it('isCheapest=false のとき 実質価格テキストに text-ink クラスが付く', () => {
      renderRow(baseListing, false);
      const priceCells = document.querySelectorAll('td');
      const priceCell = Array.from(priceCells).find((td) =>
        td.className.includes('font-bold'),
      );
      expect(priceCell).toBeDefined();
      expect(priceCell!.className).toContain('text-ink');
    });
  });
});
