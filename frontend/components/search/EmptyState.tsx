import { RuledDivider } from '@/components/editorial/RuledDivider';
import { MarginalNote } from '@/components/editorial/MarginalNote';

/**
 * 検索ヒット 0 件時の表示。
 *
 * 設計意図:
 * - 「ヒットなし」を新聞コラム風に「該当記事はありません」と表現する
 * - 二重罫線で囲い、紙面の特集枠を再現
 * - 欄外ノートでヒントを示し、ユーザーを次の検索行動へ誘導する
 */
interface EmptyStateProps {
  query: string;
}

export function EmptyState({ query }: EmptyStateProps) {
  return (
    <section className="py-12">
      <RuledDivider variant="double" />
      <div className="px-6 py-10 text-center">
        <p className="font-mono text-xs small-caps text-ink-muted mb-4">
          No matching dossier
        </p>
        <h2 className="font-display text-3xl tracking-tightish text-ink mb-3">
          該当記事はありません。
        </h2>
        <p className="font-serif text-base text-ink-muted leading-relaxed max-w-prose mx-auto">
          検索ワード「<span className="font-bold text-ink">{query}</span>
          」に一致する商品が見当たりません。別のキーワードをお試しください。
        </p>
      </div>
      <RuledDivider variant="double" />
      <div className="mt-4 px-6">
        <MarginalNote>
          ヒント: ジャンル名（イヤホン、コーヒー、文具）でも検索できます。
          ブランド名・型番のほか、JAN コードでの照会にも対応予定です。
        </MarginalNote>
      </div>
    </section>
  );
}
