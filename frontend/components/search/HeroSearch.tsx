import { SearchForm } from './SearchForm';

/**
 * トップ最上部のヒーロー検索領域。
 *
 * 設計意図:
 * - ページ全体の唯一の h1 として「Where To Buy That?」を据える。
 *   Masthead からタイトル h1 を取り除いた結果、ここがページの主見出しになる。
 * - 旧版にあった「Issue 0001 · Front Page」「実質価格特集 / Effective Price Edition」
 *   「Cross-merchant editorial price desk」「ドロップキャップ付きリード」は、
 *   検索前のトップ画面では装飾過多で視線が散るため削除。
 * - レイアウトは grid をやめ、縦積み中央寄せに変更。新聞の表紙ティザーのように、
 *   題字下に短い 1 文リードと検索フォームだけが落ちている構成にする。
 * - ヘッドラインの 1 文字ずつのスタッガー出現アニメーションは継承。
 */
interface HeroSearchProps {
  onSearch: (query: string) => void;
}

// 単語単位で span 化し animation-delay をズラす。
// 文字単位だと狭い表示幅で文字ごとに改行されて題字が崩れるため、
// 単語境界（スペース）でのみ折り返すよう inline-block を単語単位に変更している。
const HEADLINE_WORDS = ['Where', 'To', 'Buy', 'That?'];

export function HeroSearch({ onSearch }: HeroSearchProps) {
  return (
    <section className="px-6 pt-14 pb-12">
      <div className="max-w-3xl mx-auto text-center">

        {/* エディション表記 — 紙面の版数スタンプ */}
        <p
          className="hero-char font-mono text-[0.6rem] small-caps tracking-editorial text-ink-muted mb-7 opacity-0"
          style={{ animationDelay: '0ms' }}
          aria-hidden="true"
        >
          Vol. I &ensp;—&ensp; 実質価格横断比較
        </p>

        <h1
          aria-label="Where To Buy That?"
          className="font-display font-black tracking-tight leading-[0.95] text-ink break-normal"
          style={{ fontSize: 'clamp(48px, 7.5vw, 96px)' }}
        >
          {HEADLINE_WORDS.map((word, i) => (
            <span
              key={`${word}-${i}`}
              aria-hidden="true"
              className="inline-block hero-char mr-[0.25em] last:mr-0"
              style={{ animationDelay: `${(i + 1) * 90}ms` }}
            >
              {word}
            </span>
          ))}
        </h1>

        <p
          className="hero-char mt-8 font-serif text-base md:text-lg leading-relaxed text-ink-muted opacity-0"
          style={{ animationDelay: '500ms' }}
        >
          Amazon・楽天・Yahoo!ショッピングを横断し、送料・ポイントを差し引いた実質価格で比較する。
        </p>

        <div
          className="hero-char mt-10 text-left opacity-0"
          style={{ animationDelay: '600ms' }}
        >
          <SearchForm onSearch={onSearch} />
          <p className="mt-3 font-mono text-xs small-caps text-ink-muted/70">
            品名・ブランド・JAN で検索
          </p>
        </div>
      </div>

      {/*
       * ヒーロー文字のスタッガー出現。
       * Tailwind の任意 keyframes を CSS 変数で定義する代わりに、コンポーネント内の <style> で
       * keyframes を宣言する。グローバル CSS を汚さず、このコンポーネントに閉じる。
       * prefers-reduced-motion では animation を無効化し、opacity: 1 に強制して
       * テキストが不可視のまま残らないようにする。
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
        @media (prefers-reduced-motion: reduce) {
          .hero-char {
            opacity: 1 !important;
            transform: none !important;
            animation: none !important;
          }
        }
      `}</style>
    </section>
  );
}
