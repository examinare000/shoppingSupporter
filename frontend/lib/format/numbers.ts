/**
 * 数値表示のフォーマッタ。すべて純粋関数。
 * Node 環境の Intl は ja-JP の通貨記号として全角 `￥` を返すため、
 * 表示の一貫性とデザイン要件（半角 ¥）に合わせて半角へ正規化する。
 */

const yenFormatter = new Intl.NumberFormat('ja-JP', {
  style: 'currency',
  currency: 'JPY',
});

const integerFormatter = new Intl.NumberFormat('ja-JP');

const percentFormatter = new Intl.NumberFormat('ja-JP', {
  style: 'percent',
  minimumFractionDigits: 1,
  maximumFractionDigits: 1,
});

export function formatYen(n: number): string {
  return yenFormatter.format(n).replace('￥', '¥');
}

export function formatPoints(n: number): string {
  return `${integerFormatter.format(n)} pt`;
}

export function formatPercent(rate: number): string {
  return percentFormatter.format(rate);
}
