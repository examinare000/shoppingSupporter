import type { Listing } from '@/types/product';

/**
 * 実質支払額を返す。
 *
 * T-09 以降: バックエンドが PricingEngine で算出済みの effectivePrice をそのまま返す。
 * フロント側での再計算（price + shippingFee - points）は廃止した。
 * null は「未認証・プロフィール未設定のため計算不可」を意味する（T-08 仕様）。
 * 画面描画を壊さないよう、null の場合のみ 0 で下限を切る。
 */
export function calculateEffectivePrice(listing: Listing): number {
  return listing.effectivePrice ?? 0;
}
