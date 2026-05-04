import type { Product, ImagePriority } from '@/types/product';
import { resolveProductImage } from '@/lib/image/resolveProductImage';
import { SITE_LABEL } from '@/lib/image/imagePriorityDefaults';

/**
 * 商品サムネイル。エディトリアル整合のため次の処理を行う:
 * - grayscale + contrast を CSS filter で適用し、紙面の活字寄りトーンに寄せる
 * - 出典サイトを figcaption で必ず明示する（編集記事における「写真クレジット」の慣習）
 * - 解決失敗時は "No image on file" の活字フォールバックを表示する（CMS 欠落時の正直な表示）
 *
 * next/image ではなく素の <img> を使う理由:
 * モック段階では width/height 必須化や placeholder の影響でフォールバック UI と相性が悪い。
 * テスト容易性も含め、本タスクでは <img> で十分。
 */
interface ProductThumbnailProps {
  product: Product;
  priority: ImagePriority;
  size?: number;
}

export function ProductThumbnail({ product, priority, size = 96 }: ProductThumbnailProps) {
  const resolved = resolveProductImage(product, priority);

  if (resolved === null) {
    return (
      <figure
        className="border border-rule bg-paper-high flex flex-col items-center justify-center"
        style={{ width: size, height: size + 24 }}
      >
        <span
          className="font-display text-3xl text-ink-muted"
          aria-hidden="true"
          style={{ height: size, lineHeight: `${size}px` }}
        >
          —
        </span>
        <figcaption className="text-[10px] font-mono text-ink-muted small-caps px-1 text-center">
          No image on file
        </figcaption>
      </figure>
    );
  }

  return (
    <figure className="flex flex-col" style={{ width: size }}>
      {/* eslint-disable-next-line @next/next/no-img-element -- モック段階では <img> で十分。next/image は width/height 必須でモック画像差し替えと相性が悪い */}
      <img
        src={resolved.url}
        alt={product.name}
        width={size}
        height={size}
        loading="lazy"
        className="block"
        style={{
          width: size,
          height: size,
          objectFit: 'cover',
          // モノクロ寄りのトーン。彩度を落とし、新聞紙面の写真質感に寄せる
          filter: 'grayscale(0.7) contrast(1.05)',
        }}
      />
      <figcaption className="text-xs font-mono text-ink-muted mt-1 small-caps">
        Photo: {SITE_LABEL[resolved.from]}
      </figcaption>
    </figure>
  );
}
