'use client';

import { useMemo, useState } from 'react';
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
 * - 検索結果は「query が空でも全件表示」する。
 *   理由: エディトリアル誌面では「読む素材が常に紙面に乗っている」のが自然な体感であり、
 *   ユーザーが何もしていない状態でも編集記事として商品が並んでいる方がトーンに合う。
 *   フォーム submit 時はクエリで絞り込まれ、空文字 query では searchProducts が
 *   全件を返す挙動を利用する。
 * - useImagePriority はクライアント側でしか動かないため、page.tsx に 'use client' を付ける。
 *   サーバーコンポーネント分割は今は不要（モック検索のため fetch 等の I/O も無く、
 *   全体が CSR で十分速い）。
 */
export default function HomePage() {
  const [query, setQuery] = useState('');
  const { priority, moveUp, moveDown, reset } = useImagePriority();

  // searchProducts は純粋関数。query 変更時のみ再計算する
  const results = useMemo(() => searchProducts(query), [query]);

  return (
    <main className="relative z-10 min-h-screen">
      <div className="mx-auto max-w-screen-xl px-6">
        <Masthead />

        <HeroSearch onSearch={setQuery} />

        <RuledDivider variant="single" className="my-8" />

        <SearchResultsSection
          query={query}
          products={results}
          priority={priority}
          onMoveUp={moveUp}
          onMoveDown={moveDown}
          onResetPriority={reset}
        />

        <RuledDivider variant="double" className="mt-16" />
        <footer className="px-6 py-6 flex items-center justify-between font-mono text-xs small-caps text-ink-muted">
          <span>Shopping Dossier</span>
          <span>2026</span>
        </footer>
      </div>
    </main>
  );
}
