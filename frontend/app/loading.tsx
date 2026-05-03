import { RuledDivider } from '@/components/editorial/RuledDivider';

/**
 * ルート loading UI。Next.js App Router がページ遷移時に自動で挿入する。
 *
 * 設計意図:
 * - 「組版中…」というエディトリアル文脈の言い回しで、機械的な「Loading…」を避ける
 * - シマー・スピナー類は使わない（紙面の整版風景に倣い、CSS-only の静的プレースホルダ）
 * - 罫線で囲み、本文プレースホルダは段組のような幅違いの線で表現する
 */
export default function Loading() {
  return (
    <main className="relative z-10 min-h-screen">
      <div className="mx-auto max-w-screen-xl px-6 py-12">
        <RuledDivider variant="double" />
        <p className="font-mono text-xs small-caps text-ink-muted text-center mt-4">
          Composing — 組版中…
        </p>
        <RuledDivider variant="single" className="mt-4" />

        <div className="mt-12 space-y-6">
          <div className="h-12 w-3/4 border-b-2 border-rule" aria-hidden="true" />
          <div className="h-4 w-full border-b border-rule" aria-hidden="true" />
          <div className="h-4 w-5/6 border-b border-rule" aria-hidden="true" />
          <div className="h-4 w-2/3 border-b border-rule" aria-hidden="true" />
        </div>

        <RuledDivider variant="dashed" className="my-12" />

        <div className="space-y-4">
          <div className="h-4 w-1/2 border-b border-rule" aria-hidden="true" />
          <div className="h-4 w-3/4 border-b border-rule" aria-hidden="true" />
          <div className="h-4 w-1/3 border-b border-rule" aria-hidden="true" />
        </div>
      </div>
    </main>
  );
}
