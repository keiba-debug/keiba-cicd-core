'use client';

/**
 * 馬成績統計セクションコンポーネント（v2）
 */

import React from 'react';
import type { HorseStats, StatGroup } from '@/lib/data/integrated-horse-reader';

interface HorseStatsSectionProps {
  stats: HorseStats;
}

function StatRow({ label, group }: { label: string; group: StatGroup }) {
  if (group.races === 0) {
    return (
      <tr className="text-gray-400">
        <td className="px-3 py-2 border">{label}</td>
        <td className="px-3 py-2 border text-center">-</td>
        <td className="px-3 py-2 border text-center">-</td>
        <td className="px-3 py-2 border text-center">-</td>
        <td className="px-3 py-2 border text-center">-</td>
        <td className="px-3 py-2 border text-center">-</td>
        <td className="px-3 py-2 border text-center">-</td>
        <td className="px-3 py-2 border text-center">-</td>
      </tr>
    );
  }

  const outsidePlace = group.races - group.thirds;

  return (
    <tr className="hover:bg-gray-50 dark:hover:bg-gray-800/50">
      <td className="px-3 py-2 border font-medium">{label}</td>
      <td className="px-3 py-2 border text-center">{group.races}</td>
      <td className="px-3 py-2 border text-center font-bold text-yellow-600">{group.wins}</td>
      <td className="px-3 py-2 border text-center text-blue-600">{group.seconds}</td>
      <td className="px-3 py-2 border text-center text-green-600">{group.thirds}</td>
      <td className="px-3 py-2 border text-center">{outsidePlace}</td>
      <td className="px-3 py-2 border text-center">
        <span className={group.winRate >= 20 ? 'font-bold text-red-600' : ''}>
          {group.winRate}%
        </span>
      </td>
      <td className="px-3 py-2 border text-center">
        <span className={group.showRate >= 50 ? 'font-bold text-blue-600' : ''}>
          {group.showRate}%
        </span>
      </td>
    </tr>
  );
}

export function HorseStatsSection({ stats }: HorseStatsSectionProps) {
  return (
    <div className="space-y-6">
      <h2 className="text-lg font-semibold flex items-center gap-2">
        📊 成績統計
      </h2>

      {/* メイン統計 */}
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

      {/* 距離別統計 */}
      {Object.keys(stats.byDistance).length > 0 && (
        <div className="overflow-x-auto">
          <h3 className="text-sm font-medium mb-2 text-muted-foreground">距離別</h3>
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
              </tr>
            </thead>
            <tbody>
              {['1200m', '1400m', '1600m', '1800m', '2000m+'].map((dist) => {
                const group = stats.byDistance[dist];
                if (!group) return null;
                return <StatRow key={dist} label={dist} group={group} />;
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* 馬場状態別統計 */}
      {Object.keys(stats.byCondition).length > 0 && (
        <div className="overflow-x-auto">
          <h3 className="text-sm font-medium mb-2 text-muted-foreground">馬場状態別</h3>
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
              </tr>
            </thead>
            <tbody>
              {['良', '稍重', '重', '不良'].map((cond) => {
                const group = stats.byCondition[cond];
                if (!group) return null;
                return <StatRow key={cond} label={cond} group={group} />;
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
