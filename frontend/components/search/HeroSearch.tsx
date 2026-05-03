import { SearchForm } from './SearchForm';

/**
 * トップ最上部のヒーロー検索領域。
 *
 * 設計意図:
 * - ページ全体の唯一の h1 として「実質、いくら。」を据える。
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

// 「実質、いくら。」を 1 文字ずつ span に分割し、index ごとに animation-delay をズラす
const HEADLINE_CHARS = ['実', '質', '、', 'い', 'く', 'ら', '。'];

export function HeroSearch({ onSearch }: HeroSearchProps) {
  return (
    <section className="px-6 pt-16 pb-12">
      <div className="max-w-3xl mx-auto text-center">
        <h1
          aria-label="実質、いくら。"
          className="font-display font-black tracking-tightest leading-[0.85] text-ink"
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
        </h1>

        <p className="mt-8 font-serif text-base md:text-lg leading-relaxed text-ink-muted">
          Amazon・楽天・Yahoo!ショッピングを横断し、送料・ポイントを差し引いた実質価格で比較する。
        </p>

        <div className="mt-10 text-left">
          <SearchForm onSearch={onSearch} />
          <p className="mt-3 font-mono text-xs small-caps text-ink-muted/70">
            品名・ブランド・JAN で検索
          </p>
        </div>
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
