/**
 * 検索フェッチ中のローディング表示。
 *
 * 設計意図:
 * - エディトリアルなトーンに合わせ、機械的な「Loading…」ではなく `Composing — 組版中…`
 *   を併記する（`app/loading.tsx` の文脈と整合）。
 * - スピナー本体は CSS-only。罫線色（--rule-line）の輪に朱色（--accent-vermilion）を
 *   一点だけ載せ、紙面色のトークン上で読める仕上がりにする。
 * - `prefers-reduced-motion` 抑制は globals.css の全アニメ無効化規則で吸収される。
 *   ここで個別に分岐は書かない（重複ロジックを避ける）。
 * - アクセシビリティ: `role="status"` と `aria-label` を付与し、読み上げ環境でも状態が伝わる
 *   （HomePage 側のテストもこの role を起点に検出する）。
 *   ラベルは検索ローディング専用の固定文言にし、props で外部から差し替える経路は持たない
 *   （単一用途コンポーネントのため、呼び出し側に判断を委ねない）。
 */
export function Spinner() {
  return (
    <section
      role="status"
      aria-label="検索結果を読み込み中"
      aria-live="polite"
      className="py-16 flex flex-col items-center justify-center gap-4"
    >
      <span
        aria-hidden="true"
        className="block h-8 w-8 rounded-full border-2 border-rule border-t-vermilion animate-spin"
      />
      <p className="font-mono text-xs small-caps text-ink-muted">
        Composing — 組版中…
      </p>
    </section>
  );
}
