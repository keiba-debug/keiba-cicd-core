'use client';

import { useMemo } from 'react';

interface ChartDataPoint {
  date: string;
  balance: number;
  profit: number;
}

interface FundChartProps {
  data: ChartDataPoint[];
  initialBalance: number;
  height?: number;
}

// 日付を表示用にフォーマット
const formatDate = (dateStr: string): string => {
  if (dateStr.length !== 8) return dateStr;
  const month = parseInt(dateStr.slice(4, 6));
  const day = parseInt(dateStr.slice(6, 8));
  return `${month}/${day}`;
};

// 金額をフォーマット
const formatCurrency = (amount: number): string => {
  return new Intl.NumberFormat('ja-JP', {
    style: 'currency',
    currency: 'JPY',
    maximumFractionDigits: 0,
  }).format(amount);
};

export function FundChart({ data, initialBalance, height = 200 }: FundChartProps) {
  const chartData = useMemo(() => {
    // 初期残高を先頭に追加
    const withInitial: ChartDataPoint[] = [
      { date: 'start', balance: initialBalance, profit: 0 },
      ...data,
    ];
    return withInitial;
  }, [data, initialBalance]);

  const { minBalance, maxBalance, points, width } = useMemo(() => {
    if (chartData.length === 0) {
      return { minBalance: 0, maxBalance: 100000, points: '', width: 400 };
    }

    const balances = chartData.map(d => d.balance);
    const min = Math.min(...balances);
    const max = Math.max(...balances);
    
    // 余白を持たせる
    const padding = (max - min) * 0.1 || 10000;
    const adjustedMin = min - padding;
    const adjustedMax = max + padding;
    
    const w = 600;
    const h = height - 40; // 上下のパディング
    const pointSpacing = chartData.length > 1 ? w / (chartData.length - 1) : w;
    
    // ポイントを計算
    const pts = chartData.map((d, i) => {
      const x = i * pointSpacing;
      const y = h - ((d.balance - adjustedMin) / (adjustedMax - adjustedMin)) * h + 20;
      return `${x},${y}`;
    }).join(' ');
    
    return { 
      minBalance: adjustedMin, 
      maxBalance: adjustedMax, 
      points: pts,
      width: w,
    };
  }, [chartData, height]);

  // データがない場合
  if (data.length === 0) {
    return (
      <div 
        className="flex items-center justify-center bg-muted/30 rounded-lg"
        style={{ height }}
      >
        <p className="text-muted-foreground">データがありません</p>
      </div>
    );
  }

  const currentBalance = chartData[chartData.length - 1]?.balance || initialBalance;
  const profitFromStart = currentBalance - initialBalance;
  const profitColor = profitFromStart >= 0 ? '#22c55e' : '#ef4444';

  return (
    <div className="relative">
      {/* 現在値の表示 */}
      <div className="absolute top-0 right-0 text-right">
        <div className="text-2xl font-bold">{formatCurrency(currentBalance)}</div>
        <div className={`text-sm font-medium ${profitFromStart >= 0 ? 'text-green-600' : 'text-red-600'}`}>
          {profitFromStart >= 0 ? '+' : ''}{formatCurrency(profitFromStart)}
        </div>
      </div>

      {/* グラフ */}
      <svg 
        viewBox={`0 0 ${width} ${height}`} 
        className="w-full"
        style={{ height }}
        preserveAspectRatio="none"
      >
        {/* グリッド線 */}
        <defs>
          <linearGradient id="areaGradient" x1="0%" y1="0%" x2="0%" y2="100%">
            <stop offset="0%" stopColor={profitColor} stopOpacity="0.3" />
            <stop offset="100%" stopColor={profitColor} stopOpacity="0.05" />
          </linearGradient>
        </defs>

        {/* 初期残高ライン */}
        <line
          x1="0"
          y1={height - 20 - ((initialBalance - minBalance) / (maxBalance - minBalance)) * (height - 40)}
          x2={width}
          y2={height - 20 - ((initialBalance - minBalance) / (maxBalance - minBalance)) * (height - 40)}
          stroke="#888"
          strokeWidth="1"
          strokeDasharray="4,4"
          opacity="0.5"
        />

        {/* エリア塗りつぶし */}
        <polygon
          points={`0,${height - 20} ${points} ${width},${height - 20}`}
          fill="url(#areaGradient)"
        />

        {/* 折れ線 */}
        <polyline
          points={points}
          fill="none"
          stroke={profitColor}
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
        />

        {/* ポイント */}
        {chartData.map((d, i) => {
          const pointSpacing = chartData.length > 1 ? width / (chartData.length - 1) : width;
          const x = i * pointSpacing;
          const y = height - 40 - ((d.balance - minBalance) / (maxBalance - minBalance)) * (height - 40) + 20;
          
          return (
            <g key={i}>
              <circle
                cx={x}
                cy={y}
                r="4"
                fill={profitColor}
                stroke="white"
                strokeWidth="2"
              />
              {/* ラベル（最初と最後のみ） */}
              {(i === 0 || i === chartData.length - 1) && (
                <text
                  x={x}
                  y={height - 5}
                  textAnchor={i === 0 ? 'start' : 'end'}
                  fontSize="10"
                  fill="#888"
                >
                  {d.date === 'start' ? '開始' : formatDate(d.date)}
                </text>
              )}
            </g>
          );
        })}
      </svg>

      {/* 凡例 */}
      <div className="flex items-center justify-center gap-4 mt-2 text-xs text-muted-foreground">
        <span>--- 初期資金 {formatCurrency(initialBalance)}</span>
      </div>
    </div>
  );
}
