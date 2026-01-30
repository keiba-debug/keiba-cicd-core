'use client';

/**
 * 上り3F比較チャート
 * 各馬の上り3Fを横棒グラフで比較表示
 */

import React, { useState } from 'react';
import { HorseEntry, toCircleNumber, getWakuColor } from '@/types/race-data';
import { ChevronDown, ChevronUp, Timer, Zap } from 'lucide-react';
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible';
import { Button } from '@/components/ui/button';

interface Last3FComparisonChartProps {
  entries: HorseEntry[];
  defaultOpen?: boolean;
}

interface Last3FEntry {
  horseNumber: number;
  horseName: string;
  last3f: number;
  waku: string;
  finishPosition: number;
  rank: number;
}

export default function Last3FComparisonChart({ 
  entries, 
  defaultOpen = true 
}: Last3FComparisonChartProps) {
  const [isOpen, setIsOpen] = useState(defaultOpen);

  // 上り3Fデータを抽出・ソート
  const last3fData: Last3FEntry[] = entries
    .filter(e => e.result?.last_3f && !isNaN(parseFloat(e.result.last_3f)))
    .map(e => ({
      horseNumber: e.horse_number,
      horseName: e.horse_name,
      last3f: parseFloat(e.result!.last_3f),
      waku: e.entry_data.waku,
      finishPosition: parseInt(e.result!.finish_position) || 99,
    }))
    .sort((a, b) => a.last3f - b.last3f)
    .map((item, idx) => ({ ...item, rank: idx + 1 }));

  if (last3fData.length === 0) {
    return null;
  }

  // 最速・最遅のタイムを取得（バーの長さ計算用）
  const fastestTime = Math.min(...last3fData.map(d => d.last3f));
  const slowestTime = Math.max(...last3fData.map(d => d.last3f));
  const timeRange = slowestTime - fastestTime || 1;

  // バーの幅を計算（最速=100%、最遅=40%程度）
  const getBarWidth = (time: number): number => {
    const normalized = (slowestTime - time) / timeRange;
    return 40 + normalized * 60; // 40%〜100%
  };

  // ランクに応じたスタイル
  const getRankStyle = (rank: number): string => {
    if (rank === 1) return 'bg-gradient-to-r from-red-500 to-red-400 text-white';
    if (rank === 2) return 'bg-gradient-to-r from-orange-400 to-orange-300 text-white';
    if (rank === 3) return 'bg-gradient-to-r from-yellow-400 to-yellow-300 text-yellow-900';
    return 'bg-gradient-to-r from-gray-300 to-gray-200 dark:from-gray-600 dark:to-gray-500';
  };

  const getRankLabel = (rank: number): string => {
    if (rank === 1) return '🥇';
    if (rank === 2) return '🥈';
    if (rank === 3) return '🥉';
    return '';
  };

  return (
    <Collapsible open={isOpen} onOpenChange={setIsOpen}>
      <div className="border rounded-lg">
        <CollapsibleTrigger asChild>
          <Button
            variant="ghost"
            className="w-full flex items-center justify-between p-4 hover:bg-gray-50 dark:hover:bg-gray-800"
          >
            <span className="text-lg font-semibold flex items-center gap-2">
              <Zap className="w-5 h-5 text-green-600 dark:text-green-400" />
              上り3F ランキング
              <span className="text-sm font-normal text-gray-500">
                (最速: {fastestTime.toFixed(1)}秒)
              </span>
            </span>
            {isOpen ? (
              <ChevronUp className="w-5 h-5" />
            ) : (
              <ChevronDown className="w-5 h-5" />
            )}
          </Button>
        </CollapsibleTrigger>

        <CollapsibleContent>
          <div className="p-4 space-y-2">
            {last3fData.slice(0, 10).map((item) => (
              <div 
                key={item.horseNumber} 
                className="flex items-center gap-2"
              >
                {/* 順位ラベル */}
                <div className="w-8 text-center">
                  {item.rank <= 3 ? (
                    <span className="text-lg">{getRankLabel(item.rank)}</span>
                  ) : (
                    <span className="text-sm text-gray-400">{item.rank}位</span>
                  )}
                </div>

                {/* 馬番 */}
                <div 
                  className={`w-7 h-7 rounded-full flex items-center justify-center text-sm font-bold ${getWakuColor(item.waku)}`}
                >
                  {item.horseNumber}
                </div>

                {/* 馬名 */}
                <div className="w-24 truncate text-sm font-medium">
                  {item.horseName}
                </div>

                {/* バー */}
                <div className="flex-1 h-6 bg-gray-100 dark:bg-gray-800 rounded-full overflow-hidden relative">
                  <div
                    className={`h-full rounded-full transition-all duration-500 flex items-center justify-end pr-2 ${getRankStyle(item.rank)}`}
                    style={{ width: `${getBarWidth(item.last3f)}%` }}
                  >
                    <span className="text-xs font-bold whitespace-nowrap">
                      {item.last3f.toFixed(1)}
                    </span>
                  </div>
                </div>

                {/* 着順 */}
                <div className="w-10 text-right text-sm">
                  <span className={`${item.finishPosition <= 3 ? 'font-bold text-yellow-600' : 'text-gray-500'}`}>
                    {item.finishPosition}着
                  </span>
                </div>
              </div>
            ))}

            {/* 凡例 */}
            <div className="mt-4 pt-3 border-t text-xs text-gray-500 flex items-center gap-4">
              <span className="flex items-center gap-1">
                <Timer className="w-3 h-3" />
                タイム差: {(slowestTime - fastestTime).toFixed(1)}秒
              </span>
              <span>
                平均: {(last3fData.reduce((sum, d) => sum + d.last3f, 0) / last3fData.length).toFixed(1)}秒
              </span>
            </div>
          </div>
        </CollapsibleContent>
      </div>
    </Collapsible>
  );
}
