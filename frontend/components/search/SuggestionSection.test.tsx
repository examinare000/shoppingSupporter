/**
 * SuggestionSection コンポーネントのテスト
 *
 * 検証対象:
 *   - ローディング状態: SWR がフェッチ中のスケルトン表示
 *   - buy_now 状態: 緑バッジ「今買う」と rationale の表示
 *   - wait 状態: 黄バッジ「待つ」・rationale・予想節約額の表示
 *   - URL 構築: buildSuggestionUrl が生成する正しいパスにフェッチする
 *
 * Why ProductDossier.test.tsx と分離するか:
 *   SuggestionSection は useSWR を使用するためフェッチモックが必要。
 *   ProductDossier の既存テストは SWR を使わないため、
 *   SuggestionSection を統合すると既存テストが壊れる。
 *   責務を分離してモックの影響範囲を最小化する。
 *
 * SWR のモック戦略:
 *   global.fetch を vi.stubGlobal でモックし、SWRConfig で
 *   テスト間のキャッシュ共有を防ぐ（provider: () => new Map()）。
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { SWRConfig } from 'swr';
import React from 'react';

import { SuggestionSection } from './SuggestionSection';
import type { Suggestion } from '@/types/product';

// ── ヘルパー ──────────────────────────────────────────────────────────────────

/**
 * SWR テスト用ラッパー。テスト間のキャッシュ隔離と
 * 不要なリバリデーション（focus/reconnect）を無効化する。
 */
function renderWithSWR(ui: React.ReactElement) {
  return render(
    <SWRConfig
      value={{
        provider: () => new Map(),
        dedupingInterval: 0,
        focusThrottleInterval: 0,
        errorRetryCount: 0,
        revalidateOnFocus: false,
        revalidateOnReconnect: false,
      }}
    >
      {ui}
    </SWRConfig>,
  );
}

// ── フィクスチャ ──────────────────────────────────────────────────────────────

const BUY_NOW_SUGGESTION: Suggestion = {
  productId: 'p-001',
  action: 'buy_now',
  rationale: '現在は過去の中央値以下の価格です。今が買い時です。',
  currentBestEffectivePrice: 9000,
  expectedSaleEffectivePrice: null,
  estimatedSaving: null,
  nextSaleDate: null,
  nextSaleCampaign: null,
};

const WAIT_SUGGESTION: Suggestion = {
  productId: 'p-001',
  action: 'wait',
  rationale: '近日中にお買い物マラソンが予定されています。',
  currentBestEffectivePrice: 10000,
  expectedSaleEffectivePrice: 9000,
  estimatedSaving: 1000,
  nextSaleDate: '2026-05-15',
  nextSaleCampaign: 'お買い物マラソン',
};

// ── テスト ────────────────────────────────────────────────────────────────────

