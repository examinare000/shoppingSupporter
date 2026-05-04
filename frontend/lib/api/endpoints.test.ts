import { describe, it, expect } from 'vitest';
import { buildProductsSearchUrl } from '@/lib/api/endpoints';

/**
 * 設計意図:
 * - エンドポイントの契約文字列（パス・クエリ）が 1 箇所（endpoints.ts）にまとまっていることを行動レベルで保証する。
 * - URL 構築の純関数だけを検証し、HTTP 呼び出しは searchClient のテストで扱う（責務分離）。
 * - 検索エンドポイントは ADR-005 / 計画レポートで `GET /api/products/search?q=...` を暫定採用。
 *   仕様確定時の差分は本テストの URL アサーションだけで吸収できるよう、この 1 ファイルに局所化する。
 */
describe('buildProductsSearchUrl', () => {
  it('英数字クエリで /api/products/search?q=<query> を返す', () => {
    // Given-When-Then: ASCII の query は encodeURIComponent でも変化しない
    expect(buildProductsSearchUrl('wireless')).toBe(
      '/api/products/search?q=wireless',
    );
  });

  it('日本語クエリは encodeURIComponent でエスケープされる', () => {
    // 日本語が URL 上で生のままにならないこと（パーセントエンコーディング必須）
    const url = buildProductsSearchUrl('イヤホン');
    expect(url).toBe(
      `/api/products/search?q=${encodeURIComponent('イヤホン')}`,
    );
    // 念のため: 生の日本語が混ざらないことを明示
    expect(url).not.toMatch(/イヤホン/);
  });

  it('空白を含むクエリは %20 にエンコードされる（+ ではない）', () => {
    // application/x-www-form-urlencoded ではなく RFC3986 準拠の encodeURIComponent を使う想定
    expect(buildProductsSearchUrl('wireless earbuds')).toBe(
      '/api/products/search?q=wireless%20earbuds',
    );
  });

  it('& = ? # などクエリ文字列の特殊文字をエスケープする', () => {
    // クエリパラメータ境界を破壊しないこと
    const raw = 'a&b=c?d#e';
    const url = buildProductsSearchUrl(raw);
    expect(url).toBe(`/api/products/search?q=${encodeURIComponent(raw)}`);
    // & = ? # が生のままで現れない（先頭の "?q=" 以外）
    const queryPart = url.slice('/api/products/search?q='.length);
    expect(queryPart).not.toMatch(/[&=?#]/);
  });

  it('空文字でも URL を生成する（呼び出し側でスキップする責務とし、ビルダ自体は副作用を持たない）', () => {
    // 計画では HomePage が query !== '' のときだけ fetch を発火する。
    // ビルダはこの分岐責務を持たず、与えられた値をそのまま組み立てる。
    expect(buildProductsSearchUrl('')).toBe('/api/products/search?q=');
  });
});
