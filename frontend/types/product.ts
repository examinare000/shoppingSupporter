// ─── サーバ生成型（再エクスポート） ─────────────────────────────────────────
// 手書きの Listing / Product 定義はここで廃止し、バックエンド型との二重管理を解消する
// （ADR-012: OpenAPI スキーマを正本とする型同期戦略）。
import type { components } from './api';

export type Listing               = components["schemas"]["ListingOut"];
export type Product               = components["schemas"]["ProductSummary"];
export type ProductSearchEnvelope = components["schemas"]["ProductSearchEnvelope"];

// ─── フロント固有型（手書きのまま） ─────────────────────────────────────────
// 以下の型はバックエンド API には存在せず、フロント表示ロジック専用のため手書きを維持する。

/** EC サイト識別子。バックエンドの SiteType Enum.value（小文字 3 値固定）と対応する */
export type SiteType = 'amazon' | 'rakuten' | 'yahoo';

/** 画像取得優先度。先頭が最優先。長さ3でSiteTypeを1回ずつ含む */
export type ImagePriority = readonly [SiteType, SiteType, SiteType];

/** 画像解決結果（出典をキャプション表示するため from を持つ） */
export interface ResolvedImage {
  url: string;
  from: SiteType;
}

export type SortKey = 'effectivePriceAsc' | 'priceAsc' | 'pointRateDesc';
