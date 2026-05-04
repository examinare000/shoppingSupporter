import { RuledDivider } from '@/components/editorial/RuledDivider';
import { MarginalNote } from '@/components/editorial/MarginalNote';

/**
 * 検索フェッチ失敗時のエラー表示。
 *
 * 設計意図:
 * - 既存 `EmptyState` と同じ「二重罫線で囲った特集枠」のトーンを採用し、紙面の整版感を保つ。
 * - リトライ導線はテキストリンクでなく `<button>` にする（押下で SWR の再検証 = mutate を呼ぶため、
 *   ナビゲーションではなく「動作」を意味する。a11y / セマンティクス両面で button が正しい）。
 * - 例外メッセージは欄外ノートに小さく出すに留める。本文は「読み込みに失敗しました。」を主役にし、
 *   ユーザーが取れる次の行動（リトライ）を最大化する。
 * - リトライボタンの命名は「リトライ」を含む文言で固定（テスト名 `/リトライ/` と整合）。
 */
interface SearchErrorStateProps {
  /** 直前のクエリ。検索文脈を失わずに再試行できるよう案内文に埋め込む。 */
  query: string;
  /** SWR のエラー値。詳細表示はメッセージ取得用途のみ。 */
  error: unknown;
  /** リトライボタン押下時のハンドラ。SWR の `mutate()` を呼ぶ前提。 */
  onRetry: () => void;
}

function describeError(error: unknown): string {
  if (error instanceof Error && error.message) return error.message;
  return '原因不明のエラーが発生しました';
}

export function SearchErrorState({ query, error, onRetry }: SearchErrorStateProps) {
  return (
    <section className="py-12">
      <RuledDivider variant="double" />
      <div className="px-6 py-10 text-center">
        <p className="font-mono text-xs small-caps text-vermilion mb-4">
          Press stopped — 印刷停止
        </p>
        <h2 className="font-display text-3xl tracking-tightish text-ink mb-3">
          読み込みに失敗しました。
        </h2>
        <p className="font-serif text-base text-ink-muted leading-relaxed max-w-prose mx-auto mb-6">
          検索ワード「<span className="font-bold text-ink">{query}</span>
          」の取得中に問題が発生しました。通信状況を確認のうえ、再度お試しください。
        </p>
        <button
          type="button"
          onClick={onRetry}
          className="font-mono text-sm small-caps text-ink hover:text-vermilion transition-colors border-b-2 border-rule hover:border-vermilion py-2 px-1 whitespace-nowrap"
        >
          リトライ <span aria-hidden="true">↻</span>
        </button>
      </div>
      <RuledDivider variant="double" />
      <div className="mt-4 px-6">
        <MarginalNote>詳細: {describeError(error)}</MarginalNote>
      </div>
    </section>
  );
}
