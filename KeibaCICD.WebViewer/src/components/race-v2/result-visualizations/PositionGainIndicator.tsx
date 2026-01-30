'use client';

/**
 * 伸び脚インジケータ
 * 4角からゴールまでの順位変動を視覚化
 */

import React, { useState } from 'react';
import { HorseEntry, parseFinishPosition, toCircleNumber, getWakuColor } from '@/types/race-data';
import { ChevronDown, ChevronUp, TrendingUp, TrendingDown, Minus, ArrowUp, ArrowDown } from 'lucide-react';
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible';
import { Button } from '@/components/ui/button';

interface PositionGainIndicatorProps {
  entries: HorseEntry[];
  defaultOpen?: boolean;
}

interface PositionChangeEntry {
  horseNumber: number;
  horseName: string;
  waku: string;
  finishPosition: number;
  cornerPosition: number;
  gain: number; // 順位変動（プラス=伸び、マイナス=失速）
  last3f: string;
}

// 丸数字を数値に変換するマップ
const circleNumMap: Record<string, number> = {
  '①': 1, '②': 2, '③': 3, '④': 4, '⑤': 5,
  '⑥': 6, '⑦': 7, '⑧': 8, '⑨': 9, '⑩': 10,
  '⑪': 11, '⑫': 12, '⑬': 13, '⑭': 14, '⑮': 15,
  '⑯': 16, '⑰': 17, '⑱': 18, '⑲': 19, '⑳': 20,
};

/**
 * 通過順位文字列をパースして数値配列に変換
 */
function parsePassingOrders(raw: string, totalHorses: number): number[] {
  if (!raw) return [];
  
  if (raw.includes('-')) {
    return raw.split('-').map(p => parseInt(p.trim())).filter(n => !isNaN(n) && n > 0);
  }
  
  const positions: number[] = [];
  let remaining = raw;
  const hasTwoDigitNumbers = totalHorses >= 10;
  
  while (remaining.length > 0) {
    let matched = false;
    
    for (const [circle, num] of Object.entries(circleNumMap)) {
      if (remaining.startsWith(circle)) {
        positions.push(num);
        remaining = remaining.slice(circle.length);
        matched = true;
        break;
      }
    }
    
    if (matched) continue;
    
    if (hasTwoDigitNumbers && remaining.length >= 2) {
      const twoDigit = remaining.slice(0, 2);
      const twoDigitNum = parseInt(twoDigit);
      if (!isNaN(twoDigitNum) && twoDigitNum >= 10 && twoDigitNum <= Math.max(totalHorses, 18)) {
        positions.push(twoDigitNum);
        remaining = remaining.slice(2);
        continue;
      }
    }
    
    const oneDigit = remaining.slice(0, 1);
    const oneDigitNum = parseInt(oneDigit);
    if (!isNaN(oneDigitNum) && oneDigitNum > 0) {
      positions.push(oneDigitNum);
      remaining = remaining.slice(1);
      continue;
    }
    
    remaining = remaining.slice(1);
  }
  
  return positions;
}

