import { RuledDivider } from './RuledDivider';

/**
 * 新聞題字風ヘッダー。ページ最上部に固定配置される編集部のクレジット領域。
 *
 * 構成:
 *   [二重罫線]
 *   [EDITION No. ... | TOKYO]    ← 上段ステータスバー（モノスペース小カプス）
 *   [ Shopping Dossier ]         ← 中央題字（巨大ディスプレイセリフ）
 *   [ — 実質価格を、編集の眼で。 — ]  ← サブヘッド
 *   [単線罫線]
 *
 * EDITION 番号と日付は固定値で運用する（モック段階では版の概念を持たないため）。
 * 将来的には CMS の発行日メタを差し込む箇所になる。
 */
export function Masthead() {
  return (
    <header className="w-full bg-paper">
      <RuledDivider variant="double" />
      <div className="px-6 pt-3 pb-1 flex items-center justify-between gap-4">
        <span className="font-mono text-xs small-caps text-ink-muted">
          Edition No. 0001
        </span>
        <span className="font-mono text-xs small-caps text-ink-muted">
          2026.05.03 — Tokyo
        </span>
      </div>
      <div className="px-6 pb-2 text-center">
        <h1 className="font-display font-black tracking-tightest text-[clamp(48px,9vw,112px)] leading-[0.9]">
          Shopping Dossier
        </h1>
        <p className="mt-1 font-mono text-xs small-caps text-ink-muted">
          — 実質価格を、編集の眼で。 —
        </p>
      </div>
      <RuledDivider variant="single" />
    </header>
  );
}
