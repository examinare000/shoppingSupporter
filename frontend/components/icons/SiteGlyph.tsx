import type { SiteType } from '@/types/product';

/**
 * 画像アイコンを使わずテキストでサイトを示す紋章（グリフ）。
 *
 * 設計意図:
 * - エディトリアル系の整合のため、ロゴ画像の代わりにモノスペース略号を四角の罫線で囲う
 * - 二文字略号（Am / Rk / Yh）を採用。一文字 [A] [R] [Y] は識別性が低いため避けた
 * - サイト固有色は使わず、ink/vermilion の編集パレットに寄せる（紙面の色数を抑える）
 *   ただし最重要サイト（Amazon = アクセス頻度が最も高いと想定）には朱色で差別化
 */
interface SiteGlyphProps {
  site: SiteType;
  className?: string;
}

const SITE_GLYPH: Record<SiteType, string> = {
  amazon: 'Am',
  rakuten: 'Rk',
  yahoo: 'Yh',
};

const SITE_ARIA: Record<SiteType, string> = {
  amazon: 'Amazon',
  rakuten: 'Rakuten',
  yahoo: 'Yahoo!ショッピング',
};

export function SiteGlyph({ site, className = '' }: SiteGlyphProps) {
  return (
    <span
      role="img"
      aria-label={SITE_ARIA[site]}
      className={`inline-flex items-center justify-center font-mono text-xs font-bold border border-rule px-1.5 py-0.5 leading-none tracking-wider ${className}`.trim()}
    >
      {SITE_GLYPH[site]}
    </span>
  );
}
