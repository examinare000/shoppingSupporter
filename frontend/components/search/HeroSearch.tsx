import { RuledDivider } from '@/components/editorial/RuledDivider';
import { SearchForm } from './SearchForm';

/**
 * トップ最上部のヒーロー検索領域。
 *
 * 設計意図:
 * - ディスプレイセリフでの巨大ヘッドライン「実質、いくら。」を主役に据える
 * - 右半分のリードでサービスのスコープを編集記事のリード文として説明する
 * - 下端に検索フォームをフルブリードで配置
 * - 上端に二重罫線、左肩に「ISSUE 0001」の小カプスで紙面の表紙感を作る
 * - ヘッドラインに staggered fadeInUp を仕込む（prefers-reduced-motion で無効化済み）
 */
interface HeroSearchProps {
  onSearch: (query: string) => void;
}

// 「実質、いくら。」を 1 文字ずつ span に分割し、index ごとに animation-delay をズラす
const HEADLINE_CHARS = ['実', '質', '、', 'い', 'く', 'ら', '。'];

export function HeroSearch({ onSearch }: HeroSearchProps) {
  return (
    <section className="px-6 pt-6 pb-12">
      <RuledDivider variant="double" />
      <div className="pt-4 pb-8 flex items-center justify-between">
        <span className="font-mono text-xs small-caps text-ink-muted">
          Issue 0001 · Front Page
        </span>
        <span className="font-mono text-xs small-caps text-ink-muted">
          実質価格特集 / Effective Price Edition
        </span>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-12 gap-8 items-end">
        <h2
          aria-label="実質、いくら。"
          className="md:col-span-8 font-display font-black tracking-tightest leading-[0.85] text-ink"
          style={{ fontSize: 'clamp(64px, 9vw, 132px)' }}
        >
          {HEADLINE_CHARS.map((char, i) => (
            <span
              key={`${char}-${i}`}
              aria-hidden="true"
              className="inline-block hero-char"
              style={{ animationDelay: `${i * 60}ms` }}
            >
              {char}
            </span>
          ))}
        </h2>

        <div className="md:col-span-4 font-serif text-base leading-relaxed text-ink-muted">
          <p className="mb-2 first-letter:font-display first-letter:text-5xl first-letter:font-bold first-letter:float-left first-letter:mr-2 first-letter:leading-none first-letter:text-ink">
            Amazon、楽天、Yahoo!ショッピング — 三紙横断で、本体価格・送料・ポイントを差し引いた「実質価格」を一覧化する。
          </p>
          <p className="font-mono text-xs small-caps text-ink-muted/70 mt-3">
            Cross-merchant editorial price desk
          </p>
        </div>
      </div>

      <div className="mt-12">
        <RuledDivider variant="single" className="mb-6" />
        <SearchForm onSearch={onSearch} />
      </div>

      {/*
       * ヒーロー文字のスタッガー出現。
       * Tailwind の任意 keyframes を CSS 変数で定義する代わりに、コンポーネント内の <style> で
       * keyframes を宣言する。グローバル CSS を汚さず、このコンポーネントに閉じる
       * （prefers-reduced-motion はグローバル CSS で全アニメーションを無効化済み）
       */}
      <style>{`
        @keyframes heroCharFadeIn {
          from { opacity: 0; transform: translateY(0.4em); }
          to   { opacity: 1; transform: translateY(0); }
        }
        .hero-char {
          opacity: 0;
          animation: heroCharFadeIn 0.6s ease-out forwards;
        }
      `}</style>
    </section>
  );
}
