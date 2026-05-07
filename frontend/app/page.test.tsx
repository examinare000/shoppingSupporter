import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { SWRConfig } from 'swr';
import HomePage from './page';
import type { Product } from '@/types/product';

/**
 * 設計意図:
 * - HomePage は SWR + fetch でデータ取得する。境界は global.fetch のみモックし、SWR 本体はモックしない
 *   （shallow モックではマウント時破綻を見逃すため。フロント知識ファイル「外部UIライブラリとの統合」に従う）。
 * - SWR のグローバルキャッシュがテスト間で共有されないよう、テストごとに新しい Map を provider に渡す。
 *   dedupingInterval / errorRetryCount / focusThrottleInterval を 0 にして再検証タイミングを安定化する。
 * - localStorage は useImagePriority が読むため毎回クリアし、テスト間の状態漏れを断つ。
 */
const productEarbuds: Product = {
  id: 'p-001',
  name: 'ワイヤレスイヤホン Pro X3',
  category: 'オーディオ',
  listings: [
    {
      site: 'amazon',
      siteProductId: 'B0AMZN0001',
      url: 'https://example.com/amazon/p-001',
      price: 12800,
      shippingFee: 0,
      points: 128,
      pointRate: 0.01,
      imageUrl: 'https://example.com/img-amazon.jpg',
      inStock: true,
    },
  ],
};

function jsonResponse(body: unknown, init: ResponseInit = { status: 200 }): Response {
  return new Response(JSON.stringify(body), {
    ...init,
    headers: { 'content-type': 'application/json', ...(init.headers ?? {}) },
  });
}

function renderHome() {
  return render(
    <SWRConfig
      value={{
        // テスト間でキャッシュを完全分離する（SWR の「同じ key で前回成功データが見える」現象を避ける）
        provider: () => new Map(),
        dedupingInterval: 0,
        focusThrottleInterval: 0,
        errorRetryCount: 0,
        // jsdom 環境ではフォーカス・再接続の自動再検証は不要
        revalidateOnFocus: false,
        revalidateOnReconnect: false,
      }}
    >
      <HomePage />
    </SWRConfig>,
  );
}

