/**
 * 序数表示。記事の肩番号として使用する。
 * 「01.」〜「99.」のゼロパディング2桁。モノスペースで縦の桁が揃うようにする。
 *
 * aria-hidden="true" の理由:
 * 序数自体は装飾的な肩番号で、隣接する記事見出し（h2）が本文の主見出しを担う。
 * スクリーンリーダーが「ゼロイチピリオド」と読み上げてしまうとノイズになるため除外する。
 */
interface OrdinalProps {
  n: number;
  className?: string;
}

export function Ordinal({ n, className = '' }: OrdinalProps) {
  // 99 を超えると桁あふれするが、編集記事の番号として 99 を超える想定はないため
  // padStart(2) のみで運用する。
  const label = `${String(n).padStart(2, '0')}.`;
  return (
    <span
      aria-hidden="true"
      className={`font-mono font-bold text-ink tabular ${className}`.trim()}
    >
      {label}
    </span>
  );
}
