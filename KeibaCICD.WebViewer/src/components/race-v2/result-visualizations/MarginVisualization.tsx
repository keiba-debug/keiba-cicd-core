'use client';

/**
 * 着差バー
 * 着差をタイム換算した横バーで視覚化
 */

import React, { useState } from 'react';
import { HorseEntry, parseFinishPosition, toCircleNumber, getWakuColor } from '@/types/race-data';
import { ChevronDown, ChevronUp, Trophy } from 'lucide-react';
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible';
import { Button } from '@/components/ui/button';

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

// 着差を秒数に変換
function marginToSeconds(margin: string): number {
  if (!margin || margin === '-' || margin === '') return 0;
  
  const normalizedMargin = margin.trim().toLowerCase();
  
  // 着差表記の変換マップ
  const marginMap: Record<string, number> = {
    'ハナ': 0.05,
    'はな': 0.05,
    'アタマ': 0.1,
    'あたま': 0.1,
    'クビ': 0.15,
    'くび': 0.15,
    '1/2': 0.3,
    '3/4': 0.45,
    '1': 0.6,
    '1.1/4': 0.75,
    '1・1/4': 0.75,
    '1.1/2': 0.9,
    '1・1/2': 0.9,
    '1.3/4': 1.05,
    '1・3/4': 1.05,
    '2': 1.2,
    '2.1/2': 1.5,
    '2・1/2': 1.5,
    '3': 1.8,
    '4': 2.4,
    '5': 3.0,
    '6': 3.6,
    '7': 4.2,
    '8': 4.8,
    '9': 5.4,
    '10': 6.0,
    '大差': 6.0,
    '大': 6.0,
  };

  // 直接マッチ
  for (const [key, value] of Object.entries(marginMap)) {
    if (normalizedMargin === key.toLowerCase() || normalizedMargin.includes(key)) {
      return value;
    }
  }

  // 数値のみの場合（馬身数）
  const numMatch = normalizedMargin.match(/^(\d+(?:\.\d+)?)/);
  if (numMatch) {
    return parseFloat(numMatch[1]) * 0.6; // 1馬身 ≒ 0.6秒
  }

  return 0;
}

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
  let cumulativeMargin = 0;
  marginData.forEach((item, idx) => {
    if (idx === 0) {
      item.cumulativeMargin = 0;
    } else {
      cumulativeMargin += marginToSeconds(item.margin);
      item.cumulativeMargin = cumulativeMargin;
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
            {marginData.slice(0, 12).map((item) => (
              <div 
                key={item.horseNumber} 
                className="flex items-center gap-2"
              >
                {/* 着順 */}
                <div className={`w-7 h-7 rounded-full flex items-center justify-center text-sm font-bold ${
                  item.finishPosition === 1 ? 'bg-yellow-400 text-yellow-900' :
                  item.finishPosition === 2 ? 'bg-gray-300 text-gray-800' :
                  item.finishPosition === 3 ? 'bg-amber-600 text-white' :
                  'bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-300'
                }`}>
                  {item.finishPosition}
                </div>

                {/* 馬番 */}
                <div 
                  className={`w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold ${getWakuColor(item.waku)}`}
                >
                  {item.horseNumber}
                </div>

                {/* 馬名 */}
                <div className="w-20 truncate text-sm">
                  {item.horseName}
                </div>

                {/* バー */}
                <div className="flex-1 h-5 bg-gray-100 dark:bg-gray-800 rounded overflow-hidden relative">
                  <div
                    className={`h-full rounded transition-all duration-500 ${getPositionStyle(item.finishPosition)}`}
                    style={{ width: `${getBarWidth(item.cumulativeMargin)}%` }}
                  />
                  
                  {/* タイム表示（バー上） */}
                  <div className="absolute inset-0 flex items-center px-2">
                    <span className="text-xs font-mono font-medium text-gray-700 dark:text-gray-300">
                      {item.time}
                    </span>
                  </div>
                </div>

                {/* 着差 */}
                <div className="w-16 text-right text-sm">
                  {item.finishPosition === 1 ? (
                    <span className="font-bold text-yellow-600">-</span>
                  ) : (
                    <span className="text-gray-600 dark:text-gray-400">
                      {item.margin || '-'}
                    </span>
                  )}
                </div>

                {/* 累計秒差 */}
                <div className="w-14 text-right text-xs text-gray-400">
                  {item.cumulativeMargin > 0 ? `+${item.cumulativeMargin.toFixed(1)}s` : ''}
                </div>
              </div>
            ))}

            {/* 補足情報 */}
            <div className="mt-4 pt-3 border-t text-xs text-gray-500">
              <p>※ 着差の秒数換算は目安です（1馬身≒0.6秒で計算）</p>
            </div>
          </div>
        </CollapsibleContent>
      </div>
    </Collapsible>
  );
}
