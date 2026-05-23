'use client';

import React from 'react';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts';
import { components } from '@/types/api';
import { SITE_META } from '@/lib/site/siteMeta';

type PriceHistoryEntry = components['schemas']['PriceHistoryEntry'];

/**
 * 価格推移チャート。エディトリアルデザインに合わせ、グリッドを横線のみ・軸を非表示にする。
 *
 * 設計意図:
 * - siteColors はデザイントークン（ink-primary / vermilion / mustard）に揃える。
 *   Recharts の Line には CSS 変数を直接渡せないため文字列リテラルで展開する。
 * - 横方向グリッドのみ表示し縦線を除去することで紙面の升目感を排除する。
 * - Y 軸は非表示にして軸ラベルは Tooltip に集約する（最小限の情報密度）。
 * - ツールチップは紙面パレットに合わせた紙・罫線・モノスペースで統一する。
 */
interface PriceChartProps {
  data: PriceHistoryEntry[];
}

const PriceChart: React.FC<PriceChartProps> = ({ data }) => {
  const formattedData = data.map((entry) => {
    const row: { date: string; [key: string]: number | string } = { date: entry.date };
    Object.entries(entry.sites).forEach(([site, info]) => {
      row[site] = info.price;
    });
    return row;
  });

  const sites = Array.from(
    new Set(data.flatMap((entry) => Object.keys(entry.sites))),
  );

  if (data.length === 0) {
    return (
      <div className="w-full h-28 flex items-center justify-center border border-dashed border-rule">
        <p className="font-mono text-xs small-caps text-ink-muted">価格履歴データがありません</p>
      </div>
    );
  }

  return (
    <div className="w-full h-44 md:h-56 font-mono text-[9px] md:text-[10px]">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart
          data={formattedData}
          margin={{ top: 6, right: 4, left: -32, bottom: 0 }}
        >
          <CartesianGrid
            strokeDasharray="2 4"
            vertical={false}
            stroke="var(--rule-line)"
            strokeOpacity={0.4}
          />
          <XAxis
            dataKey="date"
            axisLine={false}
            tickLine={false}
            tick={{ fill: 'var(--ink-secondary)', fontSize: 9 }}
            dy={8}
            interval="preserveStartEnd"
          />
          <YAxis
            axisLine={false}
            tickLine={false}
            tick={{ fill: 'var(--ink-secondary)', fontSize: 9 }}
            tickFormatter={(v: number) =>
              v >= 10000
                ? `¥${(v / 10000).toFixed(1)}万`
                : v >= 1000
                  ? `¥${(v / 1000).toFixed(0)}k`
                  : `¥${v}`
            }
          />
          <Tooltip
            contentStyle={{
              backgroundColor: 'var(--paper-high)',
              border: '1px solid var(--rule-line)',
              borderRadius: 0,
              fontFamily: 'var(--font-jetbrains-mono)',
              fontSize: '10px',
              padding: '6px 10px',
            }}
            itemStyle={{ padding: '1px 0', color: 'var(--ink-primary)' }}
            labelStyle={{
              color: 'var(--ink-secondary)',
              marginBottom: '4px',
              fontSize: '9px',
              letterSpacing: '0.06em',
              textTransform: 'uppercase',
            }}
            // Recharts の Formatter 型が ValueType | NameType の複合型。
            // 実行時判定で安全に処理するため型アサーションを使う。
            formatter={(value, name) => {
              const v = value as unknown;
              const n = name as unknown;
              return [
                typeof v === 'number' ? `¥${v.toLocaleString()}` : String(v ?? ''),
                typeof n === 'string' && n
                  ? n.charAt(0).toUpperCase() + n.slice(1)
                  : String(n ?? ''),
              ] as [string, string];
            }}
          />
          {sites.map((site) => (
            <Line
              key={site}
              type="stepAfter"
              dataKey={site}
              stroke={SITE_META[site]?.color ?? 'var(--ink-primary)'}
              strokeWidth={site === 'rakuten' ? 1.5 : 1.25}
              dot={false}
              activeDot={{ r: 3, strokeWidth: 0 }}
              name={site}
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
};

export default PriceChart;
