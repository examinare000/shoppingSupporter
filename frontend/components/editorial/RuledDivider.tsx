/**
 * 罫線区切り。
 * variant により単線/二重線/破線を切り替える。
 * 新聞紙面のセクション分割を再現する目的で、専用コンポーネント化している。
 * （hr の border-style を都度指定するより呼び出し側の意図が読み取りやすい）
 */
type RuledDividerVariant = 'single' | 'double' | 'dashed';

interface RuledDividerProps {
  variant?: RuledDividerVariant;
  className?: string;
}

const VARIANT_CLASS: Record<RuledDividerVariant, string> = {
  // 単線。最も汎用的な区切り。
  single: 'border-t border-rule',
  // 二重線。題字や重要見出しの上下に置く。
  double: 'border-t-2 border-double border-rule',
  // 破線。補足情報・欄外の区切り用。
  dashed: 'border-t border-dashed border-rule',
};

export function RuledDivider({ variant = 'single', className = '' }: RuledDividerProps) {
  return (
    <hr
      role="separator"
      aria-hidden="true"
      className={`${VARIANT_CLASS[variant]} ${className}`.trim()}
    />
  );
}
