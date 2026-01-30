'use client';

/**
 * 上り3F比較チャート（可視化強化版）
 * 各馬の上り3Fを横棒グラフで比較表示
 * 
 * 改善点:
 * - メンバー最速との差を表示
 * - 上りランクに応じたグラデーション
 * - 好走馬（1-3着）のハイライト
 */

import React, { useState } from 'react';
import { HorseEntry, toCircleNumber, getWakuColor } from '@/types/race-data';
import { ChevronDown, ChevronUp, Timer, Zap, Trophy } from 'lucide-react';
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';

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
  const avgTime = last3fData.reduce((sum, d) => sum + d.last3f, 0) / last3fData.length;

  // バーの幅を計算（最速=100%、最遅=40%程度）
  const getBarWidth = (time: number): number => {
    const normalized = (slowestTime - time) / timeRange;
    return 40 + normalized * 60; // 40%〜100%
  };

  // ランクに応じたスタイル（よりリッチなグラデーション）
  const getRankStyle = (rank: number): string => {
    if (rank === 1) return 'bg-gradient-to-r from-red-600 via-red-500 to-red-400 text-white shadow-md';
    if (rank === 2) return 'bg-gradient-to-r from-orange-500 via-orange-400 to-orange-300 text-white';
    if (rank === 3) return 'bg-gradient-to-r from-yellow-500 via-yellow-400 to-yellow-300 text-yellow-900';
    if (rank <= 5) return 'bg-gradient-to-r from-emerald-400 to-emerald-300 text-emerald-900';
    return 'bg-gradient-to-r from-gray-300 to-gray-200 dark:from-gray-600 dark:to-gray-500';
  };

  const getRankLabel = (rank: number): string => {
    if (rank === 1) return '🥇';
    if (rank === 2) return '🥈';
    if (rank === 3) return '🥉';
    return '';
  };

  // 最速との差を計算
  const getDiffFromFastest = (time: number): string => {
    const diff = time - fastestTime;
    if (diff === 0) return '';
    return `+${diff.toFixed(1)}`;
  };

  // 上りで好走（上り3位以内で3着以内）したか
  const fastFinishers = last3fData.filter(d => d.rank <= 3 && d.finishPosition <= 3);
  
  // 上り最速が着外（追い込み届かず）
  const fastestButMissed = last3fData.find(d => d.rank === 1 && d.finishPosition > 3);

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
              {/* 上り好走インジケーター */}
              {fastFinishers.length >= 2 && (
                <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400">
                  <Trophy className="w-3 h-3" />
                  切れ味勝負
                </span>
              )}
              {fastestButMissed && (
                <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400">
                  届かず
                </span>
              )}
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
            {last3fData.slice(0, 10).map((item, index) => {
              const isWinner = item.finishPosition <= 3;
              const diffFromFastest = getDiffFromFastest(item.last3f);
              
              return (
                <div 
                  key={item.horseNumber} 
                  className={cn(
                    "flex items-center gap-2 py-0.5 rounded transition-all",
                    isWinner && item.rank <= 3 && "bg-emerald-50 dark:bg-emerald-900/10 -mx-2 px-2"
                  )}
                  style={{
                    animationDelay: `${index * 50}ms`,
                  }}
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
                    className={cn(
                      "w-7 h-7 rounded-full flex items-center justify-center text-sm font-bold",
                      getWakuColor(item.waku)
                    )}
                  >
                    {item.horseNumber}
                  </div>

                  {/* 馬名 */}
                  <div className={cn(
                    "w-24 truncate text-sm",
                    isWinner && "font-medium"
                  )}>
                    {item.horseName}
                  </div>

                  {/* バー */}
                  <div className="flex-1 h-7 bg-gray-100 dark:bg-gray-800 rounded-full overflow-hidden relative">
                    <div
                      className={cn(
                        "h-full rounded-full transition-all duration-700 ease-out flex items-center justify-end pr-3",
                        getRankStyle(item.rank)
                      )}
                      style={{ 
                        width: `${getBarWidth(item.last3f)}%`,
                        animationDelay: `${index * 50}ms`,
                      }}
                    >
                      <span className="text-xs font-bold whitespace-nowrap">
                        {item.last3f.toFixed(1)}
                      </span>
                    </div>
                  </div>

                  {/* 最速との差 */}
                  <div className="w-12 text-right text-xs font-mono">
                    {diffFromFastest ? (
                      <span className="text-gray-400">{diffFromFastest}</span>
                    ) : (
                      <span className="text-red-500 font-bold">最速</span>
                    )}
                  </div>

                  {/* 着順 */}
                  <div className="w-12 text-right">
                    <span className={cn(
                      "inline-flex items-center justify-center w-7 h-7 rounded-full text-xs font-bold",
                      item.finishPosition === 1 && "bg-yellow-400 text-yellow-900",
                      item.finishPosition === 2 && "bg-gray-300 text-gray-800",
                      item.finishPosition === 3 && "bg-amber-600 text-white",
                      item.finishPosition > 3 && "bg-gray-100 text-gray-500 dark:bg-gray-700 dark:text-gray-400"
                    )}>
                      {item.finishPosition}
                    </span>
                  </div>
                </div>
              );
            })}

            {/* サマリー */}
            <div className="mt-4 pt-3 border-t">
              <div className="grid grid-cols-3 gap-4 text-center text-sm">
                <div>
                  <div className="text-xs text-gray-500 mb-1">最速</div>
                  <div className="font-bold text-red-600">{fastestTime.toFixed(1)}秒</div>
                </div>
                <div>
                  <div className="text-xs text-gray-500 mb-1">平均</div>
                  <div className="font-bold text-gray-700 dark:text-gray-300">{avgTime.toFixed(1)}秒</div>
                </div>
                <div>
                  <div className="text-xs text-gray-500 mb-1">差</div>
                  <div className="font-bold text-gray-600">{(slowestTime - fastestTime).toFixed(1)}秒</div>
                </div>
              </div>
            </div>
          </div>
        </CollapsibleContent>
      </div>
    </Collapsible>
  );
}
