import useSWR from 'swr';
import type { Product, ImagePriority } from '@/types/product';
import type { components } from '@/types/api';
import { sortListings } from '@/lib/pricing/sortListings';
import { calculateEffectivePrice } from '@/lib/pricing/effectivePrice';
import { buildProductHistoryUrl } from '@/lib/api/endpoints';
import { Ordinal } from '@/components/editorial/Ordinal';
import { MarginalNote } from '@/components/editorial/MarginalNote';
import { RuledDivider } from '@/components/editorial/RuledDivider';
import { ProductThumbnail } from '@/components/results/ProductThumbnail';
import PriceChart from '@/components/results/PriceChart';
import { SITE_META } from '@/lib/site/siteMeta';
import { ListingRow } from './ListingRow';
import { SuggestionSection } from './SuggestionSection';

type ProductHistoryResponse = components['schemas']['ProductHistoryResponse'];

/**
 * 1 商品を 1 記事として描画する。新聞記事レイアウトを再現。
 *
 * 構成:
 *   [Ordinal]  [タグ small-caps]
 *   [h2 商品名 ディスプレイ大]
 *   [サムネイル | 比較テーブル]
 *   [単線罫線]
 *   [欄外ノート: 編集者注]
 *
 * 並び順: 実質価格昇順固定（このコンポーネントは「記事内のテーブル」であり、
 * セクション全体のソートとは別概念。記事内では常に「最安が上」が読者にとって自然）。
 *
 * T-09 以降: product.category は ProductSummary に存在しないため product.tags[0] で代替する。
 */
interface ProductDossierProps {
  product: Product;
  index: number;
  priority: ImagePriority;
}

export function ProductDossier({ product, index, priority }: ProductDossierProps) {
  const listings = product.listings ?? [];
  const sorted = sortListings(listings, 'effectivePriceAsc');
  // 最安価格を計算しておき、ListingRow に isCheapest を渡す
  // （ソート済み配列の先頭が最安だが、価格同値の場合に複数行を朱色化したいので effectivePrice 比較で判定する）
  const cheapestPrice =
    sorted.length > 0 ? calculateEffectivePrice(sorted[0]!) : Number.POSITIVE_INFINITY;

  // 価格履歴の取得 (Phase 2)
  const { data: historyData } = useSWR<ProductHistoryResponse>(
    buildProductHistoryUrl(product.id, 90) // 直近 90 日分を表示
  );

  // チャートに実際にプロットされるサイトだけ凡例に表示する。
  // PriceChart 側と同じロジック（histories に登場するサイトキーの Set）で導出する。
  const chartSites = historyData
    ? Array.from(new Set(historyData.histories.flatMap((e) => Object.keys(e.sites))))
        .filter((s) => s in SITE_META)
    : [];

  return (
    <article className="py-8">
      <header className="flex items-baseline gap-3 mb-2">
        <Ordinal n={index + 1} />
        <span className="font-mono text-xs small-caps text-ink-muted">
          {product.tags[0] ?? ''}
        </span>
      </header>

      <h2 className="font-display text-3xl md:text-5xl tracking-tightish leading-[1.05] text-ink mb-6">
        {product.name}
      </h2>

      <div className="grid grid-cols-1 md:grid-cols-[120px_1fr] gap-6 items-start">
        <ProductThumbnail product={product} priority={priority} size={120} />

        <table className="w-full border-collapse">
          <caption className="sr-only">出品比較表</caption>
          <thead>
            <tr className="border-b border-rule text-left">
              <th className="font-mono text-xs small-caps text-ink-muted py-1 pl-3">
                Site
              </th>
              <th className="font-mono text-xs small-caps text-ink-muted py-1 px-2 text-right">
                ポイント
              </th>
              <th className="font-mono text-xs small-caps text-ink-muted py-1 px-2 text-right">
                実質価格
              </th>
              <th className="font-mono text-xs small-caps text-ink-muted py-1 px-2 text-right">
                Link
              </th>
            </tr>
          </thead>
          <tbody>
            {sorted.map((listing) => (
              <ListingRow
                key={listing.siteType}
                listing={listing}
                isCheapest={calculateEffectivePrice(listing) === cheapestPrice}
              />
            ))}
          </tbody>
        </table>
      </div>

      <div className="mt-8">
        {/* チャートヘッダー: サイト凡例を右端に配置 */}
        <div className="flex items-baseline justify-between mb-3">
          <h3 className="font-mono text-[0.6rem] small-caps tracking-editorial text-ink-muted">
            Price History — 90 Days
          </h3>
          <div className="flex items-center gap-3" aria-hidden="true">
            {chartSites.map((site) => (
              <span key={site} className="flex items-center gap-1 font-mono text-[0.55rem] small-caps text-ink-muted">
                <span
                  className="inline-block w-4 h-px"
                  style={{ backgroundColor: SITE_META[site]!.color }}
                />
                {SITE_META[site]!.shortLabel}
              </span>
            ))}
          </div>
        </div>
        {historyData ? (
          <PriceChart data={historyData.histories} />
        ) : (
          /* チャートスケルトン — 紙面の升目感を出すため水平ストライプで構成 */
          <div className="w-full h-44 md:h-56 border-t border-rule overflow-hidden">
            {Array.from({ length: 5 }).map((_, i) => (
              <div
                key={i}
                className="border-b border-rule animate-pulse"
                style={{ height: '20%', opacity: 1 - i * 0.15 }}
              />
            ))}
          </div>
        )}
        <SuggestionSection productId={product.id} />
      </div>

      <div className="mt-6">
        <RuledDivider variant="dashed" />
        <div className="mt-4">
          <MarginalNote>
            編集者注: 楽天はSPU/お買い物マラソン併用で還元率が変動する。
            Amazonはプライム会員特典（送料無料・お急ぎ便）を反映済み。
            Yahoo!ショッピングはPayPay残高決済・LYPプレミアムでさらに加算される可能性がある。
          </MarginalNote>
        </div>
      </div>
    </article>
  );
}
