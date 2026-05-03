import { describe, it, expect, beforeEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useImagePriority } from './useImagePriority';
import {
  DEFAULT_IMAGE_PRIORITY,
  IMAGE_PRIORITY_STORAGE_KEY,
} from '@/lib/image/imagePriorityDefaults';

beforeEach(() => {
  // jsdom 標準の localStorage を毎テスト前にクリア
  // （vitest の jsdom 環境はテスト間で window を共有するため）
  window.localStorage.clear();
});

describe('useImagePriority', () => {
  it('初期値はデフォルト優先度', () => {
    const { result } = renderHook(() => useImagePriority());
    expect(result.current.priority).toEqual(DEFAULT_IMAGE_PRIORITY);
  });

  it('有効な保存値があれば mount 時に復元する', () => {
    window.localStorage.setItem(
      IMAGE_PRIORITY_STORAGE_KEY,
      JSON.stringify(['yahoo', 'amazon', 'rakuten']),
    );
    const { result } = renderHook(() => useImagePriority());
    expect(result.current.priority).toEqual(['yahoo', 'amazon', 'rakuten']);
  });

  it('不正な JSON はデフォルトを維持する', () => {
    window.localStorage.setItem(IMAGE_PRIORITY_STORAGE_KEY, 'not-a-json');
    const { result } = renderHook(() => useImagePriority());
    expect(result.current.priority).toEqual(DEFAULT_IMAGE_PRIORITY);
  });

  it('長さが 3 でない配列はデフォルトを維持する', () => {
    window.localStorage.setItem(
      IMAGE_PRIORITY_STORAGE_KEY,
      JSON.stringify(['amazon', 'rakuten']),
    );
    const { result } = renderHook(() => useImagePriority());
    expect(result.current.priority).toEqual(DEFAULT_IMAGE_PRIORITY);
  });

  it('重複を含む配列はデフォルトを維持する', () => {
    window.localStorage.setItem(
      IMAGE_PRIORITY_STORAGE_KEY,
      JSON.stringify(['amazon', 'amazon', 'rakuten']),
    );
    const { result } = renderHook(() => useImagePriority());
    expect(result.current.priority).toEqual(DEFAULT_IMAGE_PRIORITY);
  });

  it('未知のサイトを含む配列はデフォルトを維持する', () => {
    window.localStorage.setItem(
      IMAGE_PRIORITY_STORAGE_KEY,
      JSON.stringify(['amazon', 'rakuten', 'mercari']),
    );
    const { result } = renderHook(() => useImagePriority());
    expect(result.current.priority).toEqual(DEFAULT_IMAGE_PRIORITY);
  });

  it('moveUp で順序が入れ替わり localStorage に永続化される', () => {
    const { result } = renderHook(() => useImagePriority());
    // ['amazon', 'rakuten', 'yahoo'] → rakuten を上へ → ['rakuten', 'amazon', 'yahoo']
    act(() => result.current.moveUp('rakuten'));
    expect(result.current.priority).toEqual(['rakuten', 'amazon', 'yahoo']);
    expect(JSON.parse(window.localStorage.getItem(IMAGE_PRIORITY_STORAGE_KEY)!)).toEqual(
      ['rakuten', 'amazon', 'yahoo'],
    );
  });

  it('先頭の moveUp は no-op', () => {
    const { result } = renderHook(() => useImagePriority());
    act(() => result.current.moveUp('amazon'));
    expect(result.current.priority).toEqual(DEFAULT_IMAGE_PRIORITY);
  });

  it('末尾の moveDown は no-op', () => {
    const { result } = renderHook(() => useImagePriority());
    act(() => result.current.moveDown('yahoo'));
    expect(result.current.priority).toEqual(DEFAULT_IMAGE_PRIORITY);
  });

  it('moveDown で順序が入れ替わる', () => {
    const { result } = renderHook(() => useImagePriority());
    // ['amazon', 'rakuten', 'yahoo'] → amazon を下へ → ['rakuten', 'amazon', 'yahoo']
    act(() => result.current.moveDown('amazon'));
    expect(result.current.priority).toEqual(['rakuten', 'amazon', 'yahoo']);
  });

  it('reset でデフォルトに戻り localStorage も更新される', () => {
    const { result } = renderHook(() => useImagePriority());
    act(() => result.current.moveDown('amazon'));
    expect(result.current.priority).not.toEqual(DEFAULT_IMAGE_PRIORITY);

    act(() => result.current.reset());
    expect(result.current.priority).toEqual(DEFAULT_IMAGE_PRIORITY);
    expect(JSON.parse(window.localStorage.getItem(IMAGE_PRIORITY_STORAGE_KEY)!)).toEqual([
      ...DEFAULT_IMAGE_PRIORITY,
    ]);
  });
});
