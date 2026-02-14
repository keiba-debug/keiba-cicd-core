'use client';

/**
 * 統計可視化用共通コンポーネント
 * 
 * - HeatmapCell: 条件付きカラーリングセル
 * - PerformanceBar: 横棒グラフ付きセル
 * - TrendIndicator: 直近成績の視覚化
 * - AptitudeBadge: 得意/苦手バッジ
 */

import * as React from 'react';
import { cn } from '@/lib/utils';
import type { RaceTrendType } from '@/lib/data/rpci-utils';
import { RACE_TREND_LABELS, RACE_TREND_COLORS } from '@/lib/data/rpci-utils';

// ============================================
// HeatmapCell - ヒートマップカラーリングセル
// ============================================

type HeatmapLevel = 'excellent' | 'good' | 'normal' | 'poor' | 'insufficient';

interface HeatmapCellProps {
  value: number;
  type: 'winRate' | 'showRate';
  races?: number; // サンプル数（不足判定用）
  className?: string;
  children?: React.ReactNode;
}

function getHeatmapLevel(value: number, type: 'winRate' | 'showRate', races: number = 10): HeatmapLevel {
  // サンプル不足
  if (races < 3) return 'insufficient';
  
  if (type === 'winRate') {
    if (value >= 20) return 'excellent';
    if (value >= 10) return 'good';
    if (value >= 5) return 'normal';
    return 'poor';
  } else {
    // showRate
    if (value >= 50) return 'excellent';
    if (value >= 30) return 'good';
    if (value >= 15) return 'normal';
    return 'poor';
  }
}

const heatmapStyles: Record<HeatmapLevel, string> = {
  excellent: 'bg-emerald-100 text-emerald-700 font-bold dark:bg-emerald-900/30 dark:text-emerald-400',
  good: 'bg-green-50 text-green-600 dark:bg-green-900/20 dark:text-green-400',
  normal: '',
  poor: 'bg-red-50 text-red-500 dark:bg-red-900/20 dark:text-red-400',
  insufficient: 'bg-gray-50 text-gray-400 italic dark:bg-gray-800/50 dark:text-gray-500',
};

export function HeatmapCell({ value, type, races = 10, className, children }: HeatmapCellProps) {
  const level = getHeatmapLevel(value, type, races);
  
  return (
    <td className={cn('px-3 py-2 border text-center transition-colors', heatmapStyles[level], className)}>
      {children ?? `${value}%`}
    </td>
  );
}

// ============================================
// PerformanceBar - パフォーマンス横棒グラフ
// ============================================

interface PerformanceBarProps {
  value: number;
  maxValue?: number;
  label?: string;
  showValue?: boolean;
  size?: 'sm' | 'md';
  className?: string;
}

function getBarColor(percentage: number): string {
  if (percentage >= 50) return 'bg-gradient-to-r from-emerald-400 to-emerald-500';
  if (percentage >= 30) return 'bg-gradient-to-r from-green-400 to-green-500';
  if (percentage >= 15) return 'bg-gradient-to-r from-amber-400 to-amber-500';
  return 'bg-gradient-to-r from-gray-300 to-gray-400';
}

export function PerformanceBar({ 
  value, 
  maxValue = 100, 
  label,
  showValue = true,
  size = 'sm',
  className 
}: PerformanceBarProps) {
  const percentage = Math.min((value / maxValue) * 100, 100);
  const height = size === 'sm' ? 'h-1.5' : 'h-2.5';
  
  return (
    <div className={cn('flex flex-col gap-0.5', className)}>
      {(label || showValue) && (
        <div className="flex justify-between text-xs">
          {label && <span className="text-muted-foreground">{label}</span>}
          {showValue && <span className="font-medium">{value}%</span>}
        </div>
      )}
      <div className={cn('w-full bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden', height)}>
        <div 
          className={cn('h-full rounded-full transition-all duration-500 ease-out', getBarColor(value))}
          style={{ width: `${percentage}%` }}
        />
      </div>
    </div>
  );
}

// ============================================
// TrendIndicator - 直近成績インジケーター
// ============================================

export type RaceResult = '1st' | '2nd' | '3rd' | '4th' | '5th' | 'out';

