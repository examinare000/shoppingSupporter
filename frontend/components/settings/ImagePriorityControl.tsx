import type { ImagePriority, SiteType } from '@/types/product';
import { SITE_LABEL } from '@/lib/image/imagePriorityDefaults';

/**
 * 画像取得元の優先順位を編集するパネル。
 *
 * 設計意図:
 * - 編集記事における「編集方針」のメタ情報として位置付け、`Image Sourcing Policy` という
 *   英文小カプスのセクション見出しを与える
 * - ボタンは ↑↓ 一文字。罫線で囲うことで紙面の編集表記に寄せる
 * - aria-label は SITE_LABEL に基づいて「<サイト名> を上へ/下へ」とする
 */
interface ImagePriorityControlProps {
  priority: ImagePriority;
  onMoveUp: (site: SiteType) => void;
  onMoveDown: (site: SiteType) => void;
  onReset: () => void;
}

const SITE_ARIA_NAME: Record<SiteType, string> = {
  amazon: 'Amazon',
  rakuten: 'Rakuten',
  yahoo: 'Yahoo!ショッピング',
};

export function ImagePriorityControl({
  priority,
  onMoveUp,
  onMoveDown,
  onReset,
}: ImagePriorityControlProps) {
  return (
    <section className="border border-rule bg-paper-high p-4">
      <h3 className="font-mono text-xs small-caps text-ink mb-1">
        Image Sourcing Policy
      </h3>
      <p className="text-sm text-ink-muted font-serif italic mb-3">
        サムネイル画像の出典優先度。上にあるサイトから順に画像を採用する。
      </p>
      <ol className="space-y-1">
        {priority.map((site, index) => (
          <li
            key={site}
            className="flex items-center gap-3 py-1 border-t border-dashed border-rule first:border-t-0"
          >
            <span className="font-mono text-xs tabular text-ink-muted w-6">
              {index + 1}.
            </span>
            <span className="font-serif text-base text-ink flex-1">
              {SITE_LABEL[site]}
            </span>
            <button
              type="button"
              onClick={() => onMoveUp(site)}
              disabled={index === 0}
              aria-label={`${SITE_ARIA_NAME[site]} を上へ`}
              className="font-mono text-sm border border-rule px-2 py-0.5 hover:bg-paper disabled:opacity-30 disabled:cursor-not-allowed"
            >
              ↑
            </button>
            <button
              type="button"
              onClick={() => onMoveDown(site)}
              disabled={index === priority.length - 1}
              aria-label={`${SITE_ARIA_NAME[site]} を下へ`}
              className="font-mono text-sm border border-rule px-2 py-0.5 hover:bg-paper disabled:opacity-30 disabled:cursor-not-allowed"
            >
              ↓
            </button>
          </li>
        ))}
      </ol>
      <div className="mt-3 text-right">
        <button
          type="button"
          onClick={onReset}
          className="font-mono text-xs small-caps text-ink-muted hover:text-vermilion underline underline-offset-4 decoration-rule"
        >
          Reset to default
        </button>
      </div>
    </section>
  );
}
