import type { ElementType } from 'react';

/**
 * pricehack ワードマーク。
 *
 * 設計判断:
 * - サイト名「pricehack」を Fraunces（font-display）の黒ウェイト・小文字・tracking-tight で組み、
 *   隣に `.net` を JetBrains Mono の vermilion 色で添える。
 *   理由: Fraunces のディスプレイセリフは紙面の題字感を保てる一方で、ドメイン的記号の `.net` は
 *   モノスペースで添えた方が「URL」というデジタル属性が読み手に伝わる。色を朱色（#B23A2A）にすることで
 *   モノクロ題字に唯一のアクセントが立ち、紫グラデや絵文字に頼らずブランド色を確立できる。
 * - 大小判定は size prop（sm/md/lg）でクラスを切替。動的サイズ（vw 等）にしないのは、
 *   呼び出し側の文脈（ヘッダー / フッタ / ヒーロー）で離散的に扱った方が制御しやすいため。
 * - as prop で要素を h1 / span / div に切替。デフォルトは span（装飾的な利用が多いため）。
 *   ページの h1 はヒーローの「Where To Buy That?」に集約しているため、Masthead 側ではロゴを span として使う。
 * - withDomain=false で `.net` を非表示にできる（コンパクトな配置や、ドメインを既に文脈で示している箇所向け）。
 *
 * A11y: ロゴ自体がテキストで構成されているため、スクリーンリーダーは "pricehack.net" を自然に読み上げる。
 *       追加の aria-label は不要（テキストの可視内容と読み上げが一致するのが望ましい）。
 */
type LogoSize = 'sm' | 'md' | 'lg';
type LogoElement = 'h1' | 'span' | 'div';

interface LogoProps {
  size?: LogoSize;
  withDomain?: boolean;
  as?: LogoElement;
  className?: string;
}

// ワードマーク本体（pricehack）のサイズクラス。
// 黒ウェイト・tracking-tight・leading-none で、紙面題字としての密度感を担保する。
const WORDMARK_SIZE_CLASS: Record<LogoSize, string> = {
  sm: 'text-2xl',
  md: 'text-4xl',
  lg: 'text-6xl',
};

// `.net` の補助サイズ。ベースラインが揃うよう小さめに。
const DOMAIN_SIZE_CLASS: Record<LogoSize, string> = {
  sm: 'text-xs',
  md: 'text-sm',
  lg: 'text-base',
};

export function Logo({
  size = 'md',
  withDomain = true,
  as = 'span',
  className = '',
}: LogoProps) {
  const Wrapper = as as ElementType;

  return (
    <Wrapper className={`inline-flex items-baseline gap-1 ${className}`.trim()}>
      <span
        className={`font-display font-black tracking-tight leading-none lowercase text-ink ${WORDMARK_SIZE_CLASS[size]}`}
      >
        pricehack
      </span>
      {withDomain && (
        <span
          className={`font-mono text-vermilion leading-none ${DOMAIN_SIZE_CLASS[size]}`}
        >
          .net
        </span>
      )}
    </Wrapper>
  );
}
