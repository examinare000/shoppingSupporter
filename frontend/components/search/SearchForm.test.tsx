import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { SearchForm } from './SearchForm';

describe('SearchForm', () => {
  it('submit 時に trim 済みクエリで onSearch を呼ぶ', async () => {
    const onSearch = vi.fn();
    const user = userEvent.setup();
    render(<SearchForm onSearch={onSearch} />);

    const input = screen.getByRole('searchbox');
    await user.type(input, '  earbuds  ');
    await user.click(screen.getByRole('button', { name: /検索する/ }));

    expect(onSearch).toHaveBeenCalledTimes(1);
    expect(onSearch).toHaveBeenCalledWith('earbuds');
  });

  it('空白のみ入力では onSearch を呼ばない', async () => {
    const onSearch = vi.fn();
    const user = userEvent.setup();
    render(<SearchForm onSearch={onSearch} />);

    const input = screen.getByRole('searchbox');
    await user.type(input, '   ');
    await user.click(screen.getByRole('button', { name: /検索する/ }));

    expect(onSearch).not.toHaveBeenCalled();
  });

  it('initialQuery が input の初期値となる', () => {
    render(<SearchForm onSearch={() => {}} initialQuery="coffee" />);
    const input = screen.getByRole('searchbox') as HTMLInputElement;
    expect(input.value).toBe('coffee');
  });

  it('Enter キーで submit され onSearch が呼ばれる', async () => {
    const onSearch = vi.fn();
    const user = userEvent.setup();
    render(<SearchForm onSearch={onSearch} />);

    const input = screen.getByRole('searchbox');
    await user.type(input, 'pen{Enter}');

    expect(onSearch).toHaveBeenCalledWith('pen');
  });
});
