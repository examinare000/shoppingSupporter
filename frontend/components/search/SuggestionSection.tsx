/**
 * 商品詳細ページの「今買う / 待つ」サジェストセクション (T-21)。
 *
 * SWR で GET /api/products/{id}/suggestion を取得し、
 * ローディング中はスケルトン、取得後はバッジと根拠を表示する。
 *
 * 設計意図:
 * - バッジは設計システムのカラートークン（vermilion / mustard）でエディトリアル感を出す。
 *   汎用 Tailwind の green/yellow を使わない（紙面の色数制約、陳腐な配色回避）。
 * - ローディングスケルトンに rounded を使わない（紙面的矩形を維持）。
 * - エラー状態も MarginalNote スタイルで統一する。
 */
import useSWR from 'swr';
import React from 'react';

import type { Suggestion } from '@/types/product';
import { buildSuggestionUrl } from '@/lib/api/endpoints';
import { formatYen } from '@/lib/format/numbers';

interface SuggestionSectionProps {
  productId: string;
}

/** SWR フェッチャー: fetch → JSON
 *
 * Why 第2引数に空の RequestInit を渡すか:
 *   テストが `fetch(url, options)` の2引数形式を検証する。
 */
async function fetcher(url: string): Promise<Suggestion> {
  const res = await fetch(url, {});
  if (!res.ok) {
    throw new Error(`suggestion fetch failed: ${res.status}`);
  }
  return res.json() as Promise<Suggestion>;
}

export function SuggestionSection({ productId }: SuggestionSectionProps) {
  const url = buildSuggestionUrl(productId);
  const { data, error, mutate } = useSWR<Suggestion>(url, fetcher);

  if (error) {
    return (
      <div
        data-testid="suggestion-error"
        className="mt-5 border-l border-rule pl-3"
      >
        <p className="font-serif italic text-sm text-ink-muted">
          サジェストの取得に失敗しました。{' '}
          <button
            onClick={() => void mutate()}
            className="underline underline-offset-2 decoration-rule hover:text-vermilion transition-colors"
          >
            再試行 ↻
          </button>
        </p>
      </div>
    );
  }

  if (!data) {
    return (
      <div
        data-testid="suggestion-skeleton"
        className="w-full h-14 animate-pulse bg-paper-high mt-5"
      />
    );
  }

  const isBuyNow = data.action === 'buy_now';

  return (
    <section
      className="mt-5 pt-4"
      style={{ borderTop: '1px dashed var(--rule-line)' }}
    >
      <div className="flex flex-wrap items-baseline gap-x-4 gap-y-2">
        {isBuyNow ? (
          <span
            className="font-mono text-[0.65rem] small-caps tracking-editorial text-vermilion border border-vermilion px-2 py-0.5 leading-none shrink-0"
            aria-label="今買う"
          >
            今買う
          </span>
        ) : (
          <span
            className="font-mono text-[0.65rem] small-caps tracking-editorial text-mustard border border-mustard px-2 py-0.5 leading-none shrink-0"
            aria-label="待つ"
          >
            待つ
          </span>
        )}
        <p className="font-serif italic text-sm text-ink-muted leading-snug">
          {data.rationale}
        </p>
      </div>

      {!isBuyNow && (data.estimatedSaving != null || data.nextSaleDate != null) && (
        <dl className="mt-3 flex flex-wrap gap-x-6 gap-y-1 font-mono text-xs">
          {data.estimatedSaving != null && (
            <div className="flex items-baseline gap-2">
              <dt className="small-caps text-ink-muted">予想節約額</dt>
              <dd className="tabular text-mustard font-bold">
                {formatYen(data.estimatedSaving)}
              </dd>
            </div>
          )}
          {data.nextSaleDate != null && (
            <div className="flex items-baseline gap-2">
              <dt className="small-caps text-ink-muted">次回セール日</dt>
              <dd className="text-ink">{data.nextSaleDate}</dd>
            </div>
          )}
        </dl>
      )}
    </section>
  );
}
