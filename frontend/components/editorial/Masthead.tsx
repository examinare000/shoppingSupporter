import Link from 'next/link';
import { Logo } from '@/components/branding/Logo';
import { RuledDivider } from './RuledDivider';

/**
 * 紙面ヘッダー。
 *
 * 設計意図:
 * - ロゴ（pricehack ワードマーク）+ 右側ナビ（Account / 日付）の構成。
 * - 日付は new Date() で動的に生成する。サーバーコンポーネントのため、
 *   Next.js はリクエスト時に評価する。静的生成ではビルド時刻が入るが許容範囲。
 * - Account リンクはプロフィールページへの最短経路。
 *   アイコンは使わず mono 小カプスのテキストリンクで紙面感を保つ。
 */
function buildDate(): string {
  const d = new Date();
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${y}.${m}.${day}`;
}

export function Masthead() {
  const today = buildDate();

  return (
    <header className="w-full bg-paper">
      <RuledDivider variant="single" />
      <div className="px-6 py-4 flex items-center justify-between gap-4">
        <Link
          href="/"
          aria-label="pricehack.net ホームへ"
          className="inline-flex hover:opacity-80 transition-opacity"
        >
          <Logo size="md" as="span" />
        </Link>

        <nav className="flex items-center gap-6" aria-label="サイトナビゲーション">
          <Link
            href="/profile"
            className="font-mono text-xs small-caps tracking-editorial text-ink-muted hover:text-ink transition-colors duration-150 group"
          >
            Account{' '}
            <span
              className="inline-block transition-transform duration-150 group-hover:translate-x-0.5"
              aria-hidden="true"
            >
              →
            </span>
          </Link>
          <span className="font-mono text-xs small-caps text-ink-muted tabular">
            {today}
          </span>
        </nav>
      </div>
      <RuledDivider variant="single" />
    </header>
  );
}
