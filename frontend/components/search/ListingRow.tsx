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

  return (
    <tr
      className={`border-b border-dashed border-rule${isCheapest ? ' border-l-2 border-vermilion' : ''}`}
    >
      <td className="py-2.5 pl-3 align-middle">
        <SiteGlyph
          site={listing.siteType as SiteType}
          className={isCheapest ? 'border-vermilion text-vermilion' : ''}
        />
      </td>
      <td className="py-2.5 px-3 text-right font-mono tabular text-xs text-ink-muted align-middle">
        − {formatPoints(listing.points ?? 0)}
      </td>
      <td
        className={`py-2.5 px-3 text-right font-mono tabular text-base font-bold align-middle ${
          isCheapest ? 'text-vermilion' : 'text-ink'
        }`}
      >
        {formatYen(effective)}
      </td>
      <td className="py-2.5 px-3 text-right align-middle">
        <a
          href={listing.url}
          target="_blank"
          rel="noopener noreferrer"
          className="font-mono text-[0.65rem] small-caps tracking-editorial text-ink-muted hover:text-vermilion transition-colors duration-100 whitespace-nowrap group/link"
        >
          商品ページへ{' '}
          <span
            className="inline-block transition-transform duration-100 group-hover/link:translate-x-0.5"
            aria-hidden="true"
          >
            →
          </span>
        </a>
      </td>
    </tr>
  );
}
