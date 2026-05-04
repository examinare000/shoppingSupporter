import { describe, it, expect } from 'vitest';
import { formatYen, formatPoints, formatPercent } from '@/lib/format/numbers';

describe('formatYen', () => {
  it('整数を ¥ 付きカンマ区切りで返す', () => {
    expect(formatYen(1234)).toBe('¥1,234');
  });

  it('0 を ¥0 と返す', () => {
    expect(formatYen(0)).toBe('¥0');
  });

  it('10万円台を正しくカンマ区切りする', () => {
    expect(formatYen(123456)).toBe('¥123,456');
  });

  it('1000円ちょうどはカンマ位置が正しい', () => {
    expect(formatYen(1000)).toBe('¥1,000');
  });
});

describe('formatPoints', () => {
  it('数値に pt 単位を付けて返す', () => {
    expect(formatPoints(1234)).toBe('1,234 pt');
  });

  it('0 は 0 pt と返す', () => {
    expect(formatPoints(0)).toBe('0 pt');
  });

  it('大きな数値もカンマ区切りで返す', () => {
    expect(formatPoints(123456)).toBe('123,456 pt');
  });
});

describe('formatPercent', () => {
  it('0.01 を 1.0% と返す', () => {
    expect(formatPercent(0.01)).toBe('1.0%');
  });

  it('0 を 0.0% と返す', () => {
    expect(formatPercent(0)).toBe('0.0%');
  });

  it('0.105 を 10.5% と返す', () => {
    expect(formatPercent(0.105)).toBe('10.5%');
  });

  it('0.1 を 10.0% と返す（整数でも小数1位を表示）', () => {
    expect(formatPercent(0.1)).toBe('10.0%');
  });
});
