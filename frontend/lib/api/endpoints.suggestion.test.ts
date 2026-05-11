/**
 * buildSuggestionUrl のユニットテスト
 *
 * Why 既存の endpoints.test.ts と分離するか:
 *   buildSuggestionUrl は Phase 3-b で新規追加される関数。
 *   既存の endpoints.test.ts は buildProductsSearchUrl のみを扱い、
 *   責務が明確に分離されている。新関数のテストを既存ファイルに混入させず、
 *   機能追加ごとに独立したテストファイルを持つ。
 *
 * 設計意図:
 *   - URL 構築の純関数だけを検証する（HTTP 呼び出しは SuggestionSection テストで担当）
 *   - productId のエンコーディングを明示的に検証する
 */
import { describe, it, expect } from 'vitest';
import { buildSuggestionUrl } from '@/lib/api/endpoints';

describe('buildSuggestionUrl', () => {
  it('UUID を含むサジェスト URL を返す', () => {
    // Given-When-Then: 標準的な UUID
    const id = 'a1b2c3d4-e5f6-7890-abcd-ef1234567890';

    expect(buildSuggestionUrl(id)).toBe(
      `/api/products/${id}/suggestion`,
    );
  });

  it('UUID が URL に正確に含まれる', () => {
    const id = '00000000-0000-0000-0000-000000000001';

    const url = buildSuggestionUrl(id);

    // パスの構造を確認
    expect(url).toMatch(/^\/api\/products\//);
    expect(url).toContain(id);
    expect(url).toMatch(/\/suggestion$/);
  });

  it('productId に特殊文字が含まれる場合はエンコードする', () => {
    // URL パス区切り文字を含む productId（異常系）はエンコードされる
    const id = 'prod/with/slash';

    const url = buildSuggestionUrl(id);

    // スラッシュがそのまま残るとパス構造が壊れる
    // encodeURIComponent により %2F にエンコードされることを期待
    expect(url).not.toMatch(/\/prod\/with\/slash\//);
    expect(url).toContain('%2F');
  });

  it('エンドポイントパスは /api/products/{id}/suggestion の形式', () => {
    // API 仕様書の契約文字列を固定する
    // この 1 テストを変更するだけでパス変更に追従できる
    const id = 'test-product-id';

    expect(buildSuggestionUrl(id)).toBe(
      `/api/products/${encodeURIComponent(id)}/suggestion`,
    );
  });
});
