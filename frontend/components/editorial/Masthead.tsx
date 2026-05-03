import Link from 'next/link';
import { Logo } from '@/components/branding/Logo';
import { RuledDivider } from './RuledDivider';

/**
 * 紙面ヘッダー。
 *
 * 設計意図:
 * - サイト名（pricehack ワードマーク）と日付スタンプのみのミニマル構成。
 *   旧構成の「Edition No / Tokyo / 二重罫線 / キャッチフレーズ」は、ヒーローの h1 と
 *   役割が重複してダサくなるため一掃する（ページ全体の h1 はヒーローの「実質、いくら。」に集約）。
 * - ロゴは `<Link href="/">` でホームに遷移する。クリック可能な題字は新聞紙面の慣例から外れるが、
 *   Web のヘッダーとしては自然で発見性が高いトレードオフを優先する。
 * - 日付は固定値（モック段階）。将来は記事配信日のメタを差し込む予定地点。
 */
export function Masthead() {
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
        <span className="font-mono text-xs small-caps text-ink-muted">
          2026.05.03
        </span>
      </div>
      <RuledDivider variant="single" />
    </header>
  );
}
