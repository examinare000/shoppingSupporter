import { describe, it, expect, beforeEach } from 'vitest';
import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import HomePage from './page';

describe('HomePage（トップページ統合）', () => {
  beforeEach(() => {
    // localStorage の状態を明示的に初期化し、テスト間の useImagePriority 復元の影響を切る
    window.localStorage.clear();
  });

  it('初期表示で pricehack ロゴ・h1 ヘッドライン・検索フォームのみが見え、結果セクションは出ない', () => {
    render(<HomePage />);

    // Masthead: pricehack ワードマーク（Logo コンポーネント）
    // ロゴはテキスト構成のため getAllByText で取得（フッタにも並ぶため複数 hit を許容）
    expect(screen.getAllByText('pricehack').length).toBeGreaterThanOrEqual(1);

    // HeroSearch: ページ唯一の h1 として「Where To Buy That?」が aria-label で読める
    expect(
      screen.getByRole('heading', { level: 1, name: 'Where To Buy That?' }),
    ).toBeInTheDocument();

    // 検索フォームが配置されている
    expect(screen.getByRole('searchbox')).toBeInTheDocument();

    // 検索前: SearchResultsSection は描画されない
    // 結果セクション固有の "Hits N 件" 表記が無いこと、article 要素が 0 件であること
    expect(screen.queryByText(/Hits/)).not.toBeInTheDocument();
    expect(screen.queryAllByRole('article')).toHaveLength(0);
  });

  it('検索フォームに「イヤホン」を入力 → submit すると結果セクションに該当商品名が出る', async () => {
    const user = userEvent.setup();
    render(<HomePage />);

    const input = screen.getByRole('searchbox');
    await user.type(input, 'イヤホン');
    await user.click(screen.getByRole('button', { name: /検索する/ }));

    // ヒット件数とクエリ表示
    expect(screen.getByText(/Hits 1 件/)).toBeInTheDocument();
    expect(screen.getByText(/"イヤホン"/)).toBeInTheDocument();

    // 該当商品の見出し（モック p-001）が見える
    const articles = screen.getAllByRole('article');
    expect(articles).toHaveLength(1);
    expect(
      within(articles[0]!).getByRole('heading', { level: 2 }),
    ).toHaveTextContent(/ワイヤレスイヤホン Pro X3/);
  });
});
