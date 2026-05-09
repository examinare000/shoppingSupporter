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

type PriceHistoryEntry = components['schemas']['PriceHistoryEntry'];

/**
 * 価格推移をミニマルなチャートで表示するコンポーネント。
 * エディトリアルデザインに基づき、グリッドを最小限にし、JetBrains Mono で軸を描画する。
 */
interface PriceChartProps {
  data: PriceHistoryEntry[];
}

const PriceChart: React.FC<PriceChartProps> = ({ data }) => {
  // サイトごとの色設定（tailwind 拡張の vermilion / mustard 等に合わせる）
  const siteColors: Record<string, string> = {
    amazon: '#1a1a1a', // ink
    rakuten: '#bf360c', // vermilion
    yahoo: '#c2a000', // mustard
  };

  // Recharts用にデータをフラット化
  const formattedData = data.map((entry) => {
    const row: { date: string; [key: string]: number | string } = { date: entry.date };
    Object.entries(entry.sites).forEach(([site, info]) => {
      row[site] = info.price;
    });
    return row;
  });

  // 全てのサイトリストを抽出
  const sites = Array.from(
    new Set(data.flatMap((entry) => Object.keys(entry.sites)))
  );

  if (data.length === 0) {
    return (
      <div className="w-full h-32 flex items-center justify-center border border-dashed border-rule text-ink-muted font-mono text-xs">
        価格履歴データがありません
      </div>
    );
  }

  return (
    <div className="w-full h-48 md:h-64 font-mono text-[10px] md:text-xs">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart
          data={formattedData}
          margin={{ top: 10, right: 10, left: -20, bottom: 0 }}
        >
          <CartesianGrid
            strokeDasharray="3 3"
            vertical={false}
            stroke="var(--rule-line)"
          />
          <XAxis
            dataKey="date"
            axisLine={false}
            tickLine={false}
            tick={{ fill: 'var(--ink-secondary)' }}
            dy={10}
            // 最初と最後の日付だけ表示する等の間引きは recharts が自動で行う
          />
          <YAxis
            axisLine={false}
            tickLine={false}
            tick={{ fill: 'var(--ink-secondary)' }}
            tickFormatter={(value) =>
              value >= 1000 ? `¥${(value / 1000).toFixed(1)}k` : `¥${Math.round(value)}`
            }
          />
          <Tooltip
            contentStyle={{
              backgroundColor: 'var(--paper-base)',
              border: '1px solid var(--rule-line)',
              fontFamily: 'var(--font-jetbrains-mono)',
              fontSize: '10px',
            }}
            itemStyle={{ padding: '0px' }}
            labelStyle={{ color: 'var(--ink-primary)', marginBottom: '4px', fontWeight: 'bold' }}
            formatter={(value) =>
              typeof value === 'number'
                ? [`¥${value.toLocaleString()}`, '']
                : [`${value ?? ''}`, '']
            }
          />
          {sites.map((site) => (
            <Line
              key={site}
              type="stepAfter"
              dataKey={site}
              stroke={siteColors[site] || 'var(--ink-primary)'}
              strokeWidth={1.5}
              dot={false}
              activeDot={{ r: 4, strokeWidth: 0 }}
              name={site.charAt(0).toUpperCase() + site.slice(1)}
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
};

export default PriceChart;
