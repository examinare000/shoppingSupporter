'use client';

import { useMemo, useState } from 'react';
import type { Product, ImagePriority, SortKey, SiteType } from '@/types/product';
import { calculateEffectivePrice } from '@/lib/pricing/effectivePrice';
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
 * - 商品ソートは「商品の最安実質価格 / 最安価格 / 最大還元率」を代表値として比較する。
 *   各商品の「最安/最大」を抽出してから product 同士を比較する 2 段階構成
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
 * priceAsc → 商品内の最安本体価格
 * pointRateDesc → 商品内の最大還元率
 */
function representativeValue(product: Product, key: SortKey): number {
  if (product.listings.length === 0) {
    // 出品が無い場合は末尾に送る（実質価格・価格は最大、還元率は最小）
    return key === 'pointRateDesc' ? -Infinity : Infinity;
  }
  if (key === 'effectivePriceAsc') {
    return Math.min(...product.listings.map((l) => calculateEffectivePrice(l)));
  }
  if (key === 'priceAsc') {
    return Math.min(...product.listings.map((l) => l.price));
  }
  // pointRateDesc
  return Math.max(...product.listings.map((l) => l.pointRate));
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
      <div className="flex flex-wrap items-center justify-between gap-4 mb-4">
        <p className="font-mono text-xs small-caps text-ink-muted">
          Hits {products.length} 件 / Query &quot;{query}&quot;
        </p>
        <SortControl value={sortKey} onChange={setSortKey} />
      </div>

      <details className="mb-6 group">
        <summary className="font-mono text-xs small-caps text-ink-muted cursor-pointer hover:text-ink select-none">
          Image Sourcing Policy <span aria-hidden="true">▾</span>
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
