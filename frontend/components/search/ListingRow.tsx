import type { Listing, SiteType } from '@/types/product';
import { calculateEffectivePrice } from '@/lib/pricing/effectivePrice';
import { formatYen, formatPoints } from '@/lib/format/numbers';
import { SiteGlyph } from '@/components/icons/SiteGlyph';

/**
 * 1サイトの出品行。テーブル組みの 1 行として描画される。
 *
 * 設計意図:
 * - 数値カラムには tabular クラスで縦の桁を揃える（編集紙面の数字組版に倣う）
 * - 最安行（isCheapest）は左に朱色の縦罫線と朱の数字。最重要箇所だけに朱色を使う方針
 * - 外部リンクは target=_blank + rel="noopener noreferrer" で安全に開く
 *
 * T-09 以降: ListingOut に price / shippingFee / inStock が存在しないため
 *   「本体」「送料」列と在庫切れ表示を削除した。
 *   siteType は string のため SiteGlyph の型要件を満たすために SiteType へキャストする
 *   （バックエンドの SiteType Enum.value は 'amazon'/'rakuten'/'yahoo' の 3 値固定）。
 */
interface ListingRowProps {
  listing: Listing;
  isCheapest?: boolean;
}

export function ListingRow({ listing, isCheapest = false }: ListingRowProps) {
  const effective = calculateEffectivePrice(listing);

  const rowAccentClass = isCheapest ? 'border-l-2 border-vermilion pl-3' : 'pl-3';

  return (
    <tr
      className={`${rowAccentClass} border-b border-dashed border-rule`.trim()}
    >
      <td className="py-2 align-middle">
        <SiteGlyph site={listing.siteType as SiteType} />
      </td>
      <td className="py-2 px-2 text-right font-mono tabular text-xs text-ink-muted">
        − {formatPoints(listing.points ?? 0)}
      </td>
      <td
        className={`py-2 px-2 text-right font-mono tabular text-base font-bold ${
          isCheapest ? 'text-vermilion' : 'text-ink'
        }`}
      >
        {formatYen(effective)}
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