/** 直近戦績の1走分（リンク情報付き） */
export interface RecentFormEntry {
  result: RaceResult;
  /** レース詳細ページURL（例: /races-v2/2026-01-18/京都/202601080710） */
  href?: string;
  /** ツールチップ用ラベル（例: "1着 京都5R"） */
  label?: string;
  /** レース傾向（v3: 5段階分類） */
  raceTrend?: RaceTrendType;
}

interface TrendIndicatorProps {
  results: RaceResult[];
  /** リンク情報付きエントリ（resultsより優先） */
  entries?: RecentFormEntry[];
  maxShow?: number;
  size?: 'sm' | 'md';
  className?: string;
  /** true のとき連勝/連敗バッジを表示しない（馬名行で別表示する場合など） */
  hideStreak?: boolean;
}

const resultStyles: Record<RaceResult, { bg: string; label: string }> = {
  '1st': { bg: 'bg-emerald-500', label: '1' },
  '2nd': { bg: 'bg-blue-500', label: '2' },
  '3rd': { bg: 'bg-amber-500', label: '3' },
  '4th': { bg: 'bg-purple-400', label: '4' },
  '5th': { bg: 'bg-sky-400', label: '5' },
  'out': { bg: 'bg-gray-300 dark:bg-gray-600', label: '×' },
};

export function TrendIndicator({
  results,
  entries,
  maxShow = 5,
  size = 'sm',
  className,
  hideStreak = false,
}: TrendIndicatorProps) {
  // entries が提供されていればそちらを優先
  const displayEntries: RecentFormEntry[] = entries
    ? entries.slice(0, maxShow)
    : results.slice(0, maxShow).map(r => ({ result: r }));
  const allResults = entries ? entries.map(e => e.result) : results;
  const dotSize = size === 'sm' ? 'w-5 h-5 text-[10px]' : 'w-6 h-6 text-xs';

  // 連勝/連敗カウント
  const streak = calculateStreak(allResults);

  const resultLabel: Record<RaceResult, string> = {
    '1st': '1着', '2nd': '2着', '3rd': '3着', '4th': '4着', '5th': '5着', 'out': '着外',
  };
  const defaultTitle = (idx: number, result: RaceResult) =>
    `${allResults.length - idx}走前: ${resultLabel[result]}`;

  // レース傾向の短縮ラベル（2文字以下）
  const trendShortLabels: Record<string, string> = {
    sprint_finish: '瞬',
    long_sprint: 'ロ',
    even_pace: '平',
    front_loaded: 'H前',
    front_loaded_strong: 'H後',
  };

  return (
    <div className={cn('flex items-center gap-1', className)}>
      <div className="flex gap-0.5">
        {displayEntries.map((entry, idx) => {
          const trendLabel = entry.raceTrend ? RACE_TREND_LABELS[entry.raceTrend] : '';
          const titleText = entry.label
            ? (trendLabel ? `${entry.label} [${trendLabel}]` : entry.label)
            : (trendLabel ? `${defaultTitle(idx, entry.result)} [${trendLabel}]` : defaultTitle(idx, entry.result));

          const dotElement = (
            <div key={idx} className="flex flex-col items-center gap-px">
              <div
                className={cn(
                  'rounded-full flex items-center justify-center font-bold text-white',
                  dotSize,
                  resultStyles[entry.result].bg,
                  entry.href && 'cursor-pointer hover:ring-2 hover:ring-offset-1 hover:ring-gray-400'
                )}
                title={titleText}
              >
                {resultStyles[entry.result].label}
              </div>
              {entry.raceTrend && (
                <span
                  className={cn(
                    'text-[8px] leading-none font-medium rounded px-0.5',
                    RACE_TREND_COLORS[entry.raceTrend]
                  )}
                  title={RACE_TREND_LABELS[entry.raceTrend]}
                >
                  {trendShortLabels[entry.raceTrend] || ''}
                </span>
              )}
            </div>
          );
          if (entry.href) {
            return (
              <a key={idx} href={entry.href} target="_blank" rel="noopener noreferrer">
                {React.cloneElement(dotElement, { key: undefined })}
              </a>
            );
          }
          return dotElement;
        })}
      </div>
      {!hideStreak && streak && (
        <StreakBadge streak={streak} />
      )}
    </div>
  );
}

