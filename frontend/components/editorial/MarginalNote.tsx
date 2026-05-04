import type { ReactNode } from 'react';

/**
 * 欄外ノート。新聞・雑誌の余白に置かれる編集者注を再現する。
 * 左に細い罫線を置き、本文より一段下のヒエラルキーであることを視覚的に示す。
 * Newsreader のイタリックを使うため font-serif italic を採用。
 */
interface MarginalNoteProps {
  children: ReactNode;
  className?: string;
}

export function MarginalNote({ children, className = '' }: MarginalNoteProps) {
  return (
    <aside
      className={`border-l border-rule pl-3 text-sm italic font-serif text-ink-muted leading-relaxed ${className}`.trim()}
    >
      {children}
    </aside>
  );
}