describe('SuggestionSection', () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  describe('ローディング状態', () => {
    it('フェッチ中はスケルトンを表示する', () => {
      // Given: fetch が永遠に pending のまま（ローディング状態を維持）
      vi.stubGlobal(
        'fetch',
        vi.fn().mockReturnValue(new Promise(() => {})),
      );

      renderWithSWR(<SuggestionSection productId="p-001" />);

      // Then: スケルトンが表示される
      expect(
        screen.getByTestId('suggestion-skeleton'),
      ).toBeInTheDocument();
    });
  });

  describe('buy_now 状態', () => {
    beforeEach(() => {
      vi.stubGlobal(
        'fetch',
        vi.fn().mockResolvedValue({
          ok: true,
          json: async () => BUY_NOW_SUGGESTION,
        }),
      );
    });

    it('「今買う」バッジを表示する', async () => {
      renderWithSWR(<SuggestionSection productId="p-001" />);

      await waitFor(() => {
        expect(screen.getByText('今買う')).toBeInTheDocument();
      });
    });

    it('rationale テキストを表示する', async () => {
      renderWithSWR(<SuggestionSection productId="p-001" />);

      await waitFor(() => {
        expect(
          screen.getByText(BUY_NOW_SUGGESTION.rationale),
        ).toBeInTheDocument();
      });
    });

    it('buy_now では予想節約額を表示しない', async () => {
      renderWithSWR(<SuggestionSection productId="p-001" />);

      await waitFor(() => {
        expect(screen.getByText('今買う')).toBeInTheDocument();
      });

      // 節約額テキストは存在しない
      expect(screen.queryByText(/予想節約額/)).not.toBeInTheDocument();
    });

    it('buy_now では「待つ」バッジを表示しない', async () => {
      renderWithSWR(<SuggestionSection productId="p-001" />);

      await waitFor(() => {
        expect(screen.getByText('今買う')).toBeInTheDocument();
      });

      expect(screen.queryByText('待つ')).not.toBeInTheDocument();
    });
  });

  describe('wait 状態', () => {
    beforeEach(() => {
      vi.stubGlobal(
        'fetch',
        vi.fn().mockResolvedValue({
          ok: true,
          json: async () => WAIT_SUGGESTION,
        }),
      );
    });

    it('「待つ」バッジを表示する', async () => {
      renderWithSWR(<SuggestionSection productId="p-001" />);

      await waitFor(() => {
        expect(screen.getByText('待つ')).toBeInTheDocument();
      });
    });

    it('rationale テキストを表示する', async () => {
      renderWithSWR(<SuggestionSection productId="p-001" />);

      await waitFor(() => {
        expect(
          screen.getByText(WAIT_SUGGESTION.rationale),
        ).toBeInTheDocument();
      });
    });

    it('予想節約額を表示する', async () => {
      renderWithSWR(<SuggestionSection productId="p-001" />);

      await waitFor(() => {
        // estimatedSaving = 1000 → ¥1,000 形式で表示される
        expect(screen.getByText(/¥1,000/)).toBeInTheDocument();
      });
    });

    it('予想節約額ラベルを表示する', async () => {
      renderWithSWR(<SuggestionSection productId="p-001" />);

      await waitFor(() => {
        expect(screen.getByText(/予想節約額/)).toBeInTheDocument();
      });
    });

    it('次回セール日を表示する', async () => {
      renderWithSWR(<SuggestionSection productId="p-001" />);

      await waitFor(() => {
        // nextSaleDate = '2026-05-15' が何らかの形式で表示される
        expect(
          screen.getByText(/2026[-/]05[-/]15|5月15日/),
        ).toBeInTheDocument();
      });
    });

    it('wait では「今買う」バッジを表示しない', async () => {
      renderWithSWR(<SuggestionSection productId="p-001" />);

      await waitFor(() => {
        expect(screen.getByText('待つ')).toBeInTheDocument();
      });

      expect(screen.queryByText('今買う')).not.toBeInTheDocument();
    });
  });

  describe('URL 構築', () => {
    it('productId を含む正しいサジェスト URL にフェッチする', async () => {
      const fetchMock = vi.fn().mockResolvedValue({
        ok: true,
        json: async () => BUY_NOW_SUGGESTION,
      });
      vi.stubGlobal('fetch', fetchMock);

      renderWithSWR(<SuggestionSection productId="p-test-123" />);

      await waitFor(() => {
        expect(fetchMock).toHaveBeenCalledWith(
          expect.stringContaining('/api/products/p-test-123/suggestion'),
          expect.anything(),
        );
      });
    });

    it('productId が変わると異なる URL にフェッチする', async () => {
      const fetchMock = vi.fn().mockResolvedValue({
        ok: true,
        json: async () => BUY_NOW_SUGGESTION,
      });
      vi.stubGlobal('fetch', fetchMock);

      const { rerender } = renderWithSWR(
        <SuggestionSection productId="product-aaa" />,
      );

      await waitFor(() => {
        expect(fetchMock).toHaveBeenCalledWith(
          expect.stringContaining('/api/products/product-aaa/suggestion'),
          expect.anything(),
        );
      });

      // productId を変更してリレンダリング
      rerender(
        <SWRConfig
          value={{
            provider: () => new Map(),
            dedupingInterval: 0,
            focusThrottleInterval: 0,
            errorRetryCount: 0,
            revalidateOnFocus: false,
            revalidateOnReconnect: false,
          }}
        >
          <SuggestionSection productId="product-bbb" />
        </SWRConfig>,
      );

      await waitFor(() => {
        expect(fetchMock).toHaveBeenCalledWith(
          expect.stringContaining('/api/products/product-bbb/suggestion'),
          expect.anything(),
        );
      });
    });
  });
});
