import type { Metadata } from 'next';
import { fraunces, newsreader, jetbrainsMono } from './fonts';
import './globals.css';

export const metadata: Metadata = {
  title: 'Shopping Dossier — 実質価格の編集部',
  description: 'Amazon・楽天・Yahoo!ショッピングの実質価格を、編集の眼で横断する。',
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
