'use client';

/**
 * 馬成績統計セクションコンポーネント（v2 - 可視化強化版）
 * 
 * 改善点:
 * - ヒートマップカラーリング（勝率/複勝率の条件付きハイライト）
 * - パフォーマンスバー（横棒グラフによる視覚化）
 * - 適性バッジ（得意/苦手の明示）
 * - サマリーカード（主要統計の強調表示）
 */

import React from 'react';
import type { HorseStats, StatGroup } from '@/lib/data/integrated-horse-reader';
import { cn } from '@/lib/utils';
import { HeatmapCell, PerformanceBar, AptitudeBadge, StatCard } from '@/components/ui/visualization';

interface HorseStatsSectionProps {
  stats: HorseStats;
}

// 適性判定ロジック
function getAptitudeType(group: StatGroup): 'strong' | 'weak' | 'neutral' {
  if (group.races < 3) return 'neutral'; // サンプル不足
  if (group.winRate >= 20 || group.showRate >= 50) return 'strong';
  if (group.races >= 5 && group.showRate < 15) return 'weak';
  return 'neutral';
}

// 統計行コンポーネント（ヒートマップ対応）
function StatRow({ label, group, showAptitude = false }: {
  label: React.ReactNode;
  group: StatGroup;
  showAptitude?: boolean;
}) {
  if (group.races === 0) {
    return (
      <tr className="text-gray-400 dark:text-gray-500">
        <td className="px-3 py-2 border">{label}</td>
        <td className="px-3 py-2 border text-center">-</td>
        <td className="px-3 py-2 border text-center">-</td>
        <td className="px-3 py-2 border text-center">-</td>
        <td className="px-3 py-2 border text-center">-</td>
        <td className="px-3 py-2 border text-center">-</td>
        <td className="px-3 py-2 border text-center">-</td>
        <td className="px-3 py-2 border text-center">-</td>
        {showAptitude && <td className="px-3 py-2 border text-center">-</td>}
      </tr>
    );
  }

  const outsidePlace = group.races - group.thirds;
  const aptitude = getAptitudeType(group);

  return (
    <tr className="hover:bg-gray-50 dark:hover:bg-gray-800/50 transition-colors">
      <td className="px-3 py-2 border font-medium">{label}</td>
      <td className="px-3 py-2 border text-center">
        <span className="inline-flex items-center gap-1">
          {group.races}
          {group.races >= 10 && (
            <span className="text-[10px] text-muted-foreground">(信頼度高)</span>
          )}
        </span>
      </td>
      <td className="px-3 py-2 border text-center font-bold text-yellow-600 dark:text-yellow-500">
        {group.wins}
      </td>
      <td className="px-3 py-2 border text-center text-blue-600 dark:text-blue-400">
        {group.seconds}
      </td>
      <td className="px-3 py-2 border text-center text-green-600 dark:text-green-400">
        {group.thirds - group.seconds}
      </td>
      <td className="px-3 py-2 border text-center text-muted-foreground">
        {outsidePlace}
      </td>
      <HeatmapCell value={group.winRate} type="winRate" races={group.races} />
      <HeatmapCell value={group.showRate} type="showRate" races={group.races}>
        <div className="flex flex-col items-center gap-1">
          <span>{group.showRate}%</span>
          <PerformanceBar value={group.showRate} showValue={false} size="sm" className="w-16" />
        </div>
      </HeatmapCell>
      {showAptitude && (
        <td className="px-3 py-2 border text-center">
          <AptitudeBadge type={aptitude} />
        </td>
      )}
    </tr>
  );
}

// サマリーセクション
function StatsSummary({ stats }: { stats: HorseStats }) {
  const { total, turf, dirt } = stats;
  
  // 最も得意な条件を特定
  const allGroups = [
    { label: '芝', group: turf },
    { label: 'ダート', group: dirt },
    ...Object.entries(stats.byDistance).map(([dist, group]) => ({ label: dist, group })),
    ...Object.entries(stats.byCondition).map(([cond, group]) => ({ label: cond, group })),
  ].filter(g => g.group.races >= 3);
  
  const bestGroup = allGroups.reduce((best, current) => {
    if (!best || current.group.showRate > best.group.showRate) return current;
    return best;
  }, null as { label: string; group: StatGroup } | null);

  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
      <StatCard
        label="通算成績"
        value={`${total.wins}-${total.seconds}-${total.thirds - total.seconds}-${total.races - total.thirds}`}
        subValue={`${total.races}戦`}
        icon="🏇"
      />
      <StatCard
        label="勝率"
        value={`${total.winRate}%`}
        trend={total.winRate >= 15 ? 'up' : total.winRate < 5 ? 'down' : 'neutral'}
        subValue={total.winRate >= 15 ? '優秀' : total.winRate < 5 ? '要確認' : '平均的'}
        icon="🏆"
      />
      <StatCard
        label="複勝率"
        value={`${total.showRate}%`}
        trend={total.showRate >= 40 ? 'up' : total.showRate < 20 ? 'down' : 'neutral'}
        subValue={total.showRate >= 40 ? '安定' : total.showRate < 20 ? '不安定' : '普通'}
        icon="📊"
      />
      {bestGroup && (
        <StatCard
          label="得意条件"
          value={bestGroup.label}
          subValue={`複勝率 ${bestGroup.group.showRate}%`}
          icon="⭐"
        />
      )}
    </div>
  );
}

