import type { Listing } from '@/types/product';
import { calculateEffectivePrice } from '@/lib/pricing/effectivePrice';
import { formatYen, formatPoints } from '@/lib/format/numbers';
import { SiteGlyph } from '@/components/icons/SiteGlyph';

/**
 * 1サイトの出品行。テーブル組みの 1 行として描画される。
 *
 * 設計意図:
 * - 数値カラムには tabular クラスで縦の桁を揃える（編集紙面の数字組版に倣う）
 * - 最安行（isCheapest）は左に朱色の縦罫線と朱の数字。最重要箇所だけに朱色を使う方針
 * - 在庫切れ行は opacity を落とし「在庫なし」キャプションを追加
 * - 外部リンクは target=_blank + rel="noopener noreferrer" で安全に開く
 */
interface ListingRowProps {
  listing: Listing;
  isCheapest?: boolean;
}

export function ListingRow({ listing, isCheapest = false }: ListingRowProps) {
  const effective = calculateEffectivePrice(listing);
  const outOfStock = !listing.inStock;

  // 最安行は朱色＋左に縦罫線。在庫切れは透過と打ち消し
  const rowAccentClass = isCheapest ? 'border-l-2 border-vermilion pl-3' : 'pl-3';
  const opacityClass = outOfStock ? 'opacity-60' : '';

  return (
    <tr
      className={`${rowAccentClass} ${opacityClass} border-b border-dashed border-rule`.trim()}
    >
      <td className="py-2 align-middle">
        <SiteGlyph site={listing.site} />
      </td>
      <td className="py-2 px-2 text-right font-mono tabular text-sm text-ink-muted">
        {formatYen(listing.price)}
      </td>
      <td className="py-2 px-2 text-right font-mono tabular text-xs text-ink-muted">
        {listing.shippingFee === 0 ? '送料無料' : `+ ${formatYen(listing.shippingFee)}`}
      </td>
      <td className="py-2 px-2 text-right font-mono tabular text-xs text-ink-muted">
        − {formatPoints(listing.points)}
      </td>
      <td
        className={`py-2 px-2 text-right font-mono tabular text-base font-bold ${
          isCheapest ? 'text-vermilion' : 'text-ink'
        }`}
      >
        {formatYen(effective)}
        {outOfStock && (
          <span className="block text-[10px] font-mono small-caps text-ink-muted">
            在庫なし
          </span>
        )}
      </td>
      <td className="py-2 px-2 text-right">
        <a
          href={listing.url}
          target="_blank"
          rel="noopener noreferrer"
          className="font-mono text-xs small-caps text-ink hover:text-vermilion underline underline-offset-4 decoration-rule whitespace-nowrap"
        >
          商品ページへ <span aria-hidden="true">→</span>
        </a>
      </td>
    </tr>
  );
}
