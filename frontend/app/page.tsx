'use client';

import { useMemo, useState } from 'react';
import { Logo } from '@/components/branding/Logo';
import { Masthead } from '@/components/editorial/Masthead';
import { RuledDivider } from '@/components/editorial/RuledDivider';
import { HeroSearch } from '@/components/search/HeroSearch';
import { SearchResultsSection } from '@/components/search/SearchResultsSection';
import { useImagePriority } from '@/lib/hooks/useImagePriority';
import { searchProducts } from '@/lib/mock/searchClient';

/**
 * トップページ。
 *
 * 構成判断:
 * - 検索前（query 空）は Masthead + HeroSearch + フッタのみのミニマル一面構成にする。
 *   理由: 旧版は検索前から全件結果を並べていたが、Masthead と HeroSearch との間で
 *   視覚的ノイズが多くなり「ダサい」状態だった。表紙ティザー風に、検索が起きてから
 *   結果セクションが現れる方が情報設計として整う。
 * - useImagePriority はクライアント側でしか動かないため、page.tsx に 'use client' を付ける。
 *   サーバーコンポーネント分割は今は不要（モック検索のため fetch 等の I/O も無く、
 *   全体が CSR で十分速い）。
 */
export default function HomePage() {
  const [query, setQuery] = useState('');
  const { priority, moveUp, moveDown, reset } = useImagePriority();

  // searchProducts は純粋関数。query 変更時のみ再計算する
  const results = useMemo(() => searchProducts(query), [query]);

  // 空クエリでは結果セクションを描画しない（検索前は表紙ティザーに徹する設計）
  const hasQuery = query !== '';

  return (
    <main className="relative z-10 min-h-screen">
      <div className="mx-auto max-w-screen-xl px-6">
        <Masthead />

        <HeroSearch onSearch={setQuery} />

        {hasQuery && (
          <>
            <RuledDivider variant="single" className="my-8" />
            <SearchResultsSection
              query={query}
              products={results}
              priority={priority}
              onMoveUp={moveUp}
              onMoveDown={moveDown}
              onResetPriority={reset}
            />
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