// レース傾向の定義
const TREND_ORDER = [
  { key: 'sprint_finish', label: '瞬発', badge: 'bg-blue-100 text-blue-700' },
  { key: 'long_sprint', label: 'ロンスパ', badge: 'bg-indigo-100 text-indigo-700' },
  { key: 'even_pace', label: '平均', badge: 'bg-gray-100 text-gray-700' },
  { key: 'front_loaded', label: 'H前傾', badge: 'bg-red-100 text-red-700' },
  { key: 'front_loaded_strong', label: 'H後傾', badge: 'bg-orange-100 text-orange-700' },
];

export function HorseStatsSection({ stats }: HorseStatsSectionProps) {
  const hasDistanceData = Object.keys(stats.byDistance).length > 0;
  const hasConditionData = Object.keys(stats.byCondition).length > 0;
  const hasFrameData = Object.keys(stats.byFrame || {}).length > 0;
  const hasFieldSizeData = Object.keys(stats.byFieldSize || {}).length > 0;
  const hasTrendData = Object.keys(stats.byTrend || {}).length > 0;

  return (
    <div className="space-y-6">
      <h2 className="text-lg font-semibold flex items-center gap-2">
        📊 成績統計
      </h2>

      {/* サマリーカード */}
      <StatsSummary stats={stats} />

      {/* メイン統計テーブル */}
      <div className="overflow-x-auto">
        <table className="w-full text-sm border-collapse">
          <thead>
            <tr className="bg-gray-100 dark:bg-gray-800">
              <th className="px-3 py-2 border text-left">区分</th>
              <th className="px-3 py-2 border text-center">出走</th>
              <th className="px-3 py-2 border text-center">1着</th>
              <th className="px-3 py-2 border text-center">2着</th>
              <th className="px-3 py-2 border text-center">3着</th>
              <th className="px-3 py-2 border text-center">着外</th>
              <th className="px-3 py-2 border text-center">勝率</th>
              <th className="px-3 py-2 border text-center">複勝率</th>
            </tr>
          </thead>
          <tbody>
            <StatRow label="通算" group={stats.total} />
            <StatRow label="芝" group={stats.turf} />
            <StatRow label="ダート" group={stats.dirt} />
          </tbody>
        </table>
      </div>

      {/* 距離別統計（ヒートマップ強化） */}
      {hasDistanceData && (
        <div className="overflow-x-auto">
          <h3 className="text-sm font-medium mb-2 text-muted-foreground flex items-center gap-2">
            📏 距離別
            <span className="text-[10px] bg-muted px-2 py-0.5 rounded">
              適性判定あり
            </span>
          </h3>
          <table className="w-full text-sm border-collapse">
            <thead>
              <tr className="bg-gray-100 dark:bg-gray-800">
                <th className="px-3 py-2 border text-left">距離</th>
                <th className="px-3 py-2 border text-center">出走</th>
                <th className="px-3 py-2 border text-center">1着</th>
                <th className="px-3 py-2 border text-center">2着</th>
                <th className="px-3 py-2 border text-center">3着</th>
                <th className="px-3 py-2 border text-center">着外</th>
                <th className="px-3 py-2 border text-center">勝率</th>
                <th className="px-3 py-2 border text-center">複勝率</th>
                <th className="px-3 py-2 border text-center">適性</th>
              </tr>
            </thead>
            <tbody>
              {['1200m', '1400m', '1600m', '1800m', '2000m+'].map((dist) => {
                const group = stats.byDistance[dist];
                if (!group) return null;
                return <StatRow key={dist} label={dist} group={group} showAptitude />;
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* 馬場状態別統計（ヒートマップ強化） */}
      {hasConditionData && (
        <div className="overflow-x-auto">
          <h3 className="text-sm font-medium mb-2 text-muted-foreground flex items-center gap-2">
            🌤️ 馬場状態別
            <span className="text-[10px] bg-muted px-2 py-0.5 rounded">
              適性判定あり
            </span>
          </h3>
          <table className="w-full text-sm border-collapse">
            <thead>
              <tr className="bg-gray-100 dark:bg-gray-800">
                <th className="px-3 py-2 border text-left">馬場</th>
                <th className="px-3 py-2 border text-center">出走</th>
                <th className="px-3 py-2 border text-center">1着</th>
                <th className="px-3 py-2 border text-center">2着</th>
                <th className="px-3 py-2 border text-center">3着</th>
                <th className="px-3 py-2 border text-center">着外</th>
                <th className="px-3 py-2 border text-center">勝率</th>
                <th className="px-3 py-2 border text-center">複勝率</th>
                <th className="px-3 py-2 border text-center">適性</th>
              </tr>
            </thead>
            <tbody>
              {['良', '稍重', '重', '不良'].map((cond) => {
                const group = stats.byCondition[cond];
                if (!group) return null;
                return <StatRow key={cond} label={cond} group={group} showAptitude />;
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* 枠順別統計 */}
      {hasFrameData && (
        <div className="overflow-x-auto">
          <h3 className="text-sm font-medium mb-2 text-muted-foreground flex items-center gap-2">
            🎯 枠順別
            <span className="text-[10px] bg-muted px-2 py-0.5 rounded">
              適性判定あり
            </span>
          </h3>
          <table className="w-full text-sm border-collapse">
            <thead>
              <tr className="bg-gray-100 dark:bg-gray-800">
                <th className="px-3 py-2 border text-left">枠順</th>
                <th className="px-3 py-2 border text-center">出走</th>
                <th className="px-3 py-2 border text-center">1着</th>
                <th className="px-3 py-2 border text-center">2着</th>
                <th className="px-3 py-2 border text-center">3着</th>
                <th className="px-3 py-2 border text-center">着外</th>
                <th className="px-3 py-2 border text-center">勝率</th>
                <th className="px-3 py-2 border text-center">複勝率</th>
                <th className="px-3 py-2 border text-center">適性</th>
              </tr>
            </thead>
            <tbody>
              {['内枠(1-3)', '中枠(4-6)', '外枠(7-8)'].map((frame) => {
                const group = stats.byFrame[frame];
                if (!group) return null;
                return <StatRow key={frame} label={frame} group={group} showAptitude />;
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* 頭数別統計 */}
      {hasFieldSizeData && (
        <div className="overflow-x-auto">
          <h3 className="text-sm font-medium mb-2 text-muted-foreground flex items-center gap-2">
            👥 頭数別
            <span className="text-[10px] bg-muted px-2 py-0.5 rounded">
              適性判定あり
            </span>
          </h3>
          <table className="w-full text-sm border-collapse">
            <thead>
              <tr className="bg-gray-100 dark:bg-gray-800">
                <th className="px-3 py-2 border text-left">頭数</th>
                <th className="px-3 py-2 border text-center">出走</th>
                <th className="px-3 py-2 border text-center">1着</th>
                <th className="px-3 py-2 border text-center">2着</th>
                <th className="px-3 py-2 border text-center">3着</th>
                <th className="px-3 py-2 border text-center">着外</th>
                <th className="px-3 py-2 border text-center">勝率</th>
                <th className="px-3 py-2 border text-center">複勝率</th>
                <th className="px-3 py-2 border text-center">適性</th>
              </tr>
            </thead>
            <tbody>
              {['少頭数(～11頭)', '中頭数(12-15頭)', '多頭数(16頭～)'].map((fieldSize) => {
                const group = stats.byFieldSize[fieldSize];
                if (!group) return null;
                return <StatRow key={fieldSize} label={fieldSize} group={group} showAptitude />;
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* レース傾向別統計 */}
      {hasTrendData && (
        <div className="overflow-x-auto">
          <h3 className="text-sm font-medium mb-2 text-muted-foreground flex items-center gap-2">
            <span>ペース型別</span>
            <span className="text-[10px] bg-muted px-2 py-0.5 rounded">
              適性判定あり
            </span>
          </h3>
          <table className="w-full text-sm border-collapse">
            <thead>
              <tr className="bg-gray-100 dark:bg-gray-800">
                <th className="px-3 py-2 border text-left">傾向</th>
                <th className="px-3 py-2 border text-center">出走</th>
                <th className="px-3 py-2 border text-center">1着</th>
                <th className="px-3 py-2 border text-center">2着</th>
                <th className="px-3 py-2 border text-center">3着</th>
                <th className="px-3 py-2 border text-center">着外</th>
                <th className="px-3 py-2 border text-center">勝率</th>
                <th className="px-3 py-2 border text-center">複勝率</th>
                <th className="px-3 py-2 border text-center">適性</th>
              </tr>
            </thead>
            <tbody>
              {TREND_ORDER.map(({ key, label, badge }) => {
                const group = stats.byTrend?.[key];
                if (!group) return null;
                return (
                  <StatRow
                    key={key}
                    label={
                      <span className={cn('px-1.5 py-0.5 rounded text-xs font-medium', badge)}>
                        {label}
                      </span>
                    }
                    group={group}
                    showAptitude
                  />
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* 凡例 */}
      <div className="flex flex-wrap gap-4 text-xs text-muted-foreground border-t pt-4">
        <div className="flex items-center gap-2">
          <span className="w-4 h-4 bg-emerald-100 dark:bg-emerald-900/30 rounded"></span>
          <span>優秀（勝率20%↑ or 複勝率50%↑）</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="w-4 h-4 bg-green-50 dark:bg-green-900/20 rounded"></span>
          <span>良好（勝率10%↑ or 複勝率30%↑）</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="w-4 h-4 bg-red-50 dark:bg-red-900/20 rounded"></span>
          <span>要注意（複勝率15%↓）</span>
        </div>
        <div className="flex items-center gap-2">
          <AptitudeBadge type="strong" />
          <span>得意</span>
        </div>
        <div className="flex items-center gap-2">
          <AptitudeBadge type="weak" />
          <span>苦手</span>
        </div>
      </div>
    </div>
  );
}