export interface Streak {
  type: 'win' | 'place' | 'lose';
  count: number;
}

export function calculateStreak(results: RaceResult[]): Streak | null {
  if (results.length === 0) return null;
  
  let winCount = 0;
  let placeCount = 0;
  let loseCount = 0;
  
  for (const result of results) {
    if (result === '1st') {
      if (loseCount > 0) break;
      winCount++;
      placeCount++;
    } else if (result === '2nd' || result === '3rd') {
      if (loseCount > 0) break;
      if (winCount > 0) break;
      placeCount++;
    } else {
      if (winCount > 0 || placeCount > 0) break;
      loseCount++;
    }
  }
  
  if (winCount >= 2) return { type: 'win', count: winCount };
  if (loseCount >= 2) return { type: 'lose', count: loseCount };
  if (placeCount >= 3) return { type: 'place', count: placeCount };
  
  return null;
}

export function StreakBadge({ streak }: { streak: Streak }) {
  const styles = {
    win: 'bg-emerald-500 text-white',
    place: 'bg-blue-500 text-white',
    lose: 'bg-red-100 text-red-600 dark:bg-red-900/30 dark:text-red-400',
  };
  
  const labels = {
    win: `${streak.count}連勝`,
    place: `${streak.count}連複`,
    lose: `${streak.count}連敗`,
  };
  
  const icons = {
    win: '🔥',
    place: '✨',
    lose: '↓',
  };
  
  return (
    <span className={cn(
      'inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded text-[10px] font-medium whitespace-nowrap flex-shrink-0',
      styles[streak.type]
    )}>
      {icons[streak.type]} {labels[streak.type]}
    </span>
  );
}

// ============================================
// AptitudeBadge - 適性バッジ
// ============================================

interface AptitudeBadgeProps {
  type: 'strong' | 'weak' | 'neutral';
  label?: string;
  className?: string;
}

const aptitudeStyles = {
  strong: 'bg-emerald-100 text-emerald-700 border-emerald-200 dark:bg-emerald-900/30 dark:text-emerald-400 dark:border-emerald-800',
  weak: 'bg-red-100 text-red-600 border-red-200 dark:bg-red-900/30 dark:text-red-400 dark:border-red-800',
  neutral: 'bg-gray-100 text-gray-600 border-gray-200 dark:bg-gray-800 dark:text-gray-400 dark:border-gray-700',
};

const aptitudeIcons = {
  strong: '◎',
  weak: '△',
  neutral: '○',
};

export function AptitudeBadge({ type, label, className }: AptitudeBadgeProps) {
  return (
    <span className={cn(
      'inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded border text-xs font-medium',
      aptitudeStyles[type],
      className
    )}>
      {aptitudeIcons[type]}
      {label && <span className="ml-0.5">{label}</span>}
    </span>
  );
}

// ============================================
// RankBadge - 順位バッジ
// ============================================

interface RankBadgeProps {
  rank: number;
  total?: number;
  className?: string;
}

export function RankBadge({ rank, total, className }: RankBadgeProps) {
  const getBadgeStyle = () => {
    if (rank === 1) return 'bg-gradient-to-r from-yellow-400 to-amber-500 text-white shadow-sm';
    if (rank === 2) return 'bg-gradient-to-r from-gray-300 to-gray-400 text-gray-700';
    if (rank === 3) return 'bg-gradient-to-r from-orange-300 to-orange-400 text-orange-800';
    return 'bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400';
  };
  
  const getIcon = () => {
    if (rank === 1) return '👑';
    if (rank === 2) return '🥈';
    if (rank === 3) return '🥉';
    return null;
  };
  
  return (
    <span className={cn(
      'inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-bold',
      getBadgeStyle(),
      className
    )}>
      {getIcon()}
      <span>{rank}</span>
      {total && <span className="text-[10px] opacity-70">/{total}</span>}
    </span>
  );
}

// ============================================
// RpciGauge - RPCI半円ゲージ
// ============================================

interface RpciGaugeProps {
  value: number;
  size?: 'sm' | 'md' | 'lg';
  showLabel?: boolean;
  className?: string;
}

