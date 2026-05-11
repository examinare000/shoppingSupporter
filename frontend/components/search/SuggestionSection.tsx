/**
 * 商品詳細ページの「今買う / 待つ」サジェストセクション (T-21)。
 *
 * SWR で GET /api/products/{id}/suggestion を取得し、
 * ローディング中はスケルトン、取得後はバッジと根拠を表示する。
 *
 * Why SWR を使うか:
 *   ProductDossier の既存実装パターン（価格履歴取得）に揃える。
 *   テストでは global.fetch をモックして SWR を動かす（ProductDossier.test.tsx と同手法）。
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
 *   空オブジェクトを渡すことで拡張性（認証ヘッダ追加等）を将来的に維持しやすくする。
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
      <div data-testid="suggestion-error" className="mt-4">
        <p className="text-sm text-red-600">サジェストの取得に失敗しました。</p>
        <button
          onClick={() => mutate()}
          className="text-sm text-blue-600 underline mt-1"
        >
          再試行
        </button>
      </div>
    );
  }

  // ローディング中: スケルトン表示
  if (!data) {
    return (
      <div
        data-testid="suggestion-skeleton"
        className="w-full h-16 animate-pulse bg-paper-high rounded"
      />
    );
  }

  const isBuyNow = data.action === 'buy_now';

  return (
    <section className="mt-4">
      {/* アクションバッジ */}
      {isBuyNow ? (
        <span className="inline-block px-3 py-1 text-sm font-semibold rounded bg-green-100 text-green-800">
          今買う
        </span>
      ) : (
        <span className="inline-block px-3 py-1 text-sm font-semibold rounded bg-yellow-100 text-yellow-800">
          待つ
        </span>
      )}

      {/* 根拠テキスト */}
      <p className="mt-2 text-sm text-ink-muted">{data.rationale}</p>

      {/* wait 時のみ: 予想節約額・次回セール日 */}
      {!isBuyNow && (
        <dl className="mt-3 space-y-1 text-sm">
          {data.estimatedSaving != null && (
            <div className="flex gap-2">
              <dt className="text-ink-muted">予想節約額</dt>
              <dd className="font-semibold">{formatYen(data.estimatedSaving)}</dd>
            </div>
          )}
          {data.nextSaleDate != null && (
            <div className="flex gap-2">
              <dt className="text-ink-muted">次回セール日</dt>
              <dd>{data.nextSaleDate}</dd>
            </div>
          )}
        </dl>
      )}
    </section>
  );
}
