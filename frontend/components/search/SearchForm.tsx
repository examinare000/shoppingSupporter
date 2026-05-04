'use client';

import { useState, type FormEvent, type KeyboardEvent } from 'react';

/**
 * エディトリアル系検索フォーム。
 *
 * 設計意図:
 * - background なし・下線罫線のみ。新聞紙面の余白に手書きする感覚を再現する
 * - submit ボタンは矢印付きテキストで、ボタンらしさを排除（紙面に印刷された案内に寄せる）
 * - 空白のみ入力は submit させない。誤って全件検索が走るのを防ぐ
 * - ESC でクエリをクリア。フォームの素早い破棄が一画面操作で完結する
 */
interface SearchFormProps {
  onSearch: (query: string) => void;
  initialQuery?: string;
}

export function SearchForm({ onSearch, initialQuery = '' }: SearchFormProps) {
  const [query, setQuery] = useState(initialQuery);

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const trimmed = query.trim();
    // 空白のみ入力は無視。意図しない全件検索を防ぐため、ここでガードする
    // （input の required では空白文字が通過してしまうため、JS 側でも検証する）
    if (trimmed === '') return;
    onSearch(trimmed);
  };

  const handleKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    // ESC でクリア。ヘッドライン下の検索 UI を素早く再利用するため
    if (event.key === 'Escape') {
      setQuery('');
    }
  };

  return (
    <form
      role="search"
      onSubmit={handleSubmit}
      className="w-full flex items-end gap-4"
    >
      <label htmlFor="search-query" className="sr-only">
        検索ワード
      </label>
      <input
        id="search-query"
        type="search"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder="ワード、ブランド、JANで検索…"
        autoComplete="off"
        spellCheck={false}
        className="flex-1 bg-transparent border-0 border-b-2 border-rule font-display text-2xl md:text-4xl tracking-tightish text-ink placeholder:text-ink-muted/60 focus:outline-none focus:border-vermilion py-2"
      />
      <button
        type="submit"
        className="font-mono text-sm small-caps text-ink hover:text-vermilion transition-colors border-b-2 border-rule hover:border-vermilion py-2 whitespace-nowrap"
      >
        検索する <span aria-hidden="true">→</span>
      </button>
    </form>
  );
}
