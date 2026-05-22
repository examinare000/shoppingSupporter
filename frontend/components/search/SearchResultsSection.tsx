'use client';

import { useMemo, useState } from 'react';
import type { Product, ImagePriority, SortKey, SiteType } from '@/types/product';
import { ImagePriorityControl } from '@/components/settings/ImagePriorityControl';
import { RuledDivider } from '@/components/editorial/RuledDivider';
import { ProductDossier } from './ProductDossier';
import { SortControl } from './SortControl';
import { EmptyState } from './EmptyState';

/**
 * 検索結果セクション。トップページに 1 個だけ配置される想定。
 *
 * 設計意図:
 * - SortKey は内部 state で持つ。検索結果ごとにユーザーが並び順を切り替えるため
 * - ImagePriorityControl は <details>/<summary> で折りたたみ表示。デフォルトは閉じておき、
 *   興味のあるユーザーのみ展開する。設定パネルに紙面のスペースを取られないため
 * - 商品ソートは「商品の最安実質価格 / 最安価格 / 最大ポイント」を代表値として比較する。
 *   各商品の「最安/最大」を抽出してから product 同士を比較する 2 段階構成
 *
 * T-09 以降: ListingOut に price / pointRate が存在しないため代替フィールドを使う。
 *   priceAsc      → effectivePrice 最小値で代替
 *   pointRateDesc → points 最大値で代替
 */
interface SearchResultsSectionProps {
  query: string;
  products: Product[];
  priority: ImagePriority;
  onMoveUp: (site: SiteType) => void;
  onMoveDown: (site: SiteType) => void;
  onResetPriority: () => void;
}

/**
 * 商品の代表値（ソートキー）を計算する。
 * effectivePriceAsc → 商品内の最安実質価格
 * priceAsc          → 商品内の最安実質価格（ListingOut に price フィールドが存在しないため代替）
 * pointRateDesc     → 商品内の最大ポイント数（ListingOut に pointRate フィールドが存在しないため代替）
 */
function representativeValue(product: Product, key: SortKey): number {
  const listings = product.listings ?? [];
  if (listings.length === 0) {
    // 出品が無い場合は末尾に送る（実質価格・価格は最大、ポイントは最小）
    return key === 'pointRateDesc' ? -Infinity : Infinity;
  }
  if (key === 'effectivePriceAsc' || key === 'priceAsc') {
    // null は末尾に送る（sortListings と同じ null → Infinity 規約）
    // priceAsc は ListingOut に price フィールドが存在しないため effectivePrice で代替
    return Math.min(...listings.map((l) => l.effectivePrice ?? Infinity));
  }
  // pointRateDesc: ListingOut に pointRate が存在しないため points 降順で代替
  return Math.max(...listings.map((l) => l.points ?? 0));
}

function sortProducts(products: Product[], key: SortKey): Product[] {
  const copy = [...products];
  copy.sort((a, b) => {
    const va = representativeValue(a, key);
    const vb = representativeValue(b, key);
    return key === 'pointRateDesc' ? vb - va : va - vb;
  });
  return copy;
}

export function SearchResultsSection({
  query,
  products,
  priority,
  onMoveUp,
  onMoveDown,
  onResetPriority,
}: SearchResultsSectionProps) {
  const [sortKey, setSortKey] = useState<SortKey>('effectivePriceAsc');

  // useMemo は products / sortKey が変わったときだけ再ソートするため
  const sortedProducts = useMemo(
    () => sortProducts(products, sortKey),
    [products, sortKey],
  );

  if (products.length === 0) {
    return <EmptyState query={query} />;
  }

  return (
    <section className="px-6 py-8">
      <div className="flex flex-wrap items-baseline justify-between gap-4 mb-5">
        <div>
          {/*
           * 装飾的な大数字。aria-hidden で Testing Library と
           * スクリーンリーダーから除外し、下の p 要素に意味を集約する。
           * getByText は aria-hidden 要素を除外するため /Hits N 件/ テストに影響しない。
           */}
          <p
            className="font-display font-black text-4xl tabular text-ink leading-none mb-0.5"
            aria-hidden="true"
          >
            {products.length}
          </p>
          {/* テスト・a11y 用テキスト。getNodeText が直接テキストノードのみを読む仕様のため、
              子要素を持たない単純テキストとして維持する */}
          <p className="font-mono text-xs small-caps text-ink-muted">
            Hits {products.length} 件 / Query &quot;{query}&quot;
          </p>
        </div>
        <SortControl value={sortKey} onChange={setSortKey} />
      </div>

      <details className="mb-5 group">
        <summary className="inline-flex items-center gap-2 font-mono text-[0.65rem] small-caps tracking-editorial text-ink-muted cursor-pointer hover:text-ink select-none list-none">
          <span
            className="inline-block border border-rule px-1 py-0.5 text-[0.55rem] leading-none group-open:border-ink"
            aria-hidden="true"
          >
            ⋮
          </span>
          Image Sourcing Policy
        </summary>
        <div className="mt-3 max-w-md">
          <ImagePriorityControl
            priority={priority}
            onMoveUp={onMoveUp}
            onMoveDown={onMoveDown}
            onReset={onResetPriority}
          />
        </div>
      </details>

      <RuledDivider variant="single" />

      <div className="divide-y divide-rule">
        {sortedProducts.map((product, index) => (
          <ProductDossier
            key={product.id}
            product={product}
            index={index}
            priority={priority}
          />
        ))}
      </div>
    </section>
  );
}
