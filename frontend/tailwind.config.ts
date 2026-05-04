import type { Config } from 'tailwindcss';

// エディトリアル/データジャーナリズム系の美的方向性に合わせた拡張。
// フォントは next/font/google で読み込んだ CSS 変数経由で参照する。
// カラーは globals.css の CSS 変数を参照することで、テーマ切替時の一元管理を可能にする。
const config: Config = {
  content: [
    './app/**/*.{ts,tsx,mdx}',
    './components/**/*.{ts,tsx,mdx}',
    './lib/**/*.{ts,tsx}',
  ],
  theme: {
    extend: {
      fontFamily: {
        // 本文は Newsreader（セリフ・読み物向け）
        serif: ['var(--font-newsreader)', 'serif'],
        // 見出しは Fraunces（編集的・有機的なディスプレイ用セリフ）
        display: ['var(--font-fraunces)', 'serif'],
        // 数字・キャプションは JetBrains Mono（タビュラー数字）
        mono: ['var(--font-jetbrains-mono)', 'monospace'],
      },
      colors: {
        ink: {
          DEFAULT: 'var(--ink-primary)',
          muted: 'var(--ink-secondary)',
        },
        paper: {
          DEFAULT: 'var(--paper-base)',
          high: 'var(--paper-high)',
        },
        rule: 'var(--rule-line)',
        vermilion: 'var(--accent-vermilion)',
        mustard: 'var(--accent-mustard)',
      },
      letterSpacing: {
        // 巨大ヘッドライン用にディスプレイセリフを締める
        tightest: '-0.04em',
        tightish: '-0.02em',
        // small-caps 等のキャプション用に開ける
        editorial: '0.08em',
      },
    },
  },
  plugins: [],
};

export default config;
