import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ImagePriorityControl } from './ImagePriorityControl';
import type { ImagePriority } from '@/types/product';

const PRIORITY: ImagePriority = ['amazon', 'rakuten', 'yahoo'];

describe('ImagePriorityControl', () => {
  it('priority 順にサイト名が表示される', () => {
    render(
      <ImagePriorityControl
        priority={PRIORITY}
        onMoveUp={() => {}}
        onMoveDown={() => {}}
        onReset={() => {}}
      />,
    );
    const items = screen.getAllByRole('listitem');
    expect(items).toHaveLength(3);
    expect(items[0]).toHaveTextContent('Amazon');
    expect(items[1]).toHaveTextContent('Rakuten');
    expect(items[2]).toHaveTextContent('Yahoo!');
  });

  it('1 番目の ↑ ボタンと 3 番目の ↓ ボタンが disabled', () => {
    render(
      <ImagePriorityControl
        priority={PRIORITY}
        onMoveUp={() => {}}
        onMoveDown={() => {}}
        onReset={() => {}}
      />,
    );
    expect(screen.getByRole('button', { name: 'Amazon を上へ' })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Yahoo!ショッピング を下へ' })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Amazon を下へ' })).not.toBeDisabled();
    expect(screen.getByRole('button', { name: 'Rakuten を上へ' })).not.toBeDisabled();
  });

  it('↑ クリックで onMoveUp が site 名で呼ばれる', async () => {
    const onMoveUp = vi.fn();
    const user = userEvent.setup();
    render(
      <ImagePriorityControl
        priority={PRIORITY}
        onMoveUp={onMoveUp}
        onMoveDown={() => {}}
        onReset={() => {}}
      />,
    );
    await user.click(screen.getByRole('button', { name: 'Rakuten を上へ' }));
    expect(onMoveUp).toHaveBeenCalledWith('rakuten');
  });

  it('Reset クリックで onReset が呼ばれる', async () => {
    const onReset = vi.fn();
    const user = userEvent.setup();
    render(
      <ImagePriorityControl
        priority={PRIORITY}
        onMoveUp={() => {}}
        onMoveDown={() => {}}
        onReset={onReset}
      />,
    );
    await user.click(screen.getByRole('button', { name: /Reset to default/i }));
    expect(onReset).toHaveBeenCalledTimes(1);
  });
});
