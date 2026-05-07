import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { searchProducts } from '@/lib/api/searchClient';
import { buildProductsSearchUrl } from '@/lib/api/endpoints';
import type { ProductSearchEnvelope } from '@/types/product';

/**
 * 設計意図:
 * - 境界は global.fetch。SWR や React 側のテストはここでは扱わない。
 * - URL 組み立て (buildProductsSearchUrl) と searchProducts の HTTP 呼び出しが
 *   一致していることを行動レベルで保証する。
 * - エラーハンドリングは「Response.ok でなければ throw、ネットワーク例外はそのまま伝播」を契約とする。
 *   SWR がエラーを受け取って画面側に伝播させる前提（横断的関心事を API クライアント層に閉じ込める）。
 *
 * T-09 変更点:
 * - 返却型を Product[] → ProductSearchEnvelope に変更（バックエンドの実際のレスポンス形式に合わせる）。
 *   旧実装は Product[] 直返しを前提としていたが、バックエンドは {items, page, ...} 形式の
 *   envelope を返しており、型不整合を解消する。
 */
const sampleEnvelope: ProductSearchEnvelope = {
  items: [
    {
      id: 'p-001',
      name: 'ワイヤレスイヤホン Pro X3 / Wireless Earbuds Pro X3',
      description: null,
      imageUrl: 'https://example.com/img.jpg',
      tags: ['audio'],
      inStock: true,
      currentPrice: 12800,
      listings: [
        {
          siteType: 'amazon',
          siteProductId: 'B0AMZN0001',
          url: 'https://www.amazon.co.jp/dp/B0AMZN0001',
          points: 128,
          effectivePrice: 12672,
          breakdown: null,
        },
      ],
    },
  ],
  page: 1,
  totalPages: 1,
  totalCount: 1,
  meta: {
    personalization: {
      applied: false,
      rakutenRank: null,
      hasCard: false,
    },
  },
};

function jsonResponse(body: unknown, init: ResponseInit = { status: 200 }): Response {
  return new Response(JSON.stringify(body), {
    ...init,
    headers: { 'content-type': 'application/json', ...(init.headers ?? {}) },
  });
}

describe('searchProducts (fetch-based API クライアント)', () => {
  let fetchMock: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    fetchMock = vi.fn();
    vi.stubGlobal('fetch', fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('正常系: レスポンス JSON を ProductSearchEnvelope として解決する Promise を返す', async () => {
    // Given: バックエンドが ProductSearchEnvelope を JSON で返す
    fetchMock.mockResolvedValueOnce(jsonResponse(sampleEnvelope));

    // When: searchProducts を呼ぶ
    const result = await searchProducts('イヤホン');

    // Then: envelope 形式で返る（items が配列）
    expect(result).toEqual(sampleEnvelope);
    expect(Array.isArray(result.items)).toBe(true);
    // バグチェック: envelope ではなく items 配列そのものを返していないこと
    expect(Array.isArray(result)).toBe(false);
  });

  it('buildProductsSearchUrl が組み立てた URL に対して fetch を呼ぶ', async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse(sampleEnvelope));

    await searchProducts('イヤホン');

    expect(fetchMock).toHaveBeenCalledTimes(1);
    // 第 1 引数: URL 文字列。第 2 引数 (init) は実装裁量のため検証しない
    const calledUrl = fetchMock.mock.calls[0]?.[0];
    expect(calledUrl).toBe(buildProductsSearchUrl('イヤホン'));
  });

  it('HTTP メソッドは GET（明示指定 or 既定値どちらでも GET）', async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse(sampleEnvelope));

    await searchProducts('q');

    const init = fetchMock.mock.calls[0]?.[1] as RequestInit | undefined;
    // method が省略されていれば fetch のデフォルトが GET。明示指定された場合も GET であること
    const method = (init?.method ?? 'GET').toUpperCase();
    expect(method).toBe('GET');
  });

  it('日本語・空白・特殊文字は URL 経由でエンコードされて送信される', async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse(sampleEnvelope));

    await searchProducts('a&b イヤホン');

    const calledUrl = fetchMock.mock.calls[0]?.[0] as string;
    expect(calledUrl).toBe(buildProductsSearchUrl('a&b イヤホン'));
    // 生の文字（特に & とスペース）が URL のクエリ部分に直接現れない
    const queryPart = calledUrl.split('?q=')[1] ?? '';
    expect(queryPart).not.toMatch(/[&\s]/);
  });

  it('空の items リストを持つ envelope を正しく解決する（ヒット 0 件は成功扱い）', async () => {
    const emptyEnvelope: ProductSearchEnvelope = {
      items: [],
      page: 1,
      totalPages: 0,
      totalCount: 0,
      meta: { personalization: { applied: false, rakutenRank: null, hasCard: false } },
    };
    fetchMock.mockResolvedValueOnce(jsonResponse(emptyEnvelope));

    const result = await searchProducts('絶対に存在しない商品名');

    expect(result).toEqual(emptyEnvelope);
    expect(result.items).toHaveLength(0);
  });

  it('HTTP 4xx (404) は Error を throw する', async () => {
    fetchMock.mockResolvedValueOnce(
      new Response('not found', { status: 404 }),
    );

    await expect(searchProducts('q')).rejects.toThrowError();
  });

  it('HTTP 5xx (500) は Error を throw する', async () => {
    fetchMock.mockResolvedValueOnce(
      new Response('server error', { status: 500 }),
    );

    await expect(searchProducts('q')).rejects.toThrowError();
  });

  it('ネットワークエラー (fetch 自体が reject) は SWR に伝播する（握りつぶさない）', async () => {
    fetchMock.mockRejectedValueOnce(new Error('network down'));

    await expect(searchProducts('q')).rejects.toThrow('network down');
  });
});
