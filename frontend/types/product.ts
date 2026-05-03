export type SiteType = 'amazon' | 'rakuten' | 'yahoo';

export interface Listing {
  site: SiteType;
  siteProductId: string; // ASIN / itemCode / yahooItemId
  url: string; // 外部商品ページ
  price: number; // 本体価格（円・税込）
  shippingFee: number; // 送料（円、0=送料無料）
  points: number; // 獲得ポイント（円換算）
  pointRate: number; // 還元率 0.01 = 1%
  imageUrl?: string; // 商品画像（任意）
  seller?: string; // 出品者名
  inStock: boolean;
}

export interface Product {
  id: string; // UUID風文字列
  name: string;
  janCode?: string;
  category: string;
  listings: Listing[]; // 各サイトの出品（最大3件）
}

/** 画像取得優先度。先頭が最優先。長さ3でSiteTypeを1回ずつ含む */
export type ImagePriority = readonly [SiteType, SiteType, SiteType];

/** 画像解決結果（出典をキャプション表示するため from を持つ） */
export interface ResolvedImage {
  url: string;
  from: SiteType;
}

export type SortKey = 'effectivePriceAsc' | 'priceAsc' | 'pointRateDesc';