export default function PositionGainIndicator({ 
  entries, 
  defaultOpen = true 
}: PositionGainIndicatorProps) {
  const [isOpen, setIsOpen] = useState(defaultOpen);
  const [sortBy, setSortBy] = useState<'finish' | 'gain'>('finish');

  // 位置変動データを抽出
  const positionData: PositionChangeEntry[] = entries
    .filter(e => e.result?.finish_position)
    .map(e => {
      const finishPos = parseFinishPosition(e.result!.finish_position);
      
      // 通過順位をパースして4角位置（最後の値）を取得
      const passingOrdersRaw = e.result?.passing_orders || '';
      const positions = parsePassingOrders(passingOrdersRaw, entries.length);
      const cornerPos = positions.length > 0 ? positions[positions.length - 1] : finishPos;
      
      return {
        horseNumber: e.horse_number,
        horseName: e.horse_name,
        waku: e.entry_data.waku,
        finishPosition: finishPos,
        cornerPosition: cornerPos,
        gain: cornerPos - finishPos, // 4角順位 - 着順（プラス=伸びた）
        last3f: e.result!.last_3f || '-',
      };
    })
    .filter(e => e.cornerPosition > 0); // 有効なデータのみ

  // ソート
  const sortedData = [...positionData].sort((a, b) => {
    if (sortBy === 'gain') {
      return b.gain - a.gain; // 伸び順
    }
    return a.finishPosition - b.finishPosition; // 着順
  });

  if (sortedData.length === 0) {
    return null;
  }

  // 伸び脚の評価を取得
  const getGainLabel = (gain: number): { icon: React.ReactNode; label: string; color: string } => {
    if (gain >= 5) return { 
      icon: <ArrowUp className="w-4 h-4" />, 
      label: `↑↑${gain}`, 
      color: 'text-green-600 dark:text-green-400 bg-green-100 dark:bg-green-900/30' 
    };
    if (gain >= 3) return { 
      icon: <TrendingUp className="w-4 h-4" />, 
      label: `↑${gain}`, 
      color: 'text-green-500 dark:text-green-400 bg-green-50 dark:bg-green-900/20' 
    };
    if (gain >= 1) return { 
      icon: <TrendingUp className="w-3 h-3" />, 
      label: `↑${gain}`, 
      color: 'text-emerald-500 dark:text-emerald-400 bg-emerald-50 dark:bg-emerald-900/20' 
    };
    if (gain === 0) return { 
      icon: <Minus className="w-3 h-3" />, 
      label: '→', 
      color: 'text-gray-500 bg-gray-100 dark:bg-gray-800' 
    };
    if (gain >= -2) return { 
      icon: <TrendingDown className="w-3 h-3" />, 
      label: `↓${Math.abs(gain)}`, 
      color: 'text-orange-500 dark:text-orange-400 bg-orange-50 dark:bg-orange-900/20' 
    };
    return { 
      icon: <ArrowDown className="w-4 h-4" />, 
      label: `↓↓${Math.abs(gain)}`, 
      color: 'text-red-500 dark:text-red-400 bg-red-100 dark:bg-red-900/30' 
    };
  };

  // 統計情報
  const avgGain = positionData.reduce((sum, d) => sum + d.gain, 0) / positionData.length;
  const biggestGainer = [...positionData].sort((a, b) => b.gain - a.gain)[0];
  const biggestLoser = [...positionData].sort((a, b) => a.gain - b.gain)[0];

  return (
    <Collapsible open={isOpen} onOpenChange={setIsOpen}>
      <div className="border rounded-lg">
        <CollapsibleTrigger asChild>
          <Button
            variant="ghost"
            className="w-full flex items-center justify-between p-4 hover:bg-gray-50 dark:hover:bg-gray-800"
          >
            <span className="text-lg font-semibold flex items-center gap-2">
              <TrendingUp className="w-5 h-5 text-green-500" />
              伸び脚分析
              <span className="text-sm font-normal text-gray-500">
                (4角→ゴール)
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
          <div className="p-4">
            {/* ソート切替 */}
            <div className="flex gap-2 mb-4">
              <button
                onClick={() => setSortBy('finish')}
                className={`px-3 py-1 text-sm rounded-full transition-colors ${
                  sortBy === 'finish' 
                    ? 'bg-primary text-primary-foreground' 
                    : 'bg-gray-100 dark:bg-gray-800 hover:bg-gray-200 dark:hover:bg-gray-700'
                }`}
              >
                着順
              </button>
              <button
                onClick={() => setSortBy('gain')}
                className={`px-3 py-1 text-sm rounded-full transition-colors ${
                  sortBy === 'gain' 
                    ? 'bg-primary text-primary-foreground' 
                    : 'bg-gray-100 dark:bg-gray-800 hover:bg-gray-200 dark:hover:bg-gray-700'
                }`}
              >
                伸び順
              </button>
            </div>

            {/* テーブル */}
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b bg-gray-50 dark:bg-gray-800">
                    <th className="px-2 py-2 text-center w-12">着順</th>
                    <th className="px-2 py-2 text-center w-10">馬番</th>
                    <th className="px-2 py-2 text-left">馬名</th>
                    <th className="px-2 py-2 text-center w-12">4角</th>
                    <th className="px-2 py-2 text-center w-20">伸び</th>
                    <th className="px-2 py-2 text-center w-14">上3F</th>
                  </tr>
                </thead>
                <tbody>
                  {sortedData.slice(0, 12).map((item) => {
                    const gainInfo = getGainLabel(item.gain);
                    return (
                      <tr 
                        key={item.horseNumber}
                        className="border-b hover:bg-gray-50 dark:hover:bg-gray-800/50"
                      >
                        {/* 着順 */}
                        <td className="px-2 py-2 text-center">
                          <span className={`inline-flex items-center justify-center w-6 h-6 rounded-full text-xs font-bold ${
                            item.finishPosition === 1 ? 'bg-yellow-400 text-yellow-900' :
                            item.finishPosition === 2 ? 'bg-gray-300 text-gray-800' :
                            item.finishPosition === 3 ? 'bg-amber-600 text-white' :
                            'bg-gray-100 dark:bg-gray-700'
                          }`}>
                            {item.finishPosition}
                          </span>
                        </td>

                        {/* 馬番 */}
                        <td className="px-2 py-2 text-center">
                          <span 
                            className={`inline-flex items-center justify-center w-6 h-6 rounded-full text-xs font-bold ${getWakuColor(item.waku)}`}
                          >
                            {item.horseNumber}
                          </span>
                        </td>

                        {/* 馬名 */}
                        <td className="px-2 py-2 font-medium truncate max-w-24">
                          {item.horseName}
                        </td>

                        {/* 4角順位 */}
                        <td className="px-2 py-2 text-center text-gray-600 dark:text-gray-400">
                          {item.cornerPosition}
                        </td>

                        {/* 伸び */}
                        <td className="px-2 py-2 text-center">
                          <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-bold ${gainInfo.color}`}>
                            {gainInfo.icon}
                            {gainInfo.label}
                          </span>
                        </td>

                        {/* 上り3F */}
                        <td className="px-2 py-2 text-center font-mono text-gray-600 dark:text-gray-400">
                          {item.last3f}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>

            {/* 統計サマリー */}
            <div className="mt-4 pt-3 border-t grid grid-cols-3 gap-4 text-sm">
              <div className="text-center">
                <div className="text-xs text-gray-500 mb-1">最も伸びた馬</div>
                <div className="font-bold text-green-600 dark:text-green-400">
                  {toCircleNumber(biggestGainer.horseNumber)} {biggestGainer.horseName}
                  <span className="ml-1">(+{biggestGainer.gain})</span>
                </div>
              </div>
              <div className="text-center">
                <div className="text-xs text-gray-500 mb-1">平均順位変動</div>
                <div className={`font-bold ${avgGain > 0 ? 'text-green-600' : avgGain < 0 ? 'text-red-600' : 'text-gray-600'}`}>
                  {avgGain > 0 ? '+' : ''}{avgGain.toFixed(1)}
                </div>
              </div>
              <div className="text-center">
                <div className="text-xs text-gray-500 mb-1">最も失速した馬</div>
                <div className="font-bold text-red-600 dark:text-red-400">
                  {toCircleNumber(biggestLoser.horseNumber)} {biggestLoser.horseName}
                  <span className="ml-1">({biggestLoser.gain})</span>
                </div>
              </div>
            </div>
          </div>
        </CollapsibleContent>
      </div>
    </Collapsible>
  );
}
