'use client';

import { useCallback, useEffect, useState } from 'react';
import type { ImagePriority, SiteType } from '@/types/product';
import {
  DEFAULT_IMAGE_PRIORITY,
  IMAGE_PRIORITY_STORAGE_KEY,
} from '@/lib/image/imagePriorityDefaults';

const VALID_SITES: ReadonlySet<SiteType> = new Set<SiteType>(['amazon', 'rakuten', 'yahoo']);

/**
 * 画像取得優先度の管理フック。
 *
 * 設計意図:
 * - サーバーサイドレンダリング時は localStorage 不在のため、初期値はデフォルトで render し、
 *   useEffect 内（クライアントマウント後）で復元する。これによりハイドレーション不一致を避ける
 * - 不正な保存値は黙って無視。エラーログを出してもユーザーに価値はないため
 * - 配列のバリデーションは「長さ3 / 重複なし / 全て VALID_SITES の要素」の3条件
 */
function isValidPriority(value: unknown): value is ImagePriority {
  if (!Array.isArray(value)) return false;
  if (value.length !== 3) return false;
  const seen = new Set<string>();
  for (const item of value) {
    if (typeof item !== 'string') return false;
    if (!VALID_SITES.has(item as SiteType)) return false;
    if (seen.has(item)) return false;
    seen.add(item);
  }
  return true;
}

function readFromStorage(): ImagePriority | null {
  if (typeof window === 'undefined') return null;
  try {
    const raw = window.localStorage.getItem(IMAGE_PRIORITY_STORAGE_KEY);
    if (raw === null) return null;
    const parsed: unknown = JSON.parse(raw);
    if (!isValidPriority(parsed)) return null;
    // ImagePriority は readonly tuple なので、検証後に as でキャスト
    return parsed as ImagePriority;
  } catch {
    // JSON.parse 失敗時はデフォルトに戻す（不正値で UI が壊れるのを防ぐ）
    return null;
  }
}

function writeToStorage(priority: ImagePriority): void {
  if (typeof window === 'undefined') return;
  try {
    window.localStorage.setItem(IMAGE_PRIORITY_STORAGE_KEY, JSON.stringify(priority));
  } catch {
    // QuotaExceeded 等の例外は無視。優先度はあくまで UX 上の好みであり、
    // 保存できなくてもアプリの主機能は損なわれない
  }
}

export interface UseImagePriorityResult {
  priority: ImagePriority;
  moveUp: (site: SiteType) => void;
  moveDown: (site: SiteType) => void;
  reset: () => void;
}

export function useImagePriority(): UseImagePriorityResult {
  const [priority, setPriority] = useState<ImagePriority>(DEFAULT_IMAGE_PRIORITY);

  // mount 後に保存値を復元。SSR 時は無効、CSR で初回 effect として走る
  useEffect(() => {
    const restored = readFromStorage();
    if (restored !== null) {
      setPriority(restored);
    }
  }, []);

  const moveUp = useCallback((site: SiteType) => {
    setPriority((prev) => {
      const idx = prev.indexOf(site);
      if (idx <= 0) return prev; // 先頭または存在しない場合は no-op
      const next = [...prev];
      // swap with previous
      const tmp = next[idx - 1];
      next[idx - 1] = next[idx]!;
      next[idx] = tmp!;
      const result = next as unknown as ImagePriority;
      writeToStorage(result);
      return result;
    });
  }, []);

  const moveDown = useCallback((site: SiteType) => {
    setPriority((prev) => {
      const idx = prev.indexOf(site);
      if (idx === -1 || idx >= prev.length - 1) return prev; // 末尾または存在しない場合は no-op
      const next = [...prev];
      const tmp = next[idx + 1];
      next[idx + 1] = next[idx]!;
      next[idx] = tmp!;
      const result = next as unknown as ImagePriority;
      writeToStorage(result);
      return result;
    });
  }, []);

  const reset = useCallback(() => {
    setPriority(DEFAULT_IMAGE_PRIORITY);
    writeToStorage(DEFAULT_IMAGE_PRIORITY);
  }, []);

  return { priority, moveUp, moveDown, reset };
}
