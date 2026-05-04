/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  images: {
    remotePatterns: [
      // Amazon商品画像（現行CDN）
      { protocol: 'https', hostname: 'm.media-amazon.com' },
      // Amazon商品画像（旧CDN・互換のため許可）
      { protocol: 'https', hostname: 'images-na.ssl-images-amazon.com' },
      // 楽天市場サムネイル
      { protocol: 'https', hostname: 'thumbnail.image.rakuten.co.jp' },
      // Yahoo!ショッピング商品画像
      { protocol: 'https', hostname: 'item-shopping.c.yimg.jp' },
      // 開発時モック用 placeholder
      { protocol: 'https', hostname: 'picsum.photos' },
    ],
  },
};

export default nextConfig;