function getRpciCategory(value: number): { label: string; color: string; arcColor: string } {
  if (value >= 52) {
    return { label: '瞬発戦', color: 'text-blue-600', arcColor: '#3b82f6' };
  } else if (value >= 50.5) {
    return { label: 'やや瞬発', color: 'text-blue-400', arcColor: '#60a5fa' };
  } else if (value <= 48) {
    return { label: '持続戦', color: 'text-red-600', arcColor: '#dc2626' };
  } else if (value <= 49.5) {
    return { label: 'やや持続', color: 'text-red-400', arcColor: '#f87171' };
  }
  return { label: '平均的', color: 'text-gray-500', arcColor: '#6b7280' };
}

export function RpciGauge({ value, size = 'md', showLabel = true, className }: RpciGaugeProps) {
  const category = getRpciCategory(value);
  
  // サイズ設定
  const sizes = {
    sm: { width: 80, height: 50, fontSize: 12, labelSize: 8, strokeWidth: 6 },
    md: { width: 120, height: 70, fontSize: 18, labelSize: 10, strokeWidth: 8 },
    lg: { width: 160, height: 90, fontSize: 24, labelSize: 12, strokeWidth: 10 },
  };
  const s = sizes[size];
  
  // 半円ゲージの計算
  // RPCI範囲: 45-55 を 0-180度にマッピング
  const minRpci = 45;
  const maxRpci = 55;
  const clampedValue = Math.max(minRpci, Math.min(maxRpci, value));
  const percentage = (clampedValue - minRpci) / (maxRpci - minRpci);
  const angle = percentage * 180;
  
  const radius = s.width / 2 - s.strokeWidth;
  const centerX = s.width / 2;
  const centerY = s.height - 5;
  
  // SVGアークパス計算
  const polarToCartesian = (cx: number, cy: number, r: number, angleDeg: number) => {
    const angleRad = (angleDeg - 180) * Math.PI / 180;
    return {
      x: cx + r * Math.cos(angleRad),
      y: cy + r * Math.sin(angleRad)
    };
  };
  
  const describeArc = (cx: number, cy: number, r: number, startAngle: number, endAngle: number) => {
    const start = polarToCartesian(cx, cy, r, endAngle);
    const end = polarToCartesian(cx, cy, r, startAngle);
    const largeArcFlag = endAngle - startAngle <= 180 ? "0" : "1";
    return `M ${start.x} ${start.y} A ${r} ${r} 0 ${largeArcFlag} 0 ${end.x} ${end.y}`;
  };
  
  const bgArc = describeArc(centerX, centerY, radius, 0, 180);
  const valueArc = describeArc(centerX, centerY, radius, 0, angle);
  
  return (
    <div className={cn('flex flex-col items-center', className)}>
      <svg width={s.width} height={s.height} className="overflow-visible">
        {/* 背景アーク */}
        <path
          d={bgArc}
          fill="none"
          stroke="#e5e7eb"
          strokeWidth={s.strokeWidth}
          strokeLinecap="round"
          className="dark:stroke-gray-700"
        />
        {/* 値アーク */}
        <path
          d={valueArc}
          fill="none"
          stroke={category.arcColor}
          strokeWidth={s.strokeWidth}
          strokeLinecap="round"
          className="transition-all duration-500"
        />
        {/* 中央の値 */}
        <text
          x={centerX}
          y={centerY - 8}
          textAnchor="middle"
          className={cn('font-bold fill-current', category.color)}
          style={{ fontSize: s.fontSize }}
        >
          {value.toFixed(1)}
        </text>
        {/* スケールラベル */}
        <text x={5} y={centerY + 2} className="fill-gray-400" style={{ fontSize: s.labelSize }}>
          持続
        </text>
        <text x={s.width - 5} y={centerY + 2} textAnchor="end" className="fill-gray-400" style={{ fontSize: s.labelSize }}>
          瞬発
        </text>
      </svg>
      {showLabel && (
        <span className={cn('text-xs font-medium mt-1', category.color)}>
          {category.label}
        </span>
      )}
    </div>
  );
}

// ============================================
// RpciBar - RPCI横棒グラフ（ランキング用）
// ============================================

interface RpciBarProps {
  value: number;
  label: string;
  rank?: number;
  sampleCount?: number;
  minValue?: number;
  maxValue?: number;
  animate?: boolean;
  delay?: number;
  className?: string;
}

