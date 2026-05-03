import { Fraunces, Newsreader, JetBrains_Mono } from 'next/font/google';

// 見出し用ディスプレイセリフ。opsz/SOFT 軸を可変利用してエディトリアル感を出す。
export const fraunces = Fraunces({
  subsets: ['latin'],
  variable: '--font-fraunces',
  display: 'swap',
  axes: ['opsz', 'SOFT'],
});

// 本文用セリフ。opsz 軸でサイズに応じた最適化を有効化。
export const newsreader = Newsreader({
  subsets: ['latin'],
  variable: '--font-newsreader',
  display: 'swap',
  axes: ['opsz'],
});

// 数字・キャプション用モノスペース。価格表示など tabular-nums と組み合わせる。
export const jetbrainsMono = JetBrains_Mono({
  subsets: ['latin'],
  variable: '--font-jetbrains-mono',
  display: 'swap',
});
