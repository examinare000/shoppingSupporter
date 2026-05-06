'use client';

import { useState } from 'react';
import useSWR from 'swr';
import { Logo } from '@/components/branding/Logo';
import { Masthead } from '@/components/editorial/Masthead';
import { RuledDivider } from '@/components/editorial/RuledDivider';
import { HeroSearch } from '@/components/search/HeroSearch';
import { SearchResultsSection } from '@/components/search/SearchResultsSection';
import { Spinner } from '@/components/feedback/Spinner';
import { SearchErrorState } from '@/components/feedback/SearchErrorState';
import { useImagePriority } from '@/lib/hooks/useImagePriority';
import { searchProducts } from '@/lib/api/searchClient';
import { buildProductsSearchUrl } from '@/lib/api/endpoints';
import type { ProductSearchEnvelope } from '@/types/product';

/**
 * トップページ。
 *
 * 構成判断:
 * - 検索前（query 空）は Masthead + HeroSearch + フッタのみのミニマル一面構成にする。
 *   理由: 旧版は検索前から全件結果を並べていたが、Masthead と HeroSearch との間で
 *   視覚的ノイズが多くなり「ダサい」状態だった。表紙ティザー風に、検索が起きてから
 *   結果セクションが現れる方が情報設計として整う。
 * - データ取得は SWR を採用。fetch ベースの非同期取得で、ローディング／エラー／成功の
 *   3 状態を `Spinner` / `SearchErrorState` / `SearchResultsSection` に分岐させる。
 *   SWR の `key` を「空クエリのとき null」にすることで、検索前の不要 fetch を抑止する。
 * - エラー時のリトライは `mutate()` を直接呼ぶ。同じ key で再検証が走るため、
 *   ユーザーがクエリを再入力する手間を省ける。
 *
 * T-09 以降: searchProducts は ProductSearchEnvelope を返す。
 *   data.items を SearchResultsSection に渡すことで商品リストを表示する。
 */
export default function HomePage() {
  const [query, setQuery] = useState('');
  const { priority, moveUp, moveDown, reset } = useImagePriority();

  // 空クエリでは fetch を発火させない（SWR の key=null によるスキップ）
  const hasQuery = query !== '';
  const swrKey = hasQuery ? buildProductsSearchUrl(query) : null;

  // fetcher は searchProducts（fetch ベース）。key は URL 文字列だが、searchProducts は
  // `query` 文字列を受け取る契約のため、closure 経由で渡す（HomePage の再描画ごとに
  // key と fetcher が同期して更新される）。
  const { data, error, isLoading, mutate } = useSWR<ProductSearchEnvelope>(
    swrKey,
    () => searchProducts(query),
  );

  return (
    <main className="relative z-10 min-h-screen">
      <div className="mx-auto max-w-screen-xl px-6">
        <Masthead />

        <HeroSearch onSearch={setQuery} />

        {hasQuery && (
          <>
            <RuledDivider variant="single" className="my-8" />
            {isLoading ? (
              <Spinner />
            ) : error ? (
              <SearchErrorState
                query={query}
                error={error}
                onRetry={() => {
                  // SWR の再検証を起動。同 key を維持したまま fetcher が再実行される
                  void mutate();
                }}
              />
            ) : data ? (
              <SearchResultsSection
                query={query}
                products={data.items}
                priority={priority}
                onMoveUp={moveUp}
                onMoveDown={moveDown}
                onResetPriority={reset}
              />
            ) : null}
          </>
        )}

        <RuledDivider variant="double" className="mt-16" />
        <footer className="px-6 py-6 flex items-center justify-between font-mono text-xs small-caps text-ink-muted">
          <Logo size="sm" withDomain />
          <span>2026</span>
        </footer>
      </div>
    </main>
  );
}
