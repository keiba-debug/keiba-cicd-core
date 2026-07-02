'use client';

/**
 * 着差バー（可視化強化版）
 * 着差をタイム換算した横バーで視覚化
 * 
 * 改善点:
 * - 接戦（ハナ差、クビ差）をハイライト表示
 * - アニメーション付きバー表示
 * - 着差グループ（接戦/僅差/差あり/大差）の視覚化
 */

import React, { useState } from 'react';
import { HorseEntry, parseFinishPosition, getWakuColor } from '@/types/race-data';
import { ChevronDown, ChevronUp, Trophy, Zap } from 'lucide-react';
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import {
  marginToSeconds,
  classifyMargin,
  timeToSeconds,
  type MarginType,
} from '@/lib/data/result-utils';

interface MarginVisualizationProps {
  entries: HorseEntry[];
  defaultOpen?: boolean;
}

interface MarginEntry {
  horseNumber: number;
  horseName: string;
  waku: string;
  finishPosition: number;
  time: string;
  margin: string;
  cumulativeMargin: number; // 累計着差（秒換算）
}

// 着差換算・分類は共通ユーティリティを使用（result-utils.ts / 1馬身≒0.16秒）

export default function MarginVisualization({ 
  entries, 
  defaultOpen = true 
}: MarginVisualizationProps) {
  const [isOpen, setIsOpen] = useState(defaultOpen);

  // 着順順にソートして着差を累計
  const marginData: MarginEntry[] = entries
    .filter(e => e.result?.finish_position)
    .map(e => ({
      horseNumber: e.horse_number,
      horseName: e.horse_name,
      waku: e.entry_data.waku,
      finishPosition: parseFinishPosition(e.result!.finish_position),
      time: e.result!.time || '',
      margin: e.result!.margin || '',
      cumulativeMargin: 0,
    }))
    .sort((a, b) => a.finishPosition - b.finishPosition);

  // 累計着差を計算
  // 走破タイムの実測差を優先し、タイム欠損時のみ着差表記の秒換算（1馬身≒0.16秒）で積み上げる
  const winnerSec = marginData.length > 0 ? timeToSeconds(marginData[0].time) : null;
  marginData.forEach((item, idx) => {
    if (idx === 0) {
      item.cumulativeMargin = 0;
      return;
    }
    const t = timeToSeconds(item.time);
    if (t != null && winnerSec != null && t >= winnerSec) {
      item.cumulativeMargin = t - winnerSec;
    } else {
      item.cumulativeMargin = marginData[idx - 1].cumulativeMargin + marginToSeconds(item.margin);
    }
  });

  if (marginData.length === 0) {
    return null;
  }

  // 最大着差（バーの長さ計算用）
  const maxMargin = Math.max(...marginData.map(d => d.cumulativeMargin), 0.1);

  // バーの幅を計算（1着=100%、最後尾は着差に応じて短く）
  const getBarWidth = (cumulativeMargin: number): number => {
    if (cumulativeMargin === 0) return 100;
    // 最大着差からの比率で幅を計算
    return Math.max(30, 100 - (cumulativeMargin / maxMargin) * 70);
  };

  // 着順に応じたスタイル
  const getPositionStyle = (position: number): string => {
    if (position === 1) return 'bg-gradient-to-r from-yellow-400 to-yellow-300';
    if (position === 2) return 'bg-gradient-to-r from-gray-400 to-gray-300';
    if (position === 3) return 'bg-gradient-to-r from-amber-600 to-amber-500';
    if (position <= 5) return 'bg-gradient-to-r from-blue-400 to-blue-300';
    return 'bg-gradient-to-r from-gray-300 to-gray-200 dark:from-gray-600 dark:to-gray-500';
  };

  // 着差タイプに応じたスタイル
  const getMarginBadgeStyle = (type: MarginType): string => {
    switch (type) {
      case 'photo': return 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400 border-red-300';
      case 'close': return 'bg-orange-100 text-orange-700 dark:bg-orange-900/30 dark:text-orange-400 border-orange-300';
      case 'big': return 'bg-gray-200 text-gray-600 dark:bg-gray-700 dark:text-gray-400 border-gray-400';
      default: return 'bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400 border-gray-300';
    }
  };

  // 接戦カウント（着差表記ベース: photo=同着/ハナ/アタマ, close=クビ/1/2）
  const photoFinishCount = marginData.filter((d, i) => i > 0 && classifyMargin(d.margin) === 'photo').length;
  const closeFinishCount = marginData.filter((d, i) => i > 0 && classifyMargin(d.margin) === 'close').length;

  return (
    <Collapsible open={isOpen} onOpenChange={setIsOpen}>
      <div className="border rounded-lg">
        <CollapsibleTrigger asChild>
          <Button
            variant="ghost"
            className="w-full flex items-center justify-between p-4 hover:bg-gray-50 dark:hover:bg-gray-800"
          >
            <span className="text-lg font-semibold flex items-center gap-2">
              <Trophy className="w-5 h-5 text-yellow-500" />
              着差ビジュアル
              <span className="text-sm font-normal text-gray-500">
                (1着: {marginData[0]?.time || '-'})
              </span>
              {/* 接戦インジケーター */}
              {photoFinishCount > 0 && (
                <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400">
                  <Zap className="w-3 h-3" />
                  接戦{photoFinishCount}組
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
          <div className="p-4 space-y-1.5">
            {marginData.slice(0, 12).map((item, index) => {
              const marginType = classifyMargin(item.margin);
              const isPhotoFinish = index > 0 && marginType === 'photo';
              const isCloseFinish = index > 0 && marginType === 'close';
              
              return (
                <div 
                  key={item.horseNumber} 
                  className={cn(
                    "flex items-center gap-2 py-0.5 rounded transition-all",
                    isPhotoFinish && "bg-red-50 dark:bg-red-900/10 -mx-2 px-2",
                    isCloseFinish && "bg-orange-50 dark:bg-orange-900/10 -mx-2 px-2"
                  )}
                  style={{
                    animationDelay: `${index * 50}ms`,
                  }}
                >
                  {/* 着順 */}
                  <div className={cn(
                    "w-7 h-7 rounded-full flex items-center justify-center text-sm font-bold transition-transform",
                    item.finishPosition === 1 && 'bg-yellow-400 text-yellow-900 shadow-md',
                    item.finishPosition === 2 && 'bg-gray-300 text-gray-800',
                    item.finishPosition === 3 && 'bg-amber-600 text-white',
                    item.finishPosition > 3 && 'bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-300'
                  )}>
                    {item.finishPosition === 1 ? '👑' : item.finishPosition}
                  </div>

                  {/* 馬番 */}
                  <div 
                    className={cn(
                      "w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold",
                      getWakuColor(item.waku)
                    )}
                  >
                    {item.horseNumber}
                  </div>

                  {/* 馬名 */}
                  <div className={cn(
                    "w-20 truncate text-sm",
                    item.finishPosition <= 3 && "font-medium"
                  )}>
                    {item.horseName}
                  </div>

                  {/* バー */}
                  <div className="flex-1 h-6 bg-gray-100 dark:bg-gray-800 rounded-full overflow-hidden relative">
                    <div
                      className={cn(
                        "h-full rounded-full transition-all duration-700 ease-out",
                        getPositionStyle(item.finishPosition)
                      )}
                      style={{ 
                        width: `${getBarWidth(item.cumulativeMargin)}%`,
                        animationDelay: `${index * 50}ms`,
                      }}
                    />
                    
                    {/* タイム表示（バー上） */}
                    <div className="absolute inset-0 flex items-center px-3">
                      <span className="text-xs font-mono font-medium text-gray-700 dark:text-gray-300 drop-shadow-sm">
                        {item.time}
                      </span>
                    </div>
                  </div>

                  {/* 着差バッジ */}
                  <div className="w-20 text-right">
                    {item.finishPosition === 1 ? (
                      <span className="inline-flex items-center justify-center w-6 h-6 rounded-full bg-yellow-100 text-yellow-600 text-xs font-bold">
                        −
                      </span>
                    ) : (
                      <span className={cn(
                        "inline-flex items-center gap-0.5 px-2 py-0.5 rounded border text-xs font-medium",
                        getMarginBadgeStyle(marginType)
                      )}>
                        {marginType === 'photo' && <Zap className="w-3 h-3" />}
                        {item.margin || '-'}
                      </span>
                    )}
                  </div>

                  {/* 累計秒差 */}
                  <div className="w-14 text-right text-xs text-gray-400 font-mono">
                    {item.cumulativeMargin > 0 ? `+${item.cumulativeMargin.toFixed(1)}s` : ''}
                  </div>
                </div>
              );
            })}

            {/* サマリー情報 */}
            <div className="mt-4 pt-3 border-t">
              <div className="flex flex-wrap gap-4 text-xs text-gray-500">
                <span>※ 秒差=走破タイムの実測差（タイム欠損時のみ1馬身≒0.16秒で換算）</span>
                {photoFinishCount > 0 && (
                  <span className="flex items-center gap-1 text-red-600 dark:text-red-400">
                    <Zap className="w-3 h-3" />
                    接戦（ハナ/アタマ差）: {photoFinishCount}組
                  </span>
                )}
                {closeFinishCount > 0 && (
                  <span className="text-orange-600 dark:text-orange-400">
                    僅差（クビ/1/2）: {closeFinishCount}組
                  </span>
                )}
              </div>
            </div>
          </div>
        </CollapsibleContent>
      </div>
    </Collapsible>
  );
}
