import type { Metadata } from 'next';
import { fraunces, newsreader, jetbrainsMono } from './fonts';
import './globals.css';

export const metadata: Metadata = {
  title: 'pricehack — 実質価格で横断比較',
  description: 'Amazon・楽天・Yahoo!ショッピングの実質価格（送料・ポイント込み）を横断比較する pricehack.net。',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ja" className={`${fraunces.variable} ${newsreader.variable} ${jetbrainsMono.variable}`}>
      <body className="font-serif text-ink bg-paper antialiased">
        {children}
      </body>
    </html>
  );
}