export function RpciBar({ 
  value, 
  label, 
  rank, 
  sampleCount,
  minValue = 45, 
  maxValue = 55,
  animate = true,
  delay = 0,
  className 
}: RpciBarProps) {
  const category = getRpciCategory(value);
  
  // バー幅の計算（45-55を0-100%にマッピング）
  const percentage = ((value - minValue) / (maxValue - minValue)) * 100;
  const clampedPercentage = Math.max(0, Math.min(100, percentage));
  
  // ランクバッジ
  const getRankStyle = (rank: number) => {
    if (rank === 1) return 'bg-gradient-to-r from-yellow-400 to-amber-500 text-white';
    if (rank === 2) return 'bg-gradient-to-r from-gray-300 to-gray-400 text-gray-700';
    if (rank === 3) return 'bg-gradient-to-r from-orange-300 to-orange-400 text-orange-800';
    return 'bg-gray-100 text-gray-600';
  };
  
  return (
    <div className={cn('flex items-center gap-3 py-2', className)}>
      {/* ランクバッジ */}
      {rank && (
        <span className={cn(
          'w-8 h-8 flex items-center justify-center rounded-full text-sm font-bold shrink-0',
          getRankStyle(rank)
        )}>
          {rank}
        </span>
      )}
      
      {/* ラベル */}
      <div className="w-28 shrink-0">
        <span className="font-medium text-sm">{label}</span>
        {sampleCount && (
          <span className="text-[10px] text-muted-foreground ml-1">({sampleCount}件)</span>
        )}
      </div>
      
      {/* バー */}
      <div className="flex-1 relative h-6 bg-gray-100 dark:bg-gray-800 rounded-full overflow-hidden">
        {/* 中央線（RPCI=50） */}
        <div className="absolute left-1/2 top-0 bottom-0 w-px bg-gray-300 dark:bg-gray-600 z-10" />
        
        {/* 値バー */}
        <div
          className={cn(
            'absolute top-0 bottom-0 rounded-full transition-all ease-out',
            animate ? 'duration-700' : 'duration-0'
          )}
          style={{
            left: value >= 50 ? '50%' : `${clampedPercentage}%`,
            right: value < 50 ? '50%' : `${100 - clampedPercentage}%`,
            backgroundColor: category.arcColor,
            transitionDelay: animate ? `${delay}ms` : '0ms',
          }}
        />
        
        {/* 値ラベル */}
        <span 
          className="absolute inset-0 flex items-center justify-center text-xs font-bold text-white z-20 mix-blend-difference"
        >
          {value.toFixed(2)}
        </span>
      </div>
      
      {/* 傾向ラベル */}
      <span className={cn('text-xs font-medium w-16 text-right', category.color)}>
        {category.label}
      </span>
    </div>
  );
}

// ============================================
// StatCard - 統計カード
// ============================================

interface StatCardProps {
  label: string;
  value: string | number;
  subValue?: string;
  trend?: 'up' | 'down' | 'neutral';
  icon?: React.ReactNode;
  className?: string;
}

export function StatCard({ label, value, subValue, trend, icon, className }: StatCardProps) {
  const trendStyles = {
    up: 'text-emerald-500',
    down: 'text-red-500',
    neutral: 'text-gray-400',
  };
  
  const trendIcons = {
    up: '▲',
    down: '▼',
    neutral: '−',
  };
  
  return (
    <div className={cn(
      'flex flex-col gap-1 p-4 rounded-lg border bg-card shadow-sm hover:shadow-md transition-shadow',
      className
    )}>
      <div className="flex items-center justify-between">
        <span className="text-sm text-muted-foreground">{label}</span>
        {icon && <span className="text-lg">{icon}</span>}
      </div>
      <div className="flex items-baseline gap-2">
        <span className="text-2xl font-bold">{value}</span>
        {trend && (
          <span className={cn('text-sm font-medium', trendStyles[trend])}>
            {trendIcons[trend]} {subValue}
          </span>
        )}
        {!trend && subValue && (
          <span className="text-sm text-muted-foreground">{subValue}</span>
        )}
      </div>
    </div>
  );
}