describe('HomePage（API 接続版・SWR 経由）', () => {
  let fetchMock: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    window.localStorage.clear();
    fetchMock = vi.fn();
    vi.stubGlobal('fetch', fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('初期表示: ロゴ・h1・検索フォームのみ。結果セクションもスピナーもエラー画面も出ず、fetch も呼ばれない', () => {
    renderHome();

    // Masthead: pricehack ワードマーク（フッタにも並ぶため複数ヒットを許容）
    expect(screen.getAllByText('pricehack').length).toBeGreaterThanOrEqual(1);
    // HeroSearch: 唯一の h1
    expect(
      screen.getByRole('heading', { level: 1, name: 'Where To Buy That?' }),
    ).toBeInTheDocument();
    // 検索フォーム
    expect(screen.getByRole('searchbox')).toBeInTheDocument();

    // 検索前: 結果セクション・状態 UI は描画されない
    expect(screen.queryByText(/Hits/)).not.toBeInTheDocument();
    expect(screen.queryAllByRole('article')).toHaveLength(0);
    expect(screen.queryByRole('status')).not.toBeInTheDocument();
    expect(
      screen.queryByRole('button', { name: /リトライ/ }),
    ).not.toBeInTheDocument();

    // 空クエリでは fetch が走らない（SWR の key を null にして抑止する設計）
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it('検索 → ローディング中はスピナー (role="status") が表示される', async () => {
    // Promise を解決しないことでローディング状態に固定する
    fetchMock.mockImplementationOnce(() => new Promise<Response>(() => {}));
    const user = userEvent.setup();
    renderHome();

    await user.type(screen.getByRole('searchbox'), 'イヤホン');
    await user.click(screen.getByRole('button', { name: /検索する/ }));

    expect(await screen.findByRole('status')).toBeInTheDocument();
    // ローディング中は結果セクション・エラー画面は描画しない
    expect(screen.queryByText(/Hits/)).not.toBeInTheDocument();
    expect(
      screen.queryByRole('button', { name: /リトライ/ }),
    ).not.toBeInTheDocument();
  });

  it('検索 → 成功時: ヒット件数表示と該当商品の article が描画される', async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse({ items: [productEarbuds], page: 1, totalPages: 1, totalCount: 1 }),
    );
    const user = userEvent.setup();
    renderHome();

    await user.type(screen.getByRole('searchbox'), 'イヤホン');
    await user.click(screen.getByRole('button', { name: /検索する/ }));

    expect(await screen.findByText(/Hits 1 件/)).toBeInTheDocument();
    expect(screen.getByText(/"イヤホン"/)).toBeInTheDocument();

    const articles = screen.getAllByRole('article');
    expect(articles).toHaveLength(1);
    expect(
      within(articles[0]!).getByRole('heading', { level: 2 }),
    ).toHaveTextContent(/ワイヤレスイヤホン Pro X3/);

    // fetcher が searchClient 経由で 1 回だけ走る
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it('検索 → fetch 失敗時: エラー画面とリトライボタンが表示され、結果セクションは描画されない', async () => {
    fetchMock.mockRejectedValueOnce(new Error('network down'));
    const user = userEvent.setup();
    renderHome();

    await user.type(screen.getByRole('searchbox'), 'イヤホン');
    await user.click(screen.getByRole('button', { name: /検索する/ }));

    // エラー画面のリトライボタン（命名は実装裁量だが「リトライ」を含む）
    expect(
      await screen.findByRole('button', { name: /リトライ/ }),
    ).toBeInTheDocument();

    // 結果セクション（Hits 表記）と article は描画されない
    expect(screen.queryByText(/Hits/)).not.toBeInTheDocument();
    expect(screen.queryAllByRole('article')).toHaveLength(0);
  });

  it('リトライボタン押下で再 fetch され、2 回目の成功で結果が描画される', async () => {
    fetchMock
      .mockRejectedValueOnce(new Error('network down'))
      .mockResolvedValueOnce(
        jsonResponse({ items: [productEarbuds], page: 1, totalPages: 5, totalCount: 5 }),
      );

    const user = userEvent.setup();
    renderHome();

    await user.type(screen.getByRole('searchbox'), 'イヤホン');
    await user.click(screen.getByRole('button', { name: /検索する/ }));

    const retryBtn = await screen.findByRole('button', { name: /リトライ/ });
    await user.click(retryBtn);

    // 2 回目の応答が反映され、結果セクションが描画される（totalCount=5, 現ページ 1 件）
    expect(await screen.findByText(/Hits 5 件/)).toBeInTheDocument();
    expect(screen.getAllByRole('article')).toHaveLength(1);
    // 1 回目（失敗） + リトライ（成功） = 計 2 回 fetch されている
    expect(fetchMock).toHaveBeenCalledTimes(2);
    // エラー画面は再描画後に消える
    expect(
      screen.queryByRole('button', { name: /リトライ/ }),
    ).not.toBeInTheDocument();
  });

  it('検索 → ヒット 0 件: SearchResultsSection 内の EmptyState（該当記事はありません）が描画される', async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse({ items: [], page: 1, totalPages: 0, totalCount: 0 }),
    );
    const user = userEvent.setup();
    renderHome();

    await user.type(screen.getByRole('searchbox'), 'unknown');
    await user.click(screen.getByRole('button', { name: /検索する/ }));

    expect(await screen.findByText(/該当記事はありません/)).toBeInTheDocument();
    expect(screen.queryAllByRole('article')).toHaveLength(0);
    expect(
      screen.queryByRole('button', { name: /リトライ/ }),
    ).not.toBeInTheDocument();
  });
});
