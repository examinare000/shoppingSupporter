'use client';

import type { SortKey } from '@/types/product';

/**
 * ソート条件を選択するラジオ群。
 *
 * 設計意図:
 * - <fieldset>/<legend> でグループ化し、スクリーンリーダーに「並び替え」のコンテキストを伝える
 * - ラベルは小カプス（小キャプス）で編集紙面の見出し感を与える
 * - 選択中の項目は朱色のアンダーラインで示す（紙面の校正記号風）
 */
interface SortControlProps {
  value: SortKey;
  onChange: (key: SortKey) => void;
}

const OPTIONS: { value: SortKey; label: string }[] = [
  { value: 'effectivePriceAsc', label: '実質価格 昇順' },
  { value: 'priceAsc', label: '価格 昇順' },
  { value: 'pointRateDesc', label: '還元率 降順' },
];

export function SortControl({ value, onChange }: SortControlProps) {
  return (
    <fieldset className="flex items-center gap-3">
      <legend className="font-mono text-xs small-caps text-ink-muted mr-2">
        並び替え:
      </legend>
      {OPTIONS.map((opt) => {
        const selected = value === opt.value;
        return (
          <label
            key={opt.value}
            className={`font-mono text-xs cursor-pointer ${
              selected
                ? 'text-vermilion border-b-2 border-vermilion pb-0.5'
                : 'text-ink-muted hover:text-ink'
            }`}
          >
            <input
              type="radio"
              name="sort"
              value={opt.value}
              checked={selected}
              onChange={() => onChange(opt.value)}
              className="sr-only"
            />
            {opt.label}
          </label>
        );
      })}
    </fieldset>
  );
}
